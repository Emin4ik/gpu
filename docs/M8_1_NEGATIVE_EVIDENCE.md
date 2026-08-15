# M8.1 — Negative Evidence and Completed-Test Memory

Date: 2026-08-15

M8.1 addresses a structural gap found by the first frozen M8 benchmark: the engine understood positive evidence and missing evidence, but did not consistently remember that a diagnostic had already been completed with a negative result.

## What changed

### Evidence presence

`EvidenceIndex.has(key)` distinguishes:

- a fact that has never been collected;
- a fact that was collected and has a negative/clean outcome.

This matters because "missing" and "checked clean" must lead to different planner behavior.

### Completed diagnostic memory

Every diagnostic test may define `completion_keys`. If any completion key is present, that diagnostic is no longer eligible.

A generic marker is also supported:

```text
test_completed.<diagnostic_test_id> = true
```

This blocks re-selection even when an adapter has not yet normalized the detailed outcome.

### Negative evidence transitions

The engine now models negative controlled-test outcomes explicitly. Examples:

- `irq_affinity_clean` rejects the IRQ-overlap path when no overlap is present;
- `per_rank_work_counts_equal` rejects the work-invariant explanation when differing work is absent;
- `rollback_did_not_restore_performance` rejects the software/config rollback hypothesis;
- `targeted_nccl_validation_healthy` rejects PCIe degradation as the causal root cause even if a downtrained link exists;
- `data_path_ab_did_not_restore_performance` rejects storage/data starvation as the causal root cause;
- clean/negative thermal, CPU-profile, fabric and invariant validation signals weaken or reject their owning hypotheses instead of being treated as missing evidence.

## Safety rule

Positive confirmation always wins only when confirmation-grade positive evidence is actually present. A generic `test_completed.*` marker never fabricates an outcome or changes a hypothesis status by itself; it only prevents repeating the same diagnostic.

## Regression coverage

New M8.1 tests cover:

1. clean IRQ affinity;
2. equal per-rank work;
3. failed rollback;
4. healthy targeted NCCL validation despite a downtrained PCIe link;
5. generic completed-test memory;
6. negative controlled data-path validation.

The full repository CI remains green on Python 3.10 and 3.12, including unit tests, staged replay, structural holdout replay and frozen M8 safety/checksum validation.

## Benchmark discipline

The frozen M8 `v0.1` holdout is not edited and is not treated as a new blind measurement after these changes. Its original first-run result remains the recorded baseline.

The next meaningful measurement is **M8.2**: construct a new holdout, freeze it before execution, and run it once under a new benchmark version.
