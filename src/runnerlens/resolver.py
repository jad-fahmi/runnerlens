"""Best-effort Linux executable metadata resolution."""

from __future__ import annotations

import os
import platform
import re
import subprocess
from dataclasses import replace
from pathlib import Path

from runnerlens.models import Dependency


_VERSION_RE = re.compile(r"(?<![\w.])v?(\d+(?:\.\d+)+(?:[-+][0-9A-Za-z.-]+)?)")
_GO_VERSION_RE = re.compile(r"\bgo(\d+(?:\.\d+)+(?:[-+][0-9A-Za-z.-]+)?)\b")
_DISTRIBUTION_WRAPPED_VERSION_RE = re.compile(
    r"\((?:Ubuntu|Debian|Red Hat|Fedora|SUSE)[^)]*\)[ \t]*"
    r"(\d+(?:\.\d+)+(?:[-+][0-9A-Za-z.-]+)?)",
    re.IGNORECASE,
)
_VERSION_FLAG_EXECUTABLES = frozenset(
    {
        "c++",
        "cc",
        "clang",
        "clang++",
        "cmake",
        "cargo",
        "docker",
        "g++",
        "gcc",
        "java",
        "make",
        "ninja",
        "node",
        "nodejs",
        "npm",
        "podman",
        "python",
        "python3",
        "ruby",
        "rustc",
    }
)
_VERSIONED_COMPILER_RE = re.compile(r"(?:cc|c\+\+|gcc|g\+\+|clang\+?\+?)-\d+(?:\.\d+)*")
_VERSIONED_PYTHON_RE = re.compile(r"python3(?:\.\d+)+")
RESOLVABLE_ORIGINS = frozenset({"runner-provided", "tool-cache"})
_PROBE_ENVIRONMENT_OVERRIDES = frozenset(
    {
        "BASH_ENV",
        "COMPILER_PATH",
        "DPKG_ADMINDIR",
        "DPKG_ROOT",
        "ENV",
        "GCC_EXEC_PREFIX",
        "JAVA_TOOL_OPTIONS",
        "JDK_JAVA_OPTIONS",
        "LD_AUDIT",
        "LD_LIBRARY_PATH",
        "LD_PRELOAD",
        "NODE_OPTIONS",
        "NODE_PATH",
        "PERL5LIB",
        "PERL5OPT",
        "PYTHONHOME",
        "PYTHONINSPECT",
        "PYTHONPATH",
        "PYTHONSTARTUP",
        "RUBYLIB",
        "RUBYOPT",
        "_JAVA_OPTIONS",
    }
)


def enrich_dependencies(dependencies: list[Dependency]) -> list[Dependency]:
    """Add reliable version and package evidence where the host supports it."""
    if platform.system() != "Linux":
        return dependencies

    enriched: list[Dependency] = []
    for dependency in dependencies:
        if dependency.origin not in RESOLVABLE_ORIGINS:
            enriched.append(dependency)
            continue
        enriched.append(
            replace(
                dependency,
                version=detect_version(dependency.path),
                package=find_package_owner(dependency.path),
            )
        )
    return enriched


def detect_version(path: str | None) -> str | None:
    """Probe known version commands and return only a parsed version."""
    if not _is_absolute_file(path):
        return None
    command = _version_command(path)
    if command is None:
        return None

    try:
        completed = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=2,
            check=False,
            cwd="/",
            env=_probe_environment(),
        )
    except (OSError, UnicodeDecodeError, subprocess.TimeoutExpired):
        return None

    if completed.returncode != 0:
        return None
    match = (
        _DISTRIBUTION_WRAPPED_VERSION_RE.search(completed.stdout.splitlines()[0])
        if completed.stdout.splitlines()
        else None
    )
    match = match or _VERSION_RE.search(completed.stdout) or _GO_VERSION_RE.search(completed.stdout)
    return match.group(1) if match else None


def find_package_owner(path: str | None) -> str | None:
    """Return the Debian package owning an executable path, if dpkg knows it."""
    if not _is_absolute_file(path):
        return None

    search_pattern = re.sub(r"([*?\[\\])", r"\\\1", path)
    try:
        completed = subprocess.run(
            ["dpkg-query", "--search", "--", search_pattern],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
            check=False,
            cwd="/",
            env=_probe_environment(),
        )
    except (OSError, UnicodeDecodeError, subprocess.TimeoutExpired):
        return None

    if completed.returncode != 0 or not completed.stdout:
        return None
    owners = set()
    for line in completed.stdout.splitlines():
        owner, separator, matched_path = line.partition(": ")
        if not separator or not owner or matched_path != path:
            return None
        owner_names = owner.split(", ")
        if any(not name for name in owner_names):
            return None
        owners.update(owner_names)
    return next(iter(owners)) if len(owners) == 1 else None


def _is_absolute_file(path: str | None) -> bool:
    return bool(path and Path(path).is_absolute() and Path(path).is_file())


def _probe_environment() -> dict[str, str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in _PROBE_ENVIRONMENT_OVERRIDES
    }
    environment["LC_ALL"] = "C"
    return environment


def _version_command(path: str) -> list[str] | None:
    executable = Path(path).name.lower()
    if executable == "go":
        return [path, "version"]
    if (
        executable in _VERSION_FLAG_EXECUTABLES
        or _VERSIONED_COMPILER_RE.fullmatch(executable)
        or _VERSIONED_PYTHON_RE.fullmatch(executable)
    ):
        return [path, "--version"]
    return None
