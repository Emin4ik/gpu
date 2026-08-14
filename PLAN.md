# GPU Triage Development Plan

Last updated: 2026-08-14

## Product thesis

GPU Triage is an open, evidence-first diagnostic planner for AI/GPU infrastructure.
It should make existing tools work together rather than replace DCGM, GPUd, NCCL tools, UFM, Slurm, Linux diagnostics, or vendor control planes.

Core promise:

> Do not replace your GPU tools. Make them work together.

The product should answer three questions:

1. What does the current evidence actually support?
2. What important evidence is still missing?
3. Which diagnostic action should run next, and why?

## Non-goals

Early versions will not become another monitoring daemon, Prometheus/Grafana stack, scheduler, generic MCP gateway, LLM log chatbot, Kubernetes operator, or autonomous remediation system.

## Status

### M0 - Problem validation: DONE

Competitive research and a corpus of real cross-layer GPU infrastructure incidents established the wedge: diagnostic planning across existing tools, not another health scanner.

### M1 - Deterministic diagnosis core: DONE

Implemented observation -> hypothesis -> missing evidence -> next-test flow, qualitative hypothesis states, explicit abstention, causal confirmation rules, staged replay, and a structural holdout smoke set.

### M2 - Raw artifact ingestion: DONE

Implemented `lspci -vv`, `nvidia-smi -q`, NCCL log, IB/RoCE counter, directory ingest, and baseline support. Parsers extract facts but do not declare causality.

### M3 - Identity graph: DONE

Implemented rank/node/GPU/PCIe/HCA entities and relations, affected-path traversal, artifact scoping, rejection of unrelated hardware evidence, and explicit unresolved/ambiguous identity warnings.

### M4 - Automatic identity discovery: DONE (v0.1)

Implemented Slurm allocation parsing, runtime `rank-map.csv`, NVIDIA GPU UUID/index/PCI BDF inventory, GPU reconciliation, HCA identity, conservative GPU/NIC topology reconciliation, collection helper scripts, and `examples/auto_identity_case/`.

### M5 - Multi-device evidence model: DONE (v0.1)

Implemented multi-value entity-scoped evidence, multi-device PCIe/GPU/HCA parsing, raw evidence references, entity-aware baseline comparison, and affected-path filtering that prevents unrelated degraded devices from contaminating an investigation.

See [`docs/EVIDENCE_MODEL.md`](docs/EVIDENCE_MODEL.md).

### M6 - Explicit diagnostic test planner: DONE (v0.1)

Implemented a `DiagnosticTestSpec` registry with explicit eligibility, cost, invasiveness, duration, information value, expected outcomes, deterministic ranking, alternatives, and human-readable selection reasons.

Important boundary: scoring ranks **diagnostic actions**, not root-cause confidence.

### M7 - Cross-tool evidence adapters: DONE (v0.1)

Goal achieved: specialist/vendor and host-OS artifacts now feed the same identity-scoped evidence model without being promoted directly to root-cause verdicts.

#### M7 P0 - DCGM + NVIDIA system logs: DONE

Implemented:

- defensive DCGM JSON ingestion for diagnostic and health-style outputs;
- per-test status and failure facts with raw provenance;
- separation of DCGM execution/environment failures from hardware-class findings;
- GPU-local DCGM indexes reconciled to durable GPU UUID entities through the identity graph;
- ambiguous DCGM index mappings preserved as warnings instead of guessed;
- `journalctl` / `dmesg` parsing for NVIDIA XID records;
- BDF -> GPU UUID reconciliation from `NVRM: GPU at ...` lines;
- line-level raw references for XID/SXID events;
- conservative normalized facts for fallen-off-bus, memory/ECC-related, and NVLink-related events;
- SXID preservation for future NVSwitch topology support;
- affected-path filtering so an XID/DCGM finding on an unrelated GPU does not influence this incident;
- end-to-end `examples/m7_dcgm_xid_case/`.

See [`docs/ADAPTERS.md`](docs/ADAPTERS.md).

#### M7 P1 - Host IRQ / CPU affinity evidence: DONE

Implemented:

