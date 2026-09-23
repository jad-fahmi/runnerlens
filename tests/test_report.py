from runnerlens.models import Dependency, ObservedCommand, Receipt, RunnerInfo
from runnerlens.report import render_report


def test_report_includes_dependency_evidence() -> None:
    receipt = Receipt(
        runner=RunnerInfo(provider="github-actions", image="ubuntu24"),
        command=ObservedCommand(executable="cmake", resolved_path="/usr/bin/cmake"),
        dependencies=[
            Dependency(
                name="cmake",
                path="/usr/bin/cmake",
                origin="runner-provided",
                confidence="probable",
                version="3.30.2",
                package="cmake",
                evidence=["observed via strace-execve", "system path on GitHub-hosted runner"],
            )
        ],
        events=[],
        started_at="2026-09-22T00:00:00+00:00",
        ended_at="2026-09-22T00:00:01+00:00",
        exit_code=0,
    )

    report = render_report(receipt)

    assert "version     3.30.2" in report
    assert "package     cmake" in report
    assert "evidence" in report
    assert "observed via strace-execve" in report
