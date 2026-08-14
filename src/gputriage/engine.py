from __future__ import annotations

from collections.abc import Iterable

from .evidence import EvidenceIndex
from .models import DiagnosticTest, Hypothesis, HypothesisStatus, Investigation, Observation


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
    if h.status == HypothesisStatus.SUPPORTED and not _truth(facts, "gpu_clock_below_peer"):
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
    if h.status == HypothesisStatus.SUPPORTED and not _truth(facts, "irq_shares_nccl_cpu"):
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
    if h.status == HypothesisStatus.SUPPORTED and not _truth(facts, "storage_client_cpu_elevated"):
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
    if h.status == HypothesisStatus.SUPPORTED and not _truth(facts, "per_rank_work_counts_differ"):
        h.missing_evidence.append("per-rank work/step counts and collective sequence invariants")
    return h


def _test(id: str, title: str, purpose: str, command: str | None, cost: str, invasiveness: str, *hypotheses: str) -> DiagnosticTest:
    return DiagnosticTest(id=id, title=title, purpose=purpose, command=command, cost=cost, invasiveness=invasiveness, discriminates_between=tuple(hypotheses))


def _choose_next_test(hypotheses: list[Hypothesis], facts: EvidenceIndex) -> DiagnosticTest | None:
    by_id = {h.id: h for h in hypotheses}
    pcie = by_id["pcie_path_degradation"]
    fabric = by_id["fabric_link_degradation"]
    thermal = by_id["gpu_thermal_frequency_degradation"]
    software = by_id["software_config_regression"]
    host_cpu = by_id["host_cpu_irq_interference"]
    storage = by_id["storage_data_starvation"]
    desync = by_id["collective_work_invariant_failure"]

    if pcie.status == HypothesisStatus.SUPPORTED and pcie.missing_evidence:
        return _test("collect_pcie_link_state", "Collect PCIe link state on the affected path", "Separate PCIe degradation from fabric/NCCL hypotheses using a cheap read-only check.", "lspci -vv -s <GPU_OR_HCA_BDF>", "low", "read_only", "pcie_path_degradation", "fabric_link_degradation")
    if pcie.status == HypothesisStatus.PROBABLE and not _truth(facts, "targeted_nccl_validation_failed"):
        return _test("targeted_nccl_validation", "Run a targeted NCCL validation on affected nodes", "Confirm that the observed PCIe-path abnormality produces the workload communication regression.", "<targeted nccl-tests command>", "medium", "low_impact", "pcie_path_degradation", "software_config_regression")
    if fabric.status == HypothesisStatus.SUPPORTED and fabric.missing_evidence:
        return _test("collect_fabric_counters", "Collect HCA / fabric error counters", "Check whether the localized communication regression follows a physical or congested fabric path.", "ibqueryerrors -rR || ethtool -S <NETDEV>", "low", "read_only", "fabric_link_degradation", "pcie_path_degradation")
    if fabric.status == HypothesisStatus.PROBABLE and not _truth(facts, "faulty_fabric_port_confirmed"):
        return _test("inspect_fabric_port", "Inspect the mapped physical fabric port", "Localize rising NIC/HCA errors to a switch port, cable, or transceiver before remediation.", "mlxlink -d <DEVICE> || <query switch telemetry for mapped port>", "low", "read_only", "fabric_link_degradation")
    if thermal.status == HypothesisStatus.SUPPORTED and thermal.missing_evidence:
        return _test("collect_gpu_clock_thermal_state", "Compare GPU clocks and thermal throttle reasons to peers", "High utilization does not prove healthy compute; clocks and throttle reasons distinguish thermal degradation.", "nvidia-smi -q -d CLOCK,TEMPERATURE,PERFORMANCE", "low", "read_only", "gpu_thermal_frequency_degradation", "gpu_hardware_degradation")
    if thermal.status == HypothesisStatus.PROBABLE and not _truth(facts, "thermal_fix_restored_performance"):
        return _test("validate_thermal_recovery", "Revalidate performance after correcting the thermal condition", "A repair/recovery check turns a plausible thermal correlation into causal confirmation.", "<repeat the same peer/baseline workload check>", "medium", "low_impact", "gpu_thermal_frequency_degradation")
    if host_cpu.status == HypothesisStatus.SUPPORTED and host_cpu.missing_evidence:
        return _test("collect_irq_affinity", "Inspect NIC IRQ and NCCL CPU affinity", "Test whether host interrupt processing can preempt the communication thread without blaming the fabric prematurely.", "cat /proc/interrupts && taskset -pc <NCCL_PID>", "low", "read_only", "host_cpu_irq_interference", "fabric_link_degradation")
    if host_cpu.status == HypothesisStatus.PROBABLE and not _truth(facts, "cpu_profile_confirms_softirq_preemption"):
        return _test("short_cpu_profile", "Capture a short CPU/kernel profile on the affected node", "Confirm that NET_RX_SOFTIRQ or related host work actually preempts the NCCL communication path.", "perf record -F 99 -a -- sleep 15", "medium", "low_impact", "host_cpu_irq_interference")
    if storage.status == HypothesisStatus.SUPPORTED and storage.missing_evidence:
        return _test("collect_storage_client_profile", "Inspect data-loader and storage-client work", "Distinguish storage/data starvation from GPU or collective bottlenecks when input gaps dominate.", "<collect short host CPU/storage client profile and request-shape stats>", "medium", "read_only", "storage_data_starvation", "host_cpu_irq_interference")
    if storage.status == HypothesisStatus.PROBABLE and not _truth(facts, "storage_or_loader_fix_restored_performance"):
        return _test("controlled_data_path_ab", "Run a controlled data-path A/B validation", "Confirm whether the identified storage/data-loader path is causal rather than merely correlated.", "<repeat workload with corrected loader/storage path>", "medium", "low_impact", "storage_data_starvation")
    if desync.status == HypothesisStatus.SUPPORTED and desync.missing_evidence:
        return _test("compare_rank_work_invariants", "Compare per-rank work and collective invariants", "Before blaming NCCL transport, verify that all ranks execute the same number and sequence of collective steps.", "<compare per-rank steps/batches/tokens/blocks and flight-recorder collective state>", "low", "read_only", "collective_work_invariant_failure", "fabric_link_degradation")
    if desync.status == HypothesisStatus.PROBABLE and not _truth(facts, "invariant_fix_restored_training"):
        return _test("validate_invariant_fix", "Repeat the run with equalized per-rank work invariants", "Confirm that collective synchronization recovers when ranks execute equal work/step counts.", "<rerun after enforcing equal per-rank work counts>", "medium", "low_impact", "collective_work_invariant_failure")
    if software.status == HypothesisStatus.PROBABLE and not _truth(facts, "rollback_restored_performance"):
        return _test("controlled_rollback_ab", "Run a controlled rollback or A/B against the last known-good configuration", "Confirm whether the observed change is causal instead of merely correlated with the slowdown.", "<rollback or controlled A/B using the previous configuration>", "medium", "low_impact", "software_config_regression")
    return None


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
    next_test = _choose_next_test(hypotheses, facts)
    verdict = None
    notes: list[str] = []
    if confirmed:
        verdict = "; ".join(h.title for h in confirmed)
    elif next_test:
        notes.append("Insufficient evidence for a confirmed root-cause verdict.")
    else:
        notes.append("No useful next test is defined for the current evidence set yet.")
    return Investigation(symptom=symptom, hypotheses=hypotheses, next_best_test=next_test, verdict=verdict, notes=notes)
