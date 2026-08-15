# Security and privacy

GPU Triage is an alpha-stage offline diagnostic tool. Treat incident artifacts as potentially sensitive operational data.

## Reporting a vulnerability

Prefer GitHub private vulnerability reporting / security advisories when that option is available for this repository. Do not publish credentials, private infrastructure details, exploit payloads, or sensitive incident data in a public issue. If private reporting is unavailable, open a minimal public issue requesting a private contact path without including sensitive details.

## Sanitized export boundary

`gputriage export-sanitized` is designed to reduce accidental disclosure when sharing diagnostic structure. By default it:

- copies no raw artifact bytes;
- removes `raw_ref` values;
- pseudonymizes known identity-graph identifiers;
- omits free-text symptom text unless explicitly requested.

It is **not** a DLP, secret scanner, PII detector, or guarantee of anonymization. Arbitrary string-valued observations may still contain sensitive data. Review every exported JSON file before sharing it outside the intended trust boundary.

## Operational safety

The current CLI is offline by default and does not perform SSH/API fleet collection or autonomous remediation. Diagnostic command templates are recommendations for an operator to review; they should not be treated as automatically safe in every environment.

## Supported versions

Until a stable 1.0 release exists, security fixes target the latest public alpha unless a specific older release is explicitly documented as supported.
