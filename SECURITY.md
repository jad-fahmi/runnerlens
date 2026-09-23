# Security Policy

RunnerLens observes build execution, so privacy and evidence boundaries are core product requirements.

## Current Status

RunnerLens is in early development. Do not rely on it yet as a security control, vulnerability scanner, malware detector, or complete hermeticity verifier.

## Data Collection Principles

RunnerLens should collect the minimum evidence required to identify build-environment dependencies.

The default implementation should avoid collecting unnecessary:

- secret values
- tokens
- credentials
- file contents
- environment-variable values
- unrelated process information
- command arguments unless a feature explicitly justifies them

Version and package resolution is limited to dependencies classified as
`runner-provided` or `tool-cache`. RunnerLens does not invoke repository-provided
executables again to ask for their version.

## Reporting Vulnerabilities

Until a dedicated process is published, please open a private security advisory on GitHub if available, or contact the repository maintainer privately.

Do not include secrets, private build logs, or sensitive workflow output in public issues.
