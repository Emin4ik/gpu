# GPU Triage Development Plan

Last updated: 2026-08-15

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

See [`docs/BENCHMARK.md`](docs/BENCHMARK.md) and [`docs/M8_RESULTS_v0.1.md`](docs/M8_RESULTS_v0.1.md).

### M8.1 — Negative evidence and completed-test memory: DONE

M8.1 fixes the general model behind the first benchmark gaps without editing the frozen `v0.1` corpus.

Implemented:

- `EvidenceIndex.has(key)` so “not collected” is distinct from “collected and clean/negative”;
- per-diagnostic `completion_keys`;
- generic `test_completed.<diagnostic_id> = true` memory that blocks re-selection without inventing an outcome;
- negative controlled-test outcomes that weaken or reject hypotheses;
- explicit negative handling for IRQ affinity, CPU profile, rank-work invariants, software rollback, targeted NCCL validation, storage/data-path A/B, thermal recovery, fabric validation and related checks;
- planner behavior that does not repeat a diagnostic whose question has already been answered;
- new development regressions for clean IRQ affinity, equal per-rank work, failed rollback, healthy targeted NCCL, generic completed-test memory and failed data-path A/B.

Key state transitions now include:

```text
supported/probable hypothesis
        +
negative diagnostic result
        ↓
possible / rejected
        +
test marked complete
        ↓
planner cannot select the same diagnostic again
```

Full CI remains green on Python 3.10 and 3.12, including unit tests, staged replay, structural holdout replay, M8 development safety and frozen `v0.1` checksum/safety validation.

Important benchmark discipline: the `v0.1` first-run scores remain the recorded baseline. After seeing them, `v0.1` is no longer a blind evaluation set for future model-quality claims.

See [`docs/M8_1_NEGATIVE_EVIDENCE.md`](docs/M8_1_NEGATIVE_EVIDENCE.md).

## Next work

### M8.2 — New independently frozen benchmark v0.2: NEXT

Goal: obtain a fresh measurement after M8.1 without reusing the already-observed v0.1 answers.

Build:

1. source additional public incidents not used to design the M8.1 changes;
2. include supported, unsupported, red-herring, wrong-device, multi-cause and negative-test scenarios;
3. keep the answer rubric separate from engine development;
4. create a new development/frozen split;
5. SHA-256 freeze the new holdout before any run;
6. run the frozen split once and record every pass/fail gate;
7. advance to M9 only if the full M8 gate passes.

M8.2 gates remain:

- Domain Recall@3 >= 75%;
- useful next-test 2/2 rate >= 70%;
- premature confirmation <= 5%, with a target of 0%;
- abstention accuracy >= 90%;
- forbidden/red-herring hypothesis error <= 5%;
- median diagnostic-action reduction >= 30%;
- median tool-transition reduction >= 50%.

If v0.2 misses the gate, record the miss and continue diagnosis-model work under a new development set. Do not rewrite the frozen v0.2 holdout.

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
   + negative evidence
   + completed test results
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

M8.1 is complete. The project still has enough signal to continue, but M9 remains blocked until a **new independently frozen M8.2 benchmark** passes the full gate. The immediate next task is therefore benchmark v0.2 construction and freeze, not more adapters or UI.
