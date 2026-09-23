"""Receipt construction and serialization."""

from __future__ import annotations

import json
import os
from pathlib import Path
from collections.abc import Mapping
from typing import Any

from runnerlens.classifier import classify_events
from runnerlens.models import SCHEMA_VERSION, Dependency, ExecutionEvent, ObservedCommand, Receipt, RunnerInfo
from runnerlens.observer import Observation
from runnerlens.resolver import enrich_dependencies
from runnerlens.runner import detect_runner


def build_receipt(
    observation: Observation, repository_root: Path, env: Mapping[str, str] | None = None
) -> Receipt:
    data = env if env is not None else os.environ
    runner = detect_runner(data)
    dependencies = enrich_dependencies(classify_events(observation.events, runner, repository_root, data))

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
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("receipt JSON must contain an object")
    return data


def receipt_from_dict(data: dict[str, Any]) -> Receipt:
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            f"unsupported receipt schema version: {data.get('schema_version')!r}, expected {SCHEMA_VERSION!r}"
        )
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
