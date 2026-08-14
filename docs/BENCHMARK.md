# M8 Frozen Blind Benchmark

GPU Triage M8 is an engineering benchmark for the diagnostic-planning loop. It is designed to test whether the planner reduces uncertainty safely from staged evidence without requiring access to a live GPU cluster.

This benchmark is **not** a statistically generalizable accuracy claim and is not a substitute for later validation on real hardware.

## Dataset v0.1

`benchmark_manifest_v0.1.json` records the provenance and split for every scenario.

- 30 total scenarios
- 21 public source incidents
- 9 adversarial/mutation scenarios derived from those incidents
- 18 development scenarios
- 12 frozen holdout scenarios

The source incidents come from public production/engineering reports covering thermal and frequency degradation, PCIe faults, physical fabric faults, CPU/IRQ interference, storage/data starvation, software/config regressions, collective-work divergence, application/runtime stalls, and misleading alerts.

Each source case keeps a source URL and quality grade. Mutation cases change one causal fact or inject misleading evidence while retaining the source incident as provenance.

## What "blind" means here

The evaluator can read the answer rubric, but `investigate()` receives only:

1. the symptom text; and
2. observations accumulated up to the current stage.

Evidence from later stages is never passed to the planner when it chooses an earlier action. This is staged replay, not a double-blind human study.

Typical sequence:

```text
T0/T1 symptom + cheap evidence
          |
          v
     planner decision
          |
          v
T2 result of the selected diagnostic
          |
          v
     planner decision
          |
          v
T3 causal confirmation / rejection
```

## Frozen holdout policy

`data/benchmark_holdout_v0.1.json.gz` is frozen by SHA-256 in:

`data/benchmark_holdout_v0.1.freeze.json`

After its first evaluation, **do not edit the v0.1 holdout evidence or answer rubric in place**. If a case is wrong, ambiguous, or needs a better rubric, document the issue and create a new benchmark version. Do not tune a rule on a holdout case and then report the same holdout result as unbiased.

The corpus is stored as deterministic gzip for repository compactness; the freeze hashes the decompressed JSON bytes, so recompression cannot change the benchmark identity. The freeze protects the whole JSON payload, including expected hypotheses and next-test utility rubrics.

## Scenario classes

### Supported source cases

The current engine is expected to identify the correct diagnostic domain and choose a useful next test without confirming a root cause too early.

### Unsupported source cases

These test abstention. Examples include runtime/JIT stalls and dependency propagation that current playbooks do not model directly.

### Adversarial mutations

Mutations test causal sensitivity and resistance to red herrings. Examples include:

- healthy affected PCIe path while another domain is abnormal;
- clean IRQ affinity after an apparent communication slowdown;
- a DCGM execution failure that must not become a hardware verdict;
- equal per-rank work when a collective-invariant hypothesis would otherwise be tempting;
- a failed rollback that should prevent blindly repeating the same software test;
- unknown noisy incidents that should remain unsupported.

## Metrics

### Domain Recall@3

For stages marked `domain_check`, the expected root-cause domain should be among the top three active hypotheses.

Initial gate: **>= 75%**.

For compound cases, `domain_label_recall` also measures how many expected causal domains are retained.

### Next-Test Utility

The rubric scores the planner's selected action:

- `2` = directly useful / matches a reasonable next diagnostic;
- `1` = useful but less efficient or less discriminative;
- `0` = redundant, irrelevant, or harmful to the investigation sequence.

Initial gate: at least **70%** of scored decisions should receive `2/2`.

Abstention stages are measured separately and are not counted as next-test utility checks.

### Premature Confirmation

Any `confirmed` hypothesis before a stage explicitly marked as causal confirmation is a safety failure.

Target: **0%**. Initial hard ceiling: **5%**.

### Abstention Accuracy

Unsupported cases should return no root-cause verdict and no registered diagnostic action when the current knowledge base cannot reduce uncertainty safely.

The v0.1 engineering gate is **>= 90%** on marked abstention stages.

### Diagnostic Action Reduction

For source cases where the public investigation supports a defensible diagnostic sequence, the manifest records an approximate human/source action count. The benchmark compares it with the number of planner-selected actions before confirmation.

Initial gate: median reduction **>= 30%**.

This is a curated replay proxy, not a wall-clock user study.

### Tool-Transition Reduction

For eligible cases, the source sequence is reduced to tool families and compared with the planner's selected tool families.

Initial gate: median transition reduction **>= 50%**.

This is also a replay proxy; a later engineer study should measure real context-switching cost.

### Forbidden-Hypothesis Error Rate

Adversarial cases may declare hypotheses that must not become `supported`, `probable`, or `confirmed` under the supplied evidence. This catches red-herring promotion and causal-scope mistakes.

Initial gate: **<= 5%**.

Raw artifact identity-scoping is additionally covered by the existing identity/ingest regression suite; this metric is not a replacement for those tests.

### Specialist Overlap

Cases annotate tools that already solve or substantially explain the incident (for example DCGM, ARGUS, a framework profiler, or storage telemetry). v0.1 reports coverage/overlap annotations; it does **not** yet claim a robust automated duplicate-value score.

The M8 decision should consider whether GPU Triage shortens the cross-tool workflow rather than merely repeating a specialist tool's conclusion.

## Storage format

The two corpora are committed as `.json.gz` files to keep the repository small. Inspect them with `gzip -dc data/benchmark_holdout_v0.1.json.gz | less` or any gzip-capable JSON tool. The manifest remains plain JSON for browser inspection.

## Commands

Development replay:

```bash
gputriage-benchmark data/benchmark_dev_v0.1.json.gz
```

Frozen holdout replay:

```bash
gputriage-benchmark \
  data/benchmark_holdout_v0.1.json.gz \
  --freeze data/benchmark_holdout_v0.1.freeze.json
```

Safety-only CI gate:

```bash
gputriage-benchmark \
  data/benchmark_holdout_v0.1.json.gz \
  --freeze data/benchmark_holdout_v0.1.freeze.json \
  --enforce-safety
```

Full project gates can be checked explicitly with `--enforce-gates`. They are intentionally not used to make the normal CI green by tuning the frozen set; a failed quality gate is an M8 result to investigate, not a test fixture to rewrite.

## Interpretation rules

1. Never tune the engine to a frozen v0.1 case and then call the rerun unbiased.
2. A safe abstention is better than a confident wrong cause.
3. `confirmed` requires confirmation-grade evidence, not a vendor warning or a correlated metric.
4. A benchmark win is valuable only if it reduces diagnostic work beyond what the specialist source tool already provides.
5. Synthetic/mutation artifacts test causal logic; they do not prove that collection works on every hardware generation.
6. Real-cluster validation remains a later milestone after the replay benchmark demonstrates enough value to justify the cost.
