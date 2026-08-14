# GPU Triage Development Plan

Last updated: 2026-08-14

## Product thesis

GPU Triage is an open, evidence-first diagnostic planner for AI/GPU infrastructure.
It should not replace DCGM, GPUd, NCCL tools, UFM, Slurm, Linux diagnostics, or future vendor agents.
Its job is to connect evidence across those tools, keep competing hypotheses explicit, and choose the next diagnostic action that best reduces uncertainty.

Core promise:

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

## Status summary

### M0 - Problem validation: DONE

Completed:

- competitive research across NVIDIA and third-party GPU infrastructure tooling;
- real incident research covering GPU, PCIe, fabric, CPU/kernel, storage, runtime, and application failures;
- initial incident corpus and diagnostic playbook design;
- decision to make `next best test` a first-class output;
- decision to use qualitative states: `possible`, `supported`, `probable`, `confirmed`, `rejected`;
- explicit support for abstention and multiple possible causes.

Exit criterion: the project has a differentiated wedge above existing health scanners and dashboards.

### M1 - Deterministic planner PoC: DONE

Completed:

- observation -> hypothesis -> missing evidence -> next-test loop;
- playbooks for PCIe, fabric/HCA, thermal/frequency, software/config, host CPU/IRQ, storage/data starvation, and collective-work invariant failures;
- no fake numeric confidence scores;
- confirmation requires repair, rollback, targeted validation, invariant fix, or equivalent causal evidence;
- staged development replay;
- structural holdout smoke replay including known unsupported cases;
- explicit abstention when the engine lacks a useful playbook.

Exit criterion: the engine can preserve uncertainty and request a useful next diagnostic instead of forcing a verdict.

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

Exit criterion: a user can provide raw artifacts instead of manually writing normalized observations.

### M3 - Identity graph v0.1: DONE

Completed in v0.1:

- normalized entities and directed relations;
- traversal from rank to node/GPU/PCIe/HCA entities;
- derivation of shared affected PCIe/HCA/node paths;
- artifact-to-entity mapping through `artifact_entities`;
- rejection of hardware evidence from an unrelated device when an affected path is known;
- validation of broken graph references.

Exit criterion: evidence from `lspci` or fabric counters is only promoted when it belongs to the affected job/rank path.

### M4 - Automatic identity discovery: DONE (v0.1)

Goal: replace most hand-written identity relations with real cluster artifacts.

Completed in v0.1:

- `slurm-job.txt` parser for `JobId` and `NodeList`;
- practical Slurm hostlist expansion for common bracket/range syntax;
- automatically generated `rank-map.csv` bridge for rank/node/local-rank/CUDA visibility;
- `nvidia-gpus.csv` parser for node/index/UUID/PCI BDF;
- rank -> GPU reconciliation using UUID, GPU index, or `CUDA_VISIBLE_DEVICES` + local rank;
- `ib-devices.csv` parser for ibdev/netdev/GUID/port/PCI BDF;
- NVIDIA GPU-NIC topology parsing with conservative nearest-HCA candidates;
- automatic affected rank -> node -> GPU -> GPU PCIe -> HCA graph construction;
- auto-scoping of single-device `lspci`, `nvidia-smi -q`, and IB counter artifacts when identity is unambiguous;
- explicit unresolved/ambiguous mapping warnings;
- `scripts/capture_rank_map.sh` helper;
- end-to-end `examples/auto_identity_case/` with no hand-written `identity_graph` or `artifact_entities`.

Remaining limitations inside M4:

- rank mapping still has to be captured at job runtime because scheduler allocation metadata alone does not identify the GPU used by each process;
- topology output varies across NVIDIA driver/tool versions, so more real fixtures are required;
- current example is a targeted single-node slice, not yet a whole multi-node incident collector.

Exit criteria achieved for v0.1:

- a Slurm incident can build most rank/node/GPU/HCA mappings without hand-written relations;
- ambiguous or missing links generate explicit evidence gaps;
- wrong-device PCIe/fabric evidence remains excluded when identity is known.

## Next work - priority order

### M5 - Artifact scoping and multi-device collection: NEXT

Goal: support realistic nodes with multiple GPUs, PCIe devices, and HCAs.

Work:

- accept multiple `lspci` artifacts or one full node dump;
- parse PCI BDF per device;
- accept multiple `nvidia-smi` GPU sections;
- accept per-HCA/per-port counters;
- attach every hardware observation to an entity;
- preserve raw evidence references;
- do not collapse same-key observations from different entities during ingestion.

Exit criteria:

- eight-GPU/multi-HCA nodes do not overwrite observations by key;
- planner can select only observations on the affected path;
- unrelated degraded devices do not contaminate the incident diagnosis.

### M6 - Planner v0.2: test selection quality

Goal: make `next best test` selection explicit rather than hard-coded ordering.

Work:

- diagnostic test registry;
- cost, invasiveness, prerequisites, and expected duration;
- which hypotheses each test separates;
- expected outcome branches;
- prefer read-only/cheap tests when information value is similar;
- retain multiple simultaneous causes and time windows.

Exit criteria:

- planner can explain why test A is preferred over test B;
- test ordering changes correctly as new evidence arrives;
- no disruptive test is selected when a read-only test can separate the same hypotheses.

### M7 - Expand evidence adapters without replacing specialist tools

Priority adapters:

- DCGM diagnostic/health output;
- GPUd output;
- NCCL Doctor output;
- NVIDIA AICR snapshot/diff output;
- DCGM/NVLink/NVSwitch/Fabric Manager facts;
- UFM/NetQ or exported fabric evidence where publicly accessible;
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
- clear value beyond simply restating DCGM/GPUd/NCCL output.

Kill/rethink conditions:

- most recommendations duplicate existing tools with no workflow reduction;
- identity mapping is too unreliable to support causal correlation;
- adapter maintenance dominates diagnostic knowledge development;
- useful diagnosis requires an always-on profiler for most incidents;
- confident false root-cause claims appear regularly.

### M9 - CLI alpha

Only after the benchmark gate passes:

- stable incident directory format;
- `gputriage investigate <dir>`;
- machine-readable JSON report;
- human-readable terminal report;
- evidence references for every supported conclusion;
- explicit missing-evidence section;
- `next best test` command template;
- sanitized incident bundle export.

### M10 - Integrations and public alpha

After the local/Slurm workflow is credible:

- Slurm collection helpers/prolog/epilog integration;
- Kubernetes identity adapter;
- plugin/adapter SDK;
- optional HTML report;
- GitHub documentation and example incident library;
- versioned schemas;
- first public alpha release.

### Later, only if demanded by users

- live SSH collection;
- historical incident database;
- fleet-level baselines;
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

M5: make the identity/evidence model correct on realistic 8-GPU, multi-HCA nodes.

Prove this end-to-end flow without collapsing observations by key:

```text
affected ranks
    -> exact GPU UUIDs
    -> exact GPU PCI BDFs
    -> one or more candidate HCAs
    -> per-device raw artifacts
    -> evidence stays attached to its entity
    -> unrelated degraded devices are excluded
    -> planner sees only affected-path evidence
```

Priority work:

1. multi-GPU `nvidia-smi -q` / inventory sections;
2. multi-device `lspci` artifacts;
3. per-HCA/per-port counters;
4. observation storage keyed by `(key, entity)` instead of only `key`;
5. artifact filenames/metadata that carry durable entity IDs;
6. real topology fixtures from HGX/DGX-class nodes;
7. regression tests with one healthy and one degraded unrelated device.

This checkpoint remains more important than adding new root-cause rules.
