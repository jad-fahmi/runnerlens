"""Conservative executable origin classification."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from runnerlens.models import Dependency, ExecutionEvent, RunnerInfo


SYSTEM_PREFIXES = (
    "/bin",
    "/sbin",
    "/usr/bin",
    "/usr/sbin",
    "/usr/local/bin",
    "/usr/local/sbin",
    "/snap/bin",
)

TOOL_CACHE_MARKERS = (
    "/opt/hostedtoolcache/",
    "/hostedtoolcache/",
)


def classify_events(
    events: list[ExecutionEvent],
    runner: RunnerInfo,
    repository_root: Path,
    env: Mapping[str, str] | None = None,
) -> list[Dependency]:
    data = env if env is not None else os.environ
    dependencies: dict[tuple[str, str | None], Dependency] = {}

    for event in events:
        dependency = classify_event(event, runner, repository_root, data)
        dependencies[(dependency.name, dependency.path)] = dependency

    return sorted(dependencies.values(), key=lambda item: (item.name, item.path or ""))


def classify_event(
    event: ExecutionEvent,
    runner: RunnerInfo,
    repository_root: Path,
    env: Mapping[str, str],
) -> Dependency:
    name = event.executable
    path = _normalize_path(event.path)
    origin = "unknown"
    confidence = "unknown"
    evidence = [f"observed via {event.observation}"]

    if path and _is_relative_to(Path(path), repository_root):
        origin = "repository-provided"
        confidence = "confirmed"
        evidence.append("path is inside repository root")
    elif path and _is_tool_cache(path, env):
        origin = "tool-cache"
        confidence = "confirmed"
        evidence.append("path is inside hosted tool cache")
    elif runner.provider == "github-actions" and path and _has_system_prefix(path):
        origin = "runner-provided"
        confidence = "probable"
        evidence.append("system path on GitHub-hosted runner")
    elif runner.provider == "local" and path:
        evidence.append("local execution cannot establish CI runner provenance")
    elif path is None:
        evidence.append("executable path was not resolved")

    return Dependency(
        name=name,
        path=path,
        origin=origin,
        confidence=confidence,
        evidence=evidence,
    )


def _normalize_path(path: str | None) -> str | None:
    if path is None:
        return None
    return Path(path).as_posix()


def _has_system_prefix(path: str) -> bool:
    return any(path == prefix or path.startswith(prefix + "/") for prefix in SYSTEM_PREFIXES)


def _is_tool_cache(path: str, env: Mapping[str, str]) -> bool:
    if any(marker in path for marker in TOOL_CACHE_MARKERS):
        return True
    tool_dir = env.get("AGENT_TOOLSDIRECTORY") or env.get("RUNNER_TOOL_CACHE")
    return bool(tool_dir and _is_relative_to(Path(path), Path(tool_dir)))


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    return True
