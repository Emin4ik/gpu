# GPU Triage

**Evidence-first diagnostic planning for AI/GPU infrastructure.**

GPU Triage is an early proof of concept for a different kind of cluster troubleshooting tool. It does not try to replace DCGM, NCCL tools, GPUd, UFM, Slurm, or Linux diagnostics. It keeps competing hypotheses explicit, identifies what evidence is missing, and recommends the next low-cost diagnostic that best separates those hypotheses.

> Don't replace your GPU tools. Make them work together.

## Current PoC

The first implementation deliberately supports only a tiny deterministic investigation loop:

```text
observations
    -> hypotheses
    -> missing evidence
    -> next best test
    -> confirmation
```

It uses qualitative states instead of invented confidence percentages:

- `possible`
- `supported`
- `probable`
- `confirmed`
- `rejected`

A cause is only `confirmed` when confirmation-grade evidence is supplied.

## Demo

```bash
python -m gputriage.cli examples/pcie_suspected.json
```

Example reasoning:

```text
localized NCCL regression
+ affected ranks share PCIe path
+ GPU health is clean
+ PCIe state is missing

=> PCIe degradation is SUPPORTED, not confirmed
=> collect PCIe link state next
```

If a later artifact shows `x8` where `x16` is expected, PCIe degradation becomes `PROBABLE`. A targeted NCCL validation can then move it to `CONFIRMED`.

## Why this exists

Modern AI clusters already have many strong specialist tools. The operational gap we are testing is the workflow between them:

1. What does the current evidence actually support?
2. Which explanations are still plausible?
3. What information is missing?
4. Which diagnostic should be run next, and why?
5. When is there enough causal evidence to call the root cause confirmed?

## Scope boundary

This repository is **not** currently building:

- another GPU monitoring daemon;
- another Prometheus exporter;
- a DCGM or GPUd replacement;
- a Grafana dashboard;
- an LLM chatbot;
- a Kubernetes operator;
- automatic remediation.

The near-term goal is to validate the deterministic diagnostic planner on a corpus of real, confirmed incidents before expanding integrations.

## Development

```bash
python -m pip install -e '.[dev]'
pytest
```

## Status

Research / proof of concept. APIs and schemas will change.
