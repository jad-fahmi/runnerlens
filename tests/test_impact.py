from runnerlens.github import GitHubImageManifest
from runnerlens.impact import compare_receipts, correlate_receipt_with_image, newly_observed_ambient_dependencies
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


def test_image_impact_preserves_unknown_metadata_as_unavailable() -> None:
    receipt = _receipt(
        [
            Dependency("cmake", "/usr/bin/cmake", "runner-provided", "probable", version="3.28.1"),
            Dependency("custom-tool", "/usr/bin/custom-tool", "unknown", "unknown", version="1.0.0"),
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
        ("custom-tool", "metadata-unavailable"),
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
