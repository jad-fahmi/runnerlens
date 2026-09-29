"""Command line interface for RunnerLens."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from runnerlens import __version__
from runnerlens.github import fetch_ubuntu_manifest
from runnerlens.impact import compare_receipts, compare_runner_images, correlate_receipt_with_image, newly_observed_ambient_dependencies
from runnerlens.observer import observe_command
from runnerlens.receipt import build_receipt, load_receipt, receipt_from_dict, to_json, write_receipt
from runnerlens.report import render_baseline_report, render_image_impact_report, render_impact_report, render_report, render_runner_image_impact_report


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command_name == "version":
        print(__version__)
        return 0
    if args.command_name == "run":
        return run_command(args)
    if args.command_name == "show":
        return show_command(args)
    if args.command_name == "compare":
        return compare_command(args)
    if args.command_name == "impact":
        return image_impact_command(args)
    if args.command_name == "check":
        return check_command(args)

    parser.print_help()
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="runnerlens",
        description="Reveal the tools a build inherits from its CI runner.",
    )
    subcommands = parser.add_subparsers(dest="command_name")

    subcommands.add_parser("version", help="print RunnerLens version")

    run = subcommands.add_parser("run", help="observe one build or test command")
    run.add_argument(
        "-o",
        "--output",
        default="runnerlens-receipt.json",
        help="path to write the JSON receipt",
    )
    run.add_argument(
        "--workflow-provisioned-path",
        action="append",
        default=[],
        help="path installed or configured by an earlier workflow step, repeatable",
    )
    run.add_argument(
        "--container",
        action="store_true",
        help="record that the wrapped command executes inside a container",
    )
    run.add_argument(
        "--root-is-launcher",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    run.add_argument(
        "--include-support-tools",
        action="store_true",
        help="include routine shell and text utilities in dependency output",
    )
    run.add_argument(
        "--no-process-tree",
        action="store_true",
        help="observe only the wrapped command, preserving setuid/setgid helper behavior",
    )
    run.add_argument(
        "--json",
        action="store_true",
        help="print the JSON receipt instead of the human report",
    )
    run.add_argument(
        "wrapped_command",
        nargs=argparse.REMAINDER,
        help="command to run; use '--' before the command",
    )

    show = subcommands.add_parser("show", help="render an existing JSON receipt")
    show.add_argument("receipt", help="path to a RunnerLens receipt JSON file")
    show.add_argument("--json", action="store_true", help="print normalized JSON")

    compare = subcommands.add_parser("compare", help="compare dependencies from two receipts")
    compare.add_argument("baseline", help="path to the known-good receipt")
    compare.add_argument("target", help="path to the receipt being evaluated")
    compare.add_argument("--json", action="store_true", help="print JSON impact data")

    impact = subcommands.add_parser("impact", help="correlate a receipt with a GitHub Ubuntu image release")
    impact.add_argument("receipt", help="path to the observed receipt")
    impact.add_argument("--baseline-image", help="baseline Ubuntu image, defaults to the receipt image")
    impact.add_argument("--baseline-image-version", help="baseline GitHub runner image version")
    impact.add_argument("--target-image", help="target Ubuntu image, defaults to the receipt image")
    impact.add_argument("--target-image-version", help="target GitHub runner image version; defaults to the receipt")
    impact.add_argument("--json", action="store_true", help="print JSON impact data")

    check = subcommands.add_parser("check", help="fail when a receipt adds ambient runner dependencies")
    check.add_argument("baseline", help="path to the accepted baseline receipt")
    check.add_argument("target", help="path to the receipt being evaluated")
    check.add_argument("--json", action="store_true", help="print JSON comparison data")

    return parser


def run_command(args: argparse.Namespace) -> int:
    wrapped_command = _clean_wrapped_command(args.wrapped_command)
    if not wrapped_command:
        print("runnerlens run requires a command, for example: runnerlens run -- make", file=sys.stderr)
        return 2

    observation = observe_command(
        wrapped_command,
        cwd=Path.cwd(),
        root_is_launcher=args.root_is_launcher,
        trace_process_tree=not args.no_process_tree,
    )
    receipt_env = dict(os.environ)
    if args.workflow_provisioned_path:
        receipt_env["RUNNERLENS_WORKFLOW_PROVISIONED_PATHS"] = os.pathsep.join(args.workflow_provisioned_path)
    if args.container:
        receipt_env["RUNNERLENS_CONTAINERIZED"] = "true"
    receipt = build_receipt(
        observation,
        repository_root=Path.cwd(),
        env=receipt_env,
        include_support_tools=args.include_support_tools,
    )
    write_receipt(receipt, Path(args.output))

    if args.json:
        print(to_json(receipt.to_dict()), end="")
    else:
        print(render_report(receipt), end="")
        print(f"Receipt written to {args.output}", file=sys.stderr)

    return receipt.exit_code


def show_command(args: argparse.Namespace) -> int:
    receipt_path = Path(args.receipt)
    try:
        data = load_receipt(receipt_path)
    except (OSError, ValueError) as error:
        print(f"could not read receipt {receipt_path}: {error}", file=sys.stderr)
        return 2
    try:
        receipt = receipt_from_dict(data)
    except (ValueError, KeyError, TypeError) as error:
        print(f"could not render receipt {receipt_path}: {error}", file=sys.stderr)
        return 2

    if args.json:
        print(to_json(receipt.to_dict()), end="")
        return 0

    print(render_report(receipt), end="")
    return 0


def compare_command(args: argparse.Namespace) -> int:
    try:
        baseline = receipt_from_dict(load_receipt(Path(args.baseline)))
        target = receipt_from_dict(load_receipt(Path(args.target)))
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"could not compare receipts: {error}", file=sys.stderr)
        return 2

    impact = compare_receipts(baseline, target)
    if args.json:
        print(to_json(impact.to_dict()), end="")
    else:
        print(render_impact_report(impact), end="")
    return 0


def image_impact_command(args: argparse.Namespace) -> int:
    try:
        receipt = receipt_from_dict(load_receipt(Path(args.receipt)))
        if receipt.runner.provider != "github-actions":
            raise ValueError("receipt was not produced on GitHub Actions")
        image = args.target_image or receipt.runner.image
        if not image:
            raise ValueError("target image is required when the receipt has no runner image")
        target_image_version = args.target_image_version or receipt.runner.image_version
        if not target_image_version:
            raise ValueError(
                "target image version is required when the receipt has no runner image version"
            )
        target_manifest = fetch_ubuntu_manifest(image, target_image_version)
        baseline_manifest = None
        if args.baseline_image_version:
            baseline_manifest = fetch_ubuntu_manifest(args.baseline_image or image, args.baseline_image_version)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"could not correlate receipt with runner image: {error}", file=sys.stderr)
        return 2

    if baseline_manifest:
        impact = compare_runner_images(receipt, baseline_manifest, target_manifest)
    else:
        impact = correlate_receipt_with_image(receipt, target_manifest)
    if args.json:
        print(to_json(impact.to_dict()), end="")
    else:
        if baseline_manifest:
            print(render_runner_image_impact_report(impact), end="")
        else:
            print(render_image_impact_report(impact), end="")
    return 0


def check_command(args: argparse.Namespace) -> int:
    try:
        baseline = receipt_from_dict(load_receipt(Path(args.baseline)))
        target = receipt_from_dict(load_receipt(Path(args.target)))
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"could not check receipt baseline: {error}", file=sys.stderr)
        return 2

    impact = compare_receipts(baseline, target)
    if args.json:
        print(to_json(impact.to_dict()), end="")
    else:
        print(render_baseline_report(impact), end="")
    if impact.baseline_coverage != "process-tree" or impact.target_coverage != "process-tree":
        return 2
    return 1 if newly_observed_ambient_dependencies(impact) else 0


def _clean_wrapped_command(argv: list[str]) -> list[str]:
    if argv and argv[0] == "--":
        return argv[1:]
    return argv


if __name__ == "__main__":
    raise SystemExit(main())
