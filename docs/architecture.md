# Architecture

RunnerLens is organized around one product primitive: the Runner Dependency Receipt.

Raw tracing data is implementation detail. The user-facing output should be a stable receipt that explains which executable dependencies were observed, where they appear to come from, and what runner environment produced the observation.

## Pipeline

```text
Observed command
      ->
Runtime Observer
      ->
Normalized Execution Events
      ->
Dependency Resolver
      ->
Origin Classifier
      ->
Runner Provider
      ->
Dependency Receipt
      ->
Impact Engine
      ->
Human / JSON / CI output
```

## Current Scaffold

The current scaffold implements the first narrow slice:

- `runnerlens.cli`: command-line interface
- `runnerlens.observer`: Linux process-tree observer with a root-command fallback
- `runnerlens.runner`: CI runner metadata detection
- `runnerlens.classifier`: conservative origin classification
- `runnerlens.resolver`: Linux version and Debian package-owner resolution
- `runnerlens.receipt`: receipt construction and JSON serialization
- `runnerlens.report`: human-readable receipt report

On Linux with `strace` available, the observer records successful `execve` calls
from the wrapped command's process tree. Elsewhere, it records only the wrapped
root command and labels that lower-coverage observation method in the receipt.
If `strace` completes without any parseable execution events, RunnerLens also
retains the root command with a `subprocess-root-fallback` observation label.

After classification, RunnerLens asks an observed absolute executable for its
version with `--version`, and queries `dpkg-query` for the owning Debian package.
Both operations are bounded by a short timeout. A value is omitted when either
source does not return reliable evidence.

Resolution is limited to dependencies already classified as `runner-provided`
or `tool-cache`. RunnerLens does not invoke repository-provided executables a
second time merely to obtain metadata.

## Workflow Provisioning Evidence

`runnerlens run --workflow-provisioned-path PATH` records an explicit workflow
declaration for a path installed or configured before the observed command. Any
executables resolved below that path receive the `workflow-provisioned` origin
with confirmed confidence. This is opt-in evidence, not an inference from a
system path.

`runnerlens run --container` records a separate explicit execution boundary.
For such a run, external executable paths are classified as `container-provided`
instead of runner-provided. RunnerLens does not infer container execution from
an incidental filesystem marker.

`runnerlens compare` compares two receipts and reports observed dependencies as
added, removed, changed, or unchanged. It does not claim that a changed tool was
caused by the runner image: it preserves both receipts as the underlying evidence.

For GitHub-hosted Ubuntu receipts, `runnerlens impact` fetches the exact release
inventory from `actions/runner-images`, normalizes its documented tool versions,
and correlates only the tools that the receipt observed. A missing metadata match
is reported as `metadata-unavailable`, never as a removed tool.

When `--baseline-image-version` is supplied, the impact engine compares the two
release inventories directly. It reports a tool as removed only when the
baseline inventory documents that observed tool and the target inventory does
not. This preserves the distinction between a documented removal and an
unrecognized metadata name.

## GitHub Action

The composite `action.yml` installs RunnerLens from the checked-out action,
observes the command supplied by the workflow, and appends the report to the
GitHub job summary. It deliberately has no network upload step. The only remote
metadata request is the explicit `runnerlens impact` command.

## Evidence Rules

RunnerLens should prefer `unknown` over unsupported certainty.

For example, `/usr/bin/cmake` on GitHub Actions is probably runner-provided, but an earlier workflow step might have intentionally installed or replaced it. The classifier should preserve that uncertainty unless stronger evidence exists.
