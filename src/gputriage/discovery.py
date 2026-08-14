from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .identity import Entity, IdentityGraph, Relation


@dataclass
class DiscoveryResult:
    graph: IdentityGraph = field(default_factory=IdentityGraph)
    affected_entities: list[str] = field(default_factory=list)
    parsed_files: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _normalize_bdf(value: str) -> str:
    value = value.strip().lower()
    if not value:
        return value
    match = re.fullmatch(r"([0-9a-f]{4,8}):([0-9a-f]{2}):([0-9a-f]{2})\.([0-7])", value)
    if not match:
        return value
    domain, bus, device, function = match.groups()
    return f"{domain[-4:]}:{bus}:{device}.{function}"


def _entity_id(kind: str, value: str, node: str | None = None) -> str:
    if kind == "node":
        return f"node:{value}"
    if kind == "rank":
        return f"rank:{value}"
    if kind == "job":
        return f"job:{value}"
    if kind == "gpu":
        return f"gpu:{value}"
    if kind == "pcie_device":
        return f"pcie:{_normalize_bdf(value)}"
    if kind == "nic_hca":
        return f"hca:{node}:{value}" if node else f"hca:{value}"
    raise ValueError(f"unsupported entity kind: {kind}")


def _add_entity(graph: IdentityGraph, entity: Entity) -> None:
    existing = graph.entities.get(entity.id)
    if existing is None:
        graph.entities[entity.id] = entity
        return
    merged = dict(existing.attributes)
    merged.update({k: v for k, v in entity.attributes.items() if v not in (None, "")})
    graph.entities[entity.id] = Entity(id=existing.id, kind=existing.kind, attributes=merged)


def _add_relation(graph: IdentityGraph, relation: Relation) -> None:
    if relation not in graph.relations:
        graph.relations.append(relation)


def merge_graphs(base: IdentityGraph, other: IdentityGraph) -> IdentityGraph:
    merged = IdentityGraph(entities=dict(base.entities), relations=list(base.relations))
    for entity in other.entities.values():
        _add_entity(merged, entity)
    for relation in other.relations:
        _add_relation(merged, relation)
    return merged


def expand_slurm_hostlist(value: str) -> list[str]:
    """Expand a practical subset of Slurm hostlist syntax."""
    value = value.strip()
    if not value or value in {"(null)", "None"}:
        return []

    tokens: list[str] = []
    current = []
    depth = 0
    for char in value:
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
        if char == "," and depth == 0:
            tokens.append("".join(current))
            current = []
        else:
            current.append(char)
    if current:
        tokens.append("".join(current))

    expanded: list[str] = []
    for token in tokens:
        match = re.fullmatch(r"([^\[]+)\[([^\]]+)\](.*)", token)
        if not match:
            expanded.append(token)
            continue
        prefix, inner, suffix = match.groups()
        for part in inner.split(","):
            range_match = re.fullmatch(r"(\d+)-(\d+)", part)
            if range_match:
                start_s, end_s = range_match.groups()
                width = max(len(start_s), len(end_s))
                start, end = int(start_s), int(end_s)
                step = 1 if end >= start else -1
                for number in range(start, end + step, step):
                    expanded.append(f"{prefix}{number:0{width}d}{suffix}")
            else:
                expanded.append(f"{prefix}{part}{suffix}")
    return expanded


def parse_scontrol_job(text: str) -> tuple[IdentityGraph, dict[str, Any], list[str]]:
    graph = IdentityGraph()
    warnings: list[str] = []
    fields = dict(re.findall(r"(?:^|\s)([A-Za-z][A-Za-z0-9_]*?)=([^\s]+)", text.strip()))
    job_id = fields.get("JobId") or fields.get("JobID")
    node_list = fields.get("NodeList")

    if job_id:
        job_entity = Entity(_entity_id("job", job_id), "job", {"scheduler_job_id": job_id})
        _add_entity(graph, job_entity)
    else:
        warnings.append("slurm-job.txt: JobId was not found")

    nodes = expand_slurm_hostlist(node_list or "")
    if node_list and not nodes:
        warnings.append(f"slurm-job.txt: could not expand NodeList={node_list!r}")
    for node in nodes:
        node_id = _entity_id("node", node)
        _add_entity(graph, Entity(node_id, "node", {"hostname": node}))
        if job_id:
            _add_relation(graph, Relation(_entity_id("job", job_id), "allocated_node", node_id))

    return graph, {"job_id": job_id, "nodes": nodes}, warnings


def _csv_rows(text: str) -> list[dict[str, str]]:
    return [
        {str(key).strip(): (value or "").strip() for key, value in row.items() if key is not None}
        for row in csv.DictReader(io.StringIO(text))
    ]


