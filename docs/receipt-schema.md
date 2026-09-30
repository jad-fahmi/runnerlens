# Runner Dependency Receipt Schema

The receipt schema is experimental and versioned as `0.1.0`.

RunnerLens 0.1 rejects receipts with another schema version instead of attempting
to interpret them. This is deliberate: callers should make compatibility an
explicit decision as the schema evolves.

Example:

```json
{
  "schema_version": "0.1.0",
  "started_at": "2026-09-21T00:00:00+00:00",
  "ended_at": "2026-09-21T00:00:01+00:00",
  "exit_code": 0,
  "runner": {
    "provider": "github-actions",
    "os": "Linux",
    "image": "ubuntu24",
    "image_version": "20260921.1"
  },
  "command": {
    "executable": "make",
    "resolved_path": "/usr/bin/make",
    "arguments_recorded": false
  },
  "dependencies": [
    {
      "name": "make",
      "path": "/usr/bin/make",
      "origin": "runner-provided",
      "confidence": "probable",
      "evidence": [
        "observed via subprocess-root",
        "documented base-image path on GitHub-hosted runner"
      ]
    }
  ],
  "events": [
    {
      "executable": "make",
      "path": "/usr/bin/make",
      "observation": "subprocess-root",
      "role": "build-tool"
    }
  ]
}
```

`started_at` and `ended_at` use timezone-aware ISO 8601 timestamps, and the
ending timestamp must not precede the start.
`exit_code` preserves the subprocess return code; a negative value means the
process ended from a signal. The CLI maps that value to the shell status
`128 + signal`.

Events preserve raw execution evidence. `role` is `build-tool` by default and
is `launcher` for a wrapper such as the composite GitHub Action shell. The
default dependency list excludes launcher events and routine shell utilities to
keep the receipt focused. Use `runnerlens run --include-support-tools` to
include them in dependency output.

Unresolved executable paths are serialized as `null` in dependency and event
records so the receipt can be loaded without inventing a path.
Non-null command, dependency, and event paths must be absolute POSIX or Windows
paths; relative paths are treated as unresolved.
Dependency records are unique by executable name and path. Two records with
the same identity are rejected rather than silently choosing one provenance or
version value.
Event process IDs are positive integers when present; missing or unknown IDs
are represented as `null`.

## Origin Values

- `runner-provided`
- `workflow-provisioned`
- `repository-provided`
- `tool-cache`
- `container-provided`
- `unknown`

## Confidence Values

The initial scaffold uses:

- `confirmed`
- `probable`
- `unknown`

Future versions may refine these values, but should keep the bias toward conservative evidence.

## Human Report

`runnerlens show` renders each dependency's path, version, package owner, origin,
confidence, and evidence lines. The report intentionally includes the observation
method, such as `strace-execve`, so a classification remains inspectable outside
the JSON receipt.
