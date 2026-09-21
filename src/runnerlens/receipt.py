"""Receipt construction and serialization."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from runnerlens.classifier import classify_events
from runnerlens.models import Dependency, ExecutionEvent, ObservedCommand, Receipt, RunnerInfo
from runnerlens.observer import Observation
from runnerlens.runner import detect_runner


def build_receipt(observation: Observation, repository_root: Path) -> Receipt:
    runner = detect_runner()
    dependencies = classify_events(observation.events, runner, repository_root)

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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(to_json(receipt.to_dict()), encoding="utf-8")


def load_receipt(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def receipt_from_dict(data: dict[str, Any]) -> Receipt:
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


def to_json(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, sort_keys=True) + "\n"
