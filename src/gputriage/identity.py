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
            entity = Entity(id=item["id"], kind=item["kind"], attributes=dict(item.get("attributes", {})))
            graph.entities[entity.id] = entity
        for item in payload.get("relations", []):
            graph.relations.append(Relation(source=item["source"], type=item["type"], target=item["target"]))
        return graph

    def validation_errors(self) -> list[str]:
        errors: list[str] = []
        for relation in self.relations:
            if relation.source not in self.entities:
                errors.append(f"relation source is missing: {relation.source}")
            if relation.target not in self.entities:
                errors.append(f"relation target is missing: {relation.target}")
        return errors

    def outgoing(self, source: str, relation_type: str | None = None) -> set[str]:
        return {relation.target for relation in self.relations if relation.source == source and (relation_type is None or relation.type == relation_type)}

    def reachable(self, source: str, target_kind: str, max_depth: int = 4, relation_types: set[str] | None = None) -> set[str]:
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
                if relation_types is not None and relation.type not in relation_types:
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

    def gpu_pcie_targets(self, source: str) -> set[str]:
        targets: set[str] = set()
        for gpu_id in self.reachable(source, "gpu", max_depth=2):
            for target in self.outgoing(gpu_id, "attached_via_pcie"):
                if self.entities.get(target) and self.entities[target].kind == "pcie_device":
                    targets.add(target)
        return targets

    def hca_pcie_targets(self, source: str) -> set[str]:
        targets: set[str] = set()
        for hca_id in self.reachable(source, "nic_hca", max_depth=3):
            for target in self.outgoing(hca_id, "attached_via_pcie"):
                if self.entities.get(target) and self.entities[target].kind == "pcie_device":
                    targets.add(target)
        return targets

    def _common_specialized(self, sources: list[str], getter) -> set[str]:
        if not sources:
            return set()
        target_sets = [getter(source) for source in sources]
        if any(not targets for targets in target_sets):
            return set()
        common = set(target_sets[0])
        for targets in target_sets[1:]:
            common.intersection_update(targets)
        return common

    def common_gpu_pcie_targets(self, sources: list[str]) -> set[str]:
        return self._common_specialized(sources, self.gpu_pcie_targets)

    def common_hca_pcie_targets(self, sources: list[str]) -> set[str]:
        return self._common_specialized(sources, self.hca_pcie_targets)


def _shared_path_observation(key: str, targets: set[str]) -> Observation | None:
    if not targets:
        return None
    entity = next(iter(targets)) if len(targets) == 1 else None
    return Observation(key=key, value=True, source="derived:identity-graph", entity=entity)


def derive_identity_observations(graph: IdentityGraph, affected_entities: list[str]) -> list[Observation]:
    observations: list[Observation] = []
    observation = _shared_path_observation("affected_ranks_share_pcie_path", graph.common_gpu_pcie_targets(affected_entities))
    if observation:
        observations.append(observation)
    observation = _shared_path_observation("affected_ranks_share_hca_pcie_path", graph.common_hca_pcie_targets(affected_entities))
    if observation:
        observations.append(observation)
    for target_kind, key in (("nic_hca", "affected_ranks_share_hca"), ("node", "affected_ranks_share_node"), ("gpu", "affected_ranks_share_gpu")):
        observation = _shared_path_observation(key, graph.common_targets(affected_entities, target_kind))
        if observation:
            observations.append(observation)
    return observations


def observation_is_on_affected_path(observation: Observation, graph: IdentityGraph, affected_entities: list[str]) -> bool:
    if not affected_entities or not graph.entities:
        return True
    if observation.key.startswith("pcie_"):
        if not observation.entity:
            return False
        relevant = graph.common_gpu_pcie_targets(affected_entities) | graph.common_hca_pcie_targets(affected_entities)
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
