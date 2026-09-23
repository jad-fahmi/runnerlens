from pathlib import Path

from runnerlens.models import ExecutionEvent, ObservedCommand
from runnerlens.observer import Observation
import pytest

from runnerlens import receipt as receipt_module
from runnerlens.receipt import build_receipt, load_receipt, receipt_from_dict, write_receipt


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


@pytest.mark.parametrize(("path", "expected"), [("./tool", None), ("/usr//bin/tool", "/usr/bin/tool")])
def test_receipt_preserves_dependencies_after_path_normalization(tmp_path: Path, path, expected) -> None:
    observation = Observation(
        command=ObservedCommand(executable="tool"),
        events=[ExecutionEvent("tool", path)],
        started_at="2026-09-21T00:00:00+00:00",
        ended_at="2026-09-21T00:00:01+00:00",
        exit_code=0,
    )

    receipt = build_receipt(observation, tmp_path, env={})

    assert [(dependency.name, dependency.path) for dependency in receipt.dependencies] == [("tool", expected)]
    assert receipt.events == observation.events


def test_receipt_from_dict_rejects_an_unknown_schema_version() -> None:
    with pytest.raises(ValueError, match="unsupported receipt schema"):
        receipt_from_dict({"schema_version": "99.0.0"})


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("origin", "ambient", "unsupported dependency origin"),
        ("confidence", "certain", "unsupported dependency confidence"),
        ("evidence", "not-an-array", "dependency evidence must be an array of strings"),
    ],
)
def test_receipt_from_dict_rejects_invalid_dependency_fields(
    field: str, value: str, message: str
) -> None:
    dependency = {
        "name": "cmake",
        "path": "/usr/bin/cmake",
        "origin": "runner-provided",
        "confidence": "probable",
        "evidence": [],
    }
    dependency[field] = value
    data = {
        "schema_version": "0.1.0",
        "started_at": "2026-09-21T00:00:00+00:00",
        "ended_at": "2026-09-21T00:00:01+00:00",
        "exit_code": 0,
        "runner": {"provider": "github-actions"},
        "command": {"executable": "make"},
        "dependencies": [dependency],
        "events": [],
    }

    with pytest.raises(ValueError, match=message):
        receipt_from_dict(data)


@pytest.mark.parametrize(
    ("event", "message"),
    [
        ("not-an-object", "receipt events must contain objects"),
        ({"executable": "cmake", "path": "/usr/bin/cmake", "role": "helper"}, "unsupported event role"),
        ({"executable": "cmake", "path": "/usr/bin/cmake", "pid": True}, "event pid must be a positive integer or null"),
        ({"executable": "cmake", "path": "/usr/bin/cmake", "pid": 0}, "event pid must be a positive integer or null"),
        ({"executable": "cmake", "path": "/usr/bin/cmake", "parent_pid": -1}, "event parent_pid must be a positive integer or null"),
    ],
)
def test_receipt_from_dict_rejects_invalid_event_fields(event: object, message: str) -> None:
    data = {
        "schema_version": "0.1.0",
        "started_at": "2026-09-21T00:00:00+00:00",
        "ended_at": "2026-09-21T00:00:01+00:00",
        "exit_code": 0,
        "runner": {"provider": "github-actions"},
        "command": {"executable": "make"},
        "dependencies": [],
        "events": [event],
    }

    with pytest.raises(ValueError, match=message):
        receipt_from_dict(data)


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


def test_receipt_round_trips_unresolved_dependency_and_event_paths(tmp_path: Path) -> None:
    observation = Observation(
        command=ObservedCommand(executable="relative-tool"),
        events=[
            ExecutionEvent(
                executable="relative-tool",
                path=None,
                observation="strace-execve-unresolved",
            )
        ],
        started_at="2026-09-21T00:00:00+00:00",
        ended_at="2026-09-21T00:00:01+00:00",
        exit_code=0,
    )

    receipt = build_receipt(observation, tmp_path, env={})
    receipt_path = tmp_path / "unresolved-paths.json"
    write_receipt(receipt, receipt_path)
    data = load_receipt(receipt_path)
    loaded = receipt_from_dict(data)

    assert data["dependencies"][0]["path"] is None
    assert data["events"][0]["path"] is None
    assert loaded == receipt


def test_failed_atomic_receipt_write_preserves_existing_receipt(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "receipt.json"
    target.write_text("existing receipt", encoding="utf-8")
    observation = Observation(
        command=ObservedCommand(executable="make"),
        events=[],
        started_at="2026-09-21T00:00:00+00:00",
        ended_at="2026-09-21T00:00:01+00:00",
        exit_code=0,
    )
    receipt = build_receipt(observation, tmp_path, env={})

    def fail_replace(source, destination):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(receipt_module.os, "replace", fail_replace)

    with pytest.raises(OSError, match="simulated replace failure"):
        write_receipt(receipt, target)

    assert target.read_text(encoding="utf-8") == "existing receipt"
    assert list(tmp_path.glob(".receipt.json.*.tmp")) == []


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
