from __future__ import annotations

from collections.abc import Iterable

from .evidence import EvidenceIndex
from .models import Hypothesis, HypothesisStatus, Investigation, Observation
from .planner import plan_next_test


def _truth(facts: EvidenceIndex, key: str) -> bool:
    return facts.any_true(key)


def _pcie_hypothesis(facts: EvidenceIndex) -> Hypothesis:
    h = Hypothesis("pcie_path_degradation", "PCIe path degradation")
    if _truth(facts, "communication_regression_localized"):
        h.supporting_evidence.append("communication regression is localized")
    if _truth(facts, "affected_ranks_share_pcie_path"):
        h.supporting_evidence.append("affected ranks share a PCIe path")

    pairs = facts.pairs("pcie_width", "pcie_expected_width")
    degraded: list[tuple[str | None, int, int]] = []
    healthy: list[tuple[str | None, int, int]] = []
    for entity, width_ob, expected_ob in pairs:
        width, expected = width_ob.value, expected_ob.value
        if isinstance(width, int) and isinstance(expected, int):
            target = (entity, width, expected)
            if width < expected:
                degraded.append(target)
            else:
                healthy.append(target)

    if degraded:
        entity, width, expected = degraded[0]
        label = f" on {entity}" if entity else ""
        h.supporting_evidence.append(f"PCIe width is x{width}, expected x{expected}{label}")
        if len(degraded) > 1:
            h.supporting_evidence.append(f"{len(degraded)} affected-path PCIe devices are below expected width")
        h.status = HypothesisStatus.PROBABLE
    elif pairs and healthy:
        h.contradicting_evidence.append("affected-path PCIe widths match expected values")

    if _truth(facts, "targeted_nccl_validation_failed") and h.status == HypothesisStatus.PROBABLE:
        h.status = HypothesisStatus.CONFIRMED
    elif len(h.supporting_evidence) >= 2 and h.status == HypothesisStatus.POSSIBLE:
        h.status = HypothesisStatus.SUPPORTED

    if h.status != HypothesisStatus.CONFIRMED and _truth(facts, "targeted_nccl_validation_healthy"):
        h.contradicting_evidence.append("targeted NCCL validation is healthy on the suspected PCIe path")
        if h.status in {HypothesisStatus.SUPPORTED, HypothesisStatus.PROBABLE}:
            h.status = HypothesisStatus.REJECTED
    elif not degraded and healthy and h.status == HypothesisStatus.SUPPORTED:
        h.status = HypothesisStatus.POSSIBLE

    if h.status in {HypothesisStatus.SUPPORTED, HypothesisStatus.PROBABLE} and not pairs:
        h.missing_evidence.append("PCIe link width/speed for affected GPU/HCA path")
    return h


def _fabric_hypothesis(facts: EvidenceIndex) -> Hypothesis:
    h = Hypothesis("fabric_link_degradation", "Fabric / HCA path degradation")
    if _truth(facts, "communication_regression_localized"):
        h.supporting_evidence.append("communication regression is localized")
    if _truth(facts, "affected_ranks_share_hca"):
        h.supporting_evidence.append("affected ranks share the same HCA")
    if _truth(facts, "fabric_error_counters_rising"):
        h.supporting_evidence.append("fabric error/retry counters are rising")
        h.status = HypothesisStatus.PROBABLE
    if _truth(facts, "fabric_counters_clean"):
        h.contradicting_evidence.append("fabric counters are clean")
    if _truth(facts, "faulty_fabric_port_confirmed") and h.status == HypothesisStatus.PROBABLE:
        h.status = HypothesisStatus.CONFIRMED
    elif len(h.supporting_evidence) >= 2 and h.status == HypothesisStatus.POSSIBLE:
        h.status = HypothesisStatus.SUPPORTED

    if h.status != HypothesisStatus.CONFIRMED and _truth(facts, "fabric_path_validation_healthy"):
        h.contradicting_evidence.append("targeted fabric-path validation is healthy")
        if h.status in {HypothesisStatus.SUPPORTED, HypothesisStatus.PROBABLE}:
            h.status = HypothesisStatus.REJECTED
    elif _truth(facts, "fabric_port_clean") and h.status == HypothesisStatus.PROBABLE:
        h.contradicting_evidence.append("mapped physical fabric port is clean")
        h.status = HypothesisStatus.SUPPORTED
    elif _truth(facts, "fabric_counters_clean") and not _truth(facts, "fabric_error_counters_rising") and h.status == HypothesisStatus.SUPPORTED:
        h.status = HypothesisStatus.POSSIBLE

    if h.status in {HypothesisStatus.SUPPORTED, HypothesisStatus.PROBABLE} and not (
        _truth(facts, "fabric_error_counters_rising") or _truth(facts, "fabric_counters_clean")
    ):
        h.missing_evidence.append("IB/RoCE/HCA error and retry counters")
    return h