def parse_nvidia_gpu_csv(text: str, default_node: str | None = None) -> tuple[IdentityGraph, list[str]]:
    graph = IdentityGraph()
    warnings: list[str] = []
    for row_number, row in enumerate(_csv_rows(text), start=2):
        node = row.get("node") or row.get("hostname") or default_node
        index = row.get("index") or row.get("gpu_index")
        uuid = row.get("uuid") or row.get("gpu_uuid")
        bdf = row.get("pci.bus_id") or row.get("pci_bus_id") or row.get("bdf")
        if not node or not uuid or not bdf:
            warnings.append(f"nvidia-gpus.csv:{row_number}: node, uuid and pci bus id are required")
            continue

        node_id = _entity_id("node", node)
        gpu_id = _entity_id("gpu", uuid)
        pcie_id = _entity_id("pcie_device", bdf)
        _add_entity(graph, Entity(node_id, "node", {"hostname": node}))
        _add_entity(
            graph,
            Entity(
                gpu_id,
                "gpu",
                {"uuid": uuid, "index": index, "node": node, "pci_bdf": _normalize_bdf(bdf)},
            ),
        )
        _add_entity(
            graph,
            Entity(
                pcie_id,
                "pcie_device",
                {"bdf": _normalize_bdf(bdf), "node": node, "device_kind": "gpu"},
            ),
        )
        _add_relation(graph, Relation(gpu_id, "attached_via_pcie", pcie_id))
    return graph, warnings


def parse_rank_map_csv(text: str) -> tuple[IdentityGraph, list[dict[str, str]], list[str]]:
    graph = IdentityGraph()
    warnings: list[str] = []
    normalized_rows: list[dict[str, str]] = []
    for row_number, row in enumerate(_csv_rows(text), start=2):
        rank = row.get("rank") or row.get("global_rank") or row.get("slurm_procid")
        node = row.get("node") or row.get("hostname") or row.get("slurmd_nodename")
        local_rank = row.get("local_rank") or row.get("slurm_localid")
        if rank == "" or not node:
            warnings.append(f"rank-map.csv:{row_number}: rank and node are required")
            continue
        rank_id = _entity_id("rank", rank)
        node_id = _entity_id("node", node)
        attrs = {
            "global_rank": int(rank) if str(rank).isdigit() else rank,
            "local_rank": int(local_rank) if str(local_rank).isdigit() else local_rank,
            "node": node,
            "gpu_index": row.get("gpu_index", ""),
            "gpu_uuid": row.get("gpu_uuid", ""),
            "cuda_visible_devices": row.get("cuda_visible_devices", ""),
        }
        _add_entity(graph, Entity(rank_id, "rank", attrs))
        _add_entity(graph, Entity(node_id, "node", {"hostname": node}))
        _add_relation(graph, Relation(rank_id, "runs_on", node_id))
        normalized = dict(row)
        normalized.update({"rank": str(rank), "node": node, "local_rank": str(local_rank or "")})
        normalized_rows.append(normalized)
    return graph, normalized_rows, warnings


def _gpu_indexes_by_node(graph: IdentityGraph) -> dict[tuple[str, str], str]:
    result: dict[tuple[str, str], str] = {}
    for entity in graph.entities.values():
        if entity.kind != "gpu":
            continue
        node = str(entity.attributes.get("node", ""))
        index = str(entity.attributes.get("index", ""))
        if node and index:
            result[(node, index)] = entity.id
    return result


def _gpu_uuids(graph: IdentityGraph) -> dict[str, str]:
    return {
        str(entity.attributes.get("uuid")): entity.id
        for entity in graph.entities.values()
        if entity.kind == "gpu" and entity.attributes.get("uuid")
    }


def reconcile_rank_gpu(graph: IdentityGraph, rank_rows: list[dict[str, str]]) -> list[str]:
    warnings: list[str] = []
    by_index = _gpu_indexes_by_node(graph)
    by_uuid = _gpu_uuids(graph)

    for row in rank_rows:
        rank = row["rank"]
        node = row["node"]
        local_rank_raw = row.get("local_rank", "")
        gpu_uuid = row.get("gpu_uuid", "")
        gpu_index = row.get("gpu_index", "")
        visible = [item.strip() for item in row.get("cuda_visible_devices", "").split(",") if item.strip()]

        selected: str | None = None
        if gpu_uuid:
            selected = by_uuid.get(gpu_uuid)
        elif gpu_index:
            selected = by_index.get((node, gpu_index))
        elif visible:
            local_rank = int(local_rank_raw) if local_rank_raw.isdigit() else 0
            if local_rank < len(visible):
                token = visible[local_rank]
                if token.startswith("GPU-"):
                    selected = by_uuid.get(token)
                elif token.isdigit():
                    selected = by_index.get((node, token))

        rank_id = _entity_id("rank", rank)
        if selected:
            _add_relation(graph, Relation(rank_id, "uses_gpu", selected))
        else:
            warnings.append(f"rank {rank} on {node}: GPU mapping is unresolved")
    return warnings


