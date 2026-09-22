# Validation Corpus

RunnerLens must demonstrate value on real builds, not only synthetic process
fixtures. This document records reproducible validation cases and the evidence
each one is expected to provide.

## Public Repository Cases

| Repository | Immutable revision | Command | Expected inherited tools |
| --- | --- | --- | --- |
| [fmtlib/fmt](https://github.com/fmtlib/fmt) | `40626af88bd7df9a5fb80be7b25ac85b122d6c21` (`11.2.0`) | CMake configure and Ninja build | `cmake`, `ninja`, C++ compiler |

The `public-repository-validation` CI job runs this case on GitHub-hosted
Ubuntu. It keeps the checked-out revision and build command explicit so the
receipt is repeatable and the result can be compared as RunnerLens evolves.

## Runner-Image Cases

The `runner-image-metadata` CI job compares the public GitHub Ubuntu 24 image
releases `20260831.293` and `20260907.300` using a recorded Cargo receipt. The
expected result is Cargo `1.98.0` changing to `1.98.1`.

## Next Cases

Add public repositories from different build ecosystems and historical
runner-image incidents only when their build command and runner revision can be
recorded reproducibly. Each new case should document the observed dependency,
the relevant runner-image delta, and whether the receipt would have reduced the
diagnostic search space.
