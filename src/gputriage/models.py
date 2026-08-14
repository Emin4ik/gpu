from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class HypothesisStatus(str, Enum):
    POSSIBLE = "possible"
    SUPPORTED = "supported"
    PROBABLE = "probable"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


@dataclass(frozen=True)
class Observation:
    key: str
    value: Any
    source: str = "unknown"
    entity: str | None = None
    raw_ref: str | None = None


@dataclass
class Hypothesis:
    id: str
    title: str
    status: HypothesisStatus = HypothesisStatus.POSSIBLE
    supporting_evidence: list[str] = field(default_factory=list)
    contradicting_evidence: list[str] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DiagnosticTest:
    id: str
    title: str
    purpose: str
    command: str | None
    cost: str
    invasiveness: str
    discriminates_between: tuple[str, ...]


@dataclass
class Investigation:
    symptom: str
    hypotheses: list[Hypothesis]
    next_best_test: DiagnosticTest | None
    verdict: str | None
    notes: list[str] = field(default_factory=list)
