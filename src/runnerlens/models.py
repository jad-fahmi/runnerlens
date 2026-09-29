"""Core data structures for RunnerLens receipts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


SCHEMA_VERSION = "0.1.0"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class RunnerInfo:
    provider: str
    os: str | None = None
    image: str | None = None
    image_version: str | None = None
    architecture: str | None = None
    environment: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _without_none(
            {
                "provider": self.provider,
                "os": self.os,
                "image": self.image,
                "image_version": self.image_version,
                "architecture": self.architecture,
                "environment": self.environment,
            }
        )


@dataclass(frozen=True)
class ObservedCommand:
    executable: str
    resolved_path: str | None = None
    arguments_recorded: bool = False

    def to_dict(self) -> dict[str, Any]:
        return _without_none(
            {
                "executable": self.executable,
                "resolved_path": self.resolved_path,
                "arguments_recorded": self.arguments_recorded,
            }
        )


@dataclass(frozen=True)
class ExecutionEvent:
    executable: str
    path: str | None = None
    pid: int | None = None
    parent_pid: int | None = None
    observation: str = "subprocess-root"
    role: str = "build-tool"

    def to_dict(self) -> dict[str, Any]:
        data = _without_none(
            {
                "executable": self.executable,
                "pid": self.pid,
                "parent_pid": self.parent_pid,
                "observation": self.observation,
                "role": self.role,
            }
        )
        data["path"] = self.path
        return data


@dataclass(frozen=True)
class Dependency:
    name: str
    path: str | None
    origin: str
    confidence: str
    version: str | None = None
    package: str | None = None
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = {
            "name": self.name,
            "path": self.path,
            "version": self.version,
            "package": self.package,
            "origin": self.origin,
            "confidence": self.confidence,
            "evidence": self.evidence,
        }
        result = _without_none(data)
        result["path"] = self.path
        return result


@dataclass(frozen=True)
class Receipt:
    runner: RunnerInfo
    command: ObservedCommand
    dependencies: list[Dependency]
    events: list[ExecutionEvent]
    started_at: str
    ended_at: str
    exit_code: int
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "exit_code": self.exit_code,
            "runner": self.runner.to_dict(),
            "command": self.command.to_dict(),
            "dependencies": [dependency.to_dict() for dependency in self.dependencies],
            "events": [event.to_dict() for event in self.events],
        }


def _without_none(data: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in data.items() if value is not None}
