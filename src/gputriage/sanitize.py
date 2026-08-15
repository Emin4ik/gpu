from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .bundle import validate_bundle
from .identity import IdentityGraph
from .models import Observation

SANITIZED_BUNDLE_SCHEMA_VERSION = "gputriage.sanitized-bundle.v1"

_KIND_PREFIX = {
    "job": "job",
    "rank": "rank",
    "node": "node",
    "gpu": "gpu",
    "pcie_device": "pcie",
    "nic_hca": "hca",
}


def _alias_maps(graph: IdentityGraph) -> tuple[dict[str, str], dict[str, str]]:
    entity_aliases: dict[str, str] = {}
    text_replacements: dict[str, str] = {}
    counters: dict[str, int] = {}

    for entity_id in sorted(graph.entities):
        entity = graph.entities[entity_id]
        prefix = _KIND_PREFIX.get(entity.kind, "entity")
        counters[prefix] = counters.get(prefix, 0) + 1
        short_alias = f"{prefix}-{counters[prefix]:03d}"
        alias_id = f"{prefix}:{short_alias}"
        entity_aliases[entity.id] = alias_id
        text_replacements[entity.id] = alias_id

        for key, value in entity.attributes.items():
            if not isinstance(value, str) or not value.strip():
                continue
            key_lower = str(key).lower()
            if key_lower in {
                "hostname",
                "node",
                "uuid",
                "pci_bdf",
                "bdf",
                "guid",
                "ibdev",
                "device",
                "netdev",
                "scheduler_job_id",
            }:
                text_replacements[value] = short_alias
    return entity_aliases, text_replacements


def _scrub_text(value: str, replacements: dict[str, str]) -> str:
    scrubbed = value
    for original in sorted(replacements, key=len, reverse=True):
        if original:
            scrubbed = scrubbed.replace(original, replacements[original])
    # Remove common residual GPU UUID forms that may appear only in raw-derived strings.
    scrubbed = re.sub(r"GPU-[0-9A-Fa-f-]{8,}", "gpu-redacted", scrubbed)
    return scrubbed


def _scrub_value(value: Any, replacements: dict[str, str]) -> Any:
    if isinstance(value, str):
        return _scrub_text(value, replacements)
    if isinstance(value, list):
        return [_scrub_value(item, replacements) for item in value]
    if isinstance(value, tuple):
        return [_scrub_value(item, replacements) for item in value]
    if isinstance(value, dict):
        return {str(key): _scrub_value(item, replacements) for key, item in value.items()}
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return repr(value)


def _sanitize_observation(
    observation: Observation,
    entity_aliases: dict[str, str],
    replacements: dict[str, str],
) -> dict[str, Any]:
    entity = entity_aliases.get(observation.entity, observation.entity) if observation.entity else None
    if entity:
        entity = _scrub_text(entity, replacements)
    return {
        "key": observation.key,
        "value": _scrub_value(observation.value, replacements),
        "source": _scrub_text(observation.source, replacements),
        "entity": entity,
        "raw_ref": None,
    }


def build_sanitized_bundle(root: Path, *, include_symptom: bool = False) -> dict[str, Any]:
    """Export normalized evidence only; raw artifact bytes are never copied.

    This is deliberately conservative. It pseudonymizes identities known to the
    identity graph, removes raw references, and omits free-text symptom text by
    default. It is not a general secret/PII scanner for arbitrary user strings.
    """

    validation = validate_bundle(root)
    if not validation.valid or validation.ingest_result is None:
        details = "; ".join(validation.errors) or "bundle validation failed"
        raise ValueError(details)

    ingest = validation.ingest_result
    entity_aliases, replacements = _alias_maps(ingest.identity_graph)
    symptom = _scrub_text(ingest.symptom, replacements) if include_symptom else "sanitized incident"
    observations = [
        _sanitize_observation(observation, entity_aliases, replacements)
        for observation in ingest.observations
    ]
    affected_entities = [
        entity_aliases.get(entity, _scrub_text(entity, replacements))
        for entity in ingest.affected_entities
    ]

    return {
        "schema_version": SANITIZED_BUNDLE_SCHEMA_VERSION,
        "symptom": symptom,
        "observations": observations,
        "affected_entities": affected_entities,
        "sanitization": {
            "raw_artifacts_included": False,
            "raw_ref_removed": True,
            "identity_pseudonymization": "deterministic-within-export",
            "free_text_symptom_included": include_symptom,
            "warning": "Normalized best-effort export; review before sharing because arbitrary observation strings are not a general secret scanner.",
        },
    }


def export_sanitized_bundle(
    root: Path,
    output: Path,
    *,
    include_symptom: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    if output.exists() and not force:
        raise FileExistsError(f"output already exists: {output}; pass --force to overwrite")
    payload = build_sanitized_bundle(root, include_symptom=include_symptom)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload
