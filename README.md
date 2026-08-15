# GPU Triage

**Evidence-first diagnostic planning for AI/GPU infrastructure.**

GPU Triage is an early open-source troubleshooting layer that makes existing infrastructure tools work together instead of replacing them.

> Don't replace your GPU tools. Make them work together.

```text
raw artifacts / specialist tools
        → identity graph
        → entity-scoped evidence
        → hypotheses
        → eligible diagnostics
        → transparent test ranking
        → next best test or abstention
        → confirmation / rejection
```

The engine uses qualitative states (`possible`, `supported`, `probable`, `confirmed`, `rejected`) instead of invented root-cause confidence percentages. A cause becomes `confirmed` only after confirmation-grade evidence.

## Implemented PoC layers

- deterministic playbooks for PCIe, physical fabric/HCA, thermal/frequency, software/config, CPU/IRQ, storage/data starvation, and collective-work invariant failures;
- raw `lspci`, `nvidia-smi`, NCCL, and IB/RoCE ingestion;
- Slurm/GPU/HCA identity discovery and rank → node → GPU UUID → PCI BDF → HCA mapping;
- multi-device evidence storage and affected-path filtering;
- positive, negative, and contradictory diagnostic evidence;
- completed-test memory so already-answered diagnostics are not selected again;
- explicit diagnostic-test registry and deterministic next-test ranking;
- DCGM diagnostic/health and NVIDIA XID/SXID adapters;
- `/proc/interrupts`, IRQ affinity, and communication-process CPU-affinity evidence;
- staged replay, explicit abstention, and versioned frozen benchmark gates.

See [`PLAN.md`](PLAN.md) for the roadmap.

## Frozen benchmark v0.2

The original v0.1 benchmark exposed gaps in negative-evidence handling. M8.1 fixed the general model, then a fresh `v0.2` benchmark was sourced and frozen before execution:

- 24 staged scenarios;
- 16 public source incidents;
- 8 adversarial/mutation scenarios;
- 12 development / 12 frozen holdout;
- frozen SHA-256: `3fba89e4f644630bf4dd4a6475af33e2215983d6ae59659980a1139bd21e32a0`.

First frozen v0.2 run:

| Metric | Result |
|---|---:|
| Domain Recall@3 | 100% (10/10) |
| Directly useful next test (2/2) | 100% (10/10) |
| Premature confirmation | 0% (0/22 stages) |
| Abstention accuracy | 100% (7/7) |
| Forbidden/red-herring hypothesis error | 0% (0/10) |
| Median diagnostic-action reduction | 75% |
| Median tool-transition reduction | 100% |

All predefined M8.2 PoC gates passed and freeze verification succeeded without post-freeze engine tuning.

**This is an engineering staged-replay benchmark, not a claim of 100% real-world diagnostic accuracy.** The holdout is small and author-curated, action/tool reductions are replay proxies, and no live multi-node GPU cluster was used.

See [`docs/M8_RESULTS_v0.2.md`](docs/M8_RESULTS_v0.2.md), [`docs/M8_V0_2_SOURCES.md`](docs/M8_V0_2_SOURCES.md), and [`docs/BENCHMARK_V0_2_PROTOCOL.md`](docs/BENCHMARK_V0_2_PROTOCOL.md).

## Evidence model

Evidence is entity-scoped, not a flat key/value dictionary:

```text
pcie_width @ pcie:0000:c1:00.0 = 16
pcie_width @ pcie:0000:e1:00.0 = 8
```

Facts are paired only on the same entity. Unrelated broken hardware is filtered out when the affected workload path is known.

Completed diagnostics can contribute explicit negative results:

```text
host IRQ hypothesis SUPPORTED
  → collect IRQ affinity
  → irq_affinity_clean = true
  → hypothesis REJECTED
  → collect_irq_affinity cannot be selected again
```

## Try it

```bash
python -m pip install -e '.[dev]'

gputriage examples/auto_identity_case
gputriage examples/multidevice_case
gputriage examples/m7_dcgm_xid_case
gputriage examples/m7_irq_affinity_case
```

Run the current frozen benchmark regression:

```bash
gputriage-benchmark \
  data/benchmark_holdout_v0.2.json.gz \
  --freeze data/benchmark_holdout_v0.2.freeze.json \
  --enforce-gates
```

## Design rules

- missing evidence does not make a hypothesis more likely;
- collected negative evidence is not treated as missing evidence;
- completed diagnostics are not selected again unless an explicit retest policy says so;
- parsers/adapters extract facts, not causes;
- multiple simultaneous causes are allowed;
- supported conclusions remain traceable to evidence;
- ambiguous identity mappings are not guessed;
- unsupported cases abstain rather than manufacture a root cause;
- vendor-tool verdicts are evidence, not automatic `confirmed` causes;
- diagnostic execution failure is not hardware failure;
- frozen benchmark versions are immutable after first evaluation.

## Development

```bash
python -m pip install -e '.[dev]'
pytest -q
gputriage-eval data/staged_incidents_v0.1.json
gputriage-eval data/holdout_incidents_v0.1.json
gputriage-benchmark data/benchmark_dev_v0.2.json.gz --enforce-safety
gputriage-benchmark data/benchmark_holdout_v0.2.json.gz \
  --freeze data/benchmark_holdout_v0.2.freeze.json --enforce-gates
```

GitHub Actions runs regression suites and frozen benchmark checks on Python 3.10 and 3.12.

## Status

Research / proof of concept. **M8.2 passed the predefined frozen engineering gate. M9 CLI alpha is the next milestone.**
