# GPU Triage

**Evidence-first diagnostic planning for AI/GPU infrastructure.**

GPU Triage is an early proof of concept for a troubleshooting layer that makes existing infrastructure tools work together instead of replacing them.

> Don't replace your GPU tools. Make them work together.

The core loop is deliberately simple:

```text
raw artifacts / observations
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

Recognized v0.1 files:

- `incident.json` or `context.json` — symptom plus high-level workload/identity facts;
- `lspci.txt` — PCIe capability/current width and speed;
- `nvidia-smi-q.txt` — clocks, temperature, thermal slowdown, visible ECC facts;
- `nccl.log` — transport selection, GDR-disable signals, timeout evidence;
- `ib-counters.txt` — normalized IB/RoCE counters;
- `baseline/<same-file>` — optional baseline used to derive deltas such as falling GPU clocks or rising fabric errors.

A key design boundary is deliberate: **parsers extract evidence, they do not decide causality.** `lspci` can prove that a device is currently `x8` while its capability is `x16`; the identity/topology layer must separately establish whether that device is actually on the affected job/rank path.

The NCCL parser already extracts transport/timeout/GDR facts. A dedicated NCCL transport-fallback playbook is intentionally deferred until it has its own staged validation cases.

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

## Staged incident evaluation

`data/staged_incidents_v0.1.json` contains development cases represented as staged evidence. Future evidence is hidden while the planner chooses an earlier test:

```text
T1 symptom + cheap evidence
       -> choose next diagnostic
T2 result of that diagnostic
       -> refine hypotheses / choose confirmation test
T3 repair, rollback, targeted validation, or invariant fix
       -> CONFIRMED
```

Run:

```bash
gputriage-eval data/staged_incidents_v0.1.json
```

Current development-corpus result:

```text
7 cases / 21 stages
14/14 expected next-test choices
0 premature confirmations
7/7 final confirmations
```

This is **not a product accuracy claim** because these cases are used during playbook development.

## Structural holdout smoke set

`data/holdout_incidents_v0.1.json` is separated from the development replay. It includes both supported cases and deliberately unsupported incident classes.

Current local result:

```text
2 supported holdout cases
  4/4 expected next-test choices
  2/2 final confirmations

2 known-gap cases
  2/2 correct abstentions

0 premature confirmations
```

The holdout is still small and hand-normalized, so these numbers are not a statistically meaningful accuracy benchmark. The purpose is to test two behaviors early: generalization across independently staged cases and the ability to say **"I don't know yet"** instead of inventing a diagnosis.

## Important design rules

- Missing evidence must not make a hypothesis more likely by itself.
- Observations and causes are separate objects.
- Multiple simultaneous causes are allowed.
- Every diagnostic conclusion must be traceable to evidence.
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

The near-term goal is to validate the deterministic diagnostic planner and raw-artifact adapters on real incidents before adding live integrations.

## Development

```bash
python -m pip install -e '.[dev]'
pytest -q
gputriage-eval data/staged_incidents_v0.1.json
gputriage-eval data/holdout_incidents_v0.1.json
```

GitHub Actions runs the test suite and both replay sets on Python 3.10 and 3.12.

## Status

Research / proof of concept. APIs, schemas, and playbooks will change.
