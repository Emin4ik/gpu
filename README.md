# GPU Triage

**Evidence-first diagnostic planning for AI/GPU infrastructure.**

GPU Triage is an early proof of concept for a troubleshooting layer that makes existing infrastructure tools work together instead of replacing them.

> Don't replace your GPU tools. Make them work together.

```text
raw artifacts / specialist tools
        -> identity graph
        -> entity-scoped evidence
        -> hypotheses
        -> eligible diagnostics
        -> transparent test ranking
        -> next best test or abstention
        -> confirmation / rejection
```

The engine uses qualitative hypothesis states (`possible`, `supported`, `probable`, `confirmed`, `rejected`) instead of invented root-cause confidence percentages. A root cause only becomes `confirmed` when confirmation-grade evidence is supplied.

## What is implemented

- deterministic diagnostic playbooks for PCIe, fabric/HCA, thermal/frequency, software/config, CPU/IRQ, storage/data starvation, and collective-work invariant failures;
- raw parsers for `lspci -vv`, `nvidia-smi -q`, NCCL logs, and IB/RoCE counters;
- Slurm/GPU/HCA identity discovery;
- rank -> node -> GPU UUID -> PCI BDF -> HCA/NIC mapping;
- multi-device evidence storage without key collisions;
- affected-path filtering so unrelated broken hardware cannot contaminate an investigation;
- explicit diagnostic-test registry and deterministic next-test ranking;
- selection explanations, expected outcome branches, and alternatives;
- staged evaluation and explicit abstention.

The full roadmap and exit criteria are in [`PLAN.md`](PLAN.md). M0-M6 are implemented at PoC level; **M7 evidence adapters are next**.

## Automatic identity discovery

Supported discovery artifacts include `slurm-job.txt`, `rank-map.csv`, `nvidia-gpus.csv`, `ib-devices.csv`, and `nvidia-topo.txt`.

See [`docs/COLLECTING_IDENTITY.md`](docs/COLLECTING_IDENTITY.md).

## Multi-device evidence

Evidence is not stored as a flat `key -> value` dictionary. The entity is part of each observation:

```text
pcie_width @ pcie:0000:c1:00.0 = 16
pcie_width @ pcie:0000:e1:00.0 = 8
```

Related facts are paired only when their entities match. If the affected workload path is known, unrelated device evidence is removed before hypothesis evaluation.

See [`docs/EVIDENCE_MODEL.md`](docs/EVIDENCE_MODEL.md).

## Explicit next-test planning

Playbooks decide which diagnostics are eligible. The planner then ranks those actions using transparent operational attributes:

```text
owner hypothesis state
+ diagnostic information value
+ number of active hypotheses separated
+ supporting evidence
- cost
- invasiveness
- duration
```

This score ranks **diagnostic actions**, not root-cause probability.

A selected action carries:

- why it is useful;
- cost / invasiveness / duration;
- expected outcome branches;
- why it beat the other eligible diagnostics;
- top alternatives.

For example, when PCIe and fabric are both supported but PCIe state is missing, a cheap read-only PCIe check can outrank fabric collection. If PCIe later becomes `probable`, the planner can switch to targeted NCCL validation for causal confirmation.

## Try it

```bash
python -m pip install -e '.[dev]'

gputriage examples/auto_identity_case
gputriage examples/multidevice_case
```

## Design rules

- missing evidence does not make a hypothesis more likely;
- parsers extract facts, not causes;
- observations and causes are separate objects;
- multiple causes are allowed;
- every conclusion must be traceable to evidence;
- ambiguous identity mappings are not guessed;
- durable identifiers such as GPU UUID and PCI BDF are preferred over local indexes;
- cheap/read-only diagnostics are preferred when they provide comparable information;
- unsupported incident classes should produce abstention or handoff;
- imported vendor-tool verdicts will be treated as evidence, not unquestioned truth.

## Scope boundary

This repository is not trying to become another GPU monitoring daemon, Prometheus/Grafana stack, DCGM/GPUd replacement, scheduler, generic MCP gateway, LLM log chatbot, Kubernetes operator, or automatic remediation platform.

## Development

```bash
python -m pip install -e '.[dev]'
pytest -q
gputriage-eval data/staged_incidents_v0.1.json
gputriage-eval data/holdout_incidents_v0.1.json
```

GitHub Actions runs tests and replay sets on supported Python versions.

## Status

Research / proof of concept. APIs, schemas, adapters, and playbooks will change. **Next: M7, starting with DCGM and journal/dmesg evidence adapters.**
