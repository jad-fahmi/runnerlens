import pytest

from runnerlens.github import (
    GitHubImageManifest,
    fetch_ubuntu_manifest,
    manifest_versions,
    parse_ubuntu_software_report,
    release_tag,
)


class _Response:
    def __init__(self, content: str) -> None:
        self._content = content

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        return None

    def read(self) -> bytes:
        return self._content.encode("utf-8")


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


def test_fetch_ubuntu_manifest_uses_legacy_linux_path_when_needed(monkeypatch) -> None:
    requested_urls: list[str] = []

    def fake_urlopen(request, timeout):
        requested_urls.append(request.full_url)
        if request.full_url.endswith("images/ubuntu/Ubuntu2204-Readme.md"):
            raise OSError("not found")
        return _Response("- CMake 3.22.1\n")

    monkeypatch.setattr("runnerlens.github.urlopen", fake_urlopen)

    manifest = fetch_ubuntu_manifest("ubuntu-22.04", "20220515.1")

    assert requested_urls == [
        "https://raw.githubusercontent.com/actions/runner-images/ubuntu22/20220515.1/images/ubuntu/Ubuntu2204-Readme.md",
        "https://raw.githubusercontent.com/actions/runner-images/ubuntu22/20220515.1/images/linux/Ubuntu2204-Readme.md",
    ]
    assert manifest.source_url == requested_urls[-1]
    assert manifest.tools == {"cmake": ("3.22.1",)}
