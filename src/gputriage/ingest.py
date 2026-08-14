from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from .discovery import discover_identity, merge_graphs
from .identity import IdentityGraph, derive_identity_observations, observation_is_on_affected_path
from .models import Observation
from .parsers import parse_ib_counters, parse_lspci, parse_nccl_log, parse_nvidia_smi_q


@dataclass
class IngestResult:
    symptom: str
    observations: list[Observation]
    parsed_files: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    identity_graph: IdentityGraph = field(default_factory=IdentityGraph)
    affected_entities: list[str] = field(default_factory=list)


def _load_context(path: Path) -> tuple[dict[str, Any], list[Observation]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    observations = [Observation(**item) for item in payload.get("observations", [])]
    return payload, observations


def _find_first(root: Path, names: tuple[str, ...]) -> Path | None:
    for name in names:
        candidate = root / name
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _by_key(observations: list[Observation]) -> dict[str, Observation]:
    return {ob.key: ob for ob in observations}


def _attach_entity(observations: list[Observation], entity: str | None) -> list[Observation]:
    if not entity:
        return observations
    return [replace(observation, entity=entity) for observation in observations]


def _derive_baseline_facts(current: list[Observation], baseline: list[Observation]) -> list[Observation]:
    derived: list[Observation] = []
    cur = _by_key(current)
    base = _by_key(baseline)

    current_clock = cur.get("gpu_sm_clock_mhz")
    baseline_clock = base.get("gpu_sm_clock_mhz")
    if current_clock and baseline_clock and isinstance(current_clock.value, int) and isinstance(baseline_clock.value, int):
        if baseline_clock.value > 0 and current_clock.value < baseline_clock.value * 0.90:
            derived.append(
                Observation(
                    "gpu_clock_below_peer",
                    True,
                    "derived:nvidia-smi-baseline",
                    entity=current_clock.entity,
                )
            )

    current_errors = cur.get("fabric_error_counter_total")
    baseline_errors = base.get("fabric_error_counter_total")
    if current_errors and baseline_errors and isinstance(current_errors.value, int) and isinstance(baseline_errors.value, int):
        if current_errors.value > baseline_errors.value:
            derived.append(
                Observation(
                    "fabric_error_counters_rising",
                    True,
                    "derived:ib-baseline",
                    entity=current_errors.entity,
                )
            )
        else:
            derived.append(
                Observation(
                    "fabric_counters_clean",
                    True,
                    "derived:ib-baseline",
                    entity=current_errors.entity,
                )
            )

    return derived


def ingest_directory(root: Path) -> IngestResult:
    if not root.is_dir():
        raise ValueError(f"not a directory: {root}")

    context_path = _find_first(root, ("incident.json", "context.json"))
    if context_path:
        payload, context_observations = _load_context(context_path)
        symptom = payload.get("symptom", "unspecified incident")
        parsed_files = [context_path.name]
    else:
        payload, context_observations = {}, []
        symptom, parsed_files = "unspecified incident", []

    manual_graph = IdentityGraph.from_payload(payload.get("identity_graph"))
    discovery = discover_identity(root, payload)
    graph = merge_graphs(discovery.graph, manual_graph)
    affected_entities = list(payload.get("affected_entities", [])) or discovery.affected_entities
    artifact_entities = dict(payload.get("artifact_entities", {}))
    warnings = discovery.warnings + graph.validation_errors()
    for discovered_file in discovery.parsed_files:
        if discovered_file not in parsed_files:
            parsed_files.append(discovered_file)

    baseline_dir = root / "baseline"
    artifact_observations: list[Observation] = []
    parser_specs = [
        (("nvidia-smi-q.txt", "nvidia_smi_q.txt"), parse_nvidia_smi_q),
        (("lspci.txt", "lspci-vv.txt"), parse_lspci),
        (("nccl.log", "nccl.txt"), parse_nccl_log),
        (("ib-counters.txt", "ib_counters.txt", "ibqueryerrors.txt"), parse_ib_counters),
    ]

    for names, parser in parser_specs:
        current_path = _find_first(root, names)
        if not current_path:
            continue

        entity = artifact_entities.get(current_path.name)
        if not entity and graph.entities and affected_entities:
            target_kind = None
            if parser is parse_lspci:
                target_kind = "pcie_device"
            elif parser is parse_ib_counters:
                target_kind = "nic_hca"
            elif parser is parse_nvidia_smi_q:
                target_kind = "gpu"
            if target_kind:
                common = graph.common_targets(affected_entities, target_kind)
                if len(common) == 1:
                    entity = next(iter(common))
                elif len(common) > 1:
                    warnings.append(
                        f"Ambiguous {target_kind} scope for {current_path.name}: {', '.join(sorted(common))}"
                    )

        current_obs = parser(current_path.read_text(encoding="utf-8", errors="replace"), source=current_path.name)
        current_obs = _attach_entity(current_obs, entity)
        artifact_observations.extend(current_obs)
        parsed_files.append(current_path.name)

        if baseline_dir.is_dir():
            baseline_path = _find_first(baseline_dir, names)
            if baseline_path:
                baseline_key = f"baseline/{baseline_path.name}"
                baseline_entity = artifact_entities.get(baseline_key, entity)
                baseline_obs = parser(
                    baseline_path.read_text(encoding="utf-8", errors="replace"),
                    source=baseline_key,
                )
                baseline_obs = _attach_entity(baseline_obs, baseline_entity)
                artifact_observations.extend(_derive_baseline_facts(current_obs, baseline_obs))
                parsed_files.append(baseline_key)

    if graph.entities and affected_entities:
        scoped: list[Observation] = []
        for observation in artifact_observations:
            if observation_is_on_affected_path(observation, graph, affected_entities):
                scoped.append(observation)
            else:
                warnings.append(
                    f"Ignored unscoped or unrelated evidence {observation.key} from {observation.source}"
                )
        artifact_observations = scoped

    observations = context_observations + derive_identity_observations(graph, affected_entities) + artifact_observations

    deduped: dict[str, Observation] = {}
    for observation in observations:
        deduped[observation.key] = observation

    if not parsed_files:
        warnings.append("No recognized incident artifacts were found.")

    return IngestResult(
        symptom=symptom,
        observations=list(deduped.values()),
        parsed_files=parsed_files,
        warnings=warnings,
        identity_graph=graph,
        affected_entities=affected_entities,
    )
