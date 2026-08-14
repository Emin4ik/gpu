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
class EvaluationReport:
    cases: int = 0
    checked_stages: int = 0
    next_test_checks: int = 0
    next_test_hits: int = 0
    premature_confirmations: int = 0
    final_confirmation_checks: int = 0
    final_confirmation_hits: int = 0
    failures: list[EvaluationFailure] = field(default_factory=list)

    @property
    def next_test_accuracy(self) -> float:
        if not self.next_test_checks:
            return 0.0
        return self.next_test_hits / self.next_test_checks

    @property
    def final_confirmation_rate(self) -> float:
        if not self.final_confirmation_checks:
            return 0.0
        return self.final_confirmation_hits / self.final_confirmation_checks

    def as_dict(self) -> dict[str, Any]:
        return {
            "cases": self.cases,
            "checked_stages": self.checked_stages,
            "next_test_checks": self.next_test_checks,
            "next_test_hits": self.next_test_hits,
            "next_test_accuracy": self.next_test_accuracy,
            "premature_confirmations": self.premature_confirmations,
            "final_confirmation_checks": self.final_confirmation_checks,
            "final_confirmation_hits": self.final_confirmation_hits,
            "final_confirmation_rate": self.final_confirmation_rate,
            "failures": [failure.__dict__ for failure in self.failures],
        }


def _observations(items: list[dict[str, Any]]) -> list[Observation]:
    return [Observation(**item) for item in items]


def _by_id(result, hypothesis_id: str):
    return next((h for h in result.hypotheses if h.id == hypothesis_id), None)


def evaluate_payload(payload: dict[str, Any]) -> EvaluationReport:
    report = EvaluationReport()
    for case in payload.get("cases", []):
        report.cases += 1
        accumulated: list[Observation] = []
        stages = case.get("stages", [])
        for index, stage in enumerate(stages):
            accumulated.extend(_observations(stage.get("add_observations", [])))
            result = investigate(case["symptom"], accumulated)
            stage_name = stage.get("name", f"stage-{index}")
            report.checked_stages += 1

            expected_test = stage.get("expected_next_test")
            if expected_test:
                report.next_test_checks += 1
                actual = result.next_best_test.id if result.next_best_test else None
                if actual == expected_test:
                    report.next_test_hits += 1
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
                report.premature_confirmations += 1
                report.failures.append(EvaluationFailure(case["id"], stage_name, f"premature confirmed hypotheses: {confirmed}"))

        expected_final = case.get("expected_final_hypothesis")
        if expected_final and stages:
            report.final_confirmation_checks += 1
            final_result = investigate(case["symptom"], accumulated)
            hypothesis = _by_id(final_result, expected_final)
            if hypothesis and hypothesis.status == HypothesisStatus.CONFIRMED:
                report.final_confirmation_hits += 1
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
