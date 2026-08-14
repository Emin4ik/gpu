from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable

from .adapter_utils import reconcile_adapter_entities
from .adapters import parse_dcgm_json, parse_nvidia_system_log
from .discovery import discover_identity, merge_graphs
from .host_adapters import derive_irq_affinity_facts, parse_irq_affinity_csv, parse_proc_interrupts, parse_process_affinity_csv
from .identity import IdentityGraph, derive_identity_observations, observation_is_on_affected_path
from .models import Observation
from .parsers import parse_ib_counters, parse_lspci, parse_nccl_log, parse_nvidia_smi_q

Parser = Callable[[str, str], list[Observation]]


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
    return payload, [Observation(**item) for item in payload.get("observations", [])]


def _find_first(root: Path, names: tuple[str, ...]) -> Path | None:
    for name in names:
        candidate = root / name
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _find_artifacts(root: Path, exact_names: tuple[str, ...], patterns: tuple[str, ...]) -> list[Path]:
    found: dict[str, Path] = {}
    for name in exact_names:
        candidate = root / name
        if candidate.is_file():
            found[candidate.name] = candidate
    for pattern in patterns:
        for candidate in root.glob(pattern):
            if candidate.is_file():
                found[candidate.name] = candidate
    return [found[name] for name in sorted(found)]


def _attach_entity_if_missing(observations: list[Observation], entity: str | None) -> list[Observation]:
    if not entity:
        return observations
    return [replace(observation, entity=observation.entity or entity) for observation in observations]


def _by_entity_key(observations: list[Observation]) -> dict[tuple[str, str | None], Observation]:
    return {(ob.key, ob.entity): ob for ob in observations}


def _derive_baseline_facts(current: list[Observation], baseline: list[Observation]) -> list[Observation]:
    derived: list[Observation] = []
    cur = _by_entity_key(current)
    base = _by_entity_key(baseline)
    for entity in {entity for key, entity in cur if key == "gpu_sm_clock_mhz"}:
        current_clock = cur.get(("gpu_sm_clock_mhz", entity))
        baseline_clock = base.get(("gpu_sm_clock_mhz", entity))
        if current_clock and baseline_clock and isinstance(current_clock.value, int) and isinstance(baseline_clock.value, int):
            if baseline_clock.value > 0 and current_clock.value < baseline_clock.value * 0.90:
                derived.append(Observation("gpu_clock_below_peer", True, "derived:nvidia-smi-baseline", entity=entity, raw_ref=f"{current_clock.raw_ref or current_clock.source} vs {baseline_clock.raw_ref or baseline_clock.source}"))
    for entity in {entity for key, entity in cur if key == "fabric_error_counter_total"}:
        current_errors = cur.get(("fabric_error_counter_total", entity))
        baseline_errors = base.get(("fabric_error_counter_total", entity))
        if current_errors and baseline_errors and isinstance(current_errors.value, int) and isinstance(baseline_errors.value, int):
            key = "fabric_error_counters_rising" if current_errors.value > baseline_errors.value else "fabric_counters_clean"
            derived.append(Observation(key, True, "derived:ib-baseline", entity=entity, raw_ref=f"{current_errors.raw_ref or current_errors.source} vs {baseline_errors.raw_ref or baseline_errors.source}"))
    return derived


def _infer_entity_from_filename(path: Path, parser: Parser, graph: IdentityGraph) -> str | None:
    name = path.name
    if parser is parse_lspci:
        match = re.search(r"([0-9A-Fa-f]{4,8}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}\.[0-7])", name)
        if match:
            bdf = match.group(1).lower()
            if len(bdf.split(":", 1)[0]) > 4:
                bdf = bdf[-12:]
            candidate = f"pcie:{bdf}"
            if candidate in graph.entities:
                return candidate
    elif parser is parse_nvidia_smi_q:
        match = re.search(r"(GPU-[A-Za-z0-9-]+)", name)
        if match and f"gpu:{match.group(1)}" in graph.entities:
            return f"gpu:{match.group(1)}"
    elif parser is parse_ib_counters:
        match = re.search(r"(mlx\d+_\d+)", name)
        if match:
            candidates = [entity.id for entity in graph.entities.values() if entity.kind == "nic_hca" and entity.attributes.get("ibdev") == match.group(1)]
            if len(candidates) == 1:
                return candidates[0]
    return None


def _auto_scope_entity(parser: Parser, graph: IdentityGraph, affected_entities: list[str]) -> tuple[str | None, str | None]:
    if not graph.entities or not affected_entities:
        return None, None
    if parser is parse_lspci:
        common, kind = graph.common_gpu_pcie_targets(affected_entities), "GPU PCIe"
    elif parser is parse_ib_counters:
        common, kind = graph.common_targets(affected_entities, "nic_hca"), "HCA"
    elif parser is parse_nvidia_smi_q or parser is parse_dcgm_json:
        common, kind = graph.common_targets(affected_entities, "gpu"), "GPU"
    else:
        return None, None
    if len(common) == 1:
        return next(iter(common)), None
    if len(common) > 1:
        return None, f"Ambiguous {kind} scope: {', '.join(sorted(common))}"
    return None, None


