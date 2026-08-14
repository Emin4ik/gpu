# M7 evidence adapters

GPU Triage consumes specialist-tool output as evidence. Adapters extract facts and identity; they do not turn a vendor status into a root-cause verdict by themselves.

## DCGM JSON

Recognized incident files:

- `dcgm-diag.json` / `dcgm_diag.json`
- `dcgm-health.json` / `dcgm_health.json`
- other `dcgm*.json` files

Typical collection examples:

```bash
# Active diagnostic: run intentionally and scope it to the desired validation.
dcgmi diag -r pcie -j > dcgm-diag.json

# Passive health check (requires health watches to have been configured/sampled).
dcgmi health --check --json > dcgm-health.json
```

The adapter is intentionally defensive because `dcgmi` JSON should not be treated as a stable, versioned public schema. It walks semantic `tests`, `results`, status, entity, incident, warning, and error fields instead of assuming one exact document shape.

Normalized examples include:

- `dcgm_test_status.<test>`
- `dcgm_test_failed`
- `dcgm_pcie_test_failed`
- `dcgm_memory_test_failed`
- `dcgm_thermal_test_failed`
- `dcgm_communication_test_failed`
- `dcgm_health_incident`
- `dcgm_*_health_incident`
- `dcgm_failure_code`
- `dcgm_failure_message`
- `dcgm_test_execution_issue`
- `dcgm_hardware_failure`

A failed test is **not automatically classified as hardware**. CUDA/API/internal/disabled/aborted-style failures are kept as execution evidence so the planner does not confuse “the diagnostic could not execute” with “the component is broken.”

DCGM GPU entity IDs are local indexes. `reconcile_adapter_entities()` maps `gpu-index:N` to durable GPU UUID entities from the identity graph. When the index is ambiguous, GPU Triage emits a warning and does not guess.

## NVIDIA kernel / journal events

Recognized files:

- `journal.log` / `journal.txt`
- `dmesg.log` / `dmesg.txt`
- matching `journal*` and `dmesg*` files

Collection examples:

```bash
journalctl -k --since '2 hours ago' \
  | grep -E 'NVRM: (GPU at|Xid)|SXid' > journal.log

# Or, for the current kernel buffer:
dmesg -T | grep -E 'NVRM: (GPU at|Xid)|SXid' > dmesg.log
```

The adapter recognizes NVIDIA mappings such as a GPU UUID associated with a PCI BDF, then uses that mapping to scope subsequent XID records to a durable `gpu:<UUID>` entity. Without a UUID mapping, the XID remains attached to `pcie:<BDF>`.

Normalized examples:

- `nvidia_xid_code`
- `nvidia_xid_message`
- `gpu_xid_or_ecc_error`
- `gpu_fallen_off_bus`
- `gpu_memory_error_event`
- `gpu_nvlink_error_event`
- `nvidia_sxid_code`
- `nvidia_sxid_message`
- `nvidia_sxid_event`

Every event keeps a line-level `raw_ref` such as `journal.log:L42`.

## Identity safety

When affected ranks and topology are known, entity-scoped DCGM/XID evidence must intersect the affected GPU/PCIe path before it can reach the hypothesis engine.

Therefore:

```text
XID on affected GPU     -> accepted evidence
XID on unrelated GPU    -> ignored for this incident
ambiguous DCGM GPU index -> warning + excluded from affected-path diagnosis
```

SXID is parsed and preserved, but v0.1 does not yet have NVSwitch entities/topology in the identity graph. It should not be treated as fully topology-scoped fabric causality yet.

## Current boundary

M7 P0 imports evidence from DCGM and NVIDIA kernel logs. It does not:

- auto-run active DCGM diagnostics;
- claim that every XID is hardware-caused;
- decode the entire NVIDIA XID/SXID catalog into remediation rules;
- model NVSwitch topology yet;
- replace DCGM, `journalctl`, or vendor diagnostics.
