from runnerlens.github import GitHubImageManifest
from runnerlens.impact import (
    compare_receipts,
    compare_runner_images,
    correlate_receipt_with_image,
    newly_observed_ambient_dependencies,
    observation_coverage,
)
from runnerlens.models import Dependency, ExecutionEvent, ObservedCommand, Receipt, RunnerInfo
from runnerlens.report import (
    render_image_impact_report,
    render_impact_report,
    render_runner_image_impact_report,
)


def _receipt(dependencies: list[Dependency], version: str) -> Receipt:
    return Receipt(
        runner=RunnerInfo(provider="github-actions", image="ubuntu-24.04", image_version=version),
        command=ObservedCommand(executable="make"),
        dependencies=dependencies,
        events=[],
        started_at="2026-09-22T00:00:00+00:00",
        ended_at="2026-09-22T00:00:01+00:00",
        exit_code=0,
    )


def test_compare_receipts_reports_only_observed_dependency_changes() -> None:
    baseline = _receipt(
        [
            Dependency("cmake", "/usr/bin/cmake", "runner-provided", "probable", version="3.28.1"),
            Dependency("ninja", "/usr/bin/ninja", "runner-provided", "probable", version="1.11.1"),
        ],
        "20260901.1",
    )
    target = _receipt(
        [
            Dependency("cmake", "/usr/bin/cmake", "runner-provided", "probable", version="3.30.2"),
            Dependency("clang", "/usr/bin/clang", "runner-provided", "probable", version="20.1.0"),
        ],
        "20260922.1",
    )

    impact = compare_receipts(baseline, target)

    assert [(item.name, item.status) for item in impact.dependencies] == [
        ("clang", "added"),
        ("cmake", "changed"),
        ("ninja", "removed"),
    ]
    report = render_impact_report(impact)
    assert "changed   cmake (3.28.1 -> 3.30.2)" in report


def test_compare_receipts_preserves_same_name_path_switches() -> None:
    baseline = _receipt(
        [Dependency("python", "/usr/bin/python", "runner-provided", "probable", version="3.12.3")],
        "20260901.1",
    )
    target = _receipt(
        [Dependency("python", "/opt/hostedtoolcache/Python/3.13/bin/python", "tool-cache", "confirmed", version="3.13.0")],
        "20260922.1",
    )

    impact = compare_receipts(baseline, target)

    assert {(item.status, item.baseline.path if item.baseline else None, item.target.path if item.target else None) for item in impact.dependencies} == {
        ("removed", "/usr/bin/python", None),
        ("added", None, "/opt/hostedtoolcache/Python/3.13/bin/python"),
    }


def test_image_impact_excludes_non_ambient_dependencies() -> None:
    receipt = _receipt(
        [
            Dependency("cmake", "/usr/bin/cmake", "runner-provided", "probable", version="3.28.1"),
            Dependency("custom-tool", "/work/scripts/custom-tool", "repository-provided", "confirmed", version="1.0.0"),
        ],
        "20260901.1",
    )
    manifest = GitHubImageManifest(
        image="ubuntu24",
        release="ubuntu24/20260922.1",
        source_url="https://example.test/manifest",
        tools={"cmake": ("3.30.2",)},
    )

    impact = correlate_receipt_with_image(receipt, manifest)

    assert [(item.dependency.name, item.status) for item in impact.dependencies] == [
        ("cmake", "version-changed"),
    ]


def test_image_impact_matches_upstream_version_to_debian_package_revision() -> None:
    receipt = _receipt(
        [
            Dependency(
                "automake",
                "/usr/bin/automake",
                "runner-provided",
                "probable",
                version="1.16.5",
                package="automake:amd64",
            )
        ],
        "20260907.300.1",
    )
    package_version = GitHubImageManifest(
        image="ubuntu24",
        release="ubuntu24/20260907.300",
        source_url="https://example.test/manifest",
        tools={},
        apt_packages={"automake": "1:1.16.5-1.3ubuntu1"},
    )
    prerelease_version = GitHubImageManifest(
        image="ubuntu24",
        release="ubuntu24/20260907.300",
        source_url="https://example.test/manifest",
        tools={},
        apt_packages={"automake": "1:1.16.5~rc1-1"},
    )

    impact = correlate_receipt_with_image(receipt, package_version)
    prerelease_impact = correlate_receipt_with_image(receipt, prerelease_version)

    assert impact.dependencies[0].status == "version-present"
    assert impact.dependencies[0].documented_versions == ("1:1.16.5-1.3ubuntu1",)
    assert prerelease_impact.dependencies[0].status == "version-changed"