def _gpu_hardware_hypothesis(facts: EvidenceIndex) -> Hypothesis:
    h = Hypothesis("gpu_hardware_degradation", "GPU hardware degradation")
    if _truth(facts, "gpu_xid_or_ecc_error"):
        h.supporting_evidence.append("GPU XID/ECC evidence is present")
        h.status = HypothesisStatus.SUPPORTED
    if _truth(facts, "gpu_health_clean"):
        h.contradicting_evidence.append("GPU health checks are clean")
        h.status = HypothesisStatus.REJECTED
    return h


def _thermal_hypothesis(facts: EvidenceIndex) -> Hypothesis:
    h = Hypothesis("gpu_thermal_frequency_degradation", "GPU thermal / frequency degradation")
    if _truth(facts, "compute_straggler_localized"):
        h.supporting_evidence.append("compute slowdown is localized to one GPU/rank")
    if _truth(facts, "gpu_utilization_high"):
        h.supporting_evidence.append("GPU utilization remains high despite slower compute")
    if _truth(facts, "gpu_clock_below_peer"):
        h.supporting_evidence.append("GPU clock is below peer/baseline")
    if _truth(facts, "thermal_throttle_reason"):
        h.supporting_evidence.append("thermal throttle reason is present")
        h.status = HypothesisStatus.PROBABLE
    elif len(h.supporting_evidence) >= 2:
        h.status = HypothesisStatus.SUPPORTED
    if _truth(facts, "thermal_fix_restored_performance") and h.status in {HypothesisStatus.SUPPORTED, HypothesisStatus.PROBABLE}:
        h.status = HypothesisStatus.CONFIRMED

    if h.status != HypothesisStatus.CONFIRMED and _truth(facts, "thermal_fix_did_not_restore_performance"):
        h.contradicting_evidence.append("correcting the thermal condition did not restore performance")
        if h.status in {HypothesisStatus.SUPPORTED, HypothesisStatus.PROBABLE}:
            h.status = HypothesisStatus.REJECTED
    elif _truth(facts, "gpu_clock_thermal_state_matches_peers"):
        h.contradicting_evidence.append("GPU clock and thermal state match healthy peers")
        if h.status == HypothesisStatus.SUPPORTED:
            h.status = HypothesisStatus.POSSIBLE

    if h.status == HypothesisStatus.SUPPORTED and not (
        _truth(facts, "gpu_clock_below_peer") or _truth(facts, "gpu_clock_thermal_state_matches_peers")
    ):
        h.missing_evidence.append("peer/baseline GPU clocks and thermal throttle reasons")
    return h


