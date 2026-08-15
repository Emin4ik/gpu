from gputriage import investigate
from gputriage.models import Hypothesis, HypothesisStatus, Observation
from gputriage.planner import DiagnosticTestSpec, rank_candidate_specs


def obs(**facts):
    return [Observation(key=key, value=value, source="test") for key, value in facts.items()]


def test_planner_prefers_read_only_when_information_is_equal():
    hypothesis = Hypothesis(
        id="h1",
        title="test hypothesis",
        status=HypothesisStatus.SUPPORTED,
        supporting_evidence=["signal A", "signal B"],
    )
    cheap = DiagnosticTestSpec(
        id="cheap",
        title="cheap",
        purpose="read-only check",
        command="cheap",
        cost="low",
        invasiveness="read_only",
        duration_class="seconds",
        owner_hypothesis="h1",
        trigger_statuses=(HypothesisStatus.SUPPORTED,),
        discriminates_between=("h1",),
        information_value=5,
        expected_outcomes=("yes", "no"),
    )
    disruptive = DiagnosticTestSpec(
        id="disruptive",
        title="disruptive",
        purpose="expensive check",
        command="disruptive",
        cost="low",
        invasiveness="disruptive",
        duration_class="seconds",
        owner_hypothesis="h1",
        trigger_statuses=(HypothesisStatus.SUPPORTED,),
        discriminates_between=("h1",),
        information_value=5,
        expected_outcomes=("yes", "no"),
    )
    ranked = rank_candidate_specs([disruptive, cheap], [hypothesis])
    assert ranked[0][0].id == "cheap"
    assert ranked[0][1] > ranked[1][1]


def test_initial_pcie_vs_fabric_case_has_explainable_choice():
    result = investigate(
        "localized NCCL slowdown",
        obs(
            communication_regression_localized=True,
            affected_ranks_share_pcie_path=True,
            affected_ranks_share_hca=True,
            gpu_health_clean=True,
        ),
    )
    test = result.next_best_test
    assert test is not None
    assert test.id == "collect_pcie_link_state"
    assert test.selection_reason is not None
    assert "Selected from 2 eligible test(s)" in test.selection_reason
    assert any("collect_fabric_counters" in alternative for alternative in test.alternatives)
    assert test.expected_outcomes


def test_probable_pcie_prioritizes_confirmation_over_fabric_collection():
    result = investigate(
        "localized NCCL slowdown",
        obs(
            communication_regression_localized=True,
            affected_ranks_share_pcie_path=True,
            affected_ranks_share_hca=True,
            pcie_width=8,
            pcie_expected_width=16,
            gpu_health_clean=True,
        ),
    )
    test = result.next_best_test
    assert test is not None
    assert test.id == "targeted_nccl_validation"
    assert any("collect_fabric_counters" in alternative for alternative in test.alternatives)


def test_unknown_incident_still_abstains_without_registered_candidate():
    result = investigate("mysterious stall", obs(gpu_health_clean=True))
    assert result.verdict is None
    assert result.next_best_test is None
    assert any("No useful next test" in note for note in result.notes)
