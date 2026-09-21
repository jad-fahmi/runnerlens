import pytest

from runnerlens.github import (
    GitHubImageManifest,
    manifest_versions,
    parse_ubuntu_software_report,
    release_tag,
)


def test_release_tag_removes_the_runner_image_revision_suffix() -> None:
    assert release_tag("ubuntu-24.04", "20260907.131.1") == "ubuntu24/20260907.131"
    assert release_tag("ubuntu24", "20260907.131") == "ubuntu24/20260907.131"


def test_release_tag_rejects_non_ubuntu_image() -> None:
    with pytest.raises(ValueError, match="unsupported"):
        release_tag("windows-2025", "20260907.1")


def test_parse_ubuntu_report_and_lookup_executable_aliases() -> None:
    manifest = GitHubImageManifest(
        image="ubuntu24",
        release="ubuntu24/20260907.131",
        source_url="https://example.test/report",
        tools=parse_ubuntu_software_report(
            """## Installed Software
- CMake 3.30.5
- Clang: 18.1.8, 19.1.7
- GNU C++: 13.3.0, 14.2.0
- Node.js 22.14.0
"""
        ),
    )

    assert manifest_versions(manifest, "cmake") == ("3.30.5",)
    assert manifest_versions(manifest, "clang++") == ("18.1.8", "19.1.7")
    assert manifest_versions(manifest, "g++") == ("13.3.0", "14.2.0")
    assert manifest_versions(manifest, "node") == ("22.14.0",)
