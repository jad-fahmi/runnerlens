import json
from pathlib import Path

from runnerlens.cli import main
from runnerlens.github import GitHubImageManifest


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


def test_show_command_reports_missing_receipt(capsys) -> None:
    exit_code = main(["show", "missing-receipt.json"])

    captured = capsys.readouterr()

    assert exit_code == 2
    assert "could not read receipt" in captured.err


def test_compare_command_renders_receipt_impact(tmp_path: Path, capsys) -> None:
    baseline_path = tmp_path / "baseline.json"
    target_path = tmp_path / "target.json"
    for path, version in ((baseline_path, "1.0.0"), (target_path, "2.0.0")):
        path.write_text(
            json.dumps(
                {
                    "schema_version": "0.1.0",
                    "started_at": "2026-09-21T00:00:00+00:00",
                    "ended_at": "2026-09-21T00:00:01+00:00",
                    "exit_code": 0,
                    "runner": {"provider": "github-actions", "image": "ubuntu-24.04"},
                    "command": {"executable": "cmake", "arguments_recorded": False},
                    "dependencies": [
                        {
                            "name": "cmake",
                            "path": "/usr/bin/cmake",
                            "origin": "runner-provided",
                            "confidence": "probable",
                            "version": version,
                        }
                    ],
                    "events": [],
                }
            ),
            encoding="utf-8",
        )

    exit_code = main(["compare", str(baseline_path), str(target_path)])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "changed   cmake (1.0.0 -> 2.0.0)" in captured.out


def test_impact_command_fetches_target_image_metadata(tmp_path: Path, capsys, monkeypatch) -> None:
    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1.0",
                "started_at": "2026-09-21T00:00:00+00:00",
                "ended_at": "2026-09-21T00:00:01+00:00",
                "exit_code": 0,
                "runner": {"provider": "github-actions", "image": "ubuntu24"},
                "command": {"executable": "cmake", "arguments_recorded": False},
                "dependencies": [
                    {
                        "name": "cmake",
                        "path": "/usr/bin/cmake",
                        "origin": "runner-provided",
                        "confidence": "probable",
                        "version": "3.28.1",
                    }
                ],
                "events": [],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "runnerlens.cli.fetch_ubuntu_manifest",
        lambda image, version: GitHubImageManifest(
            image=image,
            release=f"ubuntu24/{version}",
            source_url="https://example.test/manifest",
            tools={"cmake": ("3.30.2",)},
        ),
    )

    exit_code = main(["impact", str(receipt_path), "--target-image-version", "20260922.1"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "version-changed      cmake" in captured.out
    assert "Metadata source: https://example.test/manifest" in captured.out


def test_check_command_fails_for_new_runner_dependency(tmp_path: Path, capsys) -> None:
    baseline_path = tmp_path / "baseline.json"
    target_path = tmp_path / "target.json"
    baseline_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1.0", "started_at": "2026-09-21T00:00:00+00:00", "ended_at": "2026-09-21T00:00:01+00:00", "exit_code": 0,
                "runner": {"provider": "github-actions"}, "command": {"executable": "make", "arguments_recorded": False}, "dependencies": [], "events": [],
            }
        ),
        encoding="utf-8",
    )
    target_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1.0", "started_at": "2026-09-21T00:00:00+00:00", "ended_at": "2026-09-21T00:00:01+00:00", "exit_code": 0,
                "runner": {"provider": "github-actions"}, "command": {"executable": "make", "arguments_recorded": False},
                "dependencies": [{"name": "cmake", "path": "/usr/bin/cmake", "origin": "runner-provided", "confidence": "probable"}], "events": [],
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(["check", str(baseline_path), str(target_path)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "New ambient dependencies:" in captured.out
    assert "cmake" in captured.out
