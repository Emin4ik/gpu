from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .engine import investigate
from .models import HypothesisStatus, Observation


@dataclass
class EvaluationFailure:
    case_id: str
    stage: str
    message: str


@dataclass
class EvaluationCounters:
    cases: int = 0
    checked_stages: int = 0
    next_test_checks: int = 0
    next_test_hits: int = 0
    abstention_checks: int = 0
    abstention_hits: int = 0
    premature_confirmations: int = 0
    final_confirmation_checks: int = 0
    final_confirmation_hits: int = 0

    @property
    def next_test_accuracy(self) -> float:
        return self.next_test_hits / self.next_test_checks if self.next_test_checks else 0.0

    @property
    def abstention_accuracy(self) -> float:
        return self.abstention_hits / self.abstention_checks if self.abstention_checks else 0.0

    @property
    def final_confirmation_rate(self) -> float:
        return self.final_confirmation_hits / self.final_confirmation_checks if self.final_confirmation_checks else 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "cases": self.cases,
            "checked_stages": self.checked_stages,
            "next_test_checks": self.next_test_checks,
            "next_test_hits": self.next_test_hits,
            "next_test_accuracy": self.next_test_accuracy,
            "abstention_checks": self.abstention_checks,
            "abstention_hits": self.abstention_hits,
            "abstention_accuracy": self.abstention_accuracy,
            "premature_confirmations": self.premature_confirmations,
            "final_confirmation_checks": self.final_confirmation_checks,
            "final_confirmation_hits": self.final_confirmation_hits,
            "final_confirmation_rate": self.final_confirmation_rate,
        }


@dataclass
class EvaluationReport(EvaluationCounters):
    failures: list[EvaluationFailure] = field(default_factory=list)
    by_split: dict[str, EvaluationCounters] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        payload = super().as_dict()
        payload["by_split"] = {name: counters.as_dict() for name, counters in sorted(self.by_split.items())}
        payload["failures"] = [failure.__dict__ for failure in self.failures]
        return payload


def _observations(items: list[dict[str, Any]]) -> list[Observation]:
    return [Observation(**item) for item in items]


def _by_id(result, hypothesis_id: str):
    return next((h for h in result.hypotheses if h.id == hypothesis_id), None)


def _bump(report: EvaluationReport, split: EvaluationCounters, field_name: str, amount: int = 1) -> None:
    setattr(report, field_name, getattr(report, field_name) + amount)
    setattr(split, field_name, getattr(split, field_name) + amount)


def evaluate_payload(payload: dict[str, Any]) -> EvaluationReport:
    report = EvaluationReport()
    for case in payload.get("cases", []):
        split_name = case.get("split", "unspecified")
        split = report.by_split.setdefault(split_name, EvaluationCounters())
        _bump(report, split, "cases")
        accumulated: list[Observation] = []
        stages = case.get("stages", [])

        for index, stage in enumerate(stages):
            accumulated.extend(_observations(stage.get("add_observations", [])))
            result = investigate(case["symptom"], accumulated)
            stage_name = stage.get("name", f"stage-{index}")
            _bump(report, split, "checked_stages")

            if "expected_next_test" in stage:
                expected_test = stage.get("expected_next_test")
                if expected_test is None:
                    _bump(report, split, "abstention_checks")
                    if result.next_best_test is None and result.verdict is None:
                        _bump(report, split, "abstention_hits")
                    else:
                        actual = result.next_best_test.id if result.next_best_test else None
                        report.failures.append(EvaluationFailure(case["id"], stage_name, f"expected abstention, got next_test={actual!r}, verdict={result.verdict!r}"))
                else:
                    _bump(report, split, "next_test_checks")
                    actual = result.next_best_test.id if result.next_best_test else None
                    if actual == expected_test:
                        _bump(report, split, "next_test_hits")
                    else:
                        report.failures.append(EvaluationFailure(case["id"], stage_name, f"expected next test {expected_test!r}, got {actual!r}"))

            for hypothesis_id, expected_status in stage.get("expected_statuses", {}).items():
                hypothesis = _by_id(result, hypothesis_id)
                actual_status = hypothesis.status.value if hypothesis else None
                if actual_status != expected_status:
                    report.failures.append(EvaluationFailure(case["id"], stage_name, f"expected {hypothesis_id}={expected_status!r}, got {actual_status!r}"))

            allow_confirmed = bool(stage.get("allow_confirmed", False))
            confirmed = [h.id for h in result.hypotheses if h.status == HypothesisStatus.CONFIRMED]
            if confirmed and not allow_confirmed:
                _bump(report, split, "premature_confirmations")
                report.failures.append(EvaluationFailure(case["id"], stage_name, f"premature confirmed hypotheses: {confirmed}"))

        expected_final = case.get("expected_final_hypothesis")
        if expected_final and stages:
            _bump(report, split, "final_confirmation_checks")
            final_result = investigate(case["symptom"], accumulated)
            hypothesis = _by_id(final_result, expected_final)
            if hypothesis and hypothesis.status == HypothesisStatus.CONFIRMED:
                _bump(report, split, "final_confirmation_hits")
            else:
                actual = hypothesis.status.value if hypothesis else None
                report.failures.append(EvaluationFailure(case["id"], stages[-1].get("name", "final"), f"final {expected_final} is {actual!r}"))

    return report


def evaluate_file(path: Path) -> EvaluationReport:
    return evaluate_payload(json.loads(path.read_text(encoding="utf-8")))


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay staged GPU Triage incidents without revealing future evidence")
    parser.add_argument("corpus", type=Path, help="Path to a staged incident corpus JSON file")
    args = parser.parse_args()
    report = evaluate_file(args.corpus)
    print(json.dumps(report.as_dict(), indent=2))
    raise SystemExit(1 if report.failures else 0)


if __name__ == "__main__":
    main()
