# M8 Frozen Benchmark v0.2 — First Blind Run

Date: 2026-08-15

This records the first evaluation of the frozen `v0.2` holdout after M8.1. The holdout was serialized and SHA-256 frozen before execution. No engine or planner changes were made between freeze and the first run.

## Corpus

- 24 staged scenarios total
- 16 public source incidents
- 8 adversarial/mutation scenarios
- 12 development scenarios
- 12 frozen holdout scenarios
- frozen holdout SHA-256: `3fba89e4f644630bf4dd4a6475af33e2215983d6ae59659980a1139bd21e32a0`

See [`M8_V0_2_SOURCES.md`](M8_V0_2_SOURCES.md) and [`BENCHMARK_V0_2_PROTOCOL.md`](BENCHMARK_V0_2_PROTOCOL.md).

## First frozen holdout result

| Metric | First-run result | Gate | Status |
|---|---:|---:|---|
| Domain Recall@3 | 100% (10/10) | >= 75% | PASS |
| Next-test utility 2/2 | 100% (10/10) | >= 70% | PASS |
| Premature confirmation | 0% (0/22 stages) | <= 5% | PASS |
| Abstention accuracy | 100% (7/7) | >= 90% | PASS |
| Forbidden/red-herring hypothesis error | 0% (0/10) | <= 5% | PASS |
| Median diagnostic-action reduction | 75% (5 scored cases) | >= 30% | PASS |
| Median tool-transition reduction | 100% (5 scored cases) | >= 50% | PASS |
| Final confirmation | 100% (5/5 checked cases) | informational | — |

Freeze verification returned `true`, and the evaluator reported no failures on the frozen v0.2 split.

## What v0.2 tested

The fresh holdout includes supported collective-work/invariant incidents, software/version regressions with known-good controls, a physical NIC/fabric failure, unsupported bootstrap/hostname/duplicate-device/OOM-desynchronization classes where abstention is expected, and negative-result mutations that require hypothesis reversal and prohibit repeating a completed diagnostic.

The v0.1 failure modes did not recur: abstention was 7/7 and forbidden-hypothesis checks were 10/10 clean.

## Interpretation

**The predefined M8.2 engineering gate passes.** This unblocks M9 CLI alpha.

This is not a claim of 100% real-world diagnostic accuracy. The holdout has only 12 scenarios, consists of curated staged replays from public incident reports, was selected and encoded by the project authors, and uses replay proxies rather than engineer wall-clock measurements for action/tool reduction. No live multi-node GPU cluster was used.

The narrower claim is: **on the frozen v0.2 staged replay, the current planner passed every predefined engineering gate without post-freeze tuning.**

## Decision

M8.2 is complete and the M8 PoC progression gate is passed. The frozen v0.2 corpus remains immutable. Future engine versions may replay it for regression visibility, but any new blind quality claim requires a newly sourced and frozen benchmark version.
