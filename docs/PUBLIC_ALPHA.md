# Public alpha quickstart

GPU Triage `0.2.0a1` is an offline evidence-first diagnostic planner for GPU/AI infrastructure incidents.

## Install from a built wheel

After downloading the wheel from a GitHub pre-release:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install ./gputriage-0.2.0a1-py3-none-any.whl
gputriage --version
```

Expected version output:

```text
gputriage 0.2.0a1
```

## Run the sanitized public example

```bash
gputriage investigate examples/public-alpha/pcie-needs-evidence.json
```

The example intentionally stops at `needs_evidence`: the evidence localizes a communication regression to a shared PCIe path, but it does not yet prove link degradation. The planner should recommend collecting PCIe link state rather than claiming a root cause.

Machine-readable output:

```bash
gputriage investigate examples/public-alpha/pcie-needs-evidence.json --format json
```

`needs_evidence` exits with code `10` by design. See `docs/CLI.md` for the full exit-code contract.

## Validate a real incident bundle

Before diagnosis:

```bash
gputriage validate-bundle ./incident
```

Then investigate:

```bash
gputriage investigate ./incident
gputriage investigate ./incident --format json
```

## Sharing an incident

Create a normalized pseudonymized export:

```bash
gputriage export-sanitized ./incident sanitized.json
```

Review `sanitized.json` manually before sending it outside your trust boundary. Sanitized export does not promise secret/PII detection or complete anonymization.

## Alpha expectations

- The diagnostic engine and frozen benchmark gate are deterministic.
- The CLI and JSON v1 contracts are versioned, but the package is still pre-1.0.
- No live SSH/API collection or automatic remediation occurs in the default CLI.
- The published staged-replay benchmark is an engineering gate, not a real-world accuracy guarantee.

Compatibility policy: `docs/SCHEMA_COMPATIBILITY.md`.
Security/privacy boundary: `SECURITY.md`.
