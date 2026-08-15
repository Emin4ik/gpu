# GPU Triage

**Evidence-first diagnostic planning for AI/GPU infrastructure.**

GPU Triage is an early open-source troubleshooting layer that makes existing infrastructure tools work together instead of replacing them.

> Don't replace your GPU tools. Make them work together.

Current public-alpha candidate: **`0.2.0a1`**.

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

## Public alpha quickstart

Development checkout:

```bash
python -m pip install -e '.[dev]'
gputriage --version
```

Expected version:

```text
gputriage 0.2.0a1
```

Run the public sanitized example:

```bash
gputriage investigate examples/public-alpha/pcie-needs-evidence.json
```

The example intentionally returns `needs_evidence` and recommends collecting PCIe link state rather than manufacturing a root cause.

For a real local incident bundle:

```bash
gputriage validate-bundle ./incident
gputriage investigate ./incident
gputriage investigate ./incident --format json
```

Export normalized pseudonymized evidence without copying raw artifacts:

```bash
gputriage export-sanitized ./incident sanitized.json
```

`investigate` uses explicit shell states:

| Exit | Result state |
|---:|---|
| `0` | confirmed |
| `10` | needs_evidence |
| `20` | abstain |
| `2` | invalid input/export |

JSON investigations use `gputriage.report.v1` and [`schemas/report-v1.schema.json`](schemas/report-v1.schema.json). Sanitized exports use [`schemas/sanitized-bundle-v1.schema.json`](schemas/sanitized-bundle-v1.schema.json).

See [`docs/CLI.md`](docs/CLI.md) for the operator contract and [`docs/PUBLIC_ALPHA.md`](docs/PUBLIC_ALPHA.md) for the release quickstart.

## Public-alpha packaging

Every CI candidate now:

- builds wheel and sdist;
- runs `twine check`;
- installs the built wheel into a clean virtual environment;
- verifies `gputriage --version`;
- smoke-tests the public sanitized example;
- uploads the validated distributions as a CI artifact;
- keeps the frozen M8.2 benchmark gate mandatory.

A manual [`public-alpha-release`](.github/workflows/release.yml) workflow re-runs tests, the frozen gate, build validation, and clean-wheel install before creating a GitHub **pre-release**. It refuses to replace an existing release and requires the requested tag to match the package version. PyPI publishing is intentionally not configured.

## Implemented diagnostic layers

- deterministic playbooks for PCIe, physical fabric/HCA, thermal/frequency, software/config, CPU/IRQ, storage/data starvation, and collective-work invariant failures;
- raw `lspci`, `nvidia-smi`, NCCL, and IB/RoCE ingestion;
- Slurm/GPU/HCA identity discovery and rank → node → GPU UUID → PCI BDF → HCA mapping;
- multi-device evidence storage and affected-path filtering;
- positive, negative, and contradictory diagnostic evidence;
- completed-test memory so already-answered diagnostics are not selected again;
- explicit diagnostic-test registry and deterministic next-test ranking;
- DCGM diagnostic/health and NVIDIA XID/SXID adapters;
- `/proc/interrupts`, IRQ affinity, and communication-process CPU-affinity evidence;
- versioned text/JSON CLI reports, bundle validation and sanitized normalized export;
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

## Evidence and privacy rules

- missing evidence does not make a hypothesis more likely;
- collected negative evidence is not treated as missing evidence;
- completed diagnostics are not selected again unless an explicit retest policy says so;
- parsers/adapters extract facts, not causes;
- ambiguous identity mappings are not guessed;
- unsupported cases abstain rather than manufacture a root cause;
- vendor-tool verdicts are evidence, not automatic `confirmed` causes;
- frozen benchmark versions are immutable after first evaluation;
- current CLI diagnosis is offline and performs no SSH/API/upload collection.

Sanitized export copies no raw artifact bytes, removes `raw_ref`, pseudonymizes known graph identities, and omits free-text symptom text by default. It is **not** a general DLP/secret/PII scanner; review arbitrary string-valued evidence before public sharing. See [`SECURITY.md`](SECURITY.md).

## Project policies

- [`LICENSE`](LICENSE) — Apache-2.0
- [`CHANGELOG.md`](CHANGELOG.md)
- [`CONTRIBUTING.md`](CONTRIBUTING.md)
- [`SECURITY.md`](SECURITY.md)
- [`docs/SCHEMA_COMPATIBILITY.md`](docs/SCHEMA_COMPATIBILITY.md)

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

GitHub Actions runs regression suites and frozen benchmark checks on Python 3.10 and 3.12, plus package build/install smoke tests on Python 3.12.

## Status

Research / alpha-stage proof of concept. **M8.2 passed the frozen engineering gate, M9 CLI alpha is complete, and the M10 `0.2.0a1` release candidate is build/install validated. The GitHub tag/pre-release is the remaining publication step before outside-user validation.**
