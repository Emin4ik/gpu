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

Completed competitive research and a corpus of real cross-layer GPU infrastructure incidents. The differentiated wedge is diagnostic planning across existing tools, not another health scanner.

### M1 - Deterministic planner: DONE

Implemented:

- observation -> hypothesis -> missing evidence -> next-test loop;
- qualitative states: `possible`, `supported`, `probable`, `confirmed`, `rejected`;
- explicit abstention;
- confirmation only after causal-grade evidence;
- staged development replay and structural holdout smoke cases.

### M2 - Raw artifact ingestion: DONE

Implemented parsers/adapters for:

- `lspci -vv`;
- `nvidia-smi -q`;
- NCCL logs;
- IB/RoCE counters;
- optional baseline artifacts.

Parsers extract facts but do not declare causality.

### M3 - Identity graph: DONE

Implemented:

- rank/node/GPU/PCIe/HCA entities and relations;
- affected-path traversal;
- artifact-to-entity scoping;
- rejection of unrelated hardware evidence;
- explicit unresolved/ambiguous identity warnings.

### M4 - Automatic identity discovery: DONE (v0.1)

Implemented:

- `slurm-job.txt` allocation parsing;
- Slurm hostlist expansion;
- runtime `rank-map.csv` capture;
- `nvidia-gpus.csv` UUID/index/PCI BDF inventory;
- GPU mapping through UUID, index, or `CUDA_VISIBLE_DEVICES` + local rank;
- `ib-devices.csv` identity;
- conservative NVIDIA GPU/NIC topology reconciliation;
- `scripts/capture_rank_map.sh`;
- end-to-end `examples/auto_identity_case/`.

Known limitations: rank mapping still requires runtime capture, topology formats need more real fixtures, and current collection examples are node-local rather than a full multi-node collector.

### M5 - Multi-device evidence model: DONE (v0.1)

Implemented:

- multi-value evidence index instead of flat `key -> value` state;
- same-key observations preserved for different GPUs/PCIe devices/HCAs;
- PCIe current/expected facts paired only on the same entity;
- full multi-device `lspci -vv` parsing with BDF-scoped observations;
- multi-GPU `nvidia-smi -q` parsing with UUID-scoped observations;
- multiple per-HCA counter artifacts;
- entity-aware baseline comparison;
- `Observation.raw_ref` for artifact traceability;
- affected-path filtering before hypothesis evaluation;
- regression coverage proving that an unrelated degraded device cannot contaminate a diagnosis.

Exit criteria achieved:

- observations from different devices no longer overwrite one another;
- unrelated degraded devices are excluded when identity is known;
- facts from different devices cannot be accidentally combined into a false PCIe diagnosis.

See [`docs/EVIDENCE_MODEL.md`](docs/EVIDENCE_MODEL.md).

## Next work

### M6 - Planner v0.2: NEXT

Goal: replace hard-coded test ordering with an explicit diagnostic test registry and deterministic test selection.

Build:

- `DiagnosticTestSpec` registry;
- test cost, invasiveness, prerequisites, and expected-duration class;
- which hypotheses each test discriminates;
- explicit outcome branches;
- deterministic ranking of candidate tests;
- preference for cheap/read-only tests when information value is similar;
- correct abstention when no registered test can reduce uncertainty.

Exit criteria:

- planner explains why test A is preferred over test B;
- preferred test changes correctly as new evidence arrives;
- disruptive tests are not selected when a read-only alternative separates the same hypotheses.

### M7 - Evidence adapters

Consume existing specialist tools rather than reimplement them. Priority adapters:

- DCGM health/diagnostic output;
- GPUd output;
- NCCL Doctor output;
- NVIDIA AICR snapshot/diff;
- NVLink/NVSwitch/Fabric Manager facts;
- UFM/NetQ exported evidence where available;
- `journalctl` / `dmesg` XID/SXID/kernel events;
- `/proc/interrupts` and CPU affinity;
- simple storage/data-loader evidence.

### M8 - Frozen blind benchmark

Grow the incident corpus to at least 25-30 high-quality cases and freeze a holdout before tuning new playbooks.

Measure:

- true domain among supported hypotheses;
- next-test utility;
- premature confirmation rate;
- correct abstention rate;
- diagnostic action reduction;
- unnecessary tool-transition reduction.

Project gate:

- near-zero premature `confirmed` verdicts;
- useful next test on at least 70% of supported held-out cases;
- meaningful reduction in manual diagnostic actions;
- clear value beyond restating DCGM/GPUd/NCCL output.

Rethink the project if identity mapping is too unreliable, adapter maintenance dominates diagnostic knowledge, most recommendations duplicate existing tools, or confident false root-cause claims become common.

### M9 - CLI alpha

After the benchmark gate passes:

- stable incident directory format;
- `gputriage investigate <dir>`;
- JSON report;
- human-readable terminal report;
- evidence references;
- missing-evidence section;
- next-best-test command template;
- sanitized incident bundle export.

### M10 - Public alpha and integrations

Then consider:

- Slurm prolog/epilog helpers;
- Kubernetes identity adapter;
- adapter/plugin SDK;
- optional HTML report;
- versioned schemas;
- public example incident library;
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
   diagnostic test planner
        /          \
       v            v
 next best test   abstain
       |
       v
 new evidence -> confirm / reject / keep multiple causes
```

## Immediate checkpoint

M6 is now the priority. The engine should move from ordered `if` statements to explicit test-selection logic:

```text
remaining hypotheses
        +
missing evidence
        +
test cost / invasiveness / prerequisites
        +
which hypotheses each outcome separates
        ↓
ranked next diagnostic actions
```

This is the step that turns the PoC from a deterministic rule chain into a real diagnostic planner.
