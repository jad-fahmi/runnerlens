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
- `runnerlens.receipt`: receipt construction and JSON serialization
- `runnerlens.report`: human-readable receipt report

On Linux with `strace` available, the observer records successful `execve` calls
from the wrapped command's process tree. Elsewhere, it records only the wrapped
root command and labels that lower-coverage observation method in the receipt.

## Evidence Rules

RunnerLens should prefer `unknown` over unsupported certainty.

For example, `/usr/bin/cmake` on GitHub Actions is probably runner-provided, but an earlier workflow step might have intentionally installed or replaced it. The classifier should preserve that uncertainty unless stronger evidence exists.
