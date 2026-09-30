from pathlib import Path

from runnerlens.classifier import classify_event, classify_events
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


def test_repository_path_with_parent_traversal_stays_unknown(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    tool = repository / "scripts" / "build-tool"
    tool.parent.mkdir(parents=True)
    tool.write_text("", encoding="utf-8")
    traversing_path = str(tmp_path / "outside" / ".." / "repository" / "scripts" / "build-tool")

    dependency = classify_event(
        ExecutionEvent(executable="build-tool", path=traversing_path),
        RunnerInfo(provider="github-actions", os="Linux", environment="github-hosted"),
        repository,
        {},
    )

    assert dependency.origin == "unknown"
    assert dependency.confidence == "unknown"
    assert "parent traversal" in dependency.evidence[-1]


def test_windows_path_with_parent_traversal_stays_unknown(tmp_path: Path) -> None:
    dependency = classify_event(
        ExecutionEvent(executable="tool.exe", path=r"C:\tools\..\tool.exe"),
        RunnerInfo(provider="github-actions", os="Windows", environment="github-hosted"),
        tmp_path,
        {"RUNNERLENS_CONTAINERIZED": "true"},
    )

    assert dependency.origin == "unknown"
    assert "parent traversal" in dependency.evidence[-1]


def test_duplicate_observations_preserve_distinct_evidence(tmp_path: Path) -> None:
    dependencies = classify_events(
        [
            ExecutionEvent("cmake", "/usr/bin/cmake", observation="strace-execve"),
            ExecutionEvent("cmake", "/usr/bin/cmake", observation="strace-execveat"),
        ],
        RunnerInfo(provider="github-actions", os="Linux", environment="github-hosted"),
        tmp_path,
        {},
    )

    assert len(dependencies) == 1
    assert dependencies[0].evidence == [
        "observed via strace-execve",
        "documented base-image path on GitHub-hosted runner",
        "observed via strace-execveat",
    ]


def test_github_actions_system_path_is_probable_runner_provided(tmp_path: Path) -> None:
    dependency = classify_event(
        ExecutionEvent(executable="cmake", path="/usr/bin/cmake"),
        RunnerInfo(provider="github-actions", os="Linux", environment="github-hosted"),
        tmp_path,
        {},
    )

    assert dependency.origin == "runner-provided"
    assert dependency.confidence == "probable"


def test_github_actions_preinstalled_cargo_path_is_probable_runner_provided(tmp_path: Path) -> None:
    dependency = classify_event(
        ExecutionEvent(executable="cargo", path="/home/runner/.cargo/bin/cargo"),
        RunnerInfo(provider="github-actions", os="Linux", environment="github-hosted"),
        tmp_path,
        {},
    )

    assert dependency.origin == "runner-provided"
    assert dependency.confidence == "probable"
    assert "base-image path" in dependency.evidence[-1]


def test_self_hosted_github_actions_system_path_stays_unknown(tmp_path: Path) -> None:
    dependency = classify_event(
        ExecutionEvent(executable="cmake", path="/usr/bin/cmake"),
        RunnerInfo(provider="github-actions", os="Linux", environment="self-hosted"),
        tmp_path,
        {},
    )

    assert dependency.origin == "unknown"
    assert dependency.confidence == "unknown"


def test_github_actions_without_hosted_evidence_stays_unknown(tmp_path: Path) -> None:
    dependency = classify_event(
        ExecutionEvent(executable="cmake", path="/usr/bin/cmake"),
        RunnerInfo(provider="github-actions", os="Linux"),
        tmp_path,
        {},
    )

    assert dependency.origin == "unknown"
    assert dependency.confidence == "unknown"


def test_local_system_path_stays_unknown(tmp_path: Path) -> None:
    dependency = classify_event(
        ExecutionEvent(executable="cmake", path="/usr/bin/cmake"),
        RunnerInfo(provider="local", os="Linux"),
        tmp_path,
        {},
    )

    assert dependency.origin == "unknown"
    assert dependency.confidence == "unknown"


def test_relative_executable_path_stays_unresolved(tmp_path: Path) -> None:
    dependency = classify_event(
        ExecutionEvent(executable="build-tool", path="tools/build-tool"),
        RunnerInfo(provider="github-actions", os="Linux", environment="github-hosted"),
        tmp_path,
        {},
    )

    assert dependency.path is None
    assert dependency.origin == "unknown"
    assert dependency.confidence == "unknown"
    assert "child working directory is not established" in dependency.evidence[-1]


def test_tool_cache_path_is_confirmed_tool_cache(tmp_path: Path) -> None:
    dependency = classify_event(
        ExecutionEvent(executable="python", path="/opt/hostedtoolcache/Python/3.13/bin/python"),
        RunnerInfo(provider="github-actions", os="Linux"),
        tmp_path,
        {},
    )

    assert dependency.origin == "tool-cache"
    assert dependency.confidence == "confirmed"


def test_tool_cache_marker_inside_an_unrelated_path_stays_unknown(tmp_path: Path) -> None:
    dependency = classify_event(
        ExecutionEvent(
            executable="python",
            path="/tmp/opt/hostedtoolcache/Python/3.13/bin/python",
        ),
        RunnerInfo(provider="github-actions", os="Linux"),
        tmp_path,
        {},
    )

    assert dependency.origin == "unknown"
    assert dependency.confidence == "unknown"


def test_declared_workflow_path_is_confirmed_workflow_provisioned(tmp_path: Path) -> None:
    provisioned_root = tmp_path / "workflow-tools"
    tool = provisioned_root / "bin" / "cmake"
    tool.parent.mkdir(parents=True)
    tool.write_text("", encoding="utf-8")

    dependency = classify_event(
        ExecutionEvent(executable="cmake", path=str(tool)),
        RunnerInfo(provider="github-actions", os="Linux"),
        tmp_path / "repository",
        {"RUNNERLENS_WORKFLOW_PROVISIONED_PATHS": str(provisioned_root)},
    )

    assert dependency.origin == "workflow-provisioned"
    assert dependency.confidence == "confirmed"
    assert "workflow-provisioned" in dependency.evidence[-1]


def test_explicit_container_execution_classifies_external_tool(tmp_path: Path) -> None:
    dependency = classify_event(
        ExecutionEvent(executable="cmake", path="/usr/bin/cmake"),
        RunnerInfo(provider="github-actions", os="Linux"),
        tmp_path,
        {"RUNNERLENS_CONTAINERIZED": "true"},
    )

    assert dependency.origin == "container-provided"
    assert dependency.confidence == "confirmed"
    assert "container execution" in dependency.evidence[-1]


def test_explicit_container_boundary_overrides_tool_cache_path(tmp_path: Path) -> None:
    dependency = classify_event(
        ExecutionEvent(executable="python", path="/opt/hostedtoolcache/Python/3.13/bin/python"),
        RunnerInfo(provider="github-actions", os="Linux", environment="github-hosted"),
        tmp_path,
        {"RUNNERLENS_CONTAINERIZED": "true"},
    )

    assert dependency.origin == "container-provided"
    assert dependency.confidence == "confirmed"
