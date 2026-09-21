"""Project-specific comparison of two Runner Dependency Receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from runnerlens.models import Dependency, Receipt, RunnerInfo


@dataclass(frozen=True)
class DependencyImpact:
    name: str
    status: str
    baseline: Dependency | None
    target: Dependency | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "baseline": self.baseline.to_dict() if self.baseline else None,
            "target": self.target.to_dict() if self.target else None,
        }


@dataclass(frozen=True)
class ReceiptImpact:
    baseline_runner: RunnerInfo
    target_runner: RunnerInfo
    dependencies: list[DependencyImpact]

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline_runner": self.baseline_runner.to_dict(),
            "target_runner": self.target_runner.to_dict(),
            "dependencies": [dependency.to_dict() for dependency in self.dependencies],
        }


def compare_receipts(baseline: Receipt, target: Receipt) -> ReceiptImpact:
    """Compare observed tools by name, preserving both sides as evidence."""
    baseline_dependencies = _by_name(baseline.dependencies)
    target_dependencies = _by_name(target.dependencies)
    impacts: list[DependencyImpact] = []

    for name in sorted(baseline_dependencies.keys() | target_dependencies.keys()):
        before = baseline_dependencies.get(name)
        after = target_dependencies.get(name)
        if before is None:
            status = "added"
        elif after is None:
            status = "removed"
        elif _fingerprint(before) == _fingerprint(after):
            status = "unchanged"
        else:
            status = "changed"
        impacts.append(DependencyImpact(name=name, status=status, baseline=before, target=after))

    return ReceiptImpact(
        baseline_runner=baseline.runner,
        target_runner=target.runner,
        dependencies=impacts,
    )


def _by_name(dependencies: list[Dependency]) -> dict[str, Dependency]:
    """Keep ambiguity visible by selecting no arbitrary dependency."""
    grouped: dict[str, list[Dependency]] = {}
    for dependency in dependencies:
        grouped.setdefault(dependency.name, []).append(dependency)
    return {name: items[0] for name, items in grouped.items() if len(items) == 1}


def _fingerprint(dependency: Dependency) -> tuple[str | None, str | None, str | None, str, str]:
    return (
        dependency.path,
        dependency.version,
        dependency.package,
        dependency.origin,
        dependency.confidence,
    )
