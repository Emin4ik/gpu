from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from .models import Observation


@dataclass
class EvidenceIndex:
    """Multi-value observation index keyed by fact and entity."""

    observations: list[Observation]
    _by_key: dict[str, list[Observation]] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        grouped: dict[str, list[Observation]] = defaultdict(list)
        for observation in self.observations:
            grouped[observation.key].append(observation)
        self._by_key = dict(grouped)

    @classmethod
    def from_iterable(cls, observations: Iterable[Observation]) -> "EvidenceIndex":
        return cls(list(observations))

    def all(self, key: str) -> list[Observation]:
        return list(self._by_key.get(key, ()))

    def has(self, key: str) -> bool:
        """Return whether a fact was collected, regardless of its value."""
        return key in self._by_key

    def any_true(self, key: str) -> bool:
        return any(observation.value is True for observation in self._by_key.get(key, ()))

    def values(self, key: str) -> list[Any]:
        return [observation.value for observation in self._by_key.get(key, ())]

    def first_value(self, key: str, default: Any = None) -> Any:
        observations = self._by_key.get(key, ())
        return observations[0].value if observations else default

    def entities(self, key: str) -> set[str | None]:
        return {observation.entity for observation in self._by_key.get(key, ())}

    def pairs(self, left_key: str, right_key: str) -> list[tuple[str | None, Observation, Observation]]:
        """Pair two fact types only when they belong to the same entity."""
        left = self._by_key.get(left_key, ())
        right = self._by_key.get(right_key, ())
        right_by_entity: dict[str | None, list[Observation]] = defaultdict(list)
        for observation in right:
            right_by_entity[observation.entity].append(observation)

        pairs: list[tuple[str | None, Observation, Observation]] = []
        for left_observation in left:
            for right_observation in right_by_entity.get(left_observation.entity, ()):
                pairs.append((left_observation.entity, left_observation, right_observation))
        return pairs
