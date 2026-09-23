from runnerlens.github import GitHubImageManifest
from runnerlens.impact import compare_receipts, compare_runner_images, correlate_receipt_with_image, newly_observed_ambient_dependencies
from runnerlens.models import Dependency, ObservedCommand, Receipt, RunnerInfo
from runnerlens.report import render_impact_report


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


def test_compare_runner_images_uses_cached_tool_metadata_for_tool_cache_paths() -> None:
    receipt = _receipt(
        [Dependency("python", "/opt/hostedtoolcache/Python/3.11.16/x64/bin/python", "tool-cache", "confirmed")],
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
