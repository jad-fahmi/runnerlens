from pathlib import Path
from subprocess import CompletedProcess

from runnerlens import resolver


def test_detect_version_returns_a_parsed_version(tmp_path: Path, monkeypatch) -> None:
    executable = tmp_path / "cmake"
    executable.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        resolver.subprocess,
        "run",
        lambda *args, **kwargs: CompletedProcess(args[0], 0, "cmake version 3.30.2\n"),
    )

    assert resolver.detect_version(str(executable)) == "3.30.2"


def test_detect_version_omits_unreliable_results(tmp_path: Path, monkeypatch) -> None:
    executable = tmp_path / "tool"
    executable.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        resolver.subprocess,
        "run",
        lambda *args, **kwargs: CompletedProcess(args[0], 1, "usage"),
    )

    assert resolver.detect_version(str(executable)) is None


def test_find_package_owner_parses_multiarch_package_name(tmp_path: Path, monkeypatch) -> None:
    executable = tmp_path / "tool"
    executable.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        resolver.subprocess,
        "run",
        lambda *args, **kwargs: CompletedProcess(args[0], 0, "libexample1:amd64: /usr/bin/tool\n"),
    )

    assert resolver.find_package_owner(str(executable)) == "libexample1:amd64"
