"""Runtime observation backends.

On Linux, RunnerLens uses ``strace`` to record successful ``execve`` calls for
the process tree launched by the wrapped command. It falls back to recording
only the root command when ``strace`` is unavailable, so a receipt remains
useful on unsupported development machines.
"""

from __future__ import annotations

import contextlib
import os
import platform
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from dataclasses import replace
from pathlib import Path
from typing import TextIO

from runnerlens.models import ExecutionEvent, ObservedCommand, utc_now


@dataclass(frozen=True)
class Observation:
    command: ObservedCommand
    events: list[ExecutionEvent]
    started_at: str
    ended_at: str
    exit_code: int


class TracingUnavailable(Exception):
    pass


_EXECVE_RE = re.compile(
    r"^(?:(?:\[pid\s+)?(?P<pid>\d+)\]?\s+)?execve\(\"(?P<path>(?:[^\"\\]|\\.)*)\".*\)\s+=\s+0$"
)
_EXECVEAT_RE = re.compile(
    r"^(?:(?:\[pid\s+)?(?P<pid>\d+)\]?\s+)?"
    r"execveat\([^,]+,\s*\"(?P<path>(?:[^\"\\]|\\.)*)\".*\)\s+=\s+0$"
)
_UNFINISHED_EXECVE_RE = re.compile(
    r"^(?:(?:\[pid\s+)?(?P<pid>\d+)\]?\s+)?"
    r"(?P<syscall>execve(?:at)?)\(.* <unfinished \.\.\.>$"
)
_RESUMED_EXECVE_RE = re.compile(
    r"^(?:(?:\[pid\s+)?(?P<pid>\d+)\]?\s+)?"
    r"<\.\.\. (?P<syscall>execve(?:at)?) resumed>.*?=\s+(?P<return>\S+)(?:\s|$)"
)
_EXECVE_PATH_RE = re.compile(r'^execve\("(?P<path>(?:[^"\\]|\\.)*)"')
_EXECVEAT_PATH_RE = re.compile(
    r'^execveat\([^,]+,\s*"(?P<path>(?:[^"\\]|\\.)*)"'
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
    stdout: TextIO | int | None = None,
) -> Observation:
    if not argv:
        raise ValueError("no command provided")

    started_at = utc_now()
    executable = argv[0]
    resolved_path = _resolve_executable(executable, cwd)
    if not trace_process_tree:
        events, exit_code = _observe_root_command(argv, cwd, resolved_path, stdout)
        events = [replace(event, observation="subprocess-root-only") for event in events]
    elif platform.system() == "Linux" and shutil.which("strace"):
        if not _can_trace_process_tree():
            events, exit_code = _observe_root_command(argv, cwd, resolved_path, stdout)
            events = [replace(event, observation="subprocess-root-fallback") for event in events]
        else:
            try:
                events, exit_code = _observe_with_strace(argv, cwd, stdout)
            except TracingUnavailable:
                events, exit_code = _observe_root_command(argv, cwd, resolved_path, stdout)
                events = [replace(event, observation="subprocess-root-fallback") for event in events]
    else:
        events, exit_code = _observe_root_command(argv, cwd, resolved_path, stdout)

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


def _resolve_executable(executable: str, cwd: Path | None) -> str | None:
    working_directory = os.path.abspath(cwd or Path.cwd())
    if os.path.dirname(executable):
        candidate = executable
        if not os.path.isabs(candidate):
            candidate = os.path.join(working_directory, candidate)
        return shutil.which(candidate, path=os.environ.get("PATH"))

    search_path = os.environ.get("PATH")
    if search_path is None:
        search_path = os.defpath
    absolute_search_path = os.pathsep.join(
        entry
        if os.path.isabs(entry)
        else os.path.abspath(os.path.join(working_directory, entry or os.curdir))
        for entry in search_path.split(os.pathsep)
    )
    return shutil.which(executable, path=absolute_search_path)


def _observe_root_command(
    argv: list[str], cwd: Path | None, resolved_path: str | None, stdout: TextIO | int | None
) -> tuple[list[ExecutionEvent], int]:
    completed = subprocess.run(argv, cwd=cwd, stdout=stdout, check=False)
    return [_root_event(argv[0], resolved_path, "subprocess-root")], completed.returncode


def _root_event(executable: str, resolved_path: str | None, observation: str) -> ExecutionEvent:
    return ExecutionEvent(
        executable=Path(executable).name,
        path=resolved_path,
        observation=observation,
    )