- `/proc/interrupts` parser with per-IRQ/per-CPU activity and raw line provenance;
- IRQ affinity artifact with configured and effective CPU sets;
- process/rank CPU-affinity artifact for communication roles;
- HCA/netdev/PCI identity attached to IRQ affinity;
- correlation only for active IRQs that map to an HCA/NIC on the affected rank path;
- effective IRQ CPU affinity preferred when available, falling back to configured affinity;
- derived `irq_shares_nccl_cpu` only when active IRQ + affected HCA + affected-rank communication CPU affinity are all known;
- `irq_affinity_clean` when comparable CPU sets are known and do not overlap;
- explicit evidence-gap warnings instead of guessed overlap when process/HCA/activity identity is missing;
- existing `host_cpu_irq_interference` playbook moves to `probable` from raw host artifacts;
- planner then selects `short_cpu_profile` as the causal confirmation step;
- collection helpers `scripts/capture_irq_affinity.sh` and `scripts/capture_process_affinity.sh`;
- end-to-end `examples/m7_irq_affinity_case/`.

See [`docs/HOST_AFFINITY.md`](docs/HOST_AFFINITY.md).

M7 v0.1 completion gate:

- GPU/vendor diagnostics, host event history, host IRQ/CPU evidence, and existing communication/fabric artifacts share one observation model;
- evidence keeps source/entity/raw provenance;
- mixed-source evidence changes planner state without bypassing confirmation rules;
- ambiguous identity links remain warnings/evidence gaps;
- imported tool findings are evidence, never unquestioned `confirmed` verdicts;
- full Python 3.10/3.12 CI plus staged/holdout replay remains green.

Deferred until after the benchmark unless a concrete case requires them:

- GPUd findings/output;
- NCCL Doctor findings;
- NVIDIA AICR snapshot/diff;
- richer NVLink/NVSwitch/Fabric Manager topology;
- UFM/NetQ exports;
- storage/data-loader specialist adapters.

Reason for deferral: M8 should now prove that the diagnostic-planning layer adds value before adapter breadth grows further.

## Next work

### M8 - Frozen blind benchmark: NEXT

Goal: decide objectively whether GPU Triage deserves continued development before adding more integrations or UI.

Build:

1. grow the incident corpus to at least 25-30 high-quality cases with source links and quality grades;
2. classify each case as confirmed root cause, strong causal evidence, or unresolved/symptom-only;
3. freeze a holdout set **before** tuning additional playbooks;
4. preserve staged evidence (`T0 symptom -> T1 cheap evidence -> T2 selected diagnostic -> T3 confirmation`) so future facts stay hidden;
5. include unsupported cases where correct behavior is abstention;
6. include misleading alerts, wrong-device evidence, ambiguous identities, and multi-cause incidents;
7. record which existing specialist tool already closes each case so GPU Triage is not rewarded for duplicate functionality.

Primary metrics:

- true root-cause domain among supported/top hypotheses;
- next-test utility;
- premature confirmation rate;
- correct abstention rate;
- diagnostic-action reduction;
- unnecessary tool-transition reduction;
- identity-scoping error rate;
- duplicate-value rate versus DCGM/GPUd/NCCL Doctor/etc.

Project gate:

- near-zero premature `confirmed` verdicts;
- useful next test on at least 70% of supported held-out cases;
- correct abstention on unsupported cases;
- meaningful reduction in manual diagnostic actions/tool transitions;
- clear value beyond restating specialist-tool output.

Rethink or kill the project if:

- most recommendations duplicate existing tools with little workflow reduction;
- identity mapping is too unreliable for causal correlation;
- adapter maintenance dominates diagnostic-knowledge development;
- useful diagnosis requires an always-on profiler for most incidents;
- confident false root-cause claims appear regularly.

### M9 - CLI alpha

Only after the M8 gate passes:

- stable incident directory format;
- `gputriage investigate <dir>`;
- machine-readable JSON report;
- human-readable terminal report;
- evidence references for every supported conclusion;
- explicit missing-evidence section;
- next-best-test command template;
- sanitized incident bundle export.

### M10 - Public alpha and integrations

Then consider:

- Slurm prolog/epilog collection helpers;
- Kubernetes identity adapter;
- adapter/plugin SDK;
- optional HTML report;
- versioned schemas;
- public example incident library;
- deferred GPUd/NCCL Doctor/AICR adapters where benchmark gaps justify them;
- first public alpha release.

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
   multi-device evidence store
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
 new evidence -> confirm / reject / keep multiple causes
```

## Immediate checkpoint

M8: freeze a real blind benchmark before expanding the product surface.

The important question is no longer “can we parse another tool?” It is:

> Given only the evidence an operator actually had at each stage, does GPU Triage choose a useful next diagnostic and avoid premature conclusions?

If the answer is yes on held-out real incidents, the project earns a CLI/public-alpha phase. If not, we should fix or stop the diagnostic model rather than hide the problem behind more adapters.
