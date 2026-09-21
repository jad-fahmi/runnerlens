"""CI runner metadata detection."""

from __future__ import annotations

import os
import platform
from collections.abc import Mapping

from runnerlens.models import RunnerInfo


def detect_runner(env: Mapping[str, str] | None = None) -> RunnerInfo:
    data = env if env is not None else os.environ

    if data.get("GITHUB_ACTIONS", "").lower() == "true":
        return RunnerInfo(
            provider="github-actions",
            os=data.get("RUNNER_OS"),
            image=data.get("ImageOS") or data.get("RUNNER_IMAGE"),
            image_version=data.get("ImageVersion"),
            architecture=data.get("RUNNER_ARCH"),
            environment=data.get("RUNNER_ENVIRONMENT"),
        )

    return RunnerInfo(
        provider="local",
        os=platform.system() or None,
        image=None,
        image_version=None,
        architecture=platform.machine() or None,
        environment=None,
    )