def parse_ib_devices_csv(text: str, default_node: str | None = None) -> tuple[IdentityGraph, list[str]]:
    graph = IdentityGraph()
    warnings: list[str] = []
    for row_number, row in enumerate(_csv_rows(text), start=2):
        node = row.get("node") or row.get("hostname") or default_node
        ibdev = row.get("ibdev") or row.get("ib_device") or row.get("device")
        netdev = row.get("netdev") or row.get("net_device")
        bdf = row.get("pci_bdf") or row.get("pci.bus_id") or row.get("bdf")
        guid = row.get("guid") or row.get("node_guid")
        port = row.get("port") or "1"
        if not node or not ibdev:
            warnings.append(f"ib-devices.csv:{row_number}: node and ibdev are required")
            continue
        hca_id = _entity_id("nic_hca", ibdev, node=node)
        node_id = _entity_id("node", node)
        attrs = {
            "device": ibdev,
            "ibdev": ibdev,
            "netdev": netdev,
            "guid": guid,
            "port": port,
            "node": node,
        }
        if bdf:
            attrs["pci_bdf"] = _normalize_bdf(bdf)
        _add_entity(graph, Entity(node_id, "node", {"hostname": node}))
        _add_entity(graph, Entity(hca_id, "nic_hca", attrs))
    return graph, warnings


_TOPO_DISTANCE = {"PIX": 0, "PXB": 1, "PHB": 2, "NODE": 3, "SYS": 4}


def parse_nvidia_topo_matrix(text: str, node: str, graph: IdentityGraph) -> list[str]:
    """Add conservative GPU->HCA topology candidates from nvidia-smi topology text."""
    warnings: list[str] = []
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    header_idx = next(
        (
            i
            for i, line in enumerate(lines)
            if re.search(r"\bGPU0\b", line) and re.search(r"\bNIC\d+\b", line)
        ),
        None,
    )
    if header_idx is None:
        warnings.append("nvidia-topo.txt: GPU/NIC matrix header was not found")
        return warnings

    header = re.split(r"\s+", lines[header_idx].strip())
    nic_columns = {idx: token for idx, token in enumerate(header) if re.fullmatch(r"NIC\d+", token)}
    gpu_rows: dict[str, list[str]] = {}
    for line in lines[header_idx + 1 :]:
        tokens = re.split(r"\s+", line.strip())
        if not tokens or not re.fullmatch(r"GPU\d+", tokens[0]):
            continue
        gpu_rows[tokens[0]] = tokens[1:]

    nic_to_ibdev: dict[str, str] = {}
    nic_to_bdf: dict[str, str] = {}
    for line in lines:
        match = re.search(
            r"\b(NIC\d+)\b.*?\bibdev\s*[=:]\s*([A-Za-z0-9_.-]+)",
            line,
            re.IGNORECASE,
        )
        if match:
            nic_to_ibdev[match.group(1)] = match.group(2)
        match = re.search(
            r"\b(NIC\d+)\b.*?\bPCI\s*[=:]\s*([0-9A-Fa-f]{4,8}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}\.[0-7])",
            line,
        )
        if match:
            nic_to_bdf[match.group(1)] = _normalize_bdf(match.group(2))

    bdf_to_hca: dict[str, str] = {}
    for entity in graph.entities.values():
        if entity.kind == "nic_hca" and entity.attributes.get("pci_bdf"):
            bdf_to_hca[str(entity.attributes["pci_bdf"]).lower()] = entity.id

    gpu_by_index: dict[str, str] = {}
    for entity in graph.entities.values():
        if (
            entity.kind == "gpu"
            and entity.attributes.get("node") == node
            and str(entity.attributes.get("index", ""))
        ):
            gpu_by_index[f"GPU{entity.attributes['index']}"] = entity.id

    for gpu_alias, values in gpu_rows.items():
        gpu_id = gpu_by_index.get(gpu_alias)
        if not gpu_id:
            continue
        candidates: list[tuple[int, str]] = []
        for header_index, nic_alias in nic_columns.items():
            if header_index >= len(values):
                continue
            distance = values[header_index].upper()
            if distance not in _TOPO_DISTANCE:
                continue
            hca_id = None
            ibdev = nic_to_ibdev.get(nic_alias)
            if ibdev:
                candidate_id = _entity_id("nic_hca", ibdev, node=node)
                if candidate_id in graph.entities:
                    hca_id = candidate_id
            if hca_id is None and nic_alias in nic_to_bdf:
                hca_id = bdf_to_hca.get(nic_to_bdf[nic_alias])
            if hca_id:
                candidates.append((_TOPO_DISTANCE[distance], hca_id))

        if not candidates:
            continue
        best = min(score for score, _ in candidates)
        best_hcas = sorted({hca for score, hca in candidates if score == best})
        for hca_id in best_hcas:
            _add_relation(graph, Relation(gpu_id, "topology_near_nic", hca_id))
        if len(best_hcas) > 1:
            warnings.append(
                f"{gpu_alias} on {node}: multiple equally-near HCA candidates: {', '.join(best_hcas)}"
            )

    return warnings


