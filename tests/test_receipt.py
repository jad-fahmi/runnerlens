from pathlib import Path

from runnerlens.models import ExecutionEvent, ObservedCommand
from runnerlens.observer import Observation
import pytest

from runnerlens.receipt import build_receipt, receipt_from_dict


def test_build_receipt_uses_schema_and_dependencies(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("RUNNER_OS", "Linux")
    monkeypatch.setenv("RUNNER_ENVIRONMENT", "github-hosted")
    monkeypatch.setenv("ImageOS", "ubuntu24")
    monkeypatch.setenv("ImageVersion", "20260921.1")

    observation = Observation(
        command=ObservedCommand(executable="cmake", resolved_path="/usr/bin/cmake"),
        events=[ExecutionEvent(executable="cmake", path="/usr/bin/cmake")],
        started_at="2026-09-21T00:00:00+00:00",
        ended_at="2026-09-21T00:00:01+00:00",
        exit_code=0,
    )

    receipt = build_receipt(observation, tmp_path)
    data = receipt.to_dict()

    assert data["schema_version"] == "0.1.0"
    assert data["runner"]["provider"] == "github-actions"
    assert data["runner"]["image"] == "ubuntu24"
    assert data["dependencies"][0]["origin"] == "runner-provided"


def test_receipt_from_dict_rejects_an_unknown_schema_version() -> None:
    with pytest.raises(ValueError, match="unsupported receipt schema"):
        receipt_from_dict({"schema_version": "99.0.0"})


def test_receipt_serializes_process_parent_evidence(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    observation = Observation(
        command=ObservedCommand(executable="make", resolved_path="/usr/bin/make"),
        events=[
            ExecutionEvent(executable="make", path="/usr/bin/make", pid=42),
            ExecutionEvent(executable="cmake", path="/usr/bin/cmake", pid=43, parent_pid=42),
        ],
        started_at="2026-09-21T00:00:00+00:00",
        ended_at="2026-09-21T00:00:01+00:00",
        exit_code=0,
    )

    receipt = build_receipt(observation, tmp_path)

    assert receipt.to_dict()["events"][1]["parent_pid"] == 42


def test_receipt_keeps_support_tools_as_events_but_excludes_them_from_dependencies(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    observation = Observation(
        command=ObservedCommand(executable="bash", resolved_path="/usr/bin/bash"),
        events=[
            ExecutionEvent(executable="bash", path="/usr/bin/bash", role="launcher"),
            ExecutionEvent(executable="cat", path="/usr/bin/cat"),
            ExecutionEvent(executable="cmake", path="/usr/bin/cmake"),
        ],
        started_at="2026-09-21T00:00:00+00:00",
        ended_at="2026-09-21T00:00:01+00:00",
        exit_code=0,
    )

    receipt = build_receipt(observation, tmp_path)

    assert [dependency.name for dependency in receipt.dependencies] == ["cmake"]
    assert [event.executable for event in receipt.events] == ["bash", "cat", "cmake"]


def test_receipt_can_include_support_tools_on_request(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    observation = Observation(
        command=ObservedCommand(executable="bash", resolved_path="/usr/bin/bash"),
        events=[ExecutionEvent(executable="bash", path="/usr/bin/bash", role="launcher")],
        started_at="2026-09-21T00:00:00+00:00",
        ended_at="2026-09-21T00:00:01+00:00",
        exit_code=0,
    )

    receipt = build_receipt(observation, tmp_path, include_support_tools=True)

    assert [dependency.name for dependency in receipt.dependencies] == ["bash"]
