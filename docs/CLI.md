# GPU Triage CLI alpha

The CLI is offline-by-default: it reads a local incident bundle, normalizes evidence, runs deterministic playbooks/planning, and writes only to stdout or an explicitly requested export path. It does not SSH to nodes, call vendor APIs, or upload incident data.

## Primary commands

### Investigate

```bash
gputriage investigate ./incident --format text
gputriage investigate ./incident --format json
```

A legacy single JSON file remains accepted:

```bash
gputriage investigate incident.json --format json
# Backward-compatible shorthand:
gputriage incident.json --format json
```

Directory input is validated before diagnosis. JSON output conforms to [`../schemas/report-v1.schema.json`](../schemas/report-v1.schema.json).

### Validate a bundle

```bash
gputriage validate-bundle ./incident
gputriage validate-bundle ./incident --format json
```

Validation checks the directory shape and metadata types, then runs ingestion far enough to surface malformed or ambiguous input as actionable errors. It does **not** interpret the diagnosis.

### Export normalized sanitized evidence

```bash
gputriage export-sanitized ./incident sanitized.json
```

The default export:

- copies **no raw artifact bytes**;
- exports normalized observations only;
- pseudonymizes identities known to the identity graph with deterministic aliases inside that export;
- removes every `raw_ref`;
- replaces free-text symptom text with `sanitized incident`.

Opt in to best-effort pseudonymized symptom text with:

```bash
gputriage export-sanitized ./incident sanitized.json --include-symptom
```

The export will not overwrite an existing file unless `--force` is provided.

The sanitized format is defined in [`../schemas/sanitized-bundle-v1.schema.json`](../schemas/sanitized-bundle-v1.schema.json). It is intentionally a **normalized evidence export**, not a promise of general DLP/secret/PII detection. Arbitrary string-valued evidence should still be reviewed before public sharing.

A sanitized JSON export can be replayed directly:

```bash
gputriage investigate sanitized.json --format json
```

## Incident directory contract v1

An incident is a directory containing at least one recognized metadata or diagnostic artifact. `incident.json` is the preferred metadata entrypoint; `context.json` remains accepted for compatibility.

Minimal example:

```json
{
  "symptom": "localized NCCL slowdown",
  "observations": [
    {"key": "communication_regression_localized", "value": true}
  ]
}
```

Optional metadata fields include:

- `affected_entities`: entity IDs already known to be in scope;
- `identity_graph`: explicit entities and relations when automatic discovery is unavailable;
- `artifact_entities`: explicit artifact-to-entity mappings;
- `observations`: high-level facts not extracted from raw artifacts.

Recognized raw/discovery artifacts include the existing Slurm/rank/GPU/HCA identity files plus `nvidia-smi`, `lspci`, NCCL, IB/RoCE, DCGM, journal/dmesg, `/proc/interrupts`, IRQ affinity and process-affinity files documented elsewhere in this repository.

Unknown files may coexist with recognized artifacts; they are not automatically interpreted.

## Result states and exit codes

`investigate` deliberately distinguishes a diagnosis from an incomplete or unsupported investigation:

| Exit code | State | Meaning |
|---:|---|---|
| `0` | `confirmed` | At least one hypothesis reached confirmation-grade evidence. |
| `10` | `needs_evidence` | No confirmed verdict; the planner has a useful next diagnostic. |
| `20` | `abstain` | Current playbooks cannot justify a next diagnostic or confirmed verdict. |
| `2` | invalid input | Bundle/file validation or export failed. |

`validate-bundle` returns `0` for a valid bundle and `2` for invalid input. `export-sanitized` returns `0` on success and `2` on validation/write failure.

This makes shell automation explicit rather than treating every non-crash investigation as success.

## Report v1

Machine-readable reports use:

```text
schema_version = gputriage.report.v1
```

Key fields:

- `result_state`, `symptom`, `verdict`;
- `affected_entities`, parsed files and ingestion warnings;
- every hypothesis with supporting, contradicting and missing evidence;
- selected next test with purpose, command template, cost, invasiveness, duration, expected outcomes, selection reason and alternatives;
- normalized observations with `source`, `entity` and `raw_ref` provenance.

The JSON report intentionally includes observations even when the text view summarizes them, so downstream tooling can audit why the planner reached a state.

## Offline behavior

The current CLI performs no network collection. All evidence must already be in the incident bundle. Future live collectors, if added, should be separate opt-in commands so offline replay remains deterministic and safe by default.
