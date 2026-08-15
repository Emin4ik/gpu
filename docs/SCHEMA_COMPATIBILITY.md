# Schema compatibility policy

GPU Triage separates package-version compatibility from machine-readable schema compatibility.

## Package versions

The Python package is pre-1.0. Package releases use PEP 440 versions such as `0.2.0a1`. Before 1.0, CLI flags and Python internals may still change between minor/alpha releases when the change is documented in `CHANGELOG.md`.

## Versioned JSON contracts

Machine-readable contracts use explicit identifiers such as:

- `gputriage.report.v1`
- `gputriage.sanitized-bundle.v1`
- `gputriage.bundle-validation.v1`
- `gputriage.error.v1`
- `gputriage.export-result.v1`

For a given major schema version (`v1`):

- existing required fields will not be removed;
- field meanings will not be silently redefined;
- enum/result values will not be repurposed;
- additive optional fields are allowed;
- consumers should ignore unknown optional fields;
- producers should continue emitting all required fields defined by the checked-in schema.

A change that removes required fields, changes their type/meaning, or otherwise requires existing consumers to change must use a new major schema identifier such as `v2`.

## Incident inputs

The directory ingest format is still alpha. Recognized artifact filenames may grow additively. Explicit `incident.json` observations remain normal evidence objects; new required incident metadata will not be introduced without a documented migration path.

## Sanitized exports

A sanitized export is a normalized evidence interchange format, not a lossless incident archive. Raw artifacts and raw references are intentionally absent. Schema compatibility does not imply equivalent privacy guarantees across arbitrary custom observation values.

## Benchmarks

Frozen benchmark versions are immutable after first evaluation. A changed corpus or rubric is a new benchmark version and receives a new checksum. Benchmark versioning is independent of report schema versioning.
