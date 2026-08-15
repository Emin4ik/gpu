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
- **M9 CLI alpha — DONE.** Stable offline investigation/validation/report/export contract with golden tests.

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

## M9 — CLI alpha: DONE

M9 turns the diagnostic core into an offline operator-facing interface without changing the product into a collector or monitoring service.

Implemented:

1. `gputriage investigate <dir|incident.json>` with `--format text|json`;
2. backward-compatible positional single-file invocation;
3. versioned machine-readable `gputriage.report.v1` payload and [`schemas/report-v1.schema.json`](schemas/report-v1.schema.json);
4. explicit `confirmed`, `needs_evidence`, and `abstain` result states;
5. stable shell exit codes: `0` confirmed/success, `10` needs evidence, `20` abstain, `2` invalid input/export;
6. report fields for hypotheses, supporting/contradicting/missing evidence, affected entities, warnings, normalized evidence provenance, next test, alternatives, command template, cost, invasiveness and duration;
7. `gputriage validate-bundle <dir>` with actionable metadata/ingestion errors and no diagnosis;
8. `gputriage export-sanitized <dir> <output.json>`;
9. sanitized export copies no raw artifact bytes, removes `raw_ref`, pseudonymizes known identity-graph identifiers, and omits free-text symptom text by default;
10. exported normalized evidence can be replayed by `gputriage investigate sanitized.json`;
11. report and sanitized-bundle JSON schemas;
12. golden tests for confirmed, needs-evidence, abstention, malformed/empty bundles, legacy input, pseudonymization, replay and no-overwrite behavior;
13. offline-by-default operation: current CLI performs no SSH/API/upload collection.

See [`docs/CLI.md`](docs/CLI.md).

Privacy boundary: sanitized export is a conservative normalized-evidence export, **not** a general DLP/secret/PII scanner. Arbitrary string-valued evidence should still be reviewed before public sharing.

M9 exit criteria are met: supported conclusions retain evidence provenance, unsupported inputs abstain, malformed bundles fail validation, diagnosis requires no network, and Python 3.10/3.12 CI plus the frozen v0.2 gate remain green.

## Next work

### M10 — Public alpha: NEXT

Goal: make the current CLI alpha installable, understandable and safe for outside users before adding new diagnostic breadth.

P0 release work:

1. choose and stamp a public alpha version (`0.x` pre-release) consistently in package metadata and CLI `--version`;
2. verify/build wheel and sdist in CI and install-test the built wheel in a clean environment;
3. add/verify repository license, changelog and contribution guidance;
4. publish a compact public quickstart using sanitized example bundles;
5. add a public schema/version compatibility policy for incident/report/sanitized-bundle formats;
6. document privacy/security boundaries and what sanitized export does **not** guarantee;
7. add a release GitHub Actions workflow that builds artifacts and can create a GitHub pre-release when explicitly triggered;
8. keep PyPI publishing/manual release credentials out of scope unless explicitly requested;
9. keep the frozen v0.2 gate mandatory on release candidates;
10. create the first tagged public alpha only after package-install smoke tests are green.

P1 after first outside usage:

- improve bundle collection helpers from actual user friction;
- add adapters only for benchmark/user cases that demonstrate missing value;
- consider Kubernetes identity and an adapter/plugin SDK;
- optional static HTML report;
- build a new independent benchmark version before making stronger quality claims after material engine changes.

Do **not** prioritize before external feedback:

- web dashboard;
- daemon/Prometheus stack;
- live SSH fleet collection;
- generic LLM/MCP layer;
- autonomous remediation;
- broad adapter count for its own sake.

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
            ↓
   versioned CLI/report contract
```

## Current decision

M8.2 passed the predefined PoC engineering gate and M9 has stabilized the offline operator contract. The next milestone is **M10 public alpha packaging/release hygiene**, not more diagnosis rules. The main remaining uncertainty is now external usefulness: whether real operators find the workflow materially faster and clearer on their own incident artifacts.
