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

### M7 - Evidence adapters: IN PROGRESS

Goal: consume strong specialist tools as evidence providers instead of reimplementing them.

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
- end-to-end `examples/m7_dcgm_xid_case/`;
- regression coverage for DCGM execution-vs-hardware semantics and adapter identity safety.

See [`docs/ADAPTERS.md`](docs/ADAPTERS.md).

Exit criteria achieved for P0:

- structured vendor diagnostics and host event history feed the same evidence model;
- imported evidence preserves source/entity/raw provenance;
- vendor failures are not silently promoted to `confirmed` root causes;
- unresolved local GPU indexes do not bypass identity scoping.

#### M7 P1 - Host IRQ / CPU affinity evidence: NEXT

Goal: give the existing `host_cpu_irq_interference` playbook real host artifacts instead of manually normalized facts.

Build:

1. `/proc/interrupts` parser;
2. IRQ affinity parser (`/proc/irq/*/smp_affinity_list` or collected equivalent);
3. process/thread CPU affinity artifact (`taskset -pc`, launcher/NCCL thread metadata where available);
4. NIC/netdev -> IRQ -> CPU mapping through HCA/netdev identity;
5. normalized facts such as `nic_irq_cpus`, `process_allowed_cpus`, and a derived `irq_shares_nccl_cpu` observation only when both sides are known;
6. raw references and explicit ambiguity warnings;
7. end-to-end fixture with one conflicting and one clean affinity layout.

Exit criteria:

- engine can move host IRQ hypothesis from `supported` to `probable` using raw host artifacts;
- CPU/IRQ evidence is tied to the affected NIC/node, not just any interrupt on the host;
- missing process-thread identity results in an evidence gap rather than a guessed overlap.

#### M7 P2 - Specialist tool imports

After P1, add only adapters that materially reduce manual tool transitions:

- GPUd findings/output;
- NCCL Doctor evidence/findings;
- NVIDIA AICR snapshot/diff;
- selected NVLink/NVSwitch/Fabric Manager evidence;
- UFM/NetQ exported evidence where available;
- simple storage/data-loader evidence.

Principle: consume specialist conclusions as **evidence**, never as unquestioned truth.

M7 completion gate:

- at least three distinct evidence domains feed the shared model (GPU/vendor diagnostic, host OS, and communication/fabric or config);
- mixed-source evidence changes planner decisions in deterministic tests;
- adapter maintenance remains smaller than diagnostic-knowledge development.

### M8 - Frozen blind benchmark

Grow the incident corpus to at least 25-30 high-quality cases and freeze a meaningful holdout before tuning more playbooks.

Measure:

- true-domain coverage among supported hypotheses;
- next-test utility;
- premature confirmation rate;
- correct abstention rate;
- diagnostic-action reduction;
- unnecessary tool transitions.

Project gate:

- near-zero premature `confirmed` verdicts;
- useful next test on at least 70% of supported held-out cases;
- meaningful reduction in manual diagnostic actions;
- clear value beyond restating DCGM/GPUd/NCCL output.

Rethink the project if identity mapping is too unreliable, adapter maintenance dominates diagnostic knowledge, most recommendations duplicate existing tools, or confident false root-cause claims become common.

### M9 - CLI alpha

After the benchmark gate passes: stable incident format, `gputriage investigate <dir>`, JSON + terminal reports, evidence references, missing-evidence section, next-test command template, and sanitized incident bundle export.

### M10 - Public alpha and integrations

Then consider Slurm prolog/epilog helpers, Kubernetes identity adapter, adapter/plugin SDK, optional HTML report, versioned schemas, public incident examples, and the first public alpha release.

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

M7 P1: turn host IRQ / CPU-affinity state into entity-scoped evidence.

Target flow:

```text
localized communication wait
        +
GPU kernels match peers
        +
HCA/netdev identity
        +
/proc/interrupts
        +
IRQ affinity
        +
NCCL/process CPU affinity
        ↓
Does NIC interrupt processing overlap the communication CPU?
        ↓
YES -> host CPU/IRQ hypothesis becomes probable
NO  -> weaken that path and let planner prefer fabric/other diagnostics
```

This checkpoint is more valuable than adding another generic health collector because it closes a real cross-layer gap already represented in the incident corpus.
