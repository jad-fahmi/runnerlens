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

## Components

The package follows the receipt pipeline:

- `runnerlens.cli`: command-line interface
- `runnerlens.observer`: Linux process-tree observer with a root-command fallback
- `runnerlens.runner`: CI runner metadata detection
- `runnerlens.classifier`: conservative origin classification
- `runnerlens.resolver`: Linux version and Debian package-owner resolution
- `runnerlens.receipt`: receipt construction and JSON serialization
- `runnerlens.report`: human-readable receipt report

On Linux with `strace` available, the observer records successful `execve` and
identifiable `execveat` calls from the wrapped command's process tree. Paths
passed relative to directory descriptors or through `AT_EMPTY_PATH` are kept
as unresolved events and mark coverage partial rather than guessed. Elsewhere,
it records only the wrapped root command and labels that lower-coverage
observation method in the receipt.
When strace splits a syscall across unfinished and resumed lines, the parser
pairs the lines by process and syscall and records the executable only when
the resumed call reports success. Unpaired or unmatched lines remain visible
as incomplete events, mark coverage partial, and are excluded from dependencies.
Before tracing, RunnerLens probes tracer availability with `/bin/true`. A failed
probe or a tracer launch error runs the build with root-only fallback evidence.
If `strace` completes without any parseable execution events, or its trace file
cannot be read, RunnerLens preserves the tracer's exit code but does not infer
that the root command executed. The receipt has unknown observation coverage and
no observed dependencies. It does not rerun the build after the tracer completes.
Ptrace changes setuid and setgid execution: by default, traced privileged
programs run without their effective privileges ([strace manual](https://man7.org/linux/man-pages/man1/strace.1.html)).
For commands that rely on such helpers, `runnerlens run --no-process-tree`
avoids ptrace and records the wrapped command only with the explicit
`subprocess-root-only` observation label. RunnerLens does not elevate the
tracer to preserve those privileges.
The composite action exposes `process-tree-observation: false` for the same
privilege-sensitive case. Since the action launches the supplied script
through Bash, that mode records only the Bash wrapper. It does not claim to
identify commands invoked inside the script; use the CLI mode for direct
command identity when possible.

After classification, RunnerLens requests version output only for recognized
tool names with known version commands (`--version`, or `go version` for Go),
and queries `dpkg-query` for the owning Debian package. Both operations are
bounded by a short timeout. Unknown executable names are not run a second time,
and a value is omitted when either source does not return reliable evidence.
Metadata probes run from `/` and exclude common runtime-injection and package-
database override variables, and use the C locale. This keeps repository-local
configuration, workflow preload hooks, and runner language settings from
changing the result.

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
instead of runner-provided or tool-cache. RunnerLens does not infer container
execution from an incidental filesystem marker.

`runnerlens compare` compares two receipts by executable name and observed path,
reporting dependencies as added, removed, changed, or unchanged. This preserves
switches between system and tool-cache copies of the same executable instead of
silently treating them as one dependency. It does not claim that a changed tool
was caused by the runner image: it preserves both receipts as the underlying
evidence.

For GitHub-hosted Ubuntu receipts, `runnerlens impact` fetches the release
inventory from `actions/runner-images`, normalizes its documented tool versions,
and correlates only observed `runner-provided` and `tool-cache` dependencies.
For tool-cache paths, it reads the inventory's separate Cached Tools section
rather than confusing those versions with a system tool. A confirmed tool-cache
origin also preserves that correlation when the observed path is a system
symlink into the cache. A missing metadata match is reported as
`metadata-unavailable`, never as a removed tool.

The provider supports the current Ubuntu inventory path and the two documented
legacy Linux inventory paths used by retained Ubuntu runner-image releases.

When `--baseline-image-version` is supplied, the impact engine compares the two
release inventories directly. It reports a tool as removed only when the
baseline inventory documents that observed tool and the target inventory does
not. This preserves the distinction between a documented removal and an
unrecognized metadata name.

Receipt comparisons carry observation coverage into human and JSON output.
`runnerlens check` returns an inconclusive exit status unless both receipts
contain process-tree observations. Image impact remains available for partial
receipts but marks the coverage and warns that unobserved child dependencies
are not represented.

## GitHub Action

The composite `action.yml` installs RunnerLens from the checked-out action,
observes the command supplied by the workflow, and appends the report to the
GitHub job summary. It deliberately has no network upload step. The only remote
metadata request is the explicit `runnerlens impact` command.

## Evidence Rules

RunnerLens should prefer `unknown` over unsupported certainty.

For example, `/usr/bin/cmake` on a GitHub-hosted runner is probably
runner-provided, but an earlier workflow step might have intentionally installed
or replaced it. A self-hosted or otherwise unproven GitHub Actions runner stays
`unknown`. The classifier should preserve that uncertainty unless stronger
evidence exists. Relative execution paths also stay unresolved because a traced
child may have changed its working directory, which RunnerLens does not currently
track.
