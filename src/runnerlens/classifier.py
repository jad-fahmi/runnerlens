"""Conservative executable origin classification."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path, PurePosixPath, PureWindowsPath

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

GITHUB_HOSTED_RUNNER_PREFIXES = (
    "/home/runner/.cargo/bin",
)

TOOL_CACHE_MARKERS = (
    "/opt/hostedtoolcache/",
    "/hostedtoolcache/",
)

WORKFLOW_PROVISIONED_PATHS_ENV = "RUNNERLENS_WORKFLOW_PROVISIONED_PATHS"
CONTAINERIZED_ENV = "RUNNERLENS_CONTAINERIZED"


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
        identity = (dependency.name, dependency.path)
        previous = dependencies.get(identity)
        if previous is None:
            dependencies[identity] = dependency
        else:
            dependencies[identity] = replace(
                previous,
                evidence=list(dict.fromkeys((*previous.evidence, *dependency.evidence))),
            )

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

    if path and _contains_parent_traversal(path):
        evidence.append("path contains parent traversal; origin was not inferred")
    elif path and _is_relative_to(Path(path), repository_root):
        origin = "repository-provided"
        confidence = "confirmed"
        evidence.append("path is inside repository root")
    elif path and _is_workflow_provisioned(path, env):
        origin = "workflow-provisioned"
        confidence = "confirmed"
        evidence.append("path was declared as workflow-provisioned")
    elif path and _is_containerized(env):
        origin = "container-provided"
        confidence = "confirmed"
        evidence.append("container execution was explicitly declared")
    elif path and _is_tool_cache(path, env):
        origin = "tool-cache"
        confidence = "confirmed"
        evidence.append(_tool_cache_evidence(path))
    elif _is_github_hosted_runner(runner) and path and _has_hosted_runner_prefix(path):
        origin = "runner-provided"
        confidence = "probable"
        evidence.append("documented base-image path on GitHub-hosted runner")
    elif runner.provider == "local" and path:
        evidence.append("local execution cannot establish CI runner provenance")
    elif event.path and path is None:
        evidence.append("observed path is relative; child working directory is not established")
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
    if PurePosixPath(path).is_absolute():
        return PurePosixPath(path).as_posix()
    if not PureWindowsPath(path).is_absolute():
        return None
    return Path(path).as_posix()


def _has_system_prefix(path: str) -> bool:
    return not _contains_parent_traversal(path) and any(
        path == prefix or path.startswith(prefix + "/") for prefix in SYSTEM_PREFIXES
    )


def _has_hosted_runner_prefix(path: str) -> bool:
    if _contains_parent_traversal(path):
        return False
    return _has_system_prefix(path) or any(
        path == prefix or path.startswith(prefix + "/")
        for prefix in GITHUB_HOSTED_RUNNER_PREFIXES
    )


def _is_tool_cache(path: str, env: Mapping[str, str]) -> bool:
    if _uses_tool_cache_prefix(path):
        return True
    return any(
        Path(tool_dir).is_absolute() and _is_relative_to(Path(path), Path(tool_dir))
        for tool_dir in (env.get("AGENT_TOOLSDIRECTORY"), env.get("RUNNER_TOOL_CACHE"))
        if tool_dir
    )


def _uses_tool_cache_prefix(path: str) -> bool:
    return not _contains_parent_traversal(path) and any(
        path.startswith(marker) for marker in TOOL_CACHE_MARKERS
    )


def _tool_cache_evidence(path: str) -> str:
    if _uses_tool_cache_prefix(path):
        return "observed path uses a hosted tool-cache prefix"
    return "path resolves inside a configured tool cache"


def _contains_parent_traversal(path: str) -> bool:
    return ".." in PurePosixPath(path).parts or ".." in PureWindowsPath(path).parts


def _is_workflow_provisioned(path: str, env: Mapping[str, str]) -> bool:
    declared_paths = env.get(WORKFLOW_PROVISIONED_PATHS_ENV, "")
    for declared_path in declared_paths.split(os.pathsep):
        if declared_path and _is_relative_to(Path(path), Path(declared_path)):
            return True
    return False


def _is_containerized(env: Mapping[str, str]) -> bool:
    return env.get(CONTAINERIZED_ENV, "").lower() in {"1", "true", "yes"}


def _is_github_hosted_runner(runner: RunnerInfo) -> bool:
    return runner.provider == "github-actions" and runner.environment == "github-hosted"


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except (OSError, RuntimeError, ValueError):
        return False
    return True
