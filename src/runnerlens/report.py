"""Human-readable report rendering."""

from __future__ import annotations

from runnerlens.models import Receipt
from runnerlens.impact import ImageImpact, ReceiptImpact


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
        "",
    ]
    counts = {status: 0 for status in ("added", "removed", "changed", "unchanged")}
    for dependency in impact.dependencies:
        counts[dependency.status] += 1
        before = dependency.baseline.version if dependency.baseline else None
        after = dependency.target.version if dependency.target else None
        versions = f" ({before or 'unavailable'} -> {after or 'unavailable'})"
        lines.append(f"{dependency.status:9} {dependency.name}{versions}")

    lines.extend(
        [
            "",
            "Summary: " + ", ".join(f"{counts[status]} {status}" for status in counts),
        ]
    )
    return "\n".join(lines) + "\n"


def render_image_impact_report(impact: ImageImpact) -> str:
    lines = [
        "RunnerLens runner-image impact",
        "==============================",
        "",
        f"Observed runner: {_runner_label(impact.observed_runner)}",
        f"Target release:  {impact.target_release}",
        f"Metadata source: {impact.source_url}",
        "",
    ]
    for item in impact.dependencies:
        observed = item.dependency.version or "unavailable"
        documented = ", ".join(item.documented_versions or ()) or "unavailable"
        lines.extend(
            [
                f"{item.status:20} {item.dependency.name}",
                f"  observed:   {observed}",
                f"  target:     {documented}",
            ]
        )
    return "\n".join(lines) + "\n"


def _runner_label(runner) -> str:
    values = [runner.provider, runner.image, runner.image_version]
    return " / ".join(value for value in values if value) or "unknown"
