<div align="center">

# RunnerLens

**Know what your build inherits.**

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

</div>

RunnerLens reveals the tools your build inherits from its CI runner and shows which runner image changes can affect it.

Hosted CI runners include compilers, runtimes, SDKs, package managers, and build tools by default. A build can silently depend on those tools without explicitly installing them.

When the runner image changes, the repository may stay the same while the build starts behaving differently.

RunnerLens makes those dependencies visible.

---

## Quick Links

* [Getting Started](#getting-started)
* [Why RunnerLens](#why-runnerlens)
* [Runner Dependency Receipts](#runner-dependency-receipts)
* [How It Works](#how-it-works)
* [Compatibility](#compatibility)
* [Limitations](#limitations)
* [Contributing](#contributing)
* [License](#license)

---

## Getting Started

> [!NOTE]
> RunnerLens is currently under development. The commands below describe the current local development scaffold.

Install the local development package:

```text
python -m pip install -e ".[dev]"
```

RunnerLens wraps an existing build or test command and writes a receipt to `runnerlens-receipt.json` by default:

```text
runnerlens run -- make
```

Inspect a saved receipt later with:

```text
runnerlens show runnerlens-receipt.json
```

Compare a known-good receipt with a newer run:

```text
runnerlens compare baseline-receipt.json runnerlens-receipt.json
```

Fail CI when a build introduces a new runner-provided or tool-cache dependency:

```text
runnerlens check baseline-receipt.json runnerlens-receipt.json
```

Check observed tools against a specific GitHub Ubuntu runner-image release:

```text
runnerlens impact runnerlens-receipt.json --target-image-version 20260907.131.1
```

### GitHub Actions

Use the composite action after checkout and any intentional provisioning steps:

```yaml
- uses: actions/checkout@v4
- uses: jad-fahmi/runnerlens@main
  with:
    command: python -m pytest
    baseline: .runnerlens/accepted-receipt.json
```

The action writes `runnerlens-receipt.json` and publishes the human-readable
receipt to the job summary. To retain the JSON receipt between runs, upload it
with `actions/upload-artifact` or commit it as a reviewed baseline.
When `baseline` is set, a successful build fails if it introduces a new
runner-provided or tool-cache dependency. A failing wrapped build retains its
own exit status regardless of the baseline result.

Example output:

```text
RunnerLens

Runner
  GitHub Actions
  ubuntu-24.04

Observed runner dependencies

  cmake
    path: /usr/local/bin/cmake
    origin: runner-provided

  ninja
    path: /usr/bin/ninja
    origin: runner-provided

  clang
    path: /usr/bin/clang
    origin: runner-provided

3 runner-provided dependencies observed
```

RunnerLens records executable versions and Debian package owners where reliable.
Receipt comparison narrows run-to-run changes to the tools your build actually used. `runnerlens impact` downloads the public software inventory for a specified GitHub Ubuntu image release and identifies observed tool versions that are no longer documented there.

---

## Why RunnerLens?

### Find hidden build dependencies

Discover tools that your build uses from the CI runner without explicitly provisioning them.

### Debug unexpected CI failures

Identify runner image changes that intersect with tools your build actually uses.

### Prepare runner migrations

See which observed dependencies change before moving between runner images.

### Improve build reproducibility

Expose dependencies that currently exist only because the runner happens to provide them.

### Understand self-hosted runner requirements

Use observed dependencies as evidence when preparing your own runner image.

---

## Runner Dependency Receipts

RunnerLens records observed environment dependencies in a **Runner Dependency Receipt**.

A receipt contains information such as:

```json
{
  "runner": {
    "provider": "github-actions",
    "image": "ubuntu-24.04"
  },
  "dependencies": [
    {
      "name": "cmake",
      "path": "/usr/local/bin/cmake",
      "origin": "runner-provided",
      "confidence": "confirmed"
    }
  ]
}
```

Receipts are designed to support both human investigation and automated comparison.

They can eventually answer questions such as:

* What runner-provided tools does this build use?
* What changed since the last successful run?
* Did this pull request introduce a new ambient dependency?
* Will a runner image update affect this project?
* What needs to be installed on a self-hosted runner?

---

## How It Works

RunnerLens observes the command being executed and resolves the external tools it uses.

```text
Build Command
     |
     v
Runtime Observer
     |
     v
Dependency Resolver
     |
     v
Origin Classifier
     |
     v
Runner Metadata
     |
     v
Dependency Receipt
     |
     v
Impact Analysis
```

### Runtime Observer

Records relevant process execution under the command being analyzed.

### Dependency Resolver

Identifies executables, versions, paths, and package ownership where possible.

### Origin Classifier

Determines whether an observed dependency is:

```text
runner-provided
workflow-provisioned
repository-provided
tool-cache
container-provided
unknown
```

### Runner Metadata

Correlates observed dependencies with information about the CI runner image.

### Impact Analysis

Filters runner image changes down to dependencies observed in the build.

---

## Evidence Over Guessing

RunnerLens should only report what it can support with evidence.

Seeing:

```text
/usr/bin/cmake
```

does not automatically mean the workflow forgot to install CMake.

The tool may have been installed earlier in the workflow.

RunnerLens should report:

```text
origin: unknown
```

when provenance cannot be established reliably.

Reliable evidence is more important than confident output.

---

## Compatibility

Initial target:

| Environment           | Support       |
| --------------------- | ------------- |
| GitHub-hosted Ubuntu  | Supported |
| GitHub-hosted Windows | Future        |
| GitHub-hosted macOS   | Future        |
| Self-hosted Linux     | Future        |
| GitLab CI             | Future        |
| Azure Pipelines       | Future        |
| Buildkite             | Future        |

Support will only be marked complete once it is covered by real integration tests.

---

## What RunnerLens Is Not

RunnerLens is not an SBOM generator.

RunnerLens is not a vulnerability scanner.

RunnerLens is not a CI runtime security product.

RunnerLens is not a replacement for Bazel, Nix, containers, or other reproducible build systems.

RunnerLens focuses on one problem:

> Which parts of the CI environment did this build actually depend on?

---

## Security and Privacy

Runtime observation can expose sensitive information if implemented incorrectly.

RunnerLens should collect only the information required to identify dependencies and their origin.

It should avoid collecting unnecessary:

* environment variable values
* credentials
* tokens
* file contents
* command arguments
* unrelated runtime data

The default principle is simple:

> Collect the minimum evidence required to identify the dependency.

The composite action executes only the command supplied in its `command` input.
It sends no receipt data to RunnerLens services. A dedicated security policy and threat model will be maintained as the project develops.

---

## Limitations

RunnerLens will not detect every form of environment dependency.

The first version will focus primarily on observed executable dependencies.

It may not detect dependencies on:

* system headers
* dynamically loaded libraries
* SDK files
* environment variables
* kernel behavior
* filesystem assumptions
* background services

A clean RunnerLens report should not be interpreted as proof that a build is fully hermetic.

---

## Roadmap

### Phase 1

Observe build commands and identify runner-provided executables.

### Phase 2

Generate stable Runner Dependency Receipts.

### Phase 3

Compare receipts against runner image changes.

### Phase 4

Detect newly introduced ambient dependencies. `runnerlens check` is available for receipt baselines.

### Phase 5

Analyze runner migrations.

### Phase 6

Support additional CI providers and operating systems.

The roadmap will be driven by real usage rather than feature count.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, evidence rules,
receipt compatibility guidance, and privacy requirements.

RunnerLens is intended to support contributions in areas such as:

* package provenance resolvers
* CI provider integrations
* runner metadata parsers
* tracing backends
* operating system support
* regression fixtures
* report formats

Large architectural changes should begin with an issue or discussion.

---

## Project Status

RunnerLens is currently in early development.

The first objective is to validate that runner dependency information helps diagnose real CI environment problems.

The project will prioritize real workflows and real failures over synthetic demos.

---

## License

RunnerLens is licensed under the [Apache License 2.0](LICENSE).

---

<div align="center">

**RunnerLens**

Know what your build inherits.

</div>
