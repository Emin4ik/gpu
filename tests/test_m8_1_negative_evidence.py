from gputriage import investigate
from gputriage.models import HypothesisStatus, Observation


def obs(**facts):
    return [Observation(key=k, value=v, source="test") for k, v in facts.items()]


def by_id(result, hypothesis_id):
    return next(h for h in result.hypotheses if h.id == hypothesis_id)


def test_clean_irq_affinity_rejects_host_irq_and_does_not_repeat_collection():
    result = investigate(
        "collective waits grow",
        obs(
            communication_waits=True,
            gpu_kernel_durations_match_peers=True,
            irq_affinity_clean=True,
        ),
    )
    h = by_id(result, "host_cpu_irq_interference")
    assert h.status == HypothesisStatus.REJECTED
    assert any("does not overlap" in item for item in h.contradicting_evidence)
    assert result.next_best_test is None


def test_equal_rank_work_rejects_invariant_path_and_does_not_repeat_comparison():
    result = investigate(
        "job hangs around collectives",
        obs(
            collective_hang=True,
            ranks_in_different_collectives=True,
            per_rank_work_counts_equal=True,
        ),
    )
    h = by_id(result, "collective_work_invariant_failure")
    assert h.status == HypothesisStatus.REJECTED
    assert result.next_best_test is None


def test_failed_rollback_rejects_software_and_does_not_repeat_rollback():
    result = investigate(
        "uniform regression after config change",
        obs(
            regression_after_change=True,
            all_ranks_slow_uniformly=True,
            rollback_did_not_restore_performance=True,
        ),
    )
    h = by_id(result, "software_config_regression")
    assert h.status == HypothesisStatus.REJECTED
    assert result.next_best_test is None


def test_healthy_targeted_nccl_rejects_pcie_root_cause_even_with_downtrained_link():
    result = investigate(
        "localized NCCL slowdown",
        obs(
            communication_regression_localized=True,
            affected_ranks_share_pcie_path=True,
            pcie_width=8,
            pcie_expected_width=16,
            targeted_nccl_validation_healthy=True,
        ),
    )
    h = by_id(result, "pcie_path_degradation")
    assert h.status == HypothesisStatus.REJECTED
    assert result.next_best_test is None


def test_generic_completed_test_marker_blocks_reselection_without_faking_outcome():
    result = investigate(
        "uniform regression after config change",
        obs(
            regression_after_change=True,
            all_ranks_slow_uniformly=True,
            **{"test_completed.controlled_rollback_ab": True},
        ),
    )
    h = by_id(result, "software_config_regression")
    assert h.status == HypothesisStatus.PROBABLE
    assert result.next_best_test is None


def test_negative_data_path_ab_rejects_storage_root_cause():
    result = investigate(
        "GPUs wait for input",
        obs(
            gpu_wait_for_input=True,
            communication_path_healthy=True,
            storage_client_cpu_elevated=True,
            data_path_ab_did_not_restore_performance=True,
        ),
    )
    h = by_id(result, "storage_data_starvation")
    assert h.status == HypothesisStatus.REJECTED
    assert result.next_best_test is None
