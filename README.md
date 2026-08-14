# GPU Triage

**Evidence-first diagnostic planning for AI/GPU infrastructure.**

GPU Triage is an early proof of concept for a troubleshooting layer that makes existing infrastructure tools work together instead of replacing them.

> Don't replace your GPU tools. Make them work together.

```text
raw artifacts
    -> identity graph
    -> entity-scoped evidence
    -> hypotheses
    -> missing evidence
    -> next best test
    -> confirmation or abstention
```

The engine uses qualitative states (`possible`, `supported`, `probable`, `confirmed`, `rejected`) instead of invented confidence percentages. A root cause only becomes `confirmed` when confirmation-grade evidence is supplied.

## What is implemented

- deterministic diagnostic playbooks for PCIe, fabric/HCA, thermal/frequency, software/config, CPU/IRQ, storage/data starvation, and collective-work invariant failures;
- raw parsers for `lspci -vv`, `nvidia-smi -q`, NCCL logs, and IB/RoCE counters;
- Slurm/GPU/HCA identity discovery;
- rank -> node -> GPU UUID -> PCI BDF -> HCA/NIC mapping;
- multi-device evidence storage without key collisions;
- affected-path filtering so unrelated broken hardware cannot contaminate an investigation;
- staged evaluation and explicit abstention.

The full roadmap and exit criteria are in [`PLAN.md`](PLAN.md).

## Automatic identity discovery

Supported discovery artifacts include:

- `slurm-job.txt`;
- `rank-map.csv`;
- `nvidia-gpus.csv`;
- `ib-devices.csv`;
- `nvidia-topo.txt`.

See [`docs/COLLECTING_IDENTITY.md`](docs/COLLECTING_IDENTITY.md).

## Multi-device evidence

Evidence is not stored as a flat `key -> value` dictionary. The entity is part of each observation:

```text
pcie_width @ pcie:0000:c1:00.0 = 16
pcie_width @ pcie:0000:e1:00.0 = 8
```

GPU Triage pairs related facts only when the entity matches and removes device evidence outside the affected workload path before hypothesis evaluation.

This prevents a classic false-correlation failure: a bad PCIe link elsewhere on the node cannot become the explanation for a job whose ranks never use that device.

See [`docs/EVIDENCE_MODEL.md`](docs/EVIDENCE_MODEL.md).

## Try it

```bash
python -m pip install -e '.[dev]'

gputriage examples/auto_identity_case
gputriage examples/multidevice_case
```

The multi-device example contains a degraded affected PCIe device plus another degraded but unrelated device. Only affected-path evidence is allowed into the diagnosis.

## Design rules

- missing evidence does not make a hypothesis more likely;
- parsers extract facts, not causes;
- observations and causes are separate objects;
- multiple causes are allowed;
- every conclusion must be traceable to evidence;
- ambiguous identity mappings are not guessed;
- durable identifiers such as GPU UUID and PCI BDF are preferred over local indexes;
- cheap/read-only tests are preferred before invasive diagnostics;
- unsupported incident classes should produce abstention or handoff.

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

Research / proof of concept. M0-M5 are implemented at PoC level. **M6 (explicit next-test selection) is next.** APIs, schemas, parsers, and playbooks will change.
