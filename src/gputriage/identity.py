from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any

from .models import Observation


@dataclass(frozen=True)
class Entity:
    id: str
    kind: str
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Relation:
    source: str
    type: str
    target: str


@dataclass
class IdentityGraph:
    entities: dict[str, Entity] = field(default_factory=dict)
    relations: list[Relation] = field(default_factory=list)

    @classmethod
    def from_payload(cls, payload: dict[str, Any] | None) -> "IdentityGraph":
        graph = cls()
        if not payload:
            return graph
        for item in payload.get("entities", []):
            entity = Entity(
                id=item["id"],
                kind=item["kind"],
                attributes=dict(item.get("attributes", {})),
            )
            graph.entities[entity.id] = entity
        for item in payload.get("relations", []):
            graph.relations.append(
                Relation(source=item["source"], type=item["type"], target=item["target"])
            )
        return graph

    def validation_errors(self) -> list[str]:
        errors: list[str] = []
        for relation in self.relations:
            if relation.source not in self.entities:
                errors.append(f"relation source is missing: {relation.source}")
            if relation.target not in self.entities:
                errors.append(f"relation target is missing: {relation.target}")
        return errors

    def reachable(self, source: str, target_kind: str, max_depth: int = 4) -> set[str]:
        if source not in self.entities:
            return set()
        found: set[str] = set()
        queue: deque[tuple[str, int]] = deque([(source, 0)])
        visited = {source}
        while queue:
            current, depth = queue.popleft()
            if depth >= max_depth:
                continue
            for relation in self.relations:
                if relation.source != current:
                    continue
                target = relation.target
                entity = self.entities.get(target)
                if entity and entity.kind == target_kind:
                    found.add(target)
                if target not in visited:
                    visited.add(target)
                    queue.append((target, depth + 1))
        return found

    def common_targets(self, sources: list[str], target_kind: str) -> set[str]:
        if not sources:
            return set()
        target_sets = [self.reachable(source, target_kind) for source in sources]
        if any(not targets for targets in target_sets):
            return set()
        common = set(target_sets[0])
        for targets in target_sets[1:]:
            common.intersection_update(targets)
        return common


def derive_identity_observations(graph: IdentityGraph, affected_entities: list[str]) -> list[Observation]:
    observations: list[Observation] = []
    mappings = (
        ("pcie_device", "affected_ranks_share_pcie_path"),
        ("nic_hca", "affected_ranks_share_hca"),
        ("node", "affected_ranks_share_node"),
        ("gpu", "affected_ranks_share_gpu"),
    )
    for target_kind, key in mappings:
        common = graph.common_targets(affected_entities, target_kind)
        if len(common) == 1:
            observations.append(
                Observation(
                    key=key,
                    value=True,
                    source="derived:identity-graph",
                    entity=next(iter(common)),
                )
            )
    return observations


def observation_is_on_affected_path(
    observation: Observation,
    graph: IdentityGraph,
    affected_entities: list[str],
) -> bool:
    if not affected_entities or not graph.entities:
        return True

    if observation.key.startswith("pcie_"):
        if not observation.entity:
            return False
        relevant = graph.common_targets(affected_entities, "pcie_device")
        return not relevant or observation.entity in relevant

    if observation.key.startswith("ib_counter.") or observation.key.startswith("fabric_"):
        if not observation.entity:
            return False
        relevant = graph.common_targets(affected_entities, "nic_hca")
        return not relevant or observation.entity in relevant

    if observation.key.startswith("gpu_") or observation.key == "thermal_throttle_reason":
        if not observation.entity:
            return False
        relevant = graph.common_targets(affected_entities, "gpu")
        return not relevant or observation.entity in relevant

    return True
