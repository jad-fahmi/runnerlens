"""Command line interface for RunnerLens."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from runnerlens import __version__
from runnerlens.observer import observe_command
from runnerlens.receipt import build_receipt, load_receipt, receipt_from_dict, to_json, write_receipt
from runnerlens.report import render_report


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

    return parser


def run_command(args: argparse.Namespace) -> int:
    wrapped_command = _clean_wrapped_command(args.wrapped_command)
    if not wrapped_command:
        print("runnerlens run requires a command, for example: runnerlens run -- make", file=sys.stderr)
        return 2

    observation = observe_command(wrapped_command, cwd=Path.cwd())
    receipt = build_receipt(observation, repository_root=Path.cwd())
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

    if args.json:
        print(to_json(data), end="")
        return 0

    try:
        print(render_report(receipt_from_dict(data)), end="")
    except (KeyError, TypeError) as error:
        print(f"could not render receipt {receipt_path}: {error}", file=sys.stderr)
        return 2

    return 0


def _clean_wrapped_command(argv: list[str]) -> list[str]:
    if argv and argv[0] == "--":
        return argv[1:]
    return argv


if __name__ == "__main__":
    raise SystemExit(main())
