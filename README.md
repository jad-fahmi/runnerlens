# RunnerLens

**Know what your build inherits.**

RunnerLens is an open-source tool for discovering the hidden dependencies a build inherits from its CI runner.

Hosted CI environments such as GitHub Actions include compilers, runtimes, SDKs, build tools, package managers, and system utilities by default. A project can silently depend on those tools without explicitly installing or declaring them.

That dependency often becomes visible only when the runner image changes and a previously working build suddenly fails.

RunnerLens aims to make those dependencies explicit.

---

## The Problem

A CI workflow may look simple:

```yaml
- uses: actions/checkout@v4

- name: Build
  run: make
```

But the actual build may depend on tools already installed on the runner:

```text
make
 └─ cmake
     └─ ninja
         └─ clang
```

If `cmake`, `ninja`, `clang`, an SDK, or another runner-provided component changes, the repository itself may remain unchanged while the build behaves differently.

Today, debugging this often means manually comparing:

* successful and failing CI runs;
* runner-image versions;
* installed software manifests;
* workflow steps;
* environment differences;
* long runner-image release notes.

RunnerLens is intended to reduce that investigation to the dependencies that the build actually used.

---

## What RunnerLens Does

RunnerLens observes a real build or test command and produces a **Runner Dependency Receipt** describing the external tools it used.

Conceptually:

```text
$ runnerlens run -- make release

RunnerLens

Runner:
  GitHub Actions / ubuntu-24.04

Observed runner dependencies:

  cmake
    path:       /usr/local/bin/cmake
    version:    4.x
    origin:     runner image

  ninja
    path:       /usr/bin/ninja
    version:    1.x
    origin:     runner image

  clang
    path:       /usr/bin/clang
    version:    20.x
    origin:     runner image
```

RunnerLens can then compare those dependencies against changes in a runner image:

```text
$ runnerlens impact receipt.json

Runner image impact

Observed dependencies: 3
Changed:               1
Removed:               0
Unchanged:             2

Relevant changes:

  cmake
    previous: 4.x
    current:  4.y
```

Instead of asking:

> What changed in the entire CI environment?

RunnerLens aims to answer:

> What changed that this build actually depends on?

---

## Why RunnerLens?

GitHub-hosted runners contain a large amount of preinstalled software.

That is convenient, but it also means the runner itself can become an implicit part of a project's dependency graph.

RunnerLens focuses on the relationship between:

```text
actual build execution
        ↓
host-provided dependencies
        ↓
CI runner provenance
        ↓
runner-image changes
        ↓
build-specific impact
```

RunnerLens is not intended to replace build systems, containers, SBOM tools, vulnerability scanners, or CI security products.

Its focus is narrower:

**make dependencies on the build environment visible.**

---

## Runner Dependency Receipts

The central RunnerLens primitive is the **Runner Dependency Receipt**.

A receipt is a machine-readable record of environment dependencies observed while executing a command.

A receipt may eventually contain information such as:

* executable name;
* resolved executable path;
* version;
* parent process;
* package ownership;
* dependency origin;
* CI provider;
* runner image;
* runner image version;
* provenance confidence;
* observation evidence.

Example:

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

The exact schema is still being designed.

---

## Provenance Matters

Seeing a process execute does not automatically mean a project forgot to declare it.

RunnerLens should distinguish between dependencies such as:

```text
runner-provided
workflow-provisioned
repository-provided
tool-cache
container-provided
unknown
```

RunnerLens should prefer an explicit:

```text
origin: unknown
```

over an unsupported conclusion.

Trustworthy evidence is more important than producing a confident-looking report.

---

## Initial Scope

RunnerLens will start deliberately small.

### Planned for the first usable version

* GitHub Actions
* GitHub-hosted Ubuntu runners
* explicit build/test command observation
* process-tree collection
* executable path resolution
* executable version detection where reliable
* package ownership where reliable
* runner-image metadata correlation
* human-readable reports
* machine-readable dependency receipts
* comparison against runner-image changes

### Not part of the initial scope

* Windows runners
* macOS runners
* arbitrary full-job tracing
* vulnerability scanning
* network monitoring
* malware detection
* AI-generated diagnoses
* automated workflow modification
* hosted dashboards
* complete build hermeticity verification

The first goal is to determine whether the core dependency-receipt model is genuinely useful on real projects.

---

## What RunnerLens Is Not

### Not an SBOM generator

SBOMs describe software components associated with an artifact or environment.

RunnerLens focuses on what the **build execution actually inherited from its runner**.

### Not a CI security agent

Tools such as runtime security monitors focus on suspicious processes, network activity, and workflow compromise.

RunnerLens focuses on **build dependencies and environment drift**.

### Not an environment diff tool

A runner update may change hundreds of components.