def _software_hypothesis(facts: EvidenceIndex) -> Hypothesis:
    h = Hypothesis("software_config_regression", "Software / configuration regression")
    if _truth(facts, "regression_after_change"):
        h.supporting_evidence.append("regression started after a software/configuration change")
    if _truth(facts, "all_ranks_slow_uniformly"):
        h.supporting_evidence.append("slowdown is uniform across ranks")
    if _truth(facts, "config_diff_found"):
        h.supporting_evidence.append("baseline/current configuration diff is relevant to the slow path")
    if _truth(facts, "localized_to_single_path"):
        h.contradicting_evidence.append("problem is localized to one hardware path")
    if _truth(facts, "rollback_restored_performance"):
        h.supporting_evidence.append("rollback restored performance")
        h.status = HypothesisStatus.CONFIRMED
    elif len(h.supporting_evidence) >= 2:
        h.status = HypothesisStatus.PROBABLE
    elif h.supporting_evidence:
        h.status = HypothesisStatus.SUPPORTED

    if h.status != HypothesisStatus.CONFIRMED and _truth(facts, "rollback_did_not_restore_performance"):
        h.contradicting_evidence.append("controlled rollback did not restore performance")
        if h.status in {HypothesisStatus.SUPPORTED, HypothesisStatus.PROBABLE}:
            h.status = HypothesisStatus.REJECTED
    return h


def _host_cpu_hypothesis(facts: EvidenceIndex) -> Hypothesis:
    h = Hypothesis("host_cpu_irq_interference", "Host CPU / IRQ interference")
    if _truth(facts, "communication_waits"):
        h.supporting_evidence.append("communication waits are visible")
    if _truth(facts, "gpu_kernel_durations_match_peers"):
        h.supporting_evidence.append("GPU kernel durations match healthy peers")
    if _truth(facts, "irq_shares_nccl_cpu"):
        h.supporting_evidence.append("NIC IRQ/softirq activity shares the NCCL communication CPU")
        h.status = HypothesisStatus.PROBABLE
    elif len(h.supporting_evidence) >= 2:
        h.status = HypothesisStatus.SUPPORTED
    if _truth(facts, "cpu_profile_confirms_softirq_preemption") and h.status == HypothesisStatus.PROBABLE:
        h.status = HypothesisStatus.CONFIRMED

    if h.status != HypothesisStatus.CONFIRMED and _truth(facts, "cpu_profile_no_softirq_preemption"):
        h.contradicting_evidence.append("CPU/kernel profile does not show softirq preemption on the communication path")
        if h.status in {HypothesisStatus.SUPPORTED, HypothesisStatus.PROBABLE}:
            h.status = HypothesisStatus.REJECTED
    elif _truth(facts, "irq_affinity_clean") and not _truth(facts, "irq_shares_nccl_cpu"):
        h.contradicting_evidence.append("NIC IRQ affinity does not overlap the NCCL communication CPU")
        if h.status in {HypothesisStatus.SUPPORTED, HypothesisStatus.PROBABLE}:
            h.status = HypothesisStatus.REJECTED

    if h.status == HypothesisStatus.SUPPORTED and not (
        _truth(facts, "irq_shares_nccl_cpu") or _truth(facts, "irq_affinity_clean")
    ):
        h.missing_evidence.append("IRQ/CPU affinity for NIC and NCCL communication thread")
    return h


