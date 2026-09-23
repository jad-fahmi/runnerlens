# Validation Corpus

RunnerLens must demonstrate value on real builds, not only synthetic process
fixtures. This document records reproducible validation cases and the evidence
each one is expected to provide.

## Public Repository Cases

| Repository | Immutable revision | Command | Expected inherited tools |
| --- | --- | --- | --- |
| [fmtlib/fmt](https://github.com/fmtlib/fmt) | `40626af88bd7df9a5fb80be7b25ac85b122d6c21` (`11.2.0`) | CMake configure and Ninja build | `cmake`, `ninja`, C++ compiler |
| [BurntSushi/ripgrep](https://github.com/BurntSushi/ripgrep) | `0e8390a66fbcf6eeac1aeb0541b367663a597c79` (`14.1.1`) | `cargo build --locked` | `cargo` |
| [google/uuid](https://github.com/google/uuid) | `0f11ee6918f41a04c201eceeadf612a377bc7fbc` (`v1.6.0`) | `go test ./...` | `go` |

The public-repository CI jobs run these cases on GitHub-hosted Ubuntu. They
keep each checked-out revision and build command explicit so receipts are
repeatable and results can be compared as RunnerLens evolves.

The `public-rust-validation` CI job exercises a second ecosystem using the
preinstalled Cargo path on the GitHub-hosted image. It verifies that the
receipt preserves the observed Cargo version and classifies the documented
base-image path as `runner-provided` with probable confidence.

The `public-go-validation` CI job validates the GitHub-hosted Go tool cache on
a pinned public module. It verifies that the observed `go` executable has a
recorded version and is classified as `tool-cache`. It then correlates the
receipt with the pinned Ubuntu 24 image release `20260920.314.1`, verifying
that Go is present in the release's Cached Tools inventory even though the
observed executable path is `/usr/bin/go`.

## Runner-Image Cases

The `runner-image-metadata` CI job also captures a live receipt from
`podman --version` on its own GitHub-hosted Ubuntu runner. It correlates that
receipt with the exact image version reported to the workflow and uploads the
JSON receipt as an artifact. This checks actual process observation, version
resolution, runner provenance, and image metadata together, separately from
the labeled historical reconstruction below. A second live command runs a
digest-pinned Alpine image with Podman in root-only mode. Process tracing
prevents the setuid `newuidmap` helper from receiving effective privileges, so
this case verifies the documented lower-coverage escape hatch preserves the
container command instead of claiming child-process evidence.

The `runner-image-metadata` CI job compares the public GitHub Ubuntu 24 image
releases `20260831.293` and `20260907.300` using a recorded Cargo receipt. The
expected result is Cargo `1.98.0` changing to `1.98.1`.

The same job reads the retained Ubuntu 22 release `20220515.1`, whose inventory
uses the legacy `images/linux/Ubuntu2204-Readme.md` location. This keeps
historical inventory lookup covered without inferring a missing release tag.

The job also replays the Podman change in the public [runner-images issue
#14604](https://github.com/actions/runner-images/issues/14604). That report
compares the same Uyuni container-test step from immutable revision
`318fb5dd4a7062089d4f02bbe2a3887b0624b898` across GitHub-hosted Ubuntu 24
images: `20260720.247.2` completed in about 96 to 107 seconds, while
`20260810.271.1` took about 21,500 seconds and timed out. The issue attributes
the regression to the Podman 4.9.3 to 5.8.4 bundle change, and links the
[Uyuni workflow run](https://github.com/uyuni-project/uyuni/actions/runs/31541429355)
that landed jobs on both image revisions. The job corresponds to Uyuni's
`Acceptance / tests` container workflow; it is not a small, single-command
reproducer that RunnerLens can currently rerun in this project's public CI.

`ubuntu24-podman-issue-14604.json` is a historical reconstruction from the
issue's reported Podman version and path, not a RunnerLens-captured receipt.
The replay verifies that image impact narrows the published inventory delta to
the observed Podman dependency. It does not claim to reproduce or diagnose the
hang, and the incident's detailed `crun` interaction is not fully represented
in the published image inventory.

## Next Cases

Add public repositories from different build ecosystems and historical
runner-image incidents only when their build command and runner revision can be
recorded reproducibly. Each new case should document the observed dependency,
the relevant runner-image delta, and whether the receipt would have reduced the
diagnostic search space.
