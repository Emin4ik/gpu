# GPU Triage Development Plan

Last updated: 2026-08-15

## Product thesis

GPU Triage is an open, evidence-first diagnostic planner for AI/GPU infrastructure. It makes existing tools work together rather than replacing DCGM, GPUd, NCCL tooling, Slurm, fabric tooling, Linux diagnostics, or vendor control planes.

> Don't replace your GPU tools. Make them work together.

The planner should answer: what the evidence supports, what evidence is missing or contradictory, and which diagnostic action should run next and why.

## Non-goals

Early versions are not a monitoring daemon, Prometheus/Grafana stack, scheduler, generic MCP gateway, LLM log chatbot, Kubernetes operator, or autonomous remediation system.

## Milestone status

- **M0 Problem validation — DONE.** Competitive research and production incidents established the cross-tool diagnostic-planning wedge.
- **M1 Deterministic diagnosis core — DONE.** Observation → hypothesis → missing evidence → next test, qualitative states, abstention, causal confirmation.
- **M2 Raw artifact ingestion — DONE.** `lspci`, `nvidia-smi`, NCCL, IB/RoCE, baselines and directory ingest.
- **M3 Identity graph — DONE.** Rank/node/GPU/PCIe/HCA entities and affected-path scoping.
- **M4 Automatic identity discovery — DONE (v0.1).** Slurm/runtime rank mapping, GPU UUID/BDF and HCA topology.
- **M5 Multi-device evidence — DONE (v0.1).** Entity-scoped multi-value evidence and unrelated-device filtering.
- **M6 Diagnostic test planner — DONE (v0.1).** Explicit eligibility, cost, invasiveness, information value and deterministic ranking.
- **M7 Cross-tool adapters — DONE (v0.1).** DCGM, XID/SXID, `/proc/interrupts`, IRQ/process affinity and HCA-aware correlation.
- **M8.1 Negative evidence/completed-test memory — DONE.** Negative outcomes weaken/reject hypotheses and completed diagnostics cannot be selected again.

## M8 frozen benchmark program — PoC gate PASSED

### v0.1 baseline

The first frozen benchmark exposed failures in abstention and red-herring handling. The original result is retained in [`docs/M8_RESULTS_v0.1.md`](docs/M8_RESULTS_v0.1.md) and is not reused as a fresh blind claim.

### M8.2 / benchmark v0.2 — PASS

A new benchmark was sourced after M8.1 and frozen before its first execution:

- 24 scenarios total;
- 16 public source incidents;
- 8 adversarial/mutation scenarios;
- 12 development / 12 frozen holdout;
- frozen SHA-256: `3fba89e4f644630bf4dd4a6475af33e2215983d6ae59659980a1139bd21e32a0`.

No engine/planner change occurred between freeze and the first run.

| Metric | v0.2 first run | Gate | Result |
|---|---:|---:|---|
| Domain Recall@3 | 100% (10/10) | >= 75% | PASS |
| Next-test utility 2/2 | 100% (10/10) | >= 70% | PASS |
| Premature confirmation | 0% (0/22) | <= 5% | PASS |
| Abstention accuracy | 100% (7/7) | >= 90% | PASS |
| Forbidden/red-herring hypothesis error | 0% (0/10) | <= 5% | PASS |
| Median diagnostic-action reduction | 75% | >= 30% | PASS |
| Median tool-transition reduction | 100% | >= 50% | PASS |

This is a small, author-curated staged-replay engineering benchmark, not a claim of 100% real-world accuracy. Action/tool reductions are replay proxies and no live multi-node GPU cluster was used.

See [`docs/M8_RESULTS_v0.2.md`](docs/M8_RESULTS_v0.2.md), [`docs/M8_V0_2_SOURCES.md`](docs/M8_V0_2_SOURCES.md), and [`docs/BENCHMARK_V0_2_PROTOCOL.md`](docs/BENCHMARK_V0_2_PROTOCOL.md).

## Next work

### M9 — CLI alpha: NEXT / UNBLOCKED

Goal: turn the PoC core into a stable offline operator-facing CLI without adding monitoring or autonomous remediation.

Build:

1. versioned incident-directory contract (`incident.json` + optional raw artifacts);
2. stable `gputriage investigate <dir>` primary command;
3. `--format text|json` and a versioned JSON report schema;
4. report symptom, affected entities/path, hypotheses, supporting/contradicting/missing evidence, raw provenance, next-best test, alternatives, command template, cost, invasiveness and duration;
5. explicit result states: `confirmed`, `needs_evidence`, `abstain`;
6. `gputriage validate-bundle <dir>` for malformed/ambiguous artifacts without diagnosis;
7. sanitized bundle export that removes obvious host/job identifiers while retaining diagnostic structure;
8. stable exit codes suitable for scripts;
9. offline-by-default operation;
10. golden CLI tests for supported, contradictory, multi-device and unsupported incidents.

M9 exit criteria:

- documented incident bundle works end-to-end from raw artifacts to text and JSON reports;
- every supported conclusion has evidence provenance;
- unsupported inputs abstain cleanly;
- malformed bundles fail validation with actionable messages;
- diagnosis requires no network access;
- Python 3.10/3.12 CI and frozen v0.2 benchmark gate remain green.

### M10 — Public alpha and integrations

After M9: versioned public schemas, packaging/release workflow, public incident examples, Slurm collection helpers, optional Kubernetes identity, adapter/plugin SDK, optional static HTML report, and deferred specialist adapters only where real user cases justify them.

## Architecture target

```text
raw artifacts / specialist tools
            ↓
     parsers + adapters
            ↓
       identity graph
job → rank → node → GPU → PCIe → HCA/fabric
            ↓
 entity-scoped evidence
 + positive / negative evidence
 + completed-test results
            ↓
   affected-path filter
            ↓
        hypotheses
            ↓
 eligible diagnostic actions
            ↓
 transparent test ranking
        ↙          ↘
 next best test   abstain
        ↓
 new evidence → strengthen / weaken / reject / confirm
```

## Current decision

The project has earned the CLI-alpha phase. M8.2 passed every predefined PoC engineering gate on a fresh frozen staged-replay holdout without post-freeze tuning. M9 should now stabilize the operator interface and report contract rather than add more diagnosis rules or adapters.
