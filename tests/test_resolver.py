from pathlib import Path
from subprocess import CompletedProcess

import pytest

from runnerlens import resolver
from runnerlens.models import Dependency


def test_detect_version_returns_a_parsed_version(tmp_path: Path, monkeypatch) -> None:
    executable = tmp_path / "cmake"
    executable.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        resolver.subprocess,
        "run",
        lambda *args, **kwargs: CompletedProcess(args[0], 0, "cmake version 3.30.2\n"),
    )

    assert resolver.detect_version(str(executable)) == "3.30.2"


def test_detect_version_parses_go_version_format(tmp_path: Path, monkeypatch) -> None:
    executable = tmp_path / "go"
    executable.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        resolver.subprocess,
        "run",
        lambda *args, **kwargs: CompletedProcess(args[0], 0, "go version go1.26.8 linux/amd64\n"),
    )

    assert resolver.detect_version(str(executable)) == "1.26.8"


def test_detect_version_uses_upstream_version_after_distribution_build_suffix(
    tmp_path: Path, monkeypatch
) -> None:
    executable = tmp_path / "gcc"
    executable.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        resolver.subprocess,
        "run",
        lambda *args, **kwargs: CompletedProcess(
            args[0], 0, "gcc (Ubuntu 13.3.0-6ubuntu2~24.04) 13.3.0\n"
        ),
    )

    assert resolver.detect_version(str(executable)) == "13.3.0"


def test_detect_version_uses_go_version_subcommand(tmp_path: Path, monkeypatch) -> None:
    executable = tmp_path / "go"
    executable.write_text("", encoding="utf-8")
    commands: list[list[str]] = []

    def fake_run(command, **kwargs):
        commands.append(command)
        return CompletedProcess(command, 0, "go version go1.26.8 linux/amd64\n")

    monkeypatch.setattr(resolver.subprocess, "run", fake_run)

    assert resolver.detect_version(str(executable)) == "1.26.8"
    assert commands == [[str(executable), "version"]]


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


def test_find_package_owner_omits_ambiguous_matches(tmp_path: Path, monkeypatch) -> None:
    executable = tmp_path / "tool"
    executable.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        resolver.subprocess,
        "run",
        lambda *args, **kwargs: CompletedProcess(
            args[0], 0, "tool-package: /usr/bin/tool\nalternative-package: /usr/bin/tool\n"
        ),
    )

    assert resolver.find_package_owner(str(executable)) is None


def test_find_package_owner_omits_malformed_matches(tmp_path: Path, monkeypatch) -> None:
    executable = tmp_path / "tool"
    executable.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        resolver.subprocess,
        "run",
        lambda *args, **kwargs: CompletedProcess(
            args[0], 0, "tool-package: /usr/bin/tool\nunparseable output\n"
        ),
    )

    assert resolver.find_package_owner(str(executable)) is None


@pytest.mark.parametrize("probe", [resolver.detect_version, resolver.find_package_owner])
def test_metadata_decoding_failure_leaves_metadata_unknown(tmp_path: Path, monkeypatch, probe) -> None:
    executable = tmp_path / "tool"
    executable.write_text("", encoding="utf-8")

    def fail_decode(*args, **kwargs):
        raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid byte")

    monkeypatch.setattr(resolver.subprocess, "run", fail_decode)

    assert probe(str(executable)) is None


def test_enrichment_does_not_execute_repository_provided_tools(monkeypatch) -> None:
    monkeypatch.setattr(resolver.platform, "system", lambda: "Linux")
    monkeypatch.setattr(
        resolver.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("tool must not be executed")),
    )
    dependency = Dependency(
        name="project-tool",
        path="/work/repository/project-tool",
        origin="repository-provided",
        confidence="confirmed",
    )

    result = resolver.enrich_dependencies([dependency])

    assert result == [dependency]
