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

Known limitations: rank mapping still requires runtime capture, topology formats need more real fixtures, and current examples are node-local rather than a complete multi-node collector.

### M5 - Multi-device evidence model: DONE (v0.1)

Implemented:

- multi-value evidence index instead of flat `key -> value` state;
- same-key observations preserved for different entities;
- PCIe current/expected facts paired only on the same device;
- full multi-device `lspci -vv` parsing;
- multi-GPU `nvidia-smi -q` parsing;
- multiple per-HCA counter artifacts;
- entity-aware baseline comparison;
- `Observation.raw_ref` traceability;
- affected-path filtering before diagnosis;
- regressions proving unrelated degraded devices cannot contaminate a diagnosis.

See [`docs/EVIDENCE_MODEL.md`](docs/EVIDENCE_MODEL.md).

### M6 - Explicit diagnostic test planner: DONE (v0.1)

Implemented:

- `DiagnosticTestSpec` registry independent from hypothesis rules;
- eligibility separated from ranking;
- explicit cost, invasiveness, duration class, owner hypothesis, discriminated hypotheses, information value, and expected outcome branches;
- deterministic candidate scoring;
- preference for read-only/cheap tests when information value is comparable;
- confirmation tests promoted as a hypothesis becomes `probable`;
- selected test includes a human-readable selection reason and top alternatives;
- unsupported incidents still abstain when no useful registered test exists;
- regression coverage preserving staged and holdout diagnostic paths.

Important boundary: scoring ranks **diagnostic actions**, not root-cause confidence. It does not turn hypotheses into probabilities.

Exit criteria achieved:

- planner can explain why a test was selected;
- preferred action changes as evidence changes;
- read-only tests beat disruptive alternatives when diagnostic value is otherwise equal;
- old staged/holdout behavior remains green in CI.

## Next work

### M7 - Evidence adapters: NEXT

Goal: consume strong specialist tools as evidence providers instead of reimplementing them.

P0 adapters:

1. **DCGM**
   - health and diagnostic results;
   - GPU UUID/entity mapping;
   - XID/ECC/PCIe/NVLink-related findings where present;
   - preserve raw test/result provenance.

2. **Linux incident events**
   - `journalctl` / `dmesg` NVIDIA XID/SXID events;
   - timestamps and GPU/PCI identifiers when present;
   - no assumption that an old XID caused the current incident without time/entity correlation.

3. **GPUd**
   - consume normalized component health/output;
   - map component findings to GPU/HCA/node entities;
   - do not duplicate GPUd collectors.

4. **NCCL Doctor / NCCL evidence**
   - import evidence-first diagnoses/findings where available;
   - retain source evidence and treat imported verdicts as evidence, not unquestioned truth.

5. **AICR snapshot/diff**
   - import configuration/software drift;
   - attach changes to node/software entities and incident timeline.

Later M7 adapters: NVLink/NVSwitch/Fabric Manager, UFM/NetQ exports, `/proc/interrupts` and CPU affinity, and simple storage/data-loader evidence.

Exit criteria:

- at least two external specialist tools feed the same evidence model;
- imported evidence keeps source/entity/timestamp provenance;
- planner can select a next action using mixed evidence from multiple adapters;
- adapters do not silently promote vendor verdicts to `confirmed` root cause.

### M8 - Frozen blind benchmark

Grow the incident corpus to at least 25-30 high-quality cases and freeze a meaningful holdout before tuning more playbooks.

Measure true-domain coverage, next-test utility, premature confirmation, correct abstention, diagnostic-action reduction, and unnecessary tool transitions.

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

M7 begins with **DCGM + journal/dmesg adapters**. These are useful because they provide two very different evidence sources—structured NVIDIA diagnostics and host event history—without expanding into a monitoring platform.

The first mixed-source proof should look like:

```text
DCGM result
    +
journal/XID timeline
    +
identity graph
    +
PCIe/fabric artifacts
        ↓
entity/time-scoped evidence
        ↓
existing hypotheses
        ↓
M6 planner selects next diagnostic
```
