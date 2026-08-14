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
- DCGM diagnostic/health JSON adapter;
- NVIDIA `journalctl` / `dmesg` XID/SXID adapter;
- DCGM local GPU-index reconciliation to durable GPU UUID identity;
- separation of diagnostic execution failures from hardware-class findings;
- `/proc/interrupts`, IRQ affinity, and communication-process CPU-affinity evidence;
- HCA-aware IRQ -> CPU -> communication-process correlation;
- line/raw provenance across imported evidence;
- staged evaluation and explicit abstention.

The full roadmap and exit criteria are in [`PLAN.md`](PLAN.md). **M0-M7 are implemented at PoC level. M8, the frozen blind benchmark, is next.**

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

## Cross-tool evidence adapters

### DCGM

Recognized files include `dcgm-diag.json`, `dcgm-health.json`, and other `dcgm*.json` artifacts.

The adapter keeps per-test status, failure codes/messages, entity scope, and raw references. A failed DCGM test is not automatically a hardware verdict: execution/environment failures are represented separately.

### NVIDIA kernel / journal events

Recognized files include `journal.log`, `dmesg.log`, and matching text variants.

The adapter extracts GPU UUID / PCI mapping plus XID/SXID events and preserves line-level references. When identity is known, an event on an unrelated GPU is filtered out of the current incident.

See [`docs/ADAPTERS.md`](docs/ADAPTERS.md).

### Host IRQ / CPU affinity

Recognized host artifacts include:

- `proc-interrupts.txt`;
- `irq-affinity.csv`;
- `process-affinity.csv`.

GPU Triage derives `irq_shares_nccl_cpu` only when it can prove all of the required links: the IRQ is active, it maps to an HCA/NIC on the affected workload path, and an affected-rank communication process has known CPU affinity. When an effective IRQ CPU set is available it is preferred over only the configured allowed set.

That evidence can promote the host CPU/IRQ hypothesis to `probable`; the planner still requests a short CPU/kernel profile for causal confirmation.

See [`docs/HOST_AFFINITY.md`](docs/HOST_AFFINITY.md).

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

A selected action carries why it is useful, cost/invasiveness/duration, expected outcome branches, why it beat other eligible diagnostics, and top alternatives.

## Try it

```bash
python -m pip install -e '.[dev]'

gputriage examples/auto_identity_case
gputriage examples/multidevice_case
gputriage examples/m7_dcgm_xid_case
gputriage examples/m7_irq_affinity_case
```

## Design rules

- missing evidence does not make a hypothesis more likely;
- parsers/adapters extract facts, not causes;
- observations and causes are separate objects;
- multiple causes are allowed;
- every conclusion must be traceable to evidence;
- ambiguous identity mappings are not guessed;
- durable identifiers such as GPU UUID and PCI BDF are preferred over local indexes;
- cheap/read-only diagnostics are preferred when they provide comparable information;
- unsupported incident classes should produce abstention or handoff;
- imported vendor-tool verdicts are evidence, not unquestioned truth;
- a diagnostic that failed to execute is not treated as a component hardware failure;
- IRQ/CPU overlap is not considered causal confirmation by itself.

## Why adapter expansion pauses here

The PoC can now combine GPU/vendor diagnostics, kernel event history, host IRQ/CPU state, PCIe identity, and communication/fabric evidence. The next useful question is not whether another adapter can be written; it is whether the diagnostic planner improves real investigations.

M8 therefore freezes a larger real-incident holdout before GPUd/NCCL Doctor/AICR or additional UI/integrations are added.

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

Research / proof of concept. APIs, schemas, adapters, and playbooks will change. **Next: M8 — freeze and run a real blind incident benchmark before expanding product scope.**
