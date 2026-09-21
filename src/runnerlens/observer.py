"""Runtime observation backends.

The first backend intentionally records only the wrapped command. Linux process
tree tracing will replace this narrow observer behind the same event model.
"""

from __future__ import annotations

import os
import shutil
import subprocess
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


def observe_command(argv: list[str], cwd: Path | None = None) -> Observation:
    if not argv:
        raise ValueError("no command provided")

    started_at = utc_now()
    executable = argv[0]
    resolved_path = shutil.which(executable, path=os.environ.get("PATH"))
    event = ExecutionEvent(
        executable=Path(executable).name,
        path=resolved_path,
        observation="subprocess-root",
    )

    completed = subprocess.run(argv, cwd=cwd, check=False)
    ended_at = utc_now()

    return Observation(
        command=ObservedCommand(
            executable=executable,
            resolved_path=resolved_path,
            arguments_recorded=False,
        ),
        events=[event],
        started_at=started_at,
        ended_at=ended_at,
        exit_code=completed.returncode,
    )