def _storage_hypothesis(facts: EvidenceIndex) -> Hypothesis:
    h = Hypothesis("storage_data_starvation", "Storage / data pipeline starvation")
    if _truth(facts, "gpu_wait_for_input"):
        h.supporting_evidence.append("GPU waits for input/data")
    if _truth(facts, "communication_path_healthy"):
        h.supporting_evidence.append("communication path does not explain the slowdown")
    if _truth(facts, "storage_client_cpu_elevated"):
        h.supporting_evidence.append("storage/data-loader client CPU work is elevated")
        h.status = HypothesisStatus.PROBABLE
    elif len(h.supporting_evidence) >= 2:
        h.status = HypothesisStatus.SUPPORTED
    if _truth(facts, "storage_or_loader_fix_restored_performance") and h.status == HypothesisStatus.PROBABLE:
        h.status = HypothesisStatus.CONFIRMED

    if h.status != HypothesisStatus.CONFIRMED and _truth(facts, "data_path_ab_did_not_restore_performance"):
        h.contradicting_evidence.append("controlled data-path correction did not restore performance")
        if h.status in {HypothesisStatus.SUPPORTED, HypothesisStatus.PROBABLE}:
            h.status = HypothesisStatus.REJECTED
    elif _truth(facts, "storage_client_profile_healthy") and not _truth(facts, "storage_client_cpu_elevated"):
        h.contradicting_evidence.append("storage/data-loader client profile is healthy")
        if h.status == HypothesisStatus.SUPPORTED:
            h.status = HypothesisStatus.POSSIBLE

    if h.status == HypothesisStatus.SUPPORTED and not (
        _truth(facts, "storage_client_cpu_elevated") or _truth(facts, "storage_client_profile_healthy")
    ):
        h.missing_evidence.append("host data-loader/storage client profile and request shape")
    return h


def _collective_desync_hypothesis(facts: EvidenceIndex) -> Hypothesis:
    h = Hypothesis("collective_work_invariant_failure", "Distributed work / collective invariant failure")
    if _truth(facts, "collective_hang"):
        h.supporting_evidence.append("distributed job is hung in/around collectives")
    if _truth(facts, "ranks_in_different_collectives"):
        h.supporting_evidence.append("ranks are observed in different collective states")
    if _truth(facts, "per_rank_work_counts_differ"):
        h.supporting_evidence.append("per-rank steps/batches/tokens/blocks differ")
        h.status = HypothesisStatus.PROBABLE
    elif len(h.supporting_evidence) >= 2:
        h.status = HypothesisStatus.SUPPORTED
    if _truth(facts, "invariant_fix_restored_training") and h.status == HypothesisStatus.PROBABLE:
        h.status = HypothesisStatus.CONFIRMED

    if h.status != HypothesisStatus.CONFIRMED and _truth(facts, "invariant_fix_did_not_restore_training"):
        h.contradicting_evidence.append("equalizing the work invariant did not restore the run")
        if h.status in {HypothesisStatus.SUPPORTED, HypothesisStatus.PROBABLE}:
            h.status = HypothesisStatus.REJECTED
    elif _truth(facts, "per_rank_work_counts_equal") and not _truth(facts, "per_rank_work_counts_differ"):
        h.contradicting_evidence.append("per-rank work counts are equal")
        if h.status in {HypothesisStatus.SUPPORTED, HypothesisStatus.PROBABLE}:
            h.status = HypothesisStatus.REJECTED

    if h.status == HypothesisStatus.SUPPORTED and not (
        _truth(facts, "per_rank_work_counts_differ") or _truth(facts, "per_rank_work_counts_equal")
    ):
        h.missing_evidence.append("per-rank work/step counts and collective sequence invariants")
    return h


def investigate(symptom: str, observations: Iterable[Observation]) -> Investigation:
    facts = EvidenceIndex.from_iterable(observations)
    hypotheses = [
        _pcie_hypothesis(facts),
        _fabric_hypothesis(facts),
        _gpu_hardware_hypothesis(facts),
        _thermal_hypothesis(facts),
        _software_hypothesis(facts),
        _host_cpu_hypothesis(facts),
        _storage_hypothesis(facts),
        _collective_desync_hypothesis(facts),
    ]
    confirmed = [h for h in hypotheses if h.status == HypothesisStatus.CONFIRMED]
    next_test = plan_next_test(hypotheses, facts)
    verdict = None
    notes: list[str] = []
    if confirmed:
        verdict = "; ".join(h.title for h in confirmed)
    elif next_test:
        notes.append("Insufficient evidence for a confirmed root-cause verdict.")
    else:
        notes.append("No useful next test is defined for the current evidence set yet.")
    return Investigation(symptom=symptom, hypotheses=hypotheses, next_best_test=next_test, verdict=verdict, notes=notes)