def _can_trace_process_tree() -> bool:
    try:
        completed = subprocess.run(
            ["strace", "-f", "-qq", "-e", "trace=execve", "--", "/bin/true"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0


def _observe_with_strace(
    argv: list[str], cwd: Path | None, stdout: TextIO | int | None
) -> tuple[list[ExecutionEvent], int]:
    """Run a command under strace and normalize its successful exec events."""
    with tempfile.NamedTemporaryFile(prefix="runnerlens-strace-", delete=False) as trace_file:
        trace_path = Path(trace_file.name)

    try:
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
                stdout=stdout,
                check=False,
            )
        except OSError as error:
            raise TracingUnavailable from error
        try:
            trace = trace_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            events = []
        else:
            events = parse_strace_execve(trace)
    finally:
        with contextlib.suppress(OSError):
            trace_path.unlink(missing_ok=True)

    return events, completed.returncode


def parse_strace_execve(trace: str) -> list[ExecutionEvent]:
    """Convert strace execution attempts and process-creation output into events.

    A parent PID is recorded only when strace reports a successful process
    creation syscall before that child executes. Root and incomplete lineage
    remain unset instead of being inferred.
    """
    events: list[ExecutionEvent] = []
    parents: dict[int, int] = {}
    unfinished: dict[tuple[int | None, str], str] = {}
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

        unfinished_match = _UNFINISHED_EXECVE_RE.match(line)
        if unfinished_match:
            syscall = unfinished_match.group("syscall")
            path_pattern = _EXECVEAT_PATH_RE if syscall == "execveat" else _EXECVE_PATH_RE
            path_match = path_pattern.match(line[unfinished_match.start("syscall") :])
            if path_match:
                pid = int(unfinished_match.group("pid")) if unfinished_match.group("pid") else None
                unfinished[(pid, syscall)] = path_match.group("path")
            continue

        resumed_match = _RESUMED_EXECVE_RE.match(line)
        if resumed_match:
            syscall = resumed_match.group("syscall")
            pid = int(resumed_match.group("pid")) if resumed_match.group("pid") else None
            path = unfinished.pop((pid, syscall), None)
            if path is None:
                events.append(_incomplete_exec_event(None, pid, parents, syscall))
            elif resumed_match.group("return") == "0":
                events.append(_exec_event(path, pid, parents, syscall))
            continue

        match = _EXECVE_RE.match(line)
        observation = "strace-execve"
        if not match:
            match = _EXECVEAT_RE.match(line)
            observation = "strace-execveat"
        if not match:
            continue
        pid = int(match.group("pid")) if match.group("pid") else None
        syscall = "execveat" if observation == "strace-execveat" else "execve"
        events.append(_exec_event(match.group("path"), pid, parents, syscall))
    for (pid, syscall), path in unfinished.items():
        events.append(_incomplete_exec_event(path, pid, parents, syscall))
    return events


def _exec_event(
    raw_path: str,
    pid: int | None,
    parents: dict[int, int],
    syscall: str,
) -> ExecutionEvent:
    path = _decode_strace_string(raw_path)
    observation = "strace-execveat" if syscall == "execveat" else "strace-execve"
    if not path.startswith("/"):
        executable = Path(path).name if path else "unknown-executable"
        path = None
        observation = f"{observation}-unresolved"
    else:
        executable = Path(path).name
    return ExecutionEvent(
        executable=executable,
        path=path,
        pid=pid,
        parent_pid=parents.get(pid) if pid is not None else None,
        observation=observation,
    )


def _incomplete_exec_event(
    raw_path: str | None,
    pid: int | None,
    parents: dict[int, int],
    syscall: str,
) -> ExecutionEvent:
    decoded_path = _decode_strace_string(raw_path) if raw_path is not None else ""
    path = decoded_path if decoded_path.startswith("/") else None
    executable = Path(decoded_path).name if decoded_path else "unknown-executable"
    observation = "strace-execveat-incomplete" if syscall == "execveat" else "strace-execve-incomplete"
    return ExecutionEvent(
        executable=executable,
        path=path,
        pid=pid,
        parent_pid=parents.get(pid) if pid is not None else None,
        observation=observation,
    )


def _decode_strace_string(value: str) -> str:
    """Decode strace's C-style escapes without corrupting UTF-8 path bytes."""
    decoded = bytearray()
    index = 0
    simple_escapes = {
        "a": 7,
        "b": 8,
        "f": 12,
        "n": 10,
        "r": 13,
        "t": 9,
        "v": 11,
        "\\": 92,
        '"': 34,
    }
    while index < len(value):
        char = value[index]
        if char != "\\":
            decoded.extend(char.encode("utf-8"))
            index += 1
            continue

        index += 1
        if index >= len(value):
            decoded.append(92)
            break

        escaped = value[index]
        if escaped in "01234567":
            end = index + 1
            while end < min(index + 3, len(value)) and value[end] in "01234567":
                end += 1
            decoded.append(int(value[index:end], 8))
            index = end
        elif escaped == "x":
            end = index + 1
            while end < len(value) and end < index + 3 and value[end] in "0123456789abcdefABCDEF":
                end += 1
            if end == index + 1:
                decoded.extend(b"\\x")
                index += 1
            else:
                decoded.append(int(value[index + 1 : end], 16))
                index = end
        elif escaped in simple_escapes:
            decoded.append(simple_escapes[escaped])
            index += 1
        else:
            decoded.extend(b"\\")
            decoded.extend(escaped.encode("utf-8"))
            index += 1

    return os.fsdecode(bytes(decoded))