def test_new_ambient_dependencies_excludes_unknown_and_repository_tools() -> None:
    baseline = _receipt([], "20260901.1")
    target = _receipt(
        [
            Dependency("cmake", "/usr/bin/cmake", "runner-provided", "probable"),
            Dependency("python", "/opt/hostedtoolcache/Python/bin/python", "tool-cache", "confirmed"),
            Dependency("script", "/work/scripts/script", "repository-provided", "confirmed"),
            Dependency("mystery", "/usr/bin/mystery", "unknown", "unknown"),
        ],
        "20260922.1",
    )

    changes = newly_observed_ambient_dependencies(compare_receipts(baseline, target))

    assert [change.name for change in changes] == ["cmake", "python"]


def test_compare_runner_images_filters_changes_to_observed_ambient_dependencies() -> None:
    receipt = _receipt(
        [
            Dependency("cmake", "/usr/bin/cmake", "runner-provided", "probable"),
            Dependency("ninja", "/usr/bin/ninja", "runner-provided", "probable"),
            Dependency("unknown-tool", "/usr/bin/unknown-tool", "unknown", "unknown"),
        ],
        "20260901.1",
    )
    baseline = GitHubImageManifest(
        image="ubuntu24", release="ubuntu24/20260901.1", source_url="https://example.test/baseline",
        tools={"cmake": ("3.28.1",), "ninja": ("1.11.1",)},
    )
    target = GitHubImageManifest(
        image="ubuntu24", release="ubuntu24/20260922.1", source_url="https://example.test/target",
        tools={"cmake": ("3.30.2",)},
    )

    impact = compare_runner_images(receipt, baseline, target)

    assert [(item.dependency.name, item.status) for item in impact.dependencies] == [
        ("cmake", "changed"),
        ("ninja", "removed"),
    ]


def test_compare_runner_images_ignores_inventory_version_order() -> None:
    receipt = _receipt(
        [Dependency("clang", "/usr/bin/clang", "runner-provided", "probable")],
        "20260901.1",
    )
    baseline = GitHubImageManifest(
        image="ubuntu24",
        release="ubuntu24/20260901.1",
        source_url="https://example.test/baseline",
        tools={"clang": ("18.1.8", "19.1.7")},
    )
    target = GitHubImageManifest(
        image="ubuntu24",
        release="ubuntu24/20260922.1",
        source_url="https://example.test/target",
        tools={"clang": ("19.1.7", "18.1.8")},
    )

    impact = compare_runner_images(receipt, baseline, target)

    assert impact.dependencies[0].status == "unchanged"
    assert impact.dependencies[0].baseline_versions == ("18.1.8", "19.1.7")
    assert impact.dependencies[0].target_versions == ("19.1.7", "18.1.8")


def test_compare_runner_images_correlates_a_versioned_compiler_executable() -> None:
    receipt = _receipt(
        [Dependency("g++-14", "/usr/bin/g++-14", "runner-provided", "probable")],
        "20260901.1",
    )
    baseline = GitHubImageManifest(
        image="ubuntu24", release="ubuntu24/20260901.1", source_url="https://example.test/baseline",
        tools={"gnuc": ("13.3.0",)},
    )
    target = GitHubImageManifest(
        image="ubuntu24", release="ubuntu24/20260922.1", source_url="https://example.test/target",
        tools={"gnuc": ("14.2.0",)},
    )

    impact = compare_runner_images(receipt, baseline, target)

    assert [(item.dependency.name, item.status) for item in impact.dependencies] == [
        ("g++-14", "changed"),
    ]


