from pathlib import Path

from runnerlens.classifier import classify_event
from runnerlens.models import ExecutionEvent, RunnerInfo


def test_repository_path_is_confirmed_repository_provided(tmp_path: Path) -> None:
    tool = tmp_path / "scripts" / "build-tool"
    tool.parent.mkdir()
    tool.write_text("", encoding="utf-8")

    dependency = classify_event(
        ExecutionEvent(executable="build-tool", path=str(tool)),
        RunnerInfo(provider="github-actions", os="Linux"),
        tmp_path,
        {},
    )

    assert dependency.origin == "repository-provided"
    assert dependency.confidence == "confirmed"


def test_github_actions_system_path_is_probable_runner_provided(tmp_path: Path) -> None:
    dependency = classify_event(
        ExecutionEvent(executable="cmake", path="/usr/bin/cmake"),
        RunnerInfo(provider="github-actions", os="Linux"),
        tmp_path,
        {},
    )

    assert dependency.origin == "runner-provided"
    assert dependency.confidence == "probable"


def test_local_system_path_stays_unknown(tmp_path: Path) -> None:
    dependency = classify_event(
        ExecutionEvent(executable="cmake", path="/usr/bin/cmake"),
        RunnerInfo(provider="local", os="Linux"),
        tmp_path,
        {},
    )

    assert dependency.origin == "unknown"
    assert dependency.confidence == "unknown"


def test_tool_cache_path_is_confirmed_tool_cache(tmp_path: Path) -> None:
    dependency = classify_event(
        ExecutionEvent(executable="python", path="/opt/hostedtoolcache/Python/3.13/bin/python"),
        RunnerInfo(provider="github-actions", os="Linux"),
        tmp_path,
        {},
    )

    assert dependency.origin == "tool-cache"
    assert dependency.confidence == "confirmed"
