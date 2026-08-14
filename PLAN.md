# GPU Triage Development Plan

Last updated: 2026-08-14

## Product thesis

GPU Triage is an open, evidence-first diagnostic planner for AI/GPU infrastructure.
It should not replace DCGM, GPUd, NCCL tools, UFM, Slurm, Linux diagnostics, or future vendor agents.
Its job is to connect evidence across those tools, keep competing hypotheses explicit, and choose the next diagnostic action that best reduces uncertainty.

> Do not replace your GPU tools. Make them work together.

## Non-goals

The early project will not become:

- another GPU monitoring daemon;
- another Prometheus exporter or Grafana dashboard;
- a DCGM/GPUd/NVSentinel replacement;
- a scheduler;
- a generic MCP gateway;
- an LLM that guesses from a large log dump;
- an autonomous remediation system.

## Completed milestones

### M0 - Problem validation: DONE

Completed:

- competitive research across NVIDIA and third-party GPU infrastructure tooling;
- real incident research across GPU, PCIe, fabric, CPU/kernel, storage, runtime, and application failures;
- initial incident corpus and diagnostic playbook design;
- `next best test` selected as a first-class product output;
- qualitative states: `possible`, `supported`, `probable`, `confirmed`, `rejected`;
- explicit abstention when evidence is insufficient.

### M1 - Deterministic planner PoC: DONE

Completed:

- observation -> hypothesis -> missing evidence -> next-test loop;
- playbooks for PCIe, fabric/HCA, thermal/frequency, software/config, host CPU/IRQ, storage/data starvation, and collective-work invariant failures;
- no fake numeric confidence scores;
- confirmation requires repair, rollback, targeted validation, invariant fix, or equivalent causal evidence;
- staged development replay;
- structural holdout smoke replay with supported and unsupported cases.

### M2 - Raw artifact ingestion: DONE

Completed:

- `lspci -vv` parser;
- `nvidia-smi -q` parser;
- NCCL log parser for transport, timeout, and GDR facts;
- IB/RoCE counter parser;
- directory-based incident ingestion;
- optional baseline artifacts and simple derived deltas;
- parser/diagnosis boundary: parsers extract facts but do not declare causality;
- CI test workflow.

### M3 - Identity graph v0.1: DONE

Completed:

- normalized entities and directed relations;
- traversal from rank to node/GPU/PCIe/HCA entities;
- derivation of shared affected PCIe/HCA/node paths;
- artifact-to-entity mapping through `artifact_entities`;
- rejection of hardware evidence from an unrelated device when an affected path is known;
- validation of broken graph references.

Important limitation: identity data is still supplied manually in `incident.json`.

## Next work - priority order

### M4 - Automatic identity discovery: NEXT

Goal: replace hand-written identity context with real cluster artifacts.

P0 adapters:

1. Slurm job/rank mapping
   - `scontrol show job`;
   - `scontrol show node`;
   - `sacct` where useful;
   - launcher/rank metadata.

2. NVIDIA GPU identity
   - GPU UUID;
   - PCI bus ID/BDF;
   - local GPU index only as a non-durable alias;
   - `nvidia-smi topo -m` relationships.

3. NIC/HCA identity
   - netdev;
   - mlx5/IB device;
   - PCI BDF;
   - HCA GUID and port.

4. Path reconciliation
   - rank -> node;
   - rank -> GPU UUID;
   - GPU -> PCI BDF;
   - rank/GPU -> HCA/NIC;
   - HCA -> GUID/port.

5. Identity diagnostics
   - unresolved mappings must be visible;
   - ambiguous mappings must not be silently guessed;
   - durable IDs are preferred over local indexes.

Exit criteria:

- a Slurm incident builds most rank/node/GPU/HCA mappings without hand-written relations;
- ambiguous or missing links generate explicit evidence gaps;
- wrong-device PCIe/fabric evidence remains excluded.

### M5 - Multi-device artifact scoping

Goal: support realistic 8-GPU, multi-HCA nodes.

Work:

