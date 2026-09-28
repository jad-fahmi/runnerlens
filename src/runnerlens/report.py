"""Human-readable report rendering."""

from __future__ import annotations

from runnerlens.models import Receipt
from runnerlens.impact import ImageImpact, ReceiptImpact, RunnerImageImpact, newly_observed_ambient_dependencies


def render_report(receipt: Receipt) -> str:
    lines: list[str] = [
        "RunnerLens",
        "==========",
        "",
        "Runner",
        f"  provider    {receipt.runner.provider}",
    ]

    if receipt.runner.os:
        lines.append(f"  os          {receipt.runner.os}")
    if receipt.runner.image:
        lines.append(f"  image       {receipt.runner.image}")
    if receipt.runner.image_version:
        lines.append(f"  version     {receipt.runner.image_version}")

    lines.extend(
        [
            "",
            "Observed command",
            f"  executable  {receipt.command.executable}",
        ]
    )
    if receipt.command.resolved_path:
        lines.append(f"  path        {receipt.command.resolved_path}")

    lines.extend(["", "Observed dependencies"])

    if not receipt.dependencies:
        lines.append("  none")
    else:
        for dependency in receipt.dependencies:
            lines.extend(
                [
                    "",
                    f"  {dependency.name}",
                    f"    path        {dependency.path or 'unresolved'}",
                    f"    version     {dependency.version or 'unavailable'}",
                    f"    package     {dependency.package or 'unavailable'}",
                    f"    origin      {dependency.origin}",
                    f"    confidence  {dependency.confidence}",
                ]
            )
            if dependency.evidence:
                lines.append("    evidence")
                lines.extend(f"      {evidence}" for evidence in dependency.evidence)

    lines.extend(
        [
            "",
            f"{len(receipt.dependencies)} dependencies observed",
            f"command exit code: {receipt.exit_code}",
        ]
    )
    return "\n".join(lines) + "\n"


def render_impact_report(impact: ReceiptImpact) -> str:
    lines = [
        "RunnerLens receipt impact",
        "========================",
        "",
        f"Baseline runner: {_runner_label(impact.baseline_runner)}",
        f"Target runner:   {_runner_label(impact.target_runner)}",
        f"Observation coverage: baseline={impact.baseline_coverage}, target={impact.target_coverage}",
        "",
    ]
    counts = {status: 0 for status in ("added", "removed", "changed", "unchanged")}
    for dependency in impact.dependencies:
        counts[dependency.status] += 1
        before = dependency.baseline.version if dependency.baseline else None
        after = dependency.target.version if dependency.target else None
        versions = f" ({before or 'unavailable'} -> {after or 'unavailable'})"
        lines.append(f"{dependency.status:9} {dependency.name}{versions}")
        if dependency.baseline:
            lines.append(f"  baseline path: {dependency.baseline.path or 'unresolved'}")
        if dependency.target:
            lines.append(f"  target path:   {dependency.target.path or 'unresolved'}")

    lines.extend(
        [
            "",
            "Summary: " + ", ".join(f"{counts[status]} {status}" for status in counts),
        ]
    )
    if impact.baseline_coverage != "process-tree" or impact.target_coverage != "process-tree":
        lines.extend(
            [
                "",
                "Warning: one or both receipts lack complete process-tree observation;",
                "an empty dependency delta does not establish that no dependencies changed.",
            ]
        )
    return "\n".join(lines) + "\n"


def render_baseline_report(impact: ReceiptImpact) -> str:
    new_dependencies = newly_observed_ambient_dependencies(impact)
    lines = [
        "RunnerLens baseline check",
        "========================",
        "",
        f"Observation coverage: baseline={impact.baseline_coverage}, target={impact.target_coverage}",
        "",
    ]
    if impact.baseline_coverage != "process-tree" or impact.target_coverage != "process-tree":
        lines.extend(
            [
                "Warning: check is inconclusive because one or both receipts lack complete process-tree observation.",
                "",
            ]
        )
    if not new_dependencies:
        lines.append("No newly observed runner-provided or tool-cache dependencies.")
    else:
        lines.append("New ambient dependencies:")
        for item in new_dependencies:
            dependency = item.target
            assert dependency is not None
            lines.append(f"  {dependency.name} ({dependency.origin}, {dependency.path or 'unresolved'})")
    return "\n".join(lines) + "\n"


def render_image_impact_report(impact: ImageImpact) -> str:
    lines = [
        "RunnerLens runner-image impact",
        "==============================",
        "",
        f"Observed runner: {_runner_label(impact.observed_runner)}",
        f"Target release:  {impact.target_release}",
        f"Metadata source: {impact.source_url}",
        f"Observation coverage: {impact.observation_coverage}",
        "",
    ]
    for item in impact.dependencies:
        observed = item.dependency.version or "unavailable"
        documented = ", ".join(item.documented_versions or ()) or "unavailable"
        lines.extend(
            [
                f"{item.status:20} {item.dependency.name}",
                f"  observed path: {item.dependency.path or 'unresolved'}",
                f"  observed:   {observed}",
                f"  target:     {documented}",
            ]
        )
    if impact.observation_coverage != "process-tree":
        lines.extend(
            [
                "",
                "Warning: this report is limited by incomplete process-tree observation;",
                "unobserved child dependencies are not represented.",
            ]
        )
    return "\n".join(lines) + "\n"


def render_runner_image_impact_report(impact: RunnerImageImpact) -> str:
    lines = [
        "RunnerLens runner-image impact",
        "==============================",
        "",
        f"Observed runner:  {_runner_label(impact.observed_runner)}",
        f"Baseline release: {impact.baseline_release}",
        f"Target release:   {impact.target_release}",
        f"Baseline source:  {impact.baseline_source_url}",
        f"Target source:    {impact.target_source_url}",
        f"Observation coverage: {impact.observation_coverage}",
        "",
    ]
    for item in impact.dependencies:
        baseline = ", ".join(item.baseline_versions or ()) or "unavailable"
        target = ", ".join(item.target_versions or ()) or "unavailable"
        lines.extend(
            [
                f"{item.status:20} {item.dependency.name}",
                f"  observed path: {item.dependency.path or 'unresolved'}",
                f"  baseline:   {baseline}",
                f"  target:     {target}",
            ]
        )
    if impact.observation_coverage != "process-tree":
        lines.extend(
            [
                "",
                "Warning: this report is limited by incomplete process-tree observation;",
                "unobserved child dependencies are not represented.",
            ]
        )
    return "\n".join(lines) + "\n"


def _runner_label(runner) -> str:
    values = [runner.provider, runner.image, runner.image_version]
    return " / ".join(value for value in values if value) or "unknown"
