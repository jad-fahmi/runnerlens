from pathlib import Path

from runnerlens.models import ExecutionEvent, ObservedCommand
from runnerlens.observer import Observation
from runnerlens.receipt import build_receipt


def test_build_receipt_uses_schema_and_dependencies(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("RUNNER_OS", "Linux")
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
