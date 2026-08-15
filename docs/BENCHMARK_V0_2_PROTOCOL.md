# M8.2 Frozen Benchmark Protocol

## Rule

The `benchmark_holdout_v0.2` payload is immutable after its first evaluation.

1. Build new source and mutation scenarios.
2. Split development and holdout before evaluation.
3. Serialize the holdout deterministically.
4. Compute SHA-256 on the uncompressed JSON bytes.
5. Commit corpus and freeze metadata before any holdout evaluator run.
6. Run the frozen set once with the existing engine.
7. Record all gate failures as findings.
8. Never repair v0.2 by editing evidence, expected answers, or thresholds in place.

If the engine changes after this run, a future quality claim requires a newly sourced and frozen benchmark version.

## v0.2 freeze

SHA-256: `3fba89e4f644630bf4dd4a6475af33e2215983d6ae59659980a1139bd21e32a0`

Frozen holdout cases: 12.