def test_image_impacts_preserve_and_warn_about_root_only_coverage() -> None:
    receipt = _receipt(
        [Dependency("podman", "/usr/bin/podman", "runner-provided", "probable", version="4.9.3")],
        "20260907.300.1",
    )
    receipt = Receipt(
        runner=receipt.runner,
        command=receipt.command,
        dependencies=receipt.dependencies,
        events=[
            ExecutionEvent(
                executable="podman",
                path="/usr/bin/podman",
                observation="subprocess-root-only",
            )
        ],
        started_at=receipt.started_at,
        ended_at=receipt.ended_at,
        exit_code=receipt.exit_code,
    )
    baseline = GitHubImageManifest(
        image="ubuntu24",
        release="ubuntu24/20260831.293",
        source_url="https://example.test/baseline",
        tools={"podman": ("4.9.3",)},
    )
    target = GitHubImageManifest(
        image="ubuntu24",
        release="ubuntu24/20260907.300",
        source_url="https://example.test/target",
        tools={"podman": ("4.9.3",)},
    )

    image_impact = correlate_receipt_with_image(receipt, target)
    comparison = compare_runner_images(receipt, baseline, target)

    assert image_impact.observation_coverage == "root-only"
    assert image_impact.to_dict()["observation_coverage"] == "root-only"
    assert "unobserved child dependencies are not represented" in render_image_impact_report(image_impact)
    assert comparison.observation_coverage == "root-only"
    assert comparison.to_dict()["observation_coverage"] == "root-only"
    assert "unobserved child dependencies are not represented" in render_runner_image_impact_report(comparison)


def test_observation_coverage_distinguishes_resolved_and_unresolved_execveat() -> None:
    receipt = _receipt([], "20260907.300.1")
    resolved = Receipt(
        runner=receipt.runner,
        command=receipt.command,
        dependencies=[],
        events=[ExecutionEvent("custom-tool", "/usr/local/bin/custom-tool", observation="strace-execveat")],
        started_at=receipt.started_at,
        ended_at=receipt.ended_at,
        exit_code=0,
    )
    unresolved = Receipt(
        runner=receipt.runner,
        command=receipt.command,
        dependencies=[],
        events=[ExecutionEvent("unknown-executable", None, observation="strace-execveat-unresolved")],
        started_at=receipt.started_at,
        ended_at=receipt.ended_at,
        exit_code=0,
    )
    unresolved_execve = Receipt(
        runner=receipt.runner,
        command=receipt.command,
        dependencies=[],
        events=[ExecutionEvent("build-tool", None, observation="strace-execve-unresolved")],
        started_at=receipt.started_at,
        ended_at=receipt.ended_at,
        exit_code=0,
    )

    assert observation_coverage(resolved) == "process-tree"
    assert observation_coverage(unresolved) == "partial"
    assert observation_coverage(unresolved_execve) == "partial"


def test_compare_runner_images_uses_apt_metadata_for_package_owned_dependencies() -> None:
    receipt = _receipt(
        [Dependency("crun", "/usr/bin/crun", "runner-provided", "probable", package="crun:amd64")],
        "20260720.247.2",
    )
    baseline = GitHubImageManifest(
        image="ubuntu24",
        release="ubuntu24/20260720.247",
        source_url="https://example.test/baseline",
        tools={},
        apt_packages={"crun": "1.14.1-1ubuntu1"},
    )
    target = GitHubImageManifest(
        image="ubuntu24",
        release="ubuntu24/20260810.271",
        source_url="https://example.test/target",
        tools={},
        apt_packages={"crun": "1.16.1-2"},
    )

    impact = compare_runner_images(receipt, baseline, target)

    assert [(item.dependency.name, item.status) for item in impact.dependencies] == [
        ("crun", "changed"),
    ]
    assert impact.dependencies[0].baseline_versions == ("1.14.1-1ubuntu1",)
    assert impact.dependencies[0].target_versions == ("1.16.1-2",)


def test_compare_runner_images_uses_cached_tool_metadata_for_tool_cache_paths() -> None:
    receipt = _receipt(
        [Dependency("python", "/usr/bin/python", "tool-cache", "confirmed")],
        "20260901.1",
    )
    baseline = GitHubImageManifest(
        image="ubuntu24", release="ubuntu24/20260901.1", source_url="https://example.test/baseline",
        tools={"python": ("3.12.3",)}, cached_tools={"python": ("3.11.16",)},
    )
    target = GitHubImageManifest(
        image="ubuntu24", release="ubuntu24/20260922.1", source_url="https://example.test/target",
        tools={"python": ("3.13.0",)}, cached_tools={"python": ("3.11.16",)},
    )

    impact = compare_runner_images(receipt, baseline, target)

    assert [(item.dependency.name, item.status, item.target_versions) for item in impact.dependencies] == [
        ("python", "unchanged", ("3.11.16",)),
    ]
