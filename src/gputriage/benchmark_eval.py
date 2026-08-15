from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
from typing import Any

from .engine import investigate
from .models import HypothesisStatus, Observation
from .benchmark_types import (
    STATUS_RANK,
    TEST_TOOL_FAMILY,
    BenchmarkCounters,
    BenchmarkFailure,
    BenchmarkReport,
)


def _observations(items: list[dict[str, Any]]) -> list[Observation]:
    return [Observation(**item) for item in items]


def _active_top3(result) -> list[str]:
    ranked = sorted(
        result.hypotheses,
        key=lambda h: (STATUS_RANK[h.status], len(h.supporting_evidence), -len(h.contradicting_evidence)),
        reverse=True,
    )
    return [h.id for h in ranked if h.status != HypothesisStatus.REJECTED][:3]


def _transition_count(sequence: list[str]) -> int:
    if len(sequence) < 2:
        return 0
    return sum(1 for previous, current in zip(sequence, sequence[1:]) if previous != current)


def _safe_reduction(baseline: int, actual: int) -> float | None:
    if baseline <= 0:
        return None
    return (baseline - actual) / baseline


def _bump(report: BenchmarkReport, split: BenchmarkCounters, field_name: str, amount: int = 1) -> None:
    setattr(report, field_name, getattr(report, field_name) + amount)
    setattr(split, field_name, getattr(split, field_name) + amount)


def _append(report: BenchmarkReport, split: BenchmarkCounters, field_name: str, value: float) -> None:
    getattr(report, field_name).append(value)
    getattr(split, field_name).append(value)


def _record_failure(report: BenchmarkReport, case_id: str, stage: str, kind: str, message: str) -> None:
    report.failures.append(BenchmarkFailure(case_id, stage, kind, message))


