# Contributing to RunnerLens

RunnerLens is a local-first, deterministic tool for understanding the executable
dependencies a build inherits from its CI runner. Contributions should strengthen
that evidence chain rather than broaden the project into generic tracing,
security scanning, or environment diffing.

## Development Setup

RunnerLens requires Python 3.11 or newer.

```text
python -m pip install -e ".[dev]"
python -m pytest
```

The repository CI runs the test suite on GitHub-hosted Ubuntu and executes the
composite action against real process-tree tracing.

## Contribution Priorities

Useful contributions include:

- Linux tracing reliability and low-overhead observation
- GitHub Actions runner-image metadata handling
- package ownership and executable-version resolution
- receipt schema compatibility and report clarity
- real runner-image regression fixtures
- conservative origin-classification rules

Please open an issue or discussion before proposing a large architectural
change, a new CI provider, or another operating-system backend.

## Evidence Rules

Do not turn incomplete evidence into a confident provenance claim. In
particular, observing a system path does not prove a workflow failed to install
that tool. Prefer `unknown`, lower confidence, or a clearly labeled heuristic
when the evidence cannot establish an origin safely.

Changes to a classification rule should include tests for both the intended
classification and a nearby case that must remain unknown.

## Receipt Compatibility

Runner Dependency Receipts are durable artifacts. Treat changes to their JSON
schema as compatibility work:

- preserve existing fields whenever practical
- add tests for serialization and loading behavior
- document any new field or value in `docs/receipt-schema.md`
- reject unsupported schema versions rather than guessing how to read them

## Privacy

Do not add collection of environment-variable values, credentials, tokens, file
contents, or command arguments without a narrowly justified need and explicit
documentation. Use synthetic fixtures in tests. Never commit real workflow logs
or private receipt data.

For potential vulnerabilities, follow the process in `SECURITY.md` instead of
opening a public issue.
