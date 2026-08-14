from __future__ import annotations

from dataclasses import replace

from .models import Observation


def _affected_gpu_union(graph, affected_entities: list[str]) -> set[str]:
    targets: set[str] = set()
    for source in affected_entities:
        targets.update(graph.reachable(source, "gpu", max_depth=3))
    return targets


def reconcile_adapter_entities(
    observations: list[Observation], graph, affected_entities: list[str]
) -> tuple[list[Observation], list[str]]:
    """Resolve adapter-local identifiers such as DCGM GPU indexes to durable graph IDs.

    The function is conservative: an ambiguous index is left unresolved and a
    warning is returned instead of guessing across nodes.
    """

    warnings: list[str] = []
    result: list[Observation] = []
    affected_gpus = _affected_gpu_union(graph, affected_entities) if affected_entities else set()

    for observation in observations:
        entity = observation.entity
        if not entity or not entity.startswith("gpu-index:"):
            result.append(observation)
            continue

        index = entity.split(":", 1)[1]
        all_matches = {
            entity_id
            for entity_id, graph_entity in graph.entities.items()
            if graph_entity.kind == "gpu" and str(graph_entity.attributes.get("index", "")) == index
        }
        preferred = all_matches & affected_gpus if affected_gpus else set()
        candidates = preferred or all_matches
        if len(candidates) == 1:
            result.append(replace(observation, entity=next(iter(candidates))))
        else:
            if not candidates:
                warnings.append(f"{observation.source}: unresolved DCGM GPU index {index}")
            else:
                warnings.append(
                    f"{observation.source}: ambiguous DCGM GPU index {index}: {', '.join(sorted(candidates))}"
                )
            result.append(observation)

    return result, warnings