- parse multiple devices from full `lspci` dumps;
- parse multiple GPU sections and UUID/BDF mappings;
- parse per-HCA/per-port counters;
- attach every hardware observation to an entity;
- preserve raw evidence references;
- stop collapsing same-key observations from different entities.

Exit criteria:

- observations from different GPUs/HCAs do not overwrite each other;
- only affected-path evidence influences a hypothesis;
- an unrelated degraded device does not contaminate the diagnosis.

### M6 - Planner v0.2

Goal: choose the next test by information value rather than hard-coded order.

Work:

- diagnostic test registry;
- cost, invasiveness, prerequisites, and expected duration;
- hypotheses separated by each test;
- expected outcome branches;
- prefer read-only/cheap tests when information value is similar;
- retain multiple simultaneous causes and time windows.

Exit criteria:

- planner explains why test A is preferred over test B;
- test ordering changes as evidence arrives;
- disruptive tests are avoided when a read-only test can separate the same hypotheses.

### M7 - Evidence adapters

Priority adapters:

- DCGM health/diagnostic output;
- GPUd output;
- NCCL Doctor output;
- NVIDIA AICR snapshot/diff output;
- NVLink/NVSwitch/Fabric Manager facts;
- UFM/NetQ or exported fabric evidence where available;
- `journalctl` / `dmesg` XID/SXID/kernel events;
- `/proc/interrupts` and CPU affinity evidence;
- simple storage/data-loader evidence.

Principle: consume strong existing tools instead of reimplementing them.

### M8 - Freeze a real blind benchmark

Goal: decide objectively whether the project deserves continued development.

Work:

- grow the incident corpus to at least 25-30 high-quality cases;
- freeze a meaningful holdout set before tuning new playbooks;
- preserve staged evidence so future facts are hidden;
- include unsupported cases where correct behavior is abstention;
- include misleading alerts and multi-cause incidents.

Metrics:

- true domain in top supported hypotheses;
- next-test utility;
- premature confirmation rate;
- correct abstention rate;
- diagnostic action reduction;
- unnecessary tool-transition reduction.

Initial project gate:

- near-zero premature `confirmed` verdicts;
- useful next test on at least 70% of supported held-out cases;
- meaningful reduction in manual diagnostic actions;
- clear value beyond restating DCGM/GPUd/NCCL output.

Kill/rethink conditions:

- most recommendations duplicate existing tools without reducing workflow;
- identity mapping is too unreliable for causal correlation;
- adapter maintenance dominates diagnostic-knowledge development;
- useful diagnosis requires an always-on profiler for most incidents;
- confident false root-cause claims appear regularly.

### M9 - CLI alpha

Only after the benchmark gate passes:

- stable incident directory format;
- `gputriage investigate <dir>`;
- machine-readable JSON report;
- human-readable terminal report;
- evidence references for supported conclusions;
- explicit missing-evidence section;
- `next best test` command template;
- sanitized incident bundle export.

### M10 - Public alpha and integrations

After the local/Slurm workflow is credible:

- Slurm collection helpers/prolog/epilog integration;
- Kubernetes identity adapter;
- plugin/adapter SDK;
- optional HTML report;
- versioned schemas;
- example incident library;
- first public alpha release.

Later, only if users demand it:

- live SSH collection;
- historical incident database;
- fleet baselines;
- MCP exposure;
- LLM explanation/conversation layer;
- web UI;
- notifications;
- enterprise integrations;
- safe remediation suggestions.

## Current architectural target

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
       scoped evidence
            |
            v
        hypotheses
            |
            v
   diagnostic test planner
            |
      +-----+-----+
      |           |
      v           v
 next best test  abstain
      |
      v
 new evidence -> confirm / reject / keep multiple causes
```

## Immediate next checkpoint

Implement automatic Slurm + NVIDIA identity discovery and prove this end-to-end flow:

```text
Slurm job/rank
    -> node
    -> GPU UUID
    -> GPU PCI BDF
    -> HCA/NIC
    -> raw PCIe/fabric artifact
    -> affected-path evidence only
    -> next diagnostic test
```

That checkpoint is more important than adding new root-cause rules.