def _single_node(graph: IdentityGraph) -> str | None:
    hostnames = [
        str(entity.attributes.get("hostname"))
        for entity in graph.entities.values()
        if entity.kind == "node" and entity.attributes.get("hostname")
    ]
    unique = sorted(set(hostnames))
    return unique[0] if len(unique) == 1 else None


def discover_identity(root: Path, payload: dict[str, Any] | None = None) -> DiscoveryResult:
    payload = payload or {}
    graph = IdentityGraph()
    warnings: list[str] = []
    parsed_files: list[str] = []
    rank_rows: list[dict[str, str]] = []

    slurm_path = root / "slurm-job.txt"
    if slurm_path.exists():
        slurm_graph, _, slurm_warnings = parse_scontrol_job(
            slurm_path.read_text(encoding="utf-8", errors="replace")
        )
        graph = merge_graphs(graph, slurm_graph)
        warnings.extend(slurm_warnings)
        parsed_files.append(slurm_path.name)

    rank_path = root / "rank-map.csv"
    if rank_path.exists():
        rank_graph, rank_rows, rank_warnings = parse_rank_map_csv(
            rank_path.read_text(encoding="utf-8", errors="replace")
        )
        graph = merge_graphs(graph, rank_graph)
        warnings.extend(rank_warnings)
        parsed_files.append(rank_path.name)

    default_node = _single_node(graph)

    gpu_path = root / "nvidia-gpus.csv"
    if gpu_path.exists():
        gpu_graph, gpu_warnings = parse_nvidia_gpu_csv(
            gpu_path.read_text(encoding="utf-8", errors="replace"), default_node=default_node
        )
        graph = merge_graphs(graph, gpu_graph)
        warnings.extend(gpu_warnings)
        parsed_files.append(gpu_path.name)

    warnings.extend(reconcile_rank_gpu(graph, rank_rows))

    ib_path = root / "ib-devices.csv"
    if ib_path.exists():
        ib_graph, ib_warnings = parse_ib_devices_csv(
            ib_path.read_text(encoding="utf-8", errors="replace"), default_node=default_node
        )
        graph = merge_graphs(graph, ib_graph)
        warnings.extend(ib_warnings)
        parsed_files.append(ib_path.name)

    topo_path = root / "nvidia-topo.txt"
    if topo_path.exists():
        if default_node:
            warnings.extend(
                parse_nvidia_topo_matrix(
                    topo_path.read_text(encoding="utf-8", errors="replace"),
                    default_node,
                    graph,
                )
            )
        else:
            warnings.append("nvidia-topo.txt: node is ambiguous; cannot attach topology safely")
        parsed_files.append(topo_path.name)

    for entity in list(graph.entities.values()):
        if entity.kind != "rank":
            continue
        gpu_ids = graph.reachable(entity.id, "gpu", max_depth=2)
        hca_candidates: set[str] = set()
        for gpu_id in gpu_ids:
            hca_candidates.update(graph.reachable(gpu_id, "nic_hca", max_depth=1))
        if len(hca_candidates) == 1:
            _add_relation(graph, Relation(entity.id, "uses_nic_hca", next(iter(hca_candidates))))
        elif len(hca_candidates) > 1:
            warnings.append(
                f"{entity.id}: HCA mapping is ambiguous: {', '.join(sorted(hca_candidates))}"
            )

    affected_entities = list(payload.get("affected_entities", []))
    if not affected_entities:
        affected_entities = [
            _entity_id("rank", str(rank)) for rank in payload.get("affected_ranks", [])
        ]
    if not affected_entities:
        for row in rank_rows:
            if row.get("affected", "").lower() in {"1", "true", "yes", "y"}:
                affected_entities.append(_entity_id("rank", row["rank"]))

    for entity_id in affected_entities:
        if entity_id not in graph.entities:
            warnings.append(f"affected entity is unresolved: {entity_id}")

    warnings.extend(graph.validation_errors())
    return DiscoveryResult(
        graph=graph,
        affected_entities=affected_entities,
        parsed_files=parsed_files,
        warnings=warnings,
    )
