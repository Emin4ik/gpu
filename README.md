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

The engine uses qualitative hypothesis states (`possible`, `supported`, `probable`, `confirmed`, `rejected`) instead of invented root-cause confidence percentages. A root cause only becomes `confirmed` after confirmation-grade evidence.

## Implemented PoC layers

- deterministic playbooks for PCIe, physical fabric/HCA, thermal/frequency, software/config, CPU/IRQ, storage/data starvation, and collective-work invariant failures;
- raw `lspci`, `nvidia-smi`, NCCL, and IB/RoCE ingestion;
- Slurm/GPU/HCA identity discovery and rank -> node -> GPU UUID -> PCI BDF -> HCA mapping;
- multi-device evidence storage and affected-path filtering;
- explicit diagnostic-test registry and deterministic next-test ranking;
- DCGM diagnostic/health adapter;
- NVIDIA XID/SXID history adapter;
- `/proc/interrupts`, IRQ affinity, and communication-process CPU-affinity evidence;
- HCA-aware IRQ -> CPU -> process correlation;
- staged replay, abstention, and a frozen M8 benchmark.

The complete roadmap is in [`PLAN.md`](PLAN.md).

## M8 frozen benchmark v0.1

M8 now contains **30 staged scenarios**: 21 public source incidents plus 9 adversarial/mutation scenarios. The split is 18 development / 12 frozen holdout. The holdout was SHA-256 frozen before its first run.

First frozen-run summary:

| Metric | Result |
|---|---:|
| Domain Recall@3 | 100% (9/9) |
| Directly useful next test (2/2) | 81.8% (9/11) |
| Premature confirmation | 0% |
| Abstention accuracy | **80% — below 90% gate** |
| Forbidden-hypothesis error | **25% — above 5% gate** |
| Median diagnostic-action reduction | 33.3% |
| Median tool-transition reduction | 66.7% |

This is an **engineering replay benchmark, not an accuracy claim and not real-cluster validation**. Action/tool reductions are curated proxies from published investigation sequences.

The result is intentionally not presented as a clean win: M8 exposed three concrete weaknesses around clean IRQ evidence, already-known equal rank work, and a previously failed rollback. Therefore **M9 CLI alpha remains blocked** until the general model handles negative evidence and completed diagnostics, followed by a newly frozen v0.2 benchmark.

See [`docs/BENCHMARK.md`](docs/BENCHMARK.md) for methodology and [`docs/M8_RESULTS_v0.1.md`](docs/M8_RESULTS_v0.1.md) for the first-run report.

## Automatic identity discovery

Supported discovery artifacts include `slurm-job.txt`, `rank-map.csv`, `nvidia-gpus.csv`, `ib-devices.csv`, and `nvidia-topo.txt`.

See [`docs/COLLECTING_IDENTITY.md`](docs/COLLECTING_IDENTITY.md).

## Evidence model

Evidence is entity-scoped, not a flat key/value dictionary:

```text
pcie_width @ pcie:0000:c1:00.0 = 16
pcie_width @ pcie:0000:e1:00.0 = 8
```

Facts are paired only on the same entity. If the affected workload path is known, unrelated device evidence is filtered before hypothesis evaluation.

See [`docs/EVIDENCE_MODEL.md`](docs/EVIDENCE_MODEL.md).

## Cross-tool evidence adapters

The PoC can combine DCGM findings, NVIDIA kernel events, PCIe/fabric facts, and host IRQ/CPU-affinity evidence while retaining raw provenance. Imported tool findings are evidence, not unquestioned root-cause verdicts.

See [`docs/ADAPTERS.md`](docs/ADAPTERS.md) and [`docs/HOST_AFFINITY.md`](docs/HOST_AFFINITY.md).

## Try it

```bash
python -m pip install -e '.[dev]'

gputriage examples/auto_identity_case
gputriage examples/multidevice_case
gputriage examples/m7_dcgm_xid_case
gputriage examples/m7_irq_affinity_case
```

Run the benchmark:

```bash
gputriage-benchmark data/benchmark_dev_v0.1.json.gz

gputriage-benchmark \
  data/benchmark_holdout_v0.1.json.gz \
  --freeze data/benchmark_holdout_v0.1.freeze.json
```

## Design rules

- missing evidence does not make a hypothesis more likely;
- parsers/adapters extract facts, not causes;
- multiple simultaneous causes are allowed;
- conclusions remain traceable to evidence;
- ambiguous identity mappings are not guessed;
- durable identifiers such as GPU UUID and PCI BDF are preferred over local indexes;
- cheap/read-only diagnostics are preferred when they offer comparable information;
- unsupported cases should abstain rather than manufacture a root cause;
- vendor-tool verdicts are evidence, not automatic `confirmed` causes;
- a diagnostic execution failure is not a component hardware failure;
- benchmark holdouts are versioned and immutable after first evaluation.

## Development

```bash
python -m pip install -e '.[dev]'
pytest -q
gputriage-eval data/staged_incidents_v0.1.json
gputriage-eval data/holdout_incidents_v0.1.json
gputriage-benchmark data/benchmark_dev_v0.1.json.gz --enforce-safety
```

GitHub Actions runs the regression suites and M8 safety gate on Python 3.10 and 3.12.

## Status

Research / proof of concept. **M0-M7 are complete at PoC level; M8 v0.1 baseline is recorded but the full gate did not pass. Next: M8.1 negative-evidence and redundant-test remediation, then a newly frozen M8 v0.2.**
