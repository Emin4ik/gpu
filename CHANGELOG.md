# Changelog

All notable public-alpha changes are recorded here.

The project is pre-1.0. Package versions follow PEP 440; versioned JSON schema compatibility is documented separately in `docs/SCHEMA_COMPATIBILITY.md`.

## 0.2.0a1 - 2026-08-15

First public alpha candidate.

### Added

- offline `gputriage investigate`, `validate-bundle`, and `export-sanitized` CLI contract;
- versioned `gputriage.report.v1` and `gputriage.sanitized-bundle.v1` schemas;
- explicit `confirmed`, `needs_evidence`, and `abstain` result states and stable exit codes;
- sanitized normalized-evidence export with conservative identity pseudonymization;
- M8.2 independently frozen staged-replay benchmark and permanent release gate;
- wheel/sdist build, metadata validation, and clean-wheel installation smoke tests;
- manual GitHub pre-release workflow;
- public contribution, security/privacy, and schema compatibility guidance.

### Validation

The first frozen M8.2 holdout passed all predefined PoC engineering gates. This remains a small author-curated staged replay, not a real-world accuracy claim.

## 0.1.0 - 2026-08-15

Internal proof-of-concept package version covering the deterministic diagnostic engine, raw artifact ingestion, identity graph, evidence model, diagnostic planner, cross-tool adapters, and M8.1 negative-evidence/completed-test behavior.
