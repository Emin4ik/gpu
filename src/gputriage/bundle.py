from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .ingest import IngestResult, ingest_directory


@dataclass
class BundleValidation:
    path: Path
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    ingest_result: IngestResult | None = None

    @property
    def valid(self) -> bool:
        return not self.errors


_RECOGNIZED_EXACT = {
    "incident.json",
    "context.json",
    "slurm-job.txt",
    "rank-map.csv",
    "nvidia-gpus.csv",
    "ib-devices.csv",
    "nvidia-topo.txt",
    "nvidia-smi-q.txt",
    "nvidia_smi_q.txt",
    "lspci.txt",
    "lspci-vv.txt",
    "nccl.log",
    "nccl.txt",
    "ib-counters.txt",
    "ib_counters.txt",
    "ibqueryerrors.txt",
    "dcgm-diag.json",
    "dcgm_diag.json",
    "dcgm-health.json",
    "dcgm_health.json",
    "journal.log",
    "journal.txt",
    "dmesg.log",
    "dmesg.txt",
    "proc-interrupts.txt",
    "proc_interrupts.txt",
    "irq-affinity.csv",
    "irq_affinity.csv",
    "process-affinity.csv",
    "process_affinity.csv",
}

_RECOGNIZED_PATTERNS = (
    "nvidia-smi-q*.txt",
    "nvidia_smi_q*.txt",
    "lspci*.txt",
    "nccl*.log",
    "ib-counters*.txt",
    "ib_counters*.txt",
    "ibqueryerrors*.txt",
    "dcgm*.json",
    "journal*.log",
    "journal*.txt",
    "dmesg*.log",
    "dmesg*.txt",
    "proc-interrupts*.txt",
    "proc_interrupts*.txt",
    "irq-affinity*.csv",
    "irq_affinity*.csv",
    "process-affinity*.csv",
    "process_affinity*.csv",
)


def _validate_context_payload(payload: Any, source: str, errors: list[str]) -> None:
    if not isinstance(payload, dict):
        errors.append(f"{source}: top-level JSON value must be an object")
        return
    if "symptom" in payload and not isinstance(payload["symptom"], str):
        errors.append(f"{source}: symptom must be a string")
    if "observations" in payload:
        observations = payload["observations"]
        if not isinstance(observations, list):
            errors.append(f"{source}: observations must be a list")
        else:
            for index, item in enumerate(observations):
                if not isinstance(item, dict):
                    errors.append(f"{source}: observations[{index}] must be an object")
                    continue
                if not isinstance(item.get("key"), str) or not item.get("key"):
                    errors.append(f"{source}: observations[{index}].key must be a non-empty string")
                if "value" not in item:
                    errors.append(f"{source}: observations[{index}] is missing value")
    if "affected_entities" in payload and not (
        isinstance(payload["affected_entities"], list)
        and all(isinstance(item, str) for item in payload["affected_entities"])
    ):
        errors.append(f"{source}: affected_entities must be a list of strings")
    if "identity_graph" in payload and not isinstance(payload["identity_graph"], dict):
        errors.append(f"{source}: identity_graph must be an object")
    if "artifact_entities" in payload and not isinstance(payload["artifact_entities"], dict):
        errors.append(f"{source}: artifact_entities must be an object")


def _has_recognized_artifact(root: Path) -> bool:
    if any((root / name).is_file() for name in _RECOGNIZED_EXACT):
        return True
    return any(any(root.glob(pattern)) for pattern in _RECOGNIZED_PATTERNS)


def validate_bundle(root: Path) -> BundleValidation:
    result = BundleValidation(path=root)
    if not root.exists():
        result.errors.append(f"bundle does not exist: {root}")
        return result
    if not root.is_dir():
        result.errors.append("bundle must be a directory; use `gputriage investigate <file.json>` only for legacy single-file input")
        return result

    if not _has_recognized_artifact(root):
        result.errors.append("bundle contains no recognized incident metadata or diagnostic artifacts")
        return result

    context_paths = [path for path in (root / "incident.json", root / "context.json") if path.is_file()]
    if len(context_paths) > 1:
        result.warnings.append("both incident.json and context.json exist; incident.json takes precedence")

    for context_path in context_paths:
        try:
            payload = json.loads(context_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            result.errors.append(f"{context_path.name}: invalid JSON: {exc}")
            continue
        _validate_context_payload(payload, context_path.name, result.errors)

    if result.errors:
        return result

    try:
        ingest = ingest_directory(root)
    except Exception as exc:  # validation boundary: convert parser failures into actionable CLI errors
        result.errors.append(f"bundle ingestion failed: {type(exc).__name__}: {exc}")
        return result

    result.ingest_result = ingest
    result.warnings.extend(ingest.warnings)
    return result
