"""GitHub Actions Ubuntu runner-image release metadata."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.error import URLError
from urllib.request import Request, urlopen


_VERSION_RE = re.compile(r"(?<![\w.])v?(\d+(?:\.\d+)+(?:[-+][0-9A-Za-z.-]+)?)")
_IMAGE_RE = re.compile(r"^ubuntu-?(?P<major>\d{2})(?:\.04)?$")
_COMPILER_EXECUTABLE_RE = re.compile(
    r"^(?P<name>cc|c\+\+|gcc|g\+\+|clang|clang\+\+)(?:-\d+(?:\.\d+)*)?$"
)


@dataclass(frozen=True)
class GitHubImageManifest:
    image: str
    release: str
    source_url: str
    tools: dict[str, tuple[str, ...]]
    cached_tools: dict[str, tuple[str, ...]] = field(default_factory=dict)


def normalize_ubuntu_image(image: str) -> str:
    """Normalize GitHub's ImageOS and workflow labels to a release tag prefix."""
    match = _IMAGE_RE.match(image.lower())
    if not match:
        raise ValueError(f"unsupported GitHub Actions image: {image}")
    return f"ubuntu{match.group('major')}"


def release_tag(image: str, image_version: str) -> str:
    """Build a runner-images release tag from GitHub's image metadata."""
    version_parts = image_version.split(".")
    if len(version_parts) == 3 and version_parts[-1].isdigit():
        image_version = ".".join(version_parts[:-1])
    return f"{normalize_ubuntu_image(image)}/{image_version}"


def fetch_ubuntu_manifest(image: str, image_version: str, timeout: float = 10) -> GitHubImageManifest:
    """Download and parse the public software inventory for an Ubuntu release."""
    normalized_image = normalize_ubuntu_image(image)
    tag = release_tag(image, image_version)
    errors: list[OSError] = []
    for source_url in _manifest_source_urls(tag, normalized_image):
        request = Request(source_url, headers={"User-Agent": "RunnerLens/0.1"})
        try:
            with urlopen(request, timeout=timeout) as response:
                content = response.read().decode("utf-8")
        except (OSError, URLError) as error:
            errors.append(error)
            continue
        break
    else:
        detail = errors[-1] if errors else "no manifest source candidates"
        raise ValueError(f"could not fetch GitHub runner-image metadata: {detail}") from errors[-1]

    return GitHubImageManifest(
        image=normalized_image,
        release=tag,
        source_url=source_url,
        tools=parse_ubuntu_software_report(content),
        cached_tools=parse_ubuntu_cached_tools(content),
    )


def _manifest_source_urls(tag: str, normalized_image: str) -> tuple[str, ...]:
    major = normalized_image.removeprefix("ubuntu")
    readme_base = f"Ubuntu{major}04"
    base_url = f"https://raw.githubusercontent.com/actions/runner-images/{tag}/"
    return (
        f"{base_url}images/ubuntu/{readme_base}-Readme.md",
        f"{base_url}images/linux/{readme_base}-Readme.md",
        f"{base_url}images/linux/{readme_base}-README.md",
    )


def parse_ubuntu_software_report(markdown: str) -> dict[str, tuple[str, ...]]:
    """Parse versioned software bullets from an Ubuntu runner release document."""
    tools: dict[str, tuple[str, ...]] = {}
    for line in markdown.splitlines():
        stripped_line = line.lstrip()
        if not (stripped_line.startswith("*") or stripped_line.startswith("- ")):
            continue
        text = stripped_line.lstrip("*-").strip().replace("**", "")
        version_match = _VERSION_RE.search(text)
        if not version_match:
            continue
        name = text[: version_match.start()].rstrip(": ")
        if not name:
            continue
        versions = tuple(match.group(1) for match in _VERSION_RE.finditer(text))
        key = _normalize_tool_name(name)
        if key:
            tools[key] = versions
    return tools


def manifest_versions(
    manifest: GitHubImageManifest, executable: str, path: str | None = None
) -> tuple[str, ...] | None:
    """Find documented versions for an observed executable, including core aliases."""
    normalized = _normalize_tool_name(executable)
    aliases = {
        "cmake": ("cmake",),
        "ninja": ("ninja",),
        "clang": ("clang",),
        "clang++": ("clang",),
        "gcc": ("gnuc", "gcc"),
        "g": ("gnuc", "gcc"),
        "python": ("python",),
        "python3": ("python",),
        "node": ("nodejs", "node"),
        "nodejs": ("nodejs", "node"),
        "java": ("java",),
        "ruby": ("ruby",),
        "go": ("go",),
    }
    for candidate in _manifest_candidates(executable, normalized, aliases):
        if _is_hosted_tool_cache_path(path) and candidate in manifest.cached_tools:
            return manifest.cached_tools[candidate]
        if candidate in manifest.tools:
            return manifest.tools[candidate]
    return None


def parse_ubuntu_cached_tools(markdown: str) -> dict[str, tuple[str, ...]]:
    """Parse version-only entries nested below a GitHub Ubuntu Cached Tools heading."""
    tools: dict[str, tuple[str, ...]] = {}
    cached_tools_heading_level: int | None = None
    current_tool: str | None = None

    for line in markdown.splitlines():
        heading = re.match(r"^(?P<marks>#{1,6})\s+(?P<text>.+?)\s*$", line)
        if heading:
            level = len(heading.group("marks"))
            text = heading.group("text").replace("**", "")
            if _normalize_tool_name(text) == "cachedtools":
                cached_tools_heading_level = level
                current_tool = None
            elif cached_tools_heading_level is not None and level <= cached_tools_heading_level:
                cached_tools_heading_level = None
                current_tool = None
            elif cached_tools_heading_level is not None:
                current_tool = _normalize_tool_name(text)
            continue

        if cached_tools_heading_level is None or current_tool is None:
            continue
        stripped_line = line.lstrip()
        if not (stripped_line.startswith("*") or stripped_line.startswith("- ")):
            continue
        text = stripped_line.lstrip("*-").strip().replace("**", "")
        if not _VERSION_RE.match(text):
            continue
        versions = tuple(match.group(1) for match in _VERSION_RE.finditer(text))
        if versions:
            tools[current_tool] = (*tools.get(current_tool, ()), *versions)

    return tools


def _manifest_candidates(
    executable: str, normalized: str, aliases: dict[str, tuple[str, ...]]
) -> tuple[str, ...]:
    compiler_match = _COMPILER_EXECUTABLE_RE.match(executable.lower())
    if compiler_match:
        compiler = compiler_match.group("name")
        if compiler.startswith("clang"):
            return ("clang",)
        return ("gnuc", "gcc")
    return aliases.get(normalized, (normalized,))


def _normalize_tool_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def _is_hosted_tool_cache_path(path: str | None) -> bool:
    return bool(path and "/hostedtoolcache/" in path.lower())
