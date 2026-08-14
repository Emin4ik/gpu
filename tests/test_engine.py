from gputriage import investigate
from gputriage.models import HypothesisStatus, Observation


def obs(**facts):
    return [Observation(key=k, value=v, source="test") for k, v in facts.items()]


def by_id(result, hypothesis_id):
    return next(h for h in result.hypotheses if h.id == hypothesis_id)


def test_missing_pcie_state_selects_pcie_collection_first():
    result = investigate(
        "localized NCCL slowdown",
        obs(
            communication_regression_localized=True,
            affected_ranks_share_pcie_path=True,
            affected_ranks_share_hca=True,
            gpu_health_clean=True,
        ),
    )

    assert result.verdict is None
    assert by_id(result, "gpu_hardware_degradation").status == HypothesisStatus.REJECTED
    assert by_id(result, "pcie_path_degradation").status == HypothesisStatus.SUPPORTED
    assert result.next_best_test is not None
    assert result.next_best_test.id == "collect_pcie_link_state"


def test_degraded_pcie_becomes_probable_then_requests_targeted_validation():
    result = investigate(
        "localized NCCL slowdown",
        obs(
            communication_regression_localized=True,
            affected_ranks_share_pcie_path=True,
            gpu_health_clean=True,
            pcie_width=8,
            pcie_expected_width=16,
            fabric_counters_clean=True,
        ),
    )

    assert by_id(result, "pcie_path_degradation").status == HypothesisStatus.PROBABLE
    assert result.verdict is None
    assert result.next_best_test is not None
    assert result.next_best_test.id == "targeted_nccl_validation"


def test_targeted_validation_can_confirm_pcie_without_fake_numeric_confidence():
    result = investigate(
        "localized NCCL slowdown",
        obs(
            communication_regression_localized=True,
            affected_ranks_share_pcie_path=True,
            pcie_width=8,
            pcie_expected_width=16,
            targeted_nccl_validation_failed=True,
            gpu_health_clean=True,
        ),
    )

    assert by_id(result, "pcie_path_degradation").status == HypothesisStatus.CONFIRMED
    assert result.verdict == "PCIe path degradation"


def test_software_change_can_be_probable_without_claiming_confirmation():
    result = investigate(
        "cluster-wide throughput regression",
        obs(
            regression_after_change=True,
            all_ranks_slow_uniformly=True,
            gpu_health_clean=True,
            pcie_width=16,
            pcie_expected_width=16,
            fabric_counters_clean=True,
        ),
    )

    software = by_id(result, "software_config_regression")
    assert software.status == HypothesisStatus.PROBABLE
    assert result.verdict is None
