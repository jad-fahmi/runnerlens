"""Human-readable report rendering."""

from __future__ import annotations

from runnerlens.models import Receipt


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
