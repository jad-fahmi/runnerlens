from runnerlens.impact import compare_receipts
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
