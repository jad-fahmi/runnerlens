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

The `runner-image-metadata` CI job compares the public GitHub Ubuntu 24 image
releases `20260831.293` and `20260907.300` using a recorded Cargo receipt. The
expected result is Cargo `1.98.0` changing to `1.98.1`.

The same job reads the retained Ubuntu 22 release `20220515.1`, whose inventory
uses the legacy `images/linux/Ubuntu2204-Readme.md` location. This keeps
historical inventory lookup covered without inferring a missing release tag.

## Next Cases

Add public repositories from different build ecosystems and historical
runner-image incidents only when their build command and runner revision can be
recorded reproducibly. Each new case should document the observed dependency,
the relevant runner-image delta, and whether the receipt would have reduced the
diagnostic search space.
