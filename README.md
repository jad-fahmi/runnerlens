<div align="center">

# RunnerLens

### Know what your build inherits.

**Reveal the hidden tools your build depends on from its CI runner — and see which runner-image changes can actually affect it.**

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Project Status](https://img.shields.io/badge/status-early%20development-orange)](#project-status)

</div>

---

## Why RunnerLens?

Hosted CI runners come with compilers, runtimes, SDKs, package managers, build tools, and system utilities already installed.

That convenience can hide part of your real build dependency graph.

A workflow might only say:

```yaml
- uses: actions/checkout@v4

- name: Build
  run: make
```

while the build actually relies on:

```text
make
 └── cmake
      └── ninja
           └── clang
```

If one of those runner-provided tools changes, your source code may remain identical while the build starts behaving differently.

RunnerLens is being built to make those dependencies visible.

Instead of asking:

> What changed in the entire runner image?

RunnerLens aims to answer:

> What changed that this build actually depends on?

---

## See It in Action

The intended RunnerLens workflow is deliberately simple.

```text
$ runnerlens run -- make release

RunnerLens
────────────────────────────────────────────

Runner
  GitHub Actions
  ubuntu-24.04

Observed runner dependencies

  cmake
    /usr/local/bin/cmake
    version     4.x
    origin      runner-provided

  ninja
    /usr/bin/ninja
    version     1.x
    origin      runner-provided

  clang
    /usr/bin/clang
    version     20.x
    origin      runner-provided

────────────────────────────────────────────
3 runner-provided dependencies observed
```

The resulting **Runner Dependency Receipt** can then be compared against runner-image changes:

```text
$ runnerlens impact receipt.json

Runner image impact
────────────────────────────────────────────

Observed dependencies     3
Changed                   1
Removed                   0
Unchanged                 2

Relevant changes

  cmake
    previous    4.x
    current     4.y

────────────────────────────────────────────
1 observed dependency may be affected
```

The examples above show the intended interface. RunnerLens is currently in early development and these commands are not yet a stable public API.

---

## Quick Links

* [The Problem](#the-problem)
* [What RunnerLens Does](#what-runnerlens-does)
* [Getting Started](#getting-started)
* [Why Use RunnerLens?](#why-use-runnerlens)
* [Runner Dependency Receipts](#runner-dependency-receipts)
* [How It Works](#how-it-works)
* [Initial Scope](#initial-scope)
* [Compatibility](#compatibility)
* [Security and Privacy](#security-and-privacy)
* [Roadmap](#roadmap)
* [Known Limitations](#known-limitations)
* [Contributing](#contributing)
* [Project Status](#project-status)

---

## The Problem

CI environments are part of the build whether we explicitly acknowledge them or not.

Consider a project that executes:

```text
cmake
ninja
clang
python
protoc
```

Those tools may have been:

* explicitly installed by the workflow;
* downloaded by a setup action;
* included in the repository;
* pulled from a tool cache;
* provided by a container;
* already installed on the CI runner.

Those situations are not equivalent.

When a build silently accepts whatever happens to exist on the runner, the build inherits an **ambient dependency**.

That dependency may remain invisible until:

* the runner image updates;
* a tool version changes;
* a tool is removed;
* the project moves to another runner;
* the build is reproduced locally;
* the project migrates to self-hosted infrastructure.

Debugging then becomes an environment investigation instead of a source-code investigation.

RunnerLens is designed around that failure mode.

---

## What RunnerLens Does

RunnerLens observes a real build or test command and attempts to answer four questions:

### 1. What did the build execute?

RunnerLens observes the process tree beneath the command being analyzed.

### 2. Where did those tools come from?

Observed executables are classified where possible as:

```text
runner-provided
workflow-provisioned
repository-provided
tool-cache
container-provided
unknown
```

### 3. What environment produced the build?

RunnerLens records relevant CI runner metadata alongside the observation.

### 4. Which environment changes matter?

RunnerLens correlates observed dependencies with runner-image changes so unrelated environment updates can be filtered out.

The intended relationship is:

```text
actual execution
        ↓
dependency identity
        ↓
dependency origin
        ↓
runner provenance
        ↓
runner-image history
        ↓
build-specific impact
```

---

## Getting Started

> [!NOTE]
> RunnerLens is currently in early development. Stable installation instructions will be added with the first usable release.

The first supported workflow will target:

```text
GitHub Actions
+
GitHub-hosted Ubuntu runner
+
one explicit build/test command
```

The intended usage model is:

```text
runnerlens run -- <your existing command>
```

For example:

```text
runnerlens run -- make
```

or:

```text
runnerlens run -- cargo build
```

or:

```text
runnerlens run -- ./gradlew test
```

RunnerLens should fit around an existing build rather than requiring developers to replace their build system.

---

## Why Use RunnerLens?

### Identify hidden build dependencies

Discover tools your build uses from the runner without explicitly provisioning them.

### Debug unexplained CI changes

Narrow a large runner-image update down to changes relevant to your build.

### Prepare runner migrations

Understand which environment dependencies matter before moving between runner images.

### Improve reproducibility

Expose dependencies that currently exist only because the CI environment happens to provide them.

### Understand self-hosted requirements

Use observed dependencies as evidence when determining what a custom runner image actually needs.

### Detect dependency drift

Future baseline support will make it possible to detect newly introduced runner dependencies between builds.

---

## Runner Dependency Receipts

The central RunnerLens artifact is a **Runner Dependency Receipt**.

A receipt is a versioned, machine-readable record of the environment dependencies observed during a build.

Conceptually:

```json
{
  "runner": {
    "provider": "github-actions",
    "image": "ubuntu-24.04",
    "image_version": "..."
  },
  "command": "make release",
  "dependencies": [
    {
      "name": "cmake",
      "path": "/usr/local/bin/cmake",
      "version": "4.x",
      "origin": "runner-provided",
      "confidence": "confirmed"
    }
  ]
}
```

Receipts are intended to support both human investigation and future automation.

A repository could eventually use them to answer questions such as:

```text
What runner dependencies does this build have?

What changed since the last successful build?

Did this pull request introduce a new ambient dependency?

Will the next runner image affect this project?

What software must a self-hosted runner provide?
```

---

## Evidence Over Guessing

RunnerLens should never claim more than its evidence establishes.

Seeing:

```text
/usr/bin/cmake
```

does not automatically prove:

> The project forgot to declare CMake.

The executable may have been intentionally installed during an earlier workflow step.

RunnerLens should therefore prefer:

```text
origin: unknown
```

over an unsupported conclusion.

Provenance information should include confidence where appropriate.

The project is intended to produce inspectable evidence, not confident-looking guesses.

---

## How It Works

RunnerLens is designed around separate observation and interpretation layers.

```text
Build / Test Command
        │
        ▼
┌──────────────────────┐
│   Runtime Observer   │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ Normalized Execution │
│        Events        │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ Dependency Resolver  │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  Origin Classifier   │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│   Runner Provider    │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ Dependency Receipt   │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│    Impact Engine     │
└──────────────────────┘
```

### Runtime Observer

Captures relevant process execution beneath the command being analyzed.

### Dependency Resolver

Turns raw executable observations into useful dependency identities.

### Origin Classifier

Determines where a dependency came from when sufficient evidence exists.

### Runner Provider

Understands provider-specific runner metadata and environment manifests.

### Receipt Engine

Produces a stable representation of the observed build environment dependencies.

### Impact Engine

Intersects a dependency receipt with changes between runner environments.

---

## Initial Scope

The first useful version of RunnerLens will intentionally be narrow.

### Planned

* GitHub Actions
* GitHub-hosted Ubuntu runners
* explicit command observation
* process-tree collection
* executable path resolution
* executable version detection where reliable
* Linux package ownership where reliable
* runner-image metadata correlation
* human-readable reports
* JSON dependency receipts
* runner-image impact comparison

### Not Planned for v0.1

* Windows support
* macOS support
* complete arbitrary-job tracing
* vulnerability scanning
* malware detection
* network monitoring
* AI-generated diagnoses
* automated workflow rewriting
* hosted dashboards
* complete build-hermeticity verification

RunnerLens will expand only where real use cases justify the additional complexity.

---

## Compatibility

Initial compatibility targets:

| Environment              | Planned Support  |
| ------------------------ | ---------------- |
| GitHub-hosted Ubuntu     | ✅ Initial target |
| GitHub-hosted Windows    | ⏳ Future         |
| GitHub-hosted macOS      | ⏳ Future         |
| GitHub self-hosted Linux | ⏳ Future         |
| GitLab CI                | ⏳ Future         |
| Azure Pipelines          | ⏳ Future         |
| Buildkite                | ⏳ Future         |

Support should only be marked complete once it is covered by real integration tests.

---

## What RunnerLens Is Not

RunnerLens overlaps with several existing tool categories but is not intended to replace them.

### SBOM tools

SBOM tools describe software components in an artifact or environment.

RunnerLens focuses on dependencies **observed during build execution and inherited from the runner**.

### CI runtime security

Runtime security products detect suspicious process, filesystem, and network activity.

RunnerLens focuses on build-environment dependencies and environment drift.

### Environment diff tools

Environment diff tools answer:

> What changed between these environments?

RunnerLens aims to answer:

> Which of those changes intersect with dependencies this build actually used?

### Build systems

RunnerLens does not replace Bazel, Nix, containers, or other reproducible-build approaches.

It analyzes builds developers already have.

---

## Security and Privacy

Runtime observation can expose sensitive information if implemented carelessly.

RunnerLens should collect only the information required to establish dependency identity and provenance.

The project should avoid collecting unnecessary:

* environment-variable values;
* tokens;
* credentials;
* file contents;
* command arguments;
* unrelated process information.

The default model is:

> **Collect the minimum evidence required to identify the dependency.**

A formal threat model and [`SECURITY.md`](SECURITY.md) will be maintained as the implementation matures.

---

## Roadmap

### Phase 1 — Observe

Identify external executables used by one build command.

### Phase 2 — Classify

Determine which observed dependencies originate from the runner.

### Phase 3 — Correlate

Connect those dependencies to runner-image metadata.

### Phase 4 — Impact

Show which runner-image changes intersect with the dependency receipt.

### Phase 5 — Baseline

Compare receipts between successful builds.

### Phase 6 — Drift Detection

Detect newly introduced ambient dependencies.

### Phase 7 — Migration Analysis

Analyze relevant dependency differences between runner environments.

### Phase 8 — Additional Providers

Expand beyond GitHub Actions where real demand exists.

---

## Real-World Regression Corpus

RunnerLens should be tested against actual CI environment failures rather than only synthetic examples.

A regression fixture may eventually describe:

```text
known-good runner image
known-bad runner image
sample project
observed dependency
expected diagnosis
```

These fixtures can serve as:

* integration tests;
* regression tests;
* product demonstrations;
* historical documentation;
* meaningful contribution opportunities.

---

## Known Limitations

RunnerLens will initially observe only part of the environment dependency problem.

Executable observation alone may not reveal dependencies on:

* system headers;
* dynamically loaded libraries;
* SDK files;
* environment variables;
* kernel behavior;
* filesystem conventions;
* services already running on the host.

A successful RunnerLens report should therefore not be interpreted as proof that a build is completely hermetic.

The first objective is narrower:

> Identify meaningful executable dependencies inherited from supported CI environments.

See future documentation for a complete list of known limitations as the implementation develops.

---

## Project Status

RunnerLens is currently in the **research and early development stage**.

The central hypothesis being tested is:

> Runtime-derived dependency information can materially reduce the effort required to understand CI environment drift.

Before expanding the project substantially, RunnerLens needs to prove that:

* real projects contain meaningful ambient runner dependencies;
* those dependencies can be classified reliably;
* dependency receipts help diagnose real runner-image failures;
* observation overhead remains acceptable;
* developers find enough recurring value to keep RunnerLens in CI.

A technically impressive tracer is not sufficient.

RunnerLens must solve a recurring developer problem.

---

## Contributing

RunnerLens is intended to become community-extensible only where natural technical boundaries exist.

Potential future contribution areas include:

* package provenance resolvers;
* runner metadata providers;
* process-observation backends;
* CI-platform integrations;
* operating-system support;
* historical regression fixtures;
* report formats;
* classification improvements.

Small contributions should be capable of improving one area without requiring contributors to understand the entire codebase.

For significant architectural changes, please open an issue or discussion before beginning implementation.

A full [`CONTRIBUTING.md`](CONTRIBUTING.md) will be added as the architecture stabilizes.

---

## Discussions

Questions, use cases, runner regressions, ideas, and early feedback are welcome through GitHub Issues and Discussions.

Especially useful reports include:

* builds that changed without corresponding source changes;
* runner-image migrations that caused failures;
* projects that unknowingly relied on preinstalled runner software;
* cases where existing debugging tools provided too much environment information and too little build-specific context.

Real incidents will guide the project more than speculative feature requests.

---

## License

RunnerLens is open source under the **Apache License 2.0**.

See [`LICENSE`](LICENSE) for details.

---

<div align="center">

### RunnerLens

**Know what your build inherits.**

</div>
