# M8 Frozen Benchmark v0.1 — First Run

Date: 2026-08-14

This is the first recorded run of the frozen `v0.1` holdout. The holdout was frozen before this run and is protected by SHA-256. Do not edit the v0.1 evidence or answer rubric in place after seeing these results; create a new benchmark version instead.

## Corpus

- 30 scenarios total
- 21 public source incidents
- 9 adversarial/mutation scenarios
- 18 development scenarios
- 12 frozen holdout scenarios
- frozen holdout SHA-256: `a95cea3e6adb3e260a449c6477cbd0d7f52249c1bbc8ebeb8ab07ba1bf512703`

The benchmark is staged replay, not a statistical accuracy claim and not a substitute for later real-hardware validation.

## Frozen holdout results

| Metric | Result | Gate | Status |
|---|---:|---:|---|
| Domain Recall@3 | 100% (9/9) | >= 75% | PASS |
| Next-test utility 2/2 | 81.8% (9/11) | >= 70% | PASS |
| Premature confirmation | 0% (0/19 stages) | <= 5% | PASS |
| Abstention accuracy | 80% (4/5) | >= 90% | **FAIL** |
| Forbidden-hypothesis error | 25% (1/4) | <= 5% | **FAIL** |
| Median diagnostic-action reduction | 33.3% (3 scored cases) | >= 30% | PASS |
| Median tool-transition reduction | 66.7% (3 scored cases) | >= 50% | PASS |
| Final confirmation | 100% (3/3 checked cases) | informational | — |

The safety gate is green because the frozen checksum matches and there were no premature `confirmed` verdicts. The full project gate is **not passed** because abstention and forbidden-hypothesis safety missed their thresholds.

## First-run gaps

### 1. Clean IRQ affinity still leaves host IRQ interference supported

Case: `MUT-HO-IRQ-CLEAN`

Observed behavior:

- expected: abstain after a known-clean affinity comparison;
- actual: planner selected `collect_irq_affinity` again;
- `host_cpu_irq_interference` remained `supported` even though the clean affinity evidence should weaken that path.

Needed change for a future engine version: model explicit negative/contradicting evidence for known-clean IRQ affinity and make collection tests ineligible once that evidence is already available.

### 2. Equal per-rank work still triggers the work-invariant collection test

Case: `MUT-HO-COLLECTIVE-EQUAL-WORK`

Observed behavior:

- actual next test: `compare_rank_work_invariants`;
- rubric: 0/2 because equal work is already known.

Needed change: represent the negative result (`per_rank_work_counts_equal`) and block redundant invariant collection.

### 3. Failed rollback still triggers another rollback

Case: `MUT-HO-SOFTWARE-ROLLBACK-FAIL`

Observed behavior:

- actual next test: `controlled_rollback_ab` after rollback has already failed to restore performance;
- rubric: 0/2.

Needed change: record negative controlled-test outcomes and explicitly weaken/reject the associated hypothesis or route to another domain instead of repeating the same test.

## What passed convincingly

- No premature root-cause confirmation on the frozen set.
- The expected domain remained in the top three active hypotheses on every scored domain check.
- More than 70% of scored next actions were directly useful.
- Curated replay proxies show fewer diagnostic actions and fewer tool-family transitions on the eligible cases.
- Compound and adversarial cases did not force a single root cause simply to produce an answer.

## Limitations

- Action-reduction and tool-transition metrics are curated replay proxies, not wall-clock measurements from engineers.
- The frozen set has 12 scenarios; it is an engineering gate, not a statistically powered evaluation.
- Some public incident reports expose only part of the investigation sequence, so action counts are approximate.
- Specialist overlap is annotated, but v0.1 does not yet compute a robust automated “duplicate value” score.
- No live cluster or real-hardware collection was used for this M8 replay.

## Decision

**Do not advance to M9 CLI alpha yet.**

The project shows enough signal to continue, but M8 v0.1 does not pass all gates. Next is **M8.1 gap remediation**:

1. add explicit negative-test outcomes to the evidence model;
2. prevent already-completed diagnostics from being selected again;
3. improve contradiction handling for clean IRQ affinity and failed confirmation tests;
4. add new development cases for these behaviors;
5. do not tune against frozen v0.1 cases;
6. after the fixes are stable, create a new independently frozen `v0.2` holdout before claiming the benchmark gate is passed.
