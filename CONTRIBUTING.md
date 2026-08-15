# Contributing to GPU Triage

GPU Triage is an evidence-first diagnostic planner. Contributions should preserve that boundary: parsers and adapters extract facts, hypotheses explain evidence, and the planner recommends the next diagnostic action without inventing confidence.

## Development setup

```bash
python -m pip install -e '.[dev]'
pytest -q
```

Before proposing a diagnostic-model change, also run the frozen benchmark gate:

```bash
gputriage-benchmark data/benchmark_holdout_v0.2.json.gz \
  --freeze data/benchmark_holdout_v0.2.freeze.json \
  --enforce-gates
```

## Contribution rules

- Do not turn absence of evidence into positive evidence.
- Keep entity identity and causality separate; a degraded device is not automatically the cause of a job symptom.
- Preserve negative evidence and completed-test memory.
- Prefer a general diagnostic rule plus regression cases over one-off incident matching.
- Add adapters only when they contribute evidence the planner can use.
- Keep unsupported cases capable of abstaining.
- Never rewrite a frozen benchmark corpus after its first evaluation. Material evaluation changes require a new benchmark version and freeze.
- Do not add network collection, credentials, remediation, or destructive commands to the default offline CLI without an explicit design review.

## Pull requests

Keep changes scoped and explain:

1. the operator problem;
2. the evidence or public incident motivating the change;
3. what behavior changes;
4. tests and benchmark impact;
5. any new privacy, safety, or compatibility boundary.

For parser changes, include representative sanitized fixtures where licensing and privacy allow it. For schema changes, follow `docs/SCHEMA_COMPATIBILITY.md`.

## Security and sensitive incident data

Do not commit production credentials, private logs, customer data, hostnames, job names, tokens, or proprietary incident artifacts. See `SECURITY.md` before sharing incident bundles.
