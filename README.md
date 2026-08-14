# GPU Triage

**Evidence-first diagnostic planning for AI/GPU infrastructure.**

GPU Triage is an early proof of concept for a troubleshooting layer that makes existing infrastructure tools work together instead of replacing them.

> Don't replace your GPU tools. Make them work together.

The core loop is deliberately simple:

```text
raw artifacts / observations
        -> identity graph
        -> scoped evidence
        -> hypotheses
        -> missing evidence
        -> next best test
        -> confirmation or abstention
```

The engine uses qualitative states instead of invented confidence percentages:

- `possible`
- `supported`
- `probable`
- `confirmed`
- `rejected`

A cause only becomes `confirmed` when confirmation-grade evidence is supplied. If the evidence is insufficient, the correct output is either a discriminating next test or an explicit abstention.

## Roadmap

The project roadmap, completed milestones, exit criteria, and kill/rethink conditions are tracked in [`PLAN.md`](PLAN.md).

M4 automatic identity discovery is now implemented in v0.1. The next priority is M5: correct per-device evidence handling on realistic multi-GPU / multi-HCA nodes.

## Why this exists

Modern AI clusters already have strong specialist tools: DCGM, NCCL diagnostics, GPUd, UFM, Slurm/Kubernetes tooling, Linux diagnostics, storage tools, and more. The gap this project is testing is the workflow between them:

1. What does the current evidence actually support?
2. Which explanations are still plausible?
3. What evidence is missing?
4. Which diagnostic should run next, and why?
5. When is there enough causal evidence to call the root cause confirmed?

## Current diagnostic slices

The deterministic PoC currently has small playbooks for:

- PCIe path degradation;
- physical fabric/HCA path degradation;
- GPU thermal/frequency degradation;
- software/configuration regression;
- host CPU / IRQ interference;
- storage/data-pipeline starvation;
- distributed work / collective invariant failures;
- basic GPU hardware rejection from clean health evidence.

These are intentionally narrow. The goal is to validate diagnostic planning, not to maximize the rule count.

## Raw artifact ingestion

GPU Triage can ingest a directory of artifacts:

```bash
python -m pip install -e '.[dev]'
gputriage ./incident
```

Recognized v0.1 diagnostic artifacts:

- `incident.json` or `context.json` - symptom and optional high-level facts;
- `lspci.txt` - PCIe capability/current width and speed;
- `nvidia-smi-q.txt` - clocks, temperature, thermal slowdown, visible ECC facts;
- `nccl.log` - transport selection, GDR-disable signals, timeout evidence;
- `ib-counters.txt` - normalized IB/RoCE counters;
- `baseline/<same-file>` - optional baseline used to derive deltas.

Parsers extract evidence; they do **not** decide causality. A degraded device only matters when identity reconciliation ties it to the affected workload path.

## Automatic identity discovery v0.1

The incident no longer needs a hand-written `identity_graph` for the supported Slurm path.

Discovery artifacts:

- `slurm-job.txt` - `scontrol show job -o ...` allocation metadata;
- `rank-map.csv` - runtime-captured rank, node, local rank, and `CUDA_VISIBLE_DEVICES`;
- `nvidia-gpus.csv` - node, GPU index, GPU UUID, and PCI bus ID;
- `ib-devices.csv` - node, ibdev/netdev, GUID/port, and PCI BDF;
- `nvidia-topo.txt` - GPU/NIC topology matrix.

The discovery layer reconciles:

```text
rank
  -> node
  -> exact GPU UUID
  -> GPU PCI BDF
  -> nearest unambiguous HCA/NIC
```

It can then auto-scope a single-device `lspci`, `nvidia-smi -q`, or IB-counter artifact when exactly one affected entity is known. Ambiguous mappings remain warnings instead of being guessed.

Run the end-to-end fixture:

```bash
gputriage examples/auto_identity_case
```

`examples/auto_identity_case/incident.json` contains no hand-written identity graph and no `artifact_entities` mapping.

See [`docs/COLLECTING_IDENTITY.md`](docs/COLLECTING_IDENTITY.md) for collection formats. `scripts/capture_rank_map.sh` is a small runtime helper for generating the rank mapping artifact under Slurm/torchrun-style launchers.

## Identity safety rule

Identity discovery is **evidence scoping**, not root-cause inference.

For example, if the affected ranks resolve to GPU `GPU-a` on PCIe `0000:c1:00.0`, an unrelated device at `0000:d1:00.0` may still be degraded but must not contaminate the incident diagnosis.

This is intentionally strict. Unresolved and ambiguous identity links are evidence gaps.

## Example reasoning

Given:

```text
localized NCCL regression
+ affected ranks share a PCIe path
+ GPU health is clean
+ PCIe state is missing
```

The planner should **not** claim a root cause. It should return:

```text
PCIe degradation: SUPPORTED

NEXT BEST TEST
Collect PCIe link state on the affected path.
```

If a later artifact shows `x8` where `x16` is expected, the hypothesis becomes `PROBABLE`. A targeted NCCL validation can then move it to `CONFIRMED`.

## Evaluation

`data/staged_incidents_v0.1.json` contains development cases represented as staged evidence. Future evidence is hidden while the planner chooses an earlier test.

`data/holdout_incidents_v0.1.json` is a separate structural smoke set containing both supported cases and deliberately unsupported incident classes.

These sets are **not an accuracy claim**. The real benchmark milestone is M8, where a larger incident corpus will be frozen before tuning new playbooks.

## Important design rules

- Missing evidence must not make a hypothesis more likely by itself.
- Observations and causes are separate objects.
- Multiple simultaneous causes are allowed.
- Every diagnostic conclusion must be traceable to evidence.
- Device-specific evidence must be scoped to the affected identity path when that path is known.
- Ambiguous mappings must not be silently guessed.
- Durable identifiers such as GPU UUID / PCI BDF are preferred over local indexes.
- A cheap/read-only discriminating test is preferred before an invasive benchmark.
- Unsupported incident classes should produce an explicit abstention or handoff.

## Scope boundary

This repository is **not** currently building:

- another GPU monitoring daemon;
- another Prometheus exporter;
- a DCGM or GPUd replacement;
- a Grafana dashboard;
- an LLM chatbot;
- a Kubernetes operator;
- automatic remediation.

## Development

```bash
python -m pip install -e '.[dev]'
pytest -q
gputriage-eval data/staged_incidents_v0.1.json
gputriage-eval data/holdout_incidents_v0.1.json
```

GitHub Actions runs the test suite and replay sets on Python 3.10 and 3.12.

## Status

Research / proof of concept. APIs, schemas, parsers, and playbooks will change.
