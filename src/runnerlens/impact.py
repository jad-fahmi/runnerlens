"""Project-specific comparison of two Runner Dependency Receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from runnerlens.github import GitHubImageManifest, manifest_versions
from runnerlens.models import Dependency, Receipt, RunnerInfo


AMBIENT_ORIGINS = frozenset({"runner-provided", "tool-cache"})


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


@dataclass(frozen=True)
class ImageDependencyImpact:
    dependency: Dependency
    status: str
    documented_versions: tuple[str, ...] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "dependency": self.dependency.to_dict(),
            "status": self.status,
            "documented_versions": list(self.documented_versions) if self.documented_versions else None,
        }


@dataclass(frozen=True)
class ImageImpact:
    observed_runner: RunnerInfo
    target_release: str
    source_url: str
    dependencies: list[ImageDependencyImpact]

    def to_dict(self) -> dict[str, Any]:
        return {
            "observed_runner": self.observed_runner.to_dict(),
            "target_release": self.target_release,
            "source_url": self.source_url,
            "dependencies": [dependency.to_dict() for dependency in self.dependencies],
        }


@dataclass(frozen=True)
class RunnerImageDependencyImpact:
    dependency: Dependency
    status: str
    baseline_versions: tuple[str, ...] | None
    target_versions: tuple[str, ...] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "dependency": self.dependency.to_dict(),
            "status": self.status,
            "baseline_versions": list(self.baseline_versions) if self.baseline_versions else None,
            "target_versions": list(self.target_versions) if self.target_versions else None,
        }


@dataclass(frozen=True)
class RunnerImageImpact:
    observed_runner: RunnerInfo
    baseline_release: str
    baseline_source_url: str
    target_release: str
    target_source_url: str
    dependencies: list[RunnerImageDependencyImpact]

    def to_dict(self) -> dict[str, Any]:
        return {
            "observed_runner": self.observed_runner.to_dict(),
            "baseline_release": self.baseline_release,
            "baseline_source_url": self.baseline_source_url,
            "target_release": self.target_release,
            "target_source_url": self.target_source_url,
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


def newly_observed_ambient_dependencies(impact: ReceiptImpact) -> list[DependencyImpact]:
    """Return added dependencies with evidence of runner-environment origin."""
    return [
        dependency
        for dependency in impact.dependencies
        if dependency.status == "added"
        and dependency.target is not None
        and dependency.target.origin in AMBIENT_ORIGINS
    ]


def correlate_receipt_with_image(receipt: Receipt, manifest: GitHubImageManifest) -> ImageImpact:
    """Match observed tools to documented versions in one target image release."""
    dependencies: list[ImageDependencyImpact] = []
    for dependency in _ambient_dependencies(receipt):
        documented_versions = manifest_versions(manifest, dependency.name, dependency.path)
        if documented_versions is None:
            status = "metadata-unavailable"
        elif dependency.version is None:
            status = "tool-present"
        elif _version_is_present(dependency.version, documented_versions):
            status = "version-present"
        else:
            status = "version-changed"
        dependencies.append(
            ImageDependencyImpact(
                dependency=dependency,
                status=status,
                documented_versions=documented_versions,
            )
        )
    return ImageImpact(
        observed_runner=receipt.runner,
        target_release=manifest.release,
        source_url=manifest.source_url,
        dependencies=dependencies,
    )


def compare_runner_images(
    receipt: Receipt, baseline: GitHubImageManifest, target: GitHubImageManifest
) -> RunnerImageImpact:
    """Filter documented runner-image changes to tools observed in a receipt."""
    dependencies: list[RunnerImageDependencyImpact] = []
    for dependency in _ambient_dependencies(receipt):
        baseline_versions = manifest_versions(baseline, dependency.name, dependency.path)
        target_versions = manifest_versions(target, dependency.name, dependency.path)
        if baseline_versions is None and target_versions is None:
            status = "metadata-unavailable"
        elif baseline_versions is None:
            status = "added"
        elif target_versions is None:
            status = "removed"
        elif baseline_versions == target_versions:
            status = "unchanged"
        else:
            status = "changed"
        dependencies.append(
            RunnerImageDependencyImpact(
                dependency=dependency,
                status=status,
                baseline_versions=baseline_versions,
                target_versions=target_versions,
            )
        )
    return RunnerImageImpact(
        observed_runner=receipt.runner,
        baseline_release=baseline.release,
        baseline_source_url=baseline.source_url,
        target_release=target.release,
        target_source_url=target.source_url,
        dependencies=dependencies,
    )


def _by_name(dependencies: list[Dependency]) -> dict[str, Dependency]:
    """Keep ambiguity visible by selecting no arbitrary dependency."""
    grouped: dict[str, list[Dependency]] = {}
    for dependency in dependencies:
        grouped.setdefault(dependency.name, []).append(dependency)
    return {name: items[0] for name, items in grouped.items() if len(items) == 1}


def _ambient_dependencies(receipt: Receipt) -> list[Dependency]:
    return [dependency for dependency in receipt.dependencies if dependency.origin in AMBIENT_ORIGINS]


def _fingerprint(dependency: Dependency) -> tuple[str | None, str | None, str | None, str, str]:
    return (
        dependency.path,
        dependency.version,
        dependency.package,
        dependency.origin,
        dependency.confidence,
    )


def _version_is_present(observed: str, documented_versions: tuple[str, ...]) -> bool:
    return any(
        observed == documented
        or observed.startswith(documented + ".")
        or documented.startswith(observed + ".")
        for documented in documented_versions
    )