RunnerLens attempts to reduce that information to components relevant to a particular build.

### Not a build system

RunnerLens does not attempt to replace Bazel, Nix, containers, or other reproducible-build technologies.

It is intended to help developers understand the dependencies of workflows that already exist.

---

## Example Use Cases

### A build suddenly breaks

```text
Yesterday: PASS
Today:     FAIL
Code diff: none
```

RunnerLens could help determine whether an observed runner dependency changed between the two environments.

### Migrating runner images

Before moving:

```text
ubuntu-22.04 → ubuntu-24.04
```

RunnerLens could identify which observed host dependencies differ.

### Preparing a self-hosted runner

A dependency receipt could help answer:

> What does this build actually need installed?

### Detecting new ambient dependencies

A future baseline mode could identify when a pull request begins depending on a new host-provided tool.

```text
New runner dependency:

  protoc
  origin: runner-provided
```

---

## Project Direction

RunnerLens is expected to evolve in stages.

### Stage 1 — Discovery

Identify runner-provided executables used by a real build.

### Stage 2 — Impact

Correlate observed dependencies with runner-image changes.

### Stage 3 — Baselines

Compare dependency receipts across builds.

### Stage 4 — CI Drift Detection

Detect newly introduced ambient dependencies.

### Stage 5 — Runner Migration Analysis

Evaluate the relevant differences between runner environments.

### Stage 6 — Additional CI Providers

Potential future targets include:

* GitLab CI
* Azure Pipelines
* Buildkite
* self-hosted runner environments

Additional platforms will only be added if real usage justifies them.

---

## Architecture

The intended architecture separates observation from environment interpretation.

```text
Command
   ↓
Runtime Observer
   ↓
Normalized Execution Events
   ↓
Dependency Resolver
   ↓
Origin Classifier
   ↓
Runner Provider
   ↓
Dependency Receipt
   ↓
Impact Engine
   ↓
CLI / JSON / CI Report
```

This should allow RunnerLens to support additional operating systems and CI providers without coupling the entire codebase to one tracing mechanism.

---

## Security and Privacy

Runtime observation can expose sensitive information if implemented carelessly.

RunnerLens should collect only the information required to establish dependency identity.

The project should avoid collecting sensitive data such as:

* environment-variable values;
* secrets;
* tokens;
* unnecessary command arguments;
* file contents;
* unrelated runtime information.

Security and privacy are design requirements, not optional features.

A formal threat model and `SECURITY.md` will be added as the implementation develops.

---

## Why Open Source?

RunnerLens depends on environment-specific knowledge.

Different contributors may have expertise in:

* Linux process observation;
* package managers;
* GitHub Actions;
* CI runner images;
* build systems;
* Windows;
* macOS;
* CI platforms.

Potential contribution areas include:

* package provenance resolvers;
* CI-provider adapters;
* tracing backends;
* runner metadata parsers;
* regression fixtures;
* reporting integrations;
* platform support.

The project should only introduce formal plugin interfaces once real integrations demonstrate that those boundaries are useful.

---

## Real-World Regression Corpus

One planned part of RunnerLens is a collection of reproducible historical CI environment failures.

A regression fixture could describe:

```text
known-good runner
known-bad runner
test project
relevant dependency
expected RunnerLens result
```

This provides both validation and useful contribution opportunities.

RunnerLens should be tested against real failures rather than only synthetic demonstrations.

---

## Project Status

> **Early research / validation stage**

RunnerLens is currently being designed and validated.

The immediate goal is not to build the largest possible feature set.

The first question is:

> Does runtime-derived runner dependency information materially help developers understand real CI failures and environment drift?

The project will be expanded only if evidence supports that thesis.

---

## Validation Goals

Before treating RunnerLens as a mature project, it should demonstrate that:

* meaningful ambient runner dependencies occur in real repositories;
* those dependencies can be identified reliably;
* reports materially reduce investigation effort;
* runtime overhead remains acceptable;
* provenance can be classified without misleading users;
* developers are willing to keep RunnerLens in real CI workflows.

A technically successful tracer is not enough.

The output has to solve a real developer problem.

---

## Contributing

RunnerLens is still in its early design stage.

Contributions, issue reports, research findings, CI regression examples, and technical discussion will become increasingly useful as the first implementation takes shape.

Large architectural changes should begin with an issue or discussion so the project does not accumulate incompatible abstractions before the core model stabilizes.

A full `CONTRIBUTING.md` will be added once the initial architecture is established.

---

## License

RunnerLens is licensed under the **Apache License 2.0**.

See [`LICENSE`](LICENSE) for details.

---

## Core Principle

RunnerLens should never claim more than its evidence establishes.

The project exists to make build environments **more understandable**, not to replace uncertainty with confident guesses.

---

**RunnerLens — Know what your build inherits.**
