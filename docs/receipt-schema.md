# Runner Dependency Receipt Schema

The receipt schema is experimental and versioned as `0.1.0`.

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
        "system path on GitHub-hosted runner"
      ]
    }
  ],
  "events": [
    {
      "executable": "make",
      "path": "/usr/bin/make",
      "observation": "subprocess-root"
    }
  ]
}
```

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
