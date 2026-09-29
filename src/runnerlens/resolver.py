"""Best-effort Linux executable metadata resolution."""

from __future__ import annotations

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
RESOLVABLE_ORIGINS = frozenset({"runner-provided", "tool-cache"})


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
    """Return a version only when ``--version`` succeeds and exposes one."""
    if not _is_absolute_file(path):
        return None

    try:
        completed = subprocess.run(
            _version_command(path),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=2,
            check=False,
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

    try:
        completed = subprocess.run(
            ["dpkg-query", "--search", "--", path],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, UnicodeDecodeError, subprocess.TimeoutExpired):
        return None

    if completed.returncode != 0 or not completed.stdout:
        return None
    owners = set()
    for line in completed.stdout.splitlines():
        owner, separator, _ = line.rpartition(": ")
        if not separator or not owner:
            return None
        owners.add(owner)
    return next(iter(owners)) if len(owners) == 1 else None


def _is_absolute_file(path: str | None) -> bool:
    return bool(path and Path(path).is_absolute() and Path(path).is_file())


def _version_command(path: str) -> list[str]:
    if Path(path).name == "go":
        return [path, "version"]
    return [path, "--version"]
