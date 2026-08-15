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
- **M8.2 Frozen benchmark v0.2 — PASS.** Fresh frozen holdout passed all predefined PoC engineering gates.
- **M9 CLI alpha — DONE.** Stable offline investigation/validation/report/export contract with golden tests.
- **M10 public alpha engineering — RELEASE CANDIDATE READY.** `0.2.0a1` package candidate builds, validates, installs cleanly and retains the frozen benchmark gate. Tag/pre-release publication remains pending.

## M8 frozen benchmark program — PoC gate PASSED

The v0.1 baseline exposed abstention and red-herring gaps. Those results remain recorded and were not reused as a blind claim. M8.1 fixed the general negative-evidence/completed-test model, then benchmark v0.2 was independently sourced and frozen before execution.

M8.2 v0.2:

- 24 scenarios total;
- 16 public source incidents;
- 8 adversarial/mutation scenarios;
- 12 development / 12 frozen holdout;
- frozen SHA-256: `3fba89e4f644630bf4dd4a6475af33e2215983d6ae59659980a1139bd21e32a0`.

| Metric | v0.2 first run | Gate | Result |
|---|---:|---:|---|
| Domain Recall@3 | 100% (10/10) | >= 75% | PASS |
| Next-test utility 2/2 | 100% (10/10) | >= 70% | PASS |
| Premature confirmation | 0% (0/22) | <= 5% | PASS |
| Abstention accuracy | 100% (7/7) | >= 90% | PASS |
| Forbidden/red-herring hypothesis error | 0% (0/10) | <= 5% | PASS |
| Median diagnostic-action reduction | 75% | >= 30% | PASS |
| Median tool-transition reduction | 100% | >= 50% | PASS |

This is a small author-curated staged-replay engineering benchmark, not a real-world accuracy claim. No live multi-node GPU cluster was used.

See [`docs/M8_RESULTS_v0.2.md`](docs/M8_RESULTS_v0.2.md), [`docs/M8_V0_2_SOURCES.md`](docs/M8_V0_2_SOURCES.md), and [`docs/BENCHMARK_V0_2_PROTOCOL.md`](docs/BENCHMARK_V0_2_PROTOCOL.md).

## M9 — CLI alpha: DONE

Implemented:

1. `gputriage investigate <dir|incident.json>` with text/JSON output;
2. versioned `gputriage.report.v1` report contract;
3. explicit `confirmed`, `needs_evidence`, and `abstain` states with stable exit codes;
4. `gputriage validate-bundle`;
5. `gputriage export-sanitized`;
6. evidence provenance, contradictory/missing evidence, next-test metadata and alternatives;
7. offline-by-default operation with no SSH/API/upload collection;
8. golden CLI and sanitization tests.

See [`docs/CLI.md`](docs/CLI.md).

## M10 — Public alpha: RELEASE CANDIDATE READY

Candidate version: **`0.2.0a1`**.

Completed engineering work:

1. package metadata and `gputriage --version` use the same pre-release version;
2. wheel and sdist build in CI;
3. `twine check` validates distribution metadata;
4. built wheel is installed into a clean virtual environment and smoke-tested;
5. validated distributions are uploaded as CI artifacts;
6. Apache-2.0 `LICENSE`, `CHANGELOG.md`, `CONTRIBUTING.md`, and `SECURITY.md` are present;
7. `docs/PUBLIC_ALPHA.md` provides a compact outside-user quickstart with a sanitized public example;
8. `docs/SCHEMA_COMPATIBILITY.md` defines v1 compatibility rules independently of package pre-1.0 evolution;
9. privacy/security boundaries explicitly state that sanitized export is not DLP, secret detection, or guaranteed anonymization;
10. `.github/workflows/release.yml` is manual-only and refuses tag/version mismatch or replacement of an existing release;
11. release candidates must pass unit tests, frozen M8.2 `--enforce-gates`, build validation, and clean-wheel installation before GitHub pre-release creation;
12. PyPI publishing and credentials remain intentionally out of scope.

Validation checkpoint on the M10 branch passed Python 3.10/3.12 tests, frozen M8.2 gate, wheel/sdist build, `twine check`, clean-wheel install, version check and public-example smoke test.

### Remaining publication step

Create the first GitHub tag/pre-release `v0.2.0a1` by explicitly running the checked-in `public-alpha-release` workflow from the validated release-candidate commit. Publication should not weaken or bypass the same frozen gate.

The current connector/runtime cannot dispatch or create a GitHub release directly, so the repository records the candidate as **ready, not yet published**.

## After publication — outside-user validation

The main remaining uncertainty is no longer package mechanics; it is external usefulness. Priorities after the first pre-release:

- have real operators run sanitized or local incident bundles;
- record where evidence collection, identity mapping, next-test wording, or abstention is confusing;
- add adapters/playbooks only for demonstrated user/benchmark gaps;
- measure whether the tool reduces diagnostic actions and tool transitions in real workflows;
- create a new independent benchmark version before stronger quality claims after material model changes.

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
            ↓
 validated wheel/sdist + manual pre-release gate
```

## Current decision

M10 engineering work has produced a validated `0.2.0a1` release candidate without adding diagnostic breadth or weakening the frozen benchmark. The next irreversible step is publishing the GitHub pre-release; after that, development should prioritize real operator feedback over speculative features.
