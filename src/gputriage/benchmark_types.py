from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Any

from .models import HypothesisStatus


STATUS_RANK = {
    HypothesisStatus.CONFIRMED: 4,
    HypothesisStatus.PROBABLE: 3,
    HypothesisStatus.SUPPORTED: 2,
    HypothesisStatus.POSSIBLE: 1,
    HypothesisStatus.REJECTED: 0,
}

TEST_TOOL_FAMILY = {
    "collect_pcie_link_state": "lspci",
    "targeted_nccl_validation": "nccl",
    "collect_fabric_counters": "fabric_counters",
    "inspect_fabric_port": "fabric_link",
    "collect_gpu_clock_thermal_state": "gpu_telemetry",
    "validate_thermal_recovery": "workload_validation",
    "collect_irq_affinity": "host_irq",
    "short_cpu_profile": "cpu_profile",
    "collect_storage_client_profile": "storage_profile",
    "controlled_data_path_ab": "workload_validation",
    "compare_rank_work_invariants": "rank_invariants",
    "validate_invariant_fix": "workload_validation",
    "controlled_rollback_ab": "workload_validation",
}


@dataclass
class BenchmarkFailure:
    case_id: str
    stage: str
    kind: str
    message: str


@dataclass
class BenchmarkCounters:
    cases: int = 0
    source_cases: int = 0
    mutation_cases: int = 0
    stages: int = 0
    domain_checks: int = 0
    domain_hits_at_3: int = 0
    domain_label_checks: int = 0
    domain_label_hits: int = 0
    next_test_checks: int = 0
    next_test_utility_points: int = 0
    next_test_utility_2_hits: int = 0
    abstention_checks: int = 0
    abstention_hits: int = 0
    premature_confirmations: int = 0
    confirmation_checks: int = 0
    confirmation_hits: int = 0
    forbidden_hypothesis_checks: int = 0
    forbidden_hypothesis_errors: int = 0
    workflow_handoff_checks: int = 0
    workflow_handoff_hits: int = 0
    specialist_overlap_cases: int = 0
    action_reduction_samples: list[float] = field(default_factory=list)
    tool_transition_reduction_samples: list[float] = field(default_factory=list)

    @property
    def domain_recall_at_3(self) -> float:
        return self.domain_hits_at_3 / self.domain_checks if self.domain_checks else 0.0

    @property
    def domain_label_recall(self) -> float:
        return self.domain_label_hits / self.domain_label_checks if self.domain_label_checks else 0.0

    @property
    def next_test_utility_2_rate(self) -> float:
        return self.next_test_utility_2_hits / self.next_test_checks if self.next_test_checks else 0.0

    @property
    def mean_next_test_utility(self) -> float:
        return self.next_test_utility_points / self.next_test_checks if self.next_test_checks else 0.0

    @property
    def abstention_accuracy(self) -> float:
        return self.abstention_hits / self.abstention_checks if self.abstention_checks else 0.0

    @property
    def premature_confirmation_rate(self) -> float:
        return self.premature_confirmations / self.stages if self.stages else 0.0

    @property
    def confirmation_rate(self) -> float:
        return self.confirmation_hits / self.confirmation_checks if self.confirmation_checks else 0.0

    @property
    def forbidden_hypothesis_error_rate(self) -> float:
        return self.forbidden_hypothesis_errors / self.forbidden_hypothesis_checks if self.forbidden_hypothesis_checks else 0.0

    @property
    def workflow_handoff_rate(self) -> float:
        return self.workflow_handoff_hits / self.workflow_handoff_checks if self.workflow_handoff_checks else 0.0

    @property
    def median_action_reduction(self) -> float | None:
        return statistics.median(self.action_reduction_samples) if self.action_reduction_samples else None

    @property
    def median_tool_transition_reduction(self) -> float | None:
        return statistics.median(self.tool_transition_reduction_samples) if self.tool_transition_reduction_samples else None

    def as_dict(self) -> dict[str, Any]:
        return {
            "cases": self.cases,
            "source_cases": self.source_cases,
            "mutation_cases": self.mutation_cases,
            "stages": self.stages,
            "domain_checks": self.domain_checks,
            "domain_hits_at_3": self.domain_hits_at_3,
            "domain_recall_at_3": self.domain_recall_at_3,
            "domain_label_checks": self.domain_label_checks,
            "domain_label_hits": self.domain_label_hits,
            "domain_label_recall": self.domain_label_recall,
            "next_test_checks": self.next_test_checks,
            "next_test_utility_2_hits": self.next_test_utility_2_hits,
            "next_test_utility_2_rate": self.next_test_utility_2_rate,
            "mean_next_test_utility": self.mean_next_test_utility,
            "abstention_checks": self.abstention_checks,
            "abstention_hits": self.abstention_hits,
            "abstention_accuracy": self.abstention_accuracy,
            "premature_confirmations": self.premature_confirmations,
            "premature_confirmation_rate": self.premature_confirmation_rate,
            "confirmation_checks": self.confirmation_checks,
            "confirmation_hits": self.confirmation_hits,
            "confirmation_rate": self.confirmation_rate,
            "forbidden_hypothesis_checks": self.forbidden_hypothesis_checks,
            "forbidden_hypothesis_errors": self.forbidden_hypothesis_errors,
            "forbidden_hypothesis_error_rate": self.forbidden_hypothesis_error_rate,
            "workflow_handoff_checks": self.workflow_handoff_checks,
            "workflow_handoff_hits": self.workflow_handoff_hits,
            "workflow_handoff_rate": self.workflow_handoff_rate,
            "specialist_overlap_cases": self.specialist_overlap_cases,
            "action_reduction_sample_count": len(self.action_reduction_samples),
            "median_action_reduction": self.median_action_reduction,
            "tool_transition_reduction_sample_count": len(self.tool_transition_reduction_samples),
            "median_tool_transition_reduction": self.median_tool_transition_reduction,
        }