def _dedupe_observations(observations: list[Observation]) -> list[Observation]:
    result: list[Observation] = []
    seen: set[tuple[str, str | None, str, str, str | None]] = set()
    for observation in observations:
        token = (observation.key, observation.entity, repr(observation.value), observation.source, observation.raw_ref)
        if token not in seen:
            seen.add(token)
            result.append(observation)
    return result


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
    parser_specs: list[tuple[tuple[str, ...], tuple[str, ...], Parser]] = [
        (("nvidia-smi-q.txt", "nvidia_smi_q.txt"), ("nvidia-smi-q*.txt", "nvidia_smi_q*.txt"), parse_nvidia_smi_q),
        (("lspci.txt", "lspci-vv.txt"), ("lspci*.txt",), parse_lspci),
        (("nccl.log", "nccl.txt"), ("nccl*.log",), parse_nccl_log),
        (("ib-counters.txt", "ib_counters.txt", "ibqueryerrors.txt"), ("ib-counters*.txt", "ib_counters*.txt", "ibqueryerrors*.txt"), parse_ib_counters),
        (("dcgm-diag.json", "dcgm_diag.json", "dcgm-health.json", "dcgm_health.json"), ("dcgm*.json",), parse_dcgm_json),
        (("journal.log", "journal.txt", "dmesg.log", "dmesg.txt"), ("journal*.log", "journal*.txt", "dmesg*.log", "dmesg*.txt"), parse_nvidia_system_log),
        (("proc-interrupts.txt", "proc_interrupts.txt"), ("proc-interrupts*.txt", "proc_interrupts*.txt"), parse_proc_interrupts),
        (("irq-affinity.csv", "irq_affinity.csv"), ("irq-affinity*.csv", "irq_affinity*.csv"), parse_irq_affinity_csv),
        (("process-affinity.csv", "process_affinity.csv"), ("process-affinity*.csv", "process_affinity*.csv"), parse_process_affinity_csv),
    ]
    for exact_names, patterns, parser in parser_specs:
        for current_path in _find_artifacts(root, exact_names, patterns):
            entity = artifact_entities.get(current_path.name) or _infer_entity_from_filename(current_path, parser, graph)
            current_obs = parser(current_path.read_text(encoding="utf-8", errors="replace"), source=current_path.name)
            current_obs, adapter_warnings = reconcile_adapter_entities(current_obs, graph, affected_entities)
            warnings.extend(adapter_warnings)
            if not entity and not {ob.entity for ob in current_obs if ob.entity}:
                entity, scope_warning = _auto_scope_entity(parser, graph, affected_entities)
                if scope_warning:
                    warnings.append(f"{current_path.name}: {scope_warning}")
            current_obs = _attach_entity_if_missing(current_obs, entity)
            artifact_observations.extend(current_obs)
            if current_path.name not in parsed_files:
                parsed_files.append(current_path.name)
            if baseline_dir.is_dir():
                baseline_path = baseline_dir / current_path.name
                if baseline_path.is_file():
                    baseline_key = f"baseline/{baseline_path.name}"
                    baseline_entity = artifact_entities.get(baseline_key, entity)
                    baseline_obs = parser(baseline_path.read_text(encoding="utf-8", errors="replace"), source=baseline_key)
                    baseline_obs, baseline_adapter_warnings = reconcile_adapter_entities(baseline_obs, graph, affected_entities)
                    warnings.extend(baseline_adapter_warnings)
                    baseline_obs = _attach_entity_if_missing(baseline_obs, baseline_entity)
                    artifact_observations.extend(_derive_baseline_facts(current_obs, baseline_obs))
                    parsed_files.append(baseline_key)

    if graph.entities and affected_entities:
        scoped: list[Observation] = []
        for observation in artifact_observations:
            if observation_is_on_affected_path(observation, graph, affected_entities):
                scoped.append(observation)
            else:
                warnings.append(f"Ignored unscoped or unrelated evidence {observation.key} from {observation.source}")
        artifact_observations = scoped

    host_derived, host_warnings = derive_irq_affinity_facts(artifact_observations, graph, affected_entities)
    artifact_observations.extend(host_derived)
    warnings.extend(host_warnings)

    observations = _dedupe_observations(context_observations + derive_identity_observations(graph, affected_entities) + artifact_observations)
    if not parsed_files:
        warnings.append("No recognized incident artifacts were found.")
    return IngestResult(symptom=symptom, observations=observations, parsed_files=parsed_files, warnings=warnings, identity_graph=graph, affected_entities=affected_entities)
