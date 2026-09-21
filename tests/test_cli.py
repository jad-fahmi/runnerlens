import json
from pathlib import Path

from runnerlens.cli import main


def test_version_command_prints_version(capsys) -> None:
    exit_code = main(["version"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.strip()


def test_show_command_renders_human_readable_receipt(tmp_path: Path, capsys) -> None:
    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1.0",
                "started_at": "2026-09-21T00:00:00+00:00",
                "ended_at": "2026-09-21T00:00:01+00:00",
                "exit_code": 0,
                "runner": {"provider": "github-actions", "os": "Linux"},
                "command": {"executable": "cmake", "arguments_recorded": False},
                "dependencies": [],
                "events": [],
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(["show", str(receipt_path)])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "RunnerLens" in captured.out
    assert '"schema_version"' not in captured.out