@dataclass
class BenchmarkReport(BenchmarkCounters):
    failures: list[BenchmarkFailure] = field(default_factory=list)
    by_split: dict[str, BenchmarkCounters] = field(default_factory=dict)
    distinct_source_incidents: set[str] = field(default_factory=set)
    quality_grades: dict[str, int] = field(default_factory=dict)
    freeze_verified: bool | None = None

    def as_dict(self) -> dict[str, Any]:
        payload = super().as_dict()
        payload["distinct_source_incidents"] = len(self.distinct_source_incidents)
        payload["quality_grades"] = dict(sorted(self.quality_grades.items()))
        payload["by_split"] = {name: counters.as_dict() for name, counters in sorted(self.by_split.items())}
        payload["freeze_verified"] = self.freeze_verified
        payload["gates"] = evaluate_gates(self)
        payload["failures"] = [failure.__dict__ for failure in self.failures ]
        return payload


def evaluate_gates(report: BenchmarkCounters) -> dict[str, dict[str, Any]]:
    def gate(value: float | None, threshold: float, op: str, samples: int | None = None) -> dict[str, Any]:
        if value is None or (samples is not None and samples == 0):
            return {"status": "not_measured", "value": value, "threshold": threshold, "op": op}
        passed = value >= threshold if op == ">=" else value <= threshold
        return {"status": "pass" if passed else "fail", "value": value, "threshold": threshold, "op": op}

    return {
        "domain_recall_at_3": gate(report.domain_recall_at_3, 0.75, ">=", report.domain_checks),
        "next_test_utility_2_rate": gate(report.next_test_utility_2_rate, 0.70, ">=", report.next_test_checks),
        "premature_confirmation_rate": gate(report.premature_confirmation_rate, 0.05, "<=", report.stages),
        "abstention_accuracy": gate(report.abstention_accuracy, 0.90, ">=", report.abstention_checks),
        "median_action_reduction": gate(report.median_action_reduction, 0.30, ">=", len(report.action_reduction_samples)),
        "median_tool_transition_reduction": gate(report.median_tool_transition_reduction, 0.50, ">=", len(report.tool_transition_reduction_samples)),
        "forbidden_hypothesis_error_rate": gate(report.forbidden_hypothesis_error_rate, 0.05, "<=", report.forbidden_hypothesis_checks),
    }


def gate_failed(report: BenchmarkReport, safety_only: bool) -> bool:
    if report.freeze_verified is False:
        return True
    gates = evaluate_gates(report)
    names = {"premature_confirmation_rate"} if safety_only else set(gates)
    return any(gates[name]["status"] == "fail" for name in names)
