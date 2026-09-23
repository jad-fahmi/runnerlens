"""Receipt construction and serialization."""

from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import tempfile
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from runnerlens.classifier import classify_events
from runnerlens.models import SCHEMA_VERSION, Dependency, ExecutionEvent, ObservedCommand, Receipt, RunnerInfo
from runnerlens.observer import Observation
from runnerlens.resolver import enrich_dependencies
from runnerlens.runner import detect_runner


SUPPORT_EXECUTABLES = frozenset({"awk", "basename", "bash", "cat", "cut", "dirname", "env", "grep", "sed", "sh", "tr"})
_RECEIPT_ORIGINS = frozenset(
    {"runner-provided", "workflow-provisioned", "repository-provided", "tool-cache", "container-provided", "unknown"}
)
_RECEIPT_CONFIDENCE = frozenset({"confirmed", "probable", "unknown"})
_RECEIPT_EVENT_ROLES = frozenset({"build-tool", "launcher"})


def build_receipt(
    observation: Observation,
    repository_root: Path,
    env: Mapping[str, str] | None = None,
    include_support_tools: bool = False,
) -> Receipt:
    data = env if env is not None else os.environ
    runner = detect_runner(data)
    reportable_events = [
        event for event in observation.events
        if not event.observation.endswith("-incomplete")
        and (include_support_tools or _is_reportable_event(event))
    ]
    dependencies = classify_events(reportable_events, runner, repository_root, data)
    dependencies = enrich_dependencies(dependencies)

    return Receipt(
        runner=runner,
        command=observation.command,
        dependencies=dependencies,
        events=observation.events,
        started_at=observation.started_at,
        ended_at=observation.ended_at,
        exit_code=observation.exit_code,
    )


def write_receipt(receipt: Receipt, path: Path) -> None:
    data = receipt.to_dict()
    receipt_from_dict(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        destination = path.resolve() if path.is_symlink() else path
    except (OSError, RuntimeError) as error:
        raise ValueError(f"receipt output path cannot be resolved: {path}") from error
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(to_json(data))
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, destination)
    finally:
        if temporary_path is not None:
            with contextlib.suppress(OSError):
                temporary_path.unlink(missing_ok=True)


def load_receipt(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("receipt JSON must contain an object")
    return data


def receipt_from_dict(data: dict[str, Any]) -> Receipt:
    if not isinstance(data, dict):
        raise ValueError("receipt JSON must contain an object")
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            f"unsupported receipt schema version: {data.get('schema_version')!r}, expected {SCHEMA_VERSION!r}"
        )
    started_at = _parse_timestamp(data, "started_at")
    ended_at = _parse_timestamp(data, "ended_at")
    if ended_at < started_at:
        raise ValueError("receipt ended_at must not precede started_at")
    if type(data.get("exit_code")) is not int:
        raise ValueError("receipt exit_code must be an integer")
    runner = data.get("runner")
    if not isinstance(runner, dict):
        raise ValueError("receipt runner must be an object")
    _require_string(runner, "provider", "runner")
    for field in ("os", "image", "image_version", "architecture", "environment"):
        _validate_optional_string(runner, field, "runner")
    command = data.get("command")
    if not isinstance(command, dict):
        raise ValueError("receipt command must be an object")
    _require_string(command, "executable", "command")
    _validate_optional_path(command, "resolved_path", "command")
    if "arguments_recorded" in command and type(command["arguments_recorded"]) is not bool:
        raise ValueError("command arguments_recorded must be a boolean")
    if not isinstance(data.get("dependencies"), list):
        raise ValueError("receipt dependencies must be an array")
    if not isinstance(data.get("events"), list):
        raise ValueError("receipt events must be an array")
    dependency_identities: set[tuple[str, str | None]] = set()
    for dependency in data["dependencies"]:
        if not isinstance(dependency, dict):
            raise ValueError("receipt dependencies must contain objects")
        _require_string(dependency, "name", "dependency")
        if "path" not in dependency:
            raise ValueError("dependency path must be a string or null")
        _validate_optional_path(dependency, "path", "dependency")
        for field in ("version", "package"):
            _validate_optional_string(dependency, field, "dependency")
        identity = (dependency["name"], dependency["path"])
        if identity in dependency_identities:
            raise ValueError(f"duplicate dependency identity: {identity!r}")
        dependency_identities.add(identity)
        origin = dependency.get("origin")
        if not isinstance(origin, str) or origin not in _RECEIPT_ORIGINS:
            raise ValueError(f"unsupported dependency origin: {origin!r}")
        confidence = dependency.get("confidence")
        if not isinstance(confidence, str) or confidence not in _RECEIPT_CONFIDENCE:
            raise ValueError(f"unsupported dependency confidence: {confidence!r}")
        evidence = dependency.get("evidence", [])
        if not isinstance(evidence, list) or any(not isinstance(item, str) for item in evidence):
            raise ValueError("dependency evidence must be an array of strings")
    for event in data["events"]:
        if not isinstance(event, dict):
            raise ValueError("receipt events must contain objects")
        _require_string(event, "executable", "event")
        _validate_optional_path(event, "path", "event")
        if not isinstance(event.get("observation", "subprocess-root"), str):
            raise ValueError("event observation must be a string")
        role = event.get("role", "build-tool")
        if not isinstance(role, str) or role not in _RECEIPT_EVENT_ROLES:
            raise ValueError(f"unsupported event role: {role!r}")
        for field in ("pid", "parent_pid"):
            value = event.get(field)
            if value is not None and (type(value) is not int or value < 1):
                raise ValueError(f"event {field} must be a positive integer or null")
    return Receipt(
        runner=RunnerInfo(**data["runner"]),
        command=ObservedCommand(**data["command"]),
        dependencies=[Dependency(**dependency) for dependency in data["dependencies"]],
        events=[ExecutionEvent(**event) for event in data["events"]],
        started_at=data["started_at"],
        ended_at=data["ended_at"],
        exit_code=data["exit_code"],
        schema_version=data["schema_version"],
    )


def _require_string(data: dict[str, Any], field: str, context: str) -> None:
    if not isinstance(data.get(field), str) or not data[field]:
        raise ValueError(f"{context} {field} must be a non-empty string")


def _parse_timestamp(data: dict[str, Any], field: str) -> datetime:
    _require_string(data, field, "receipt")
    value = data[field]
    normalized = f"{value[:-1]}+00:00" if value.endswith("Z") else value
    try:
        timestamp = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise ValueError(f"receipt {field} must be an ISO 8601 timestamp") from error
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError(f"receipt {field} must include a timezone")
    return timestamp


def _validate_optional_string(data: dict[str, Any], field: str, context: str) -> None:
    value = data.get(field)
    if value is not None and not isinstance(value, str):
        raise ValueError(f"{context} {field} must be a string or null")


def _validate_optional_path(data: dict[str, Any], field: str, context: str) -> None:
    value = data.get(field)
    if value is not None and (
        not isinstance(value, str)
        or "\x00" in value
        or not (PurePosixPath(value).is_absolute() or PureWindowsPath(value).is_absolute())
    ):
        raise ValueError(f"{context} {field} must be an absolute filesystem path or null")


def to_json(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def _is_reportable_event(event: ExecutionEvent) -> bool:
    return event.role != "launcher" and event.executable not in SUPPORT_EXECUTABLES
