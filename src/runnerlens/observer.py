"""Runtime observation backends.

On Linux, RunnerLens uses ``strace`` to record successful ``execve`` calls for
the process tree launched by the wrapped command. It falls back to recording
only the root command when ``strace`` is unavailable, so a receipt remains
useful on unsupported development machines.
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from runnerlens.models import ExecutionEvent, ObservedCommand, utc_now


@dataclass(frozen=True)
class Observation:
    command: ObservedCommand
    events: list[ExecutionEvent]
    started_at: str
    ended_at: str
    exit_code: int


_EXECVE_RE = re.compile(
    r"^(?:\[pid\s+(?P<pid>\d+)\]\s+)?execve\(\"(?P<path>(?:[^\"\\]|\\.)*)\".*\)\s+=\s+0$"
)


def observe_command(argv: list[str], cwd: Path | None = None) -> Observation:
    if not argv:
        raise ValueError("no command provided")

    started_at = utc_now()
    executable = argv[0]
    resolved_path = shutil.which(executable, path=os.environ.get("PATH"))
    if platform.system() == "Linux" and shutil.which("strace"):
        events, exit_code = _observe_with_strace(argv, cwd)
    else:
        events, exit_code = _observe_root_command(argv, cwd, resolved_path)

    ended_at = utc_now()

    return Observation(
        command=ObservedCommand(
            executable=executable,
            resolved_path=resolved_path,
            arguments_recorded=False,
        ),
        events=events,
        started_at=started_at,
        ended_at=ended_at,
        exit_code=exit_code,
    )


def _observe_root_command(
    argv: list[str], cwd: Path | None, resolved_path: str | None
) -> tuple[list[ExecutionEvent], int]:
    event = ExecutionEvent(
        executable=Path(argv[0]).name,
        path=resolved_path,
        observation="subprocess-root",
    )
    completed = subprocess.run(argv, cwd=cwd, check=False)
    return [event], completed.returncode


def _observe_with_strace(argv: list[str], cwd: Path | None) -> tuple[list[ExecutionEvent], int]:
    """Run a command under strace and normalize its successful exec events."""
    with tempfile.NamedTemporaryFile(prefix="runnerlens-strace-", delete=False) as trace_file:
        trace_path = Path(trace_file.name)

    try:
        completed = subprocess.run(
            ["strace", "-f", "-qq", "-e", "trace=execve", "-s", "0", "-o", str(trace_path), "--", *argv],
            cwd=cwd,
            check=False,
        )
        events = parse_strace_execve(trace_path.read_text(encoding="utf-8", errors="replace"))
    finally:
        trace_path.unlink(missing_ok=True)

    return events, completed.returncode


def parse_strace_execve(trace: str) -> list[ExecutionEvent]:
    """Convert successful ``strace -f -e execve`` output into execution events."""
    events: list[ExecutionEvent] = []
    for line in trace.splitlines():
        match = _EXECVE_RE.match(line)
        if not match:
            continue
        path = bytes(match.group("path"), "utf-8").decode("unicode_escape")
        events.append(
            ExecutionEvent(
                executable=Path(path).name,
                path=path,
                pid=int(match.group("pid")) if match.group("pid") else None,
                observation="strace-execve",
            )
        )
    return events