def evaluate_payload(payload: dict[str, Any]) -> BenchmarkReport:
    report = BenchmarkReport()
    for case in payload.get("cases", []):
        split_name = case.get("split", "unspecified")
        split = report.by_split.setdefault(split_name, BenchmarkCounters())
        _bump(report, split, "cases")
        scenario_type = case.get("scenario_type", "source")
        _bump(report, split, "source_cases" if scenario_type == "source" else "mutation_cases")
        source_incident_id = case.get("source_incident_id")
        if source_incident_id:
            report.distinct_source_incidents.add(source_incident_id)
        quality = case.get("quality")
        if quality:
            report.quality_grades[quality] = report.quality_grades.get(quality, 0) + 1
        if case.get("specialist_overlap"):
            _bump(report, split, "specialist_overlap_cases")

        accumulated: list[Observation] = []
        selected_tests: list[str] = []
        domain_hit_seen = False
        final_result = None

        for index, stage in enumerate(case.get("stages", [])):
            stage_name = stage.get("name", f"stage-{index}")
            accumulated.extend(_observations(stage.get("add_observations", [])))
            result = investigate(case["symptom"], accumulated)
            final_result = result
            _bump(report, split, "stages")

            actual_test = result.next_best_test.id if result.next_best_test else None
            if actual_test:
                selected_tests.append(actual_test)

            expected_hypotheses = stage.get("expected_hypotheses", case.get("expected_hypotheses", []))
            if stage.get("domain_check") and expected_hypotheses:
                _bump(report, split, "domain_checks")
                top3 = _active_top3(result)
                if any(hypothesis_id in top3 for hypothesis_id in expected_hypotheses):
                    _bump(report, split, "domain_hits_at_3")
                    domain_hit_seen = True
                else:
                    _record_failure(report, case["id"], stage_name, "domain", f"expected one of {expected_hypotheses!r} in top3, got {top3!r}")
                for hypothesis_id in expected_hypotheses:
                    _bump(report, split, "domain_label_checks")
                    if hypothesis_id in top3:
                        _bump(report, split, "domain_label_hits")

            utility = stage.get("next_test_utility")
            if utility is not None and not stage.get("expect_abstention"):
                _bump(report, split, "next_test_checks")
                score = int(utility.get(actual_test, utility.get("*", 0))) if isinstance(utility, dict) else 0
                _bump(report, split, "next_test_utility_points", score)
                if score == 2:
                    _bump(report, split, "next_test_utility_2_hits")
                else:
                    _record_failure(report, case["id"], stage_name, "next_test_utility", f"next_test={actual_test!r} scored {score}/2")

            if stage.get("expect_abstention"):
                _bump(report, split, "abstention_checks")
                if result.next_best_test is None and result.verdict is None:
                    _bump(report, split, "abstention_hits")
                else:
                    _record_failure(report, case["id"], stage_name, "abstention", f"expected abstention, got next_test={actual_test!r}, verdict={result.verdict!r}")

            confirmation_stage = bool(stage.get("confirmation_stage", False))
            confirmed = [h.id for h in result.hypotheses if h.status == HypothesisStatus.CONFIRMED]
            if confirmed and not confirmation_stage:
                _bump(report, split, "premature_confirmations")
                _record_failure(report, case["id"], stage_name, "premature_confirmation", f"confirmed before confirmation stage: {confirmed!r}")

            forbidden = stage.get("forbidden_hypotheses", case.get("forbidden_hypotheses", []))
            for hypothesis_id in forbidden:
                _bump(report, split, "forbidden_hypothesis_checks")
                hypothesis = next((h for h in result.hypotheses if h.id == hypothesis_id), None)
                if hypothesis and hypothesis.status in {HypothesisStatus.SUPPORTED, HypothesisStatus.PROBABLE, HypothesisStatus.CONFIRMED}:
                    _bump(report, split, "forbidden_hypothesis_errors")
                    _record_failure(report, case["id"], stage_name, "scope", f"forbidden hypothesis {hypothesis_id} became {hypothesis.status.value}")

            if stage.get("workflow_handoff_check"):
                _bump(report, split, "workflow_handoff_checks")
                current_families = set(stage.get("evidence_tool_families", []))
                next_family = TEST_TOOL_FAMILY.get(actual_test or "")
                if next_family and next_family not in current_families:
                    _bump(report, split, "workflow_handoff_hits")

        expected_final = case.get("expected_final_hypotheses", [])
        if expected_final and final_result is not None:
            for hypothesis_id in expected_final:
                _bump(report, split, "confirmation_checks")
                hypothesis = next((h for h in final_result.hypotheses if h.id == hypothesis_id), None)
                if hypothesis and hypothesis.status == HypothesisStatus.CONFIRMED:
                    _bump(report, split, "confirmation_hits")
                elif case.get("require_final_confirmation", False):
                    actual = hypothesis.status.value if hypothesis else None
                    _record_failure(report, case["id"], "final", "confirmation", f"expected {hypothesis_id} confirmed, got {actual!r}")

        source_actions = case.get("source_diagnostic_actions")
        if case.get("action_reduction_eligible") and isinstance(source_actions, int) and (domain_hit_seen or not case.get("expected_hypotheses")):
            reduction = _safe_reduction(source_actions, len(selected_tests))
            if reduction is not None:
                _append(report, split, "action_reduction_samples", reduction)

        source_tools = case.get("source_tool_sequence", [])
        if case.get("tool_transition_eligible") and source_tools:
            planner_tools = [TEST_TOOL_FAMILY.get(test_id, test_id) for test_id in selected_tests]
            reduction = _safe_reduction(_transition_count(source_tools), _transition_count(planner_tools))
            if reduction is not None:
                _append(report, split, "tool_transition_reduction_samples", reduction)

    return report


def read_corpus_bytes(path: Path) -> bytes:
    data = path.read_bytes()
    return gzip.decompress(data) if path.suffix == ".gz" else data


def evaluate_file(path: Path) -> BenchmarkReport:
    return evaluate_payload(json.loads(read_corpus_bytes(path).decode("utf-8")))


def verify_freeze(corpus_path: Path, freeze_path: Path) -> bool:
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    expected = str(freeze.get("sha256", "")).lower()
    actual = hashlib.sha256(read_corpus_bytes(corpus_path)).hexdigest()
    return bool(expected) and actual == expected
