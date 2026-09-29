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
from dataclasses import replace
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
    r"^(?:(?:\[pid\s+)?(?P<pid>\d+)\]?\s+)?execve\(\"(?P<path>(?:[^\"\\]|\\.)*)\".*\)\s+=\s+0$"
)
_EXECVEAT_RE = re.compile(
    r"^(?:(?:\[pid\s+)?(?P<pid>\d+)\]?\s+)?"
    r"execveat\([^,]+,\s*\"(?P<path>(?:[^\"\\]|\\.)*)\".*\)\s+=\s+0$"
)
_PROCESS_CREATE_RE = re.compile(
    r"^(?:(?:\[pid\s+)?(?P<parent_pid>\d+)\]?\s+)?"
    r"(?:clone|clone3|fork|vfork)\(.*\)\s+=\s+(?P<child_pid>\d+)$"
)
_ROOT_GETPID_RE = re.compile(r"^getpid\(\)\s+=\s+(?P<pid>\d+)$")


def observe_command(
    argv: list[str],
    cwd: Path | None = None,
    root_is_launcher: bool = False,
    trace_process_tree: bool = True,
) -> Observation:
    if not argv:
        raise ValueError("no command provided")

    started_at = utc_now()
    executable = argv[0]
    resolved_path = shutil.which(executable, path=os.environ.get("PATH"))
    if not trace_process_tree:
        events, exit_code = _observe_root_command(argv, cwd, resolved_path)
        events = [replace(event, observation="subprocess-root-only") for event in events]
    elif platform.system() == "Linux" and shutil.which("strace"):
        events, exit_code = _observe_with_strace(argv, cwd)
        if not events:
            events = [_root_event(argv[0], resolved_path, "subprocess-root-fallback")]
    else:
        events, exit_code = _observe_root_command(argv, cwd, resolved_path)

    if root_is_launcher and events:
        events[0] = replace(events[0], role="launcher")

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
    completed = subprocess.run(argv, cwd=cwd, check=False)
    return [_root_event(argv[0], resolved_path, "subprocess-root")], completed.returncode


def _root_event(executable: str, resolved_path: str | None, observation: str) -> ExecutionEvent:
    return ExecutionEvent(
        executable=Path(executable).name,
        path=resolved_path,
        observation=observation,
    )


def _observe_with_strace(argv: list[str], cwd: Path | None) -> tuple[list[ExecutionEvent], int]:
    """Run a command under strace and normalize its successful exec events."""
    with tempfile.NamedTemporaryFile(prefix="runnerlens-strace-", delete=False) as trace_file:
        trace_path = Path(trace_file.name)

    try:
        completed = subprocess.run(
            [
                "strace",
                "-f",
                "-qq",
                "-e",
                "trace=execve,execveat,clone,clone3,fork,vfork,getpid",
                "-s",
                "0",
                "-o",
                str(trace_path),
                "--",
                *argv,
            ],
            cwd=cwd,
            check=False,
        )
        events = parse_strace_execve(trace_path.read_text(encoding="utf-8", errors="replace"))
    finally:
        trace_path.unlink(missing_ok=True)

    return events, completed.returncode


def parse_strace_execve(trace: str) -> list[ExecutionEvent]:
    """Convert strace execution and process-creation output into events.

    A parent PID is recorded only when strace reports a successful process
    creation syscall before that child executes. Root and incomplete lineage
    remain unset instead of being inferred.
    """
    events: list[ExecutionEvent] = []
    parents: dict[int, int] = {}
    root_pid: int | None = None
    for line in trace.splitlines():
        root_pid_match = _ROOT_GETPID_RE.match(line)
        if root_pid_match:
            root_pid = int(root_pid_match.group("pid"))
            continue

        creation_match = _PROCESS_CREATE_RE.match(line)
        if creation_match:
            parent_pid = creation_match.group("parent_pid")
            parent = int(parent_pid) if parent_pid is not None else root_pid
            if parent is not None:
                parents[int(creation_match.group("child_pid"))] = parent
            continue

        match = _EXECVE_RE.match(line)
        observation = "strace-execve"
        if not match:
            match = _EXECVEAT_RE.match(line)
            observation = "strace-execveat"
        if not match:
            continue
        path = bytes(match.group("path"), "utf-8").decode("unicode_escape")
        pid = int(match.group("pid")) if match.group("pid") else None
        if observation == "strace-execveat" and not path.startswith("/"):
            executable = Path(path).name if path else "unknown-executable"
            path = None
            observation = "strace-execveat-unresolved"
        else:
            executable = Path(path).name
        events.append(
            ExecutionEvent(
                executable=executable,
                path=path,
                pid=pid,
                parent_pid=parents.get(pid) if pid is not None else None,
                observation=observation,
            )
        )
    return events
