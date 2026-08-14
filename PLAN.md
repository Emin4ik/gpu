# GPU Triage Development Plan

Last updated: 2026-08-14

## Product thesis

GPU Triage is an open, evidence-first diagnostic planner for AI/GPU infrastructure. It should make existing tools work together rather than replace DCGM, GPUd, NCCL tooling, Slurm, fabric tooling, Linux diagnostics, or vendor control planes.

Core promise:

> Do not replace your GPU tools. Make them work together.

The planner should answer:

1. What does the current evidence actually support?
2. What important evidence is missing or contradicting the current hypotheses?
3. Which diagnostic action should run next, and why?

## Non-goals

Early versions are not another monitoring daemon, Prometheus/Grafana stack, scheduler, generic MCP gateway, LLM log chatbot, Kubernetes operator, or autonomous remediation system.

## Milestone status

### M0 — Problem validation: DONE

Competitive research and public production incidents established the wedge: cross-tool diagnostic planning, not another health scanner.

### M1 — Deterministic diagnosis core: DONE

Observation -> hypothesis -> missing evidence -> next-test flow; qualitative hypothesis states; explicit abstention; confirmation only after causal-grade evidence.

### M2 — Raw artifact ingestion: DONE

`lspci -vv`, `nvidia-smi -q`, NCCL logs, IB/RoCE counters, directory ingest, and baseline comparison.

### M3 — Identity graph: DONE

Rank/node/GPU/PCIe/HCA entities, affected-path traversal, artifact scoping, and rejection of unrelated hardware evidence.

### M4 — Automatic identity discovery: DONE (v0.1)

Slurm allocation, runtime rank mapping, GPU UUID/index/PCI BDF inventory, HCA identity, and conservative GPU/NIC topology reconciliation.

### M5 — Multi-device evidence model: DONE (v0.1)

Entity-scoped multi-value evidence, same-device fact pairing, raw evidence references, and affected-path filtering. See [`docs/EVIDENCE_MODEL.md`](docs/EVIDENCE_MODEL.md).

### M6 — Explicit diagnostic test planner: DONE (v0.1)

Independent test registry with eligibility, cost, invasiveness, duration, information value, expected outcomes, alternatives, and deterministic ranking. Scores rank actions, not root-cause confidence.

### M7 — Cross-tool evidence adapters: DONE (v0.1)

Implemented DCGM diagnostic/health ingestion, NVIDIA XID/SXID history, `/proc/interrupts`, IRQ affinity, communication-process affinity, and HCA-aware CPU overlap. Vendor findings remain evidence rather than automatic root-cause verdicts.

See [`docs/ADAPTERS.md`](docs/ADAPTERS.md) and [`docs/HOST_AFFINITY.md`](docs/HOST_AFFINITY.md).

### M8 — Frozen blind benchmark: BASELINE COMPLETE (v0.1)

The benchmark infrastructure and first frozen run are complete.

Corpus:

- 30 scenarios total;
- 21 public source incidents;
- 9 adversarial/mutation scenarios;
- 18 development scenarios;
- 12 frozen holdout scenarios.

The frozen `v0.1` holdout was checksummed **before** its first run. It must not be edited or re-rubriced in place after seeing the results. A new evaluation requires a new benchmark version.

First frozen holdout result:

| Metric | v0.1 | Gate | Result |
|---|---:|---:|---|
| Domain Recall@3 | 100% (9/9) | >= 75% | PASS |
| Next-test utility 2/2 | 81.8% (9/11) | >= 70% | PASS |
| Premature confirmation | 0% (0/19 stages) | <= 5% | PASS |
| Abstention accuracy | 80% (4/5) | >= 90% | **FAIL** |
| Forbidden-hypothesis error | 25% (1/4) | <= 5% | **FAIL** |
| Median diagnostic-action reduction | 33.3% | >= 30% | PASS |
| Median tool-transition reduction | 66.7% | >= 50% | PASS |

Safety is green: frozen checksum verified and no premature `confirmed` verdicts occurred. The **full M8 project gate is not passed**, because abstention and red-herring/forbidden-hypothesis handling missed their thresholds.

The first-run gaps are deliberately retained as benchmark findings:

1. known-clean IRQ affinity still leaves `host_cpu_irq_interference` supported and can cause redundant `collect_irq_affinity`;
2. known-equal per-rank work can still trigger `compare_rank_work_invariants`;
3. a failed rollback can still trigger `controlled_rollback_ab` again.

See [`docs/BENCHMARK.md`](docs/BENCHMARK.md) and [`docs/M8_RESULTS_v0.1.md`](docs/M8_RESULTS_v0.1.md).

## Next work

### M8.1 — Negative evidence and completed-test memory: NEXT

Do **not** tune against the frozen v0.1 holdout. Fix the general diagnostic model using new development cases only.

Build:

1. explicit negative/contradicting observations for completed diagnostics, e.g. clean IRQ affinity, equal rank work, healthy targeted validation, failed rollback, clean fabric/PCIe checks;
2. completed-test/result memory so a diagnostic that already answered its question cannot be selected again;
3. hypothesis weakening/rejection rules driven by negative controlled-test outcomes;
4. planner prerequisites that distinguish “missing evidence” from “evidence already collected and negative”;
5. new development mutations for redundant-test prevention and hypothesis reversal;
6. deterministic state-transition tests for `supported -> possible/rejected` where negative evidence warrants it.

Exit criteria:

- all new development regressions pass;
- no change to `benchmark_holdout_v0.1` or its freeze hash;
- old unit/staged regressions remain green;
- no new path to premature confirmation.

### M8.2 — New independently frozen benchmark v0.2

Only after M8.1 stabilizes:

1. add or replace public incidents without exposing the new answer rubric to rule tuning;
2. build a new holdout split;
3. freeze it under a new SHA-256 before running it;
4. run once and record all pass/fail gates;
5. advance to M9 only if the full gate passes.

### M9 — CLI alpha: BLOCKED BY M8 GATE

Once the benchmark gate passes:

- stable incident directory format;
- `gputriage investigate <dir>`;
- machine-readable JSON report;
- human-readable terminal report;
- evidence references and missing/contradicting evidence;
- next-best-test command template;
- sanitized incident-bundle export.

### M10 — Public alpha and integrations

After M9: Slurm collection helpers, optional Kubernetes identity adapter, adapter/plugin SDK, optional HTML report, versioned schemas, public examples, and deferred specialist adapters only where benchmark gaps justify them.

Later, only if users demand it: live SSH collection, historical incident DB, fleet baselines, MCP exposure, LLM explanation layer, web UI, notifications, enterprise integrations, and safe remediation suggestions.

## Architecture target

```text
raw artifacts / specialist tools
            |
            v
     parsers + adapters
            |
            v
       identity graph
job -> rank -> node -> GPU -> PCIe -> HCA/fabric
            |
            v
   entity-scoped evidence
   + positive evidence
   + negative evidence      <- M8.1
   + completed test results <- M8.1
            |
            v
       affected-path filter
            |
            v
        hypotheses
            |
            v
 eligible diagnostic actions
            |
            v
 transparent test ranking
        /          \
       v            v
 next best test   abstain
       |
       v
 new evidence -> strengthen / weaken / reject / confirm
```

## Current decision

The v0.1 benchmark gives enough signal to continue the project, but not enough to advance to CLI alpha. The next engineering priority is **better handling of negative evidence and already-completed diagnostics**, followed by a fresh independently frozen v0.2 benchmark.
