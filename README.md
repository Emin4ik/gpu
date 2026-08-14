# GPU Triage

**Evidence-first diagnostic planning for AI/GPU infrastructure.**

GPU Triage is an early proof of concept for a different kind of cluster troubleshooting tool. It does not try to replace DCGM, NCCL tools, GPUd, UFM, Slurm, or Linux diagnostics. It keeps competing hypotheses explicit, identifies what evidence is missing, and recommends the next low-cost diagnostic that best separates those hypotheses.

> Don't replace your GPU tools. Make them work together.

## Current PoC

The implementation deliberately starts with a small deterministic investigation loop:

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

## Supported diagnostic slices

The current engine has small playbooks for:

- PCIe path degradation;
- physical fabric/HCA path degradation;
- GPU thermal/frequency degradation;
- software/configuration regression;
- host CPU / IRQ interference;
- storage/data-pipeline starvation;
- distributed work / collective invariant failures;
- basic GPU hardware rejection from clean health evidence.

These are intentionally narrow. The goal is to validate diagnostic planning, not to maximize the number of rules.

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

## Staged incident evaluation

`data/staged_incidents_v0.1.json` contains real incident patterns represented as staged evidence. Later evidence is not visible while the planner chooses an earlier test:

```text
T1 symptom + cheap evidence
       -> choose next diagnostic
T2 result of that diagnostic
       -> refine hypotheses / choose confirmation test
T3 repair, rollback, targeted validation, or invariant fix
       -> CONFIRMED
```

Run the replay with:

```bash
python -m gputriage.evaluator data/staged_incidents_v0.1.json
```

Current development-corpus result:

```text
cases:                    7
stages:                  21
next-test checks:        14
next-test hits:          14
premature confirmations: 0
final confirmations:     7/7
```

This is **not a product accuracy claim**: these cases are currently used during rule development. The next milestone is a held-out corpus that is not used to tune the playbooks.

## Why this exists

Modern AI clusters already have many strong specialist tools. The operational gap we are testing is the workflow between them:

1. What does the current evidence actually support?
2. Which explanations are still plausible?
3. What information is missing?
4. Which diagnostic should be run next, and why?
5. When is there enough causal evidence to call the root cause confirmed?

## Important design rule

Missing evidence must not make a hypothesis more likely by itself. A diagnostic is selected only after the available symptoms already support a hypothesis enough to justify collecting discriminating evidence.

The engine is also allowed to say that there is not enough evidence instead of forcing a root-cause verdict.

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
