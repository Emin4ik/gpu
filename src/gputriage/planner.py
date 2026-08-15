from __future__ import annotations

from dataclasses import dataclass

from .evidence import EvidenceIndex
from .models import DiagnosticTest, Hypothesis, HypothesisStatus


@dataclass(frozen=True)
class DiagnosticTestSpec:
    id: str
    title: str
    purpose: str
    command: str | None
    cost: str
    invasiveness: str
    duration_class: str
    owner_hypothesis: str
    trigger_statuses: tuple[HypothesisStatus, ...]
    discriminates_between: tuple[str, ...]
    information_value: int
    expected_outcomes: tuple[str, ...]
    require_missing_evidence: bool = False
    blocked_by_true: tuple[str, ...] = ()
    completion_keys: tuple[str, ...] = ()


STATUS_BONUS = {
    HypothesisStatus.POSSIBLE: 1,
    HypothesisStatus.SUPPORTED: 6,
    HypothesisStatus.PROBABLE: 10,
    HypothesisStatus.CONFIRMED: 0,
    HypothesisStatus.REJECTED: 0,
}
COST_PENALTY = {"low": 0, "medium": 2, "high": 5}
INVASIVENESS_PENALTY = {"read_only": 0, "low_impact": 1, "disruptive": 6}
DURATION_PENALTY = {"seconds": 0, "minutes": 1, "long": 4}


TEST_REGISTRY: tuple[DiagnosticTestSpec, ...] = (
    DiagnosticTestSpec(
        id="collect_pcie_link_state",
        title="Collect PCIe link state on the affected path",
        purpose="Separate PCIe degradation from fabric/NCCL hypotheses using a cheap read-only check.",
        command="lspci -vv -s <GPU_OR_HCA_BDF>",
        cost="low",
        invasiveness="read_only",
        duration_class="seconds",
        owner_hypothesis="pcie_path_degradation",
        trigger_statuses=(HypothesisStatus.SUPPORTED,),
        discriminates_between=("pcie_path_degradation", "fabric_link_degradation"),
        information_value=5,
        expected_outcomes=(
            "link matches expected width/speed -> weaken PCIe degradation",
            "link is downtrained/degraded -> strengthen PCIe degradation",
        ),
        require_missing_evidence=True,
    ),
    DiagnosticTestSpec(
        id="targeted_nccl_validation",
        title="Run a targeted NCCL validation on affected nodes",
        purpose="Confirm whether the localized PCIe-path abnormality produces the workload communication regression.",
        command="<targeted nccl-tests command>",
        cost="medium",
        invasiveness="low_impact",
        duration_class="minutes",
        owner_hypothesis="pcie_path_degradation",
        trigger_statuses=(HypothesisStatus.PROBABLE,),
        discriminates_between=("pcie_path_degradation", "software_config_regression"),
        information_value=5,
        expected_outcomes=(
            "targeted validation reproduces degradation -> confirm PCIe path hypothesis",
            "targeted validation is healthy -> weaken PCIe path hypothesis",
        ),
        completion_keys=("targeted_nccl_validation_failed", "targeted_nccl_validation_healthy"),
    ),
    DiagnosticTestSpec(
        id="collect_fabric_counters",
        title="Collect HCA / fabric error counters",
        purpose="Check whether the localized communication regression follows a physical or congested fabric path.",
        command="ibqueryerrors -rR || ethtool -S <NETDEV>",
        cost="low",
        invasiveness="read_only",
        duration_class="seconds",
        owner_hypothesis="fabric_link_degradation",
        trigger_statuses=(HypothesisStatus.SUPPORTED,),
        discriminates_between=("fabric_link_degradation", "pcie_path_degradation"),
        information_value=4,
        expected_outcomes=(
            "error/retry counters rise on affected path -> strengthen fabric hypothesis",
            "counters remain clean -> weaken physical fabric hypothesis",
        ),
        require_missing_evidence=True,
        completion_keys=("fabric_error_counters_rising", "fabric_counters_clean"),
    ),
    DiagnosticTestSpec(
        id="inspect_fabric_port",
        title="Inspect the mapped physical fabric port",
        purpose="Localize rising NIC/HCA errors to a switch port, cable, or transceiver before remediation.",
        command="mlxlink -d <DEVICE> || <query switch telemetry for mapped port>",
        cost="low",
        invasiveness="read_only",
        duration_class="seconds",
        owner_hypothesis="fabric_link_degradation",
        trigger_statuses=(HypothesisStatus.PROBABLE,),
        discriminates_between=("fabric_link_degradation",),
        information_value=5,
        expected_outcomes=(
            "mapped port shows physical errors -> confirm/localize fabric path",
            "mapped port is clean -> search upstream congestion or alternate cause",
        ),
        completion_keys=("faulty_fabric_port_confirmed", "fabric_port_clean"),
    ),
    DiagnosticTestSpec(
        id="collect_gpu_clock_thermal_state",
        title="Compare GPU clocks and thermal throttle reasons to peers",
        purpose="Distinguish thermal/frequency degradation from healthy high-utilization compute.",
        command="nvidia-smi -q -d CLOCK,TEMPERATURE,PERFORMANCE",
        cost="low",
        invasiveness="read_only",
        duration_class="seconds",
        owner_hypothesis="gpu_thermal_frequency_degradation",
        trigger_statuses=(HypothesisStatus.SUPPORTED,),
        discriminates_between=("gpu_thermal_frequency_degradation", "gpu_hardware_degradation"),
        information_value=5,
        expected_outcomes=(
            "clock/throttle state diverges from peers -> strengthen thermal hypothesis",
            "clock/thermal state matches peers -> weaken thermal hypothesis",
        ),
        require_missing_evidence=True,
        completion_keys=("thermal_throttle_reason", "gpu_clock_thermal_state_matches_peers"),
    ),
    DiagnosticTestSpec(
        id="validate_thermal_recovery",
        title="Revalidate performance after correcting the thermal condition",
        purpose="Turn a strong thermal correlation into causal confirmation.",
        command="<repeat the same peer/baseline workload check>",
        cost="medium",
        invasiveness="low_impact",
        duration_class="minutes",
        owner_hypothesis="gpu_thermal_frequency_degradation",
        trigger_statuses=(HypothesisStatus.PROBABLE,),
        discriminates_between=("gpu_thermal_frequency_degradation",),
        information_value=5,
        expected_outcomes=(
            "performance recovers -> confirm thermal cause",
            "performance remains degraded -> keep alternative causes active",
        ),
        completion_keys=("thermal_fix_restored_performance", "thermal_fix_did_not_restore_performance"),
    ),
    DiagnosticTestSpec(
        id="collect_irq_affinity",
        title="Inspect NIC IRQ and NCCL CPU affinity",
        purpose="Test whether host interrupt processing can preempt the communication thread without blaming fabric prematurely.",
        command="cat /proc/interrupts && taskset -pc <NCCL_PID>",
        cost="low",
        invasiveness="read_only",
        duration_class="seconds",
        owner_hypothesis="host_cpu_irq_interference",
        trigger_statuses=(HypothesisStatus.SUPPORTED,),
        discriminates_between=("host_cpu_irq_interference", "fabric_link_degradation"),
        information_value=5,
        expected_outcomes=(
            "NIC IRQ overlaps NCCL communication CPU -> strengthen host interference",
            "affinity is clean -> weaken IRQ-interference hypothesis",
        ),
        require_missing_evidence=True,
        completion_keys=("irq_shares_nccl_cpu", "irq_affinity_clean"),
    ),
    DiagnosticTestSpec(
        id="short_cpu_profile",
        title="Capture a short CPU/kernel profile on the affected node",
        purpose="Confirm whether NET_RX_SOFTIRQ or related host work actually preempts the NCCL communication path.",
        command="perf record -F 99 -a -- sleep 15",
        cost="medium",
        invasiveness="low_impact",
        duration_class="minutes",
        owner_hypothesis="host_cpu_irq_interference",
        trigger_statuses=(HypothesisStatus.PROBABLE,),
        discriminates_between=("host_cpu_irq_interference",),
        information_value=5,
        expected_outcomes=(
            "profile shows softirq/preemption on communication CPU -> confirm host cause",
            "profile does not show host contention -> search alternate cause",
        ),
        completion_keys=("cpu_profile_confirms_softirq_preemption", "cpu_profile_no_softirq_preemption"),
    ),
    DiagnosticTestSpec(
        id="collect_storage_client_profile",
        title="Inspect data-loader and storage-client work",
        purpose="Distinguish storage/data starvation from GPU or collective bottlenecks when input gaps dominate.",
        command="<collect short host CPU/storage client profile and request-shape stats>",
        cost="medium",
        invasiveness="read_only",
        duration_class="minutes",
        owner_hypothesis="storage_data_starvation",
        trigger_statuses=(HypothesisStatus.SUPPORTED,),
        discriminates_between=("storage_data_starvation", "host_cpu_irq_interference"),
        information_value=4,
        expected_outcomes=(
            "loader/storage client dominates wait -> strengthen storage/data hypothesis",
            "storage path is healthy -> weaken storage/data hypothesis",
        ),
        require_missing_evidence=True,
        completion_keys=("storage_client_cpu_elevated", "storage_client_profile_healthy"),
    ),
    DiagnosticTestSpec(
        id="controlled_data_path_ab",
        title="Run a controlled data-path A/B validation",
        purpose="Confirm whether the identified storage/data-loader path is causal rather than merely correlated.",
        command="<repeat workload with corrected loader/storage path>",
        cost="medium",
        invasiveness="low_impact",
        duration_class="minutes",
        owner_hypothesis="storage_data_starvation",
        trigger_statuses=(HypothesisStatus.PROBABLE,),
        discriminates_between=("storage_data_starvation",),
        information_value=5,
        expected_outcomes=(
            "corrected data path restores throughput -> confirm storage/data cause",
            "no recovery -> keep alternate causes active",
        ),
        completion_keys=("storage_or_loader_fix_restored_performance", "data_path_ab_did_not_restore_performance"),
    ),
    DiagnosticTestSpec(
        id="compare_rank_work_invariants",
        title="Compare per-rank work and collective invariants",
        purpose="Verify that all ranks execute the same number and sequence of collective steps before blaming NCCL transport.",
        command="<compare per-rank steps/batches/tokens/blocks and flight-recorder collective state>",
        cost="low",
        invasiveness="read_only",
        duration_class="seconds",
        owner_hypothesis="collective_work_invariant_failure",
        trigger_statuses=(HypothesisStatus.SUPPORTED,),
        discriminates_between=("collective_work_invariant_failure", "fabric_link_degradation"),
        information_value=5,
        expected_outcomes=(
            "per-rank work diverges -> strengthen application/invariant cause",
            "rank work is identical -> weaken invariant cause",
        ),
        require_missing_evidence=True,
        completion_keys=("per_rank_work_counts_differ", "per_rank_work_counts_equal"),
    ),
    DiagnosticTestSpec(
        id="validate_invariant_fix",
        title="Repeat the run with equalized per-rank work invariants",
        purpose="Confirm that collective synchronization recovers when ranks execute equal work/step counts.",
        command="<rerun after enforcing equal per-rank work counts>",
        cost="medium",
        invasiveness="low_impact",
        duration_class="minutes",
        owner_hypothesis="collective_work_invariant_failure",
        trigger_statuses=(HypothesisStatus.PROBABLE,),
        discriminates_between=("collective_work_invariant_failure",),
        information_value=5,
        expected_outcomes=(
            "full run completes cleanly -> confirm invariant cause",
            "hang persists -> keep communication/runtime alternatives active",
        ),
        completion_keys=("invariant_fix_restored_training", "invariant_fix_did_not_restore_training"),
    ),
    DiagnosticTestSpec(
        id="controlled_rollback_ab",
        title="Run a controlled rollback or A/B against the last known-good configuration",
        purpose="Confirm whether the observed software/configuration change is causal instead of merely correlated.",
        command="<rollback or controlled A/B using the previous configuration>",
        cost="medium",
        invasiveness="low_impact",
        duration_class="minutes",
        owner_hypothesis="software_config_regression",
        trigger_statuses=(HypothesisStatus.PROBABLE,),
        discriminates_between=("software_config_regression",),
        information_value=5,
        expected_outcomes=(
            "rollback restores throughput -> confirm software/config cause",
            "rollback does not help -> weaken software/config hypothesis",
        ),
        completion_keys=("rollback_restored_performance", "rollback_did_not_restore_performance"),
    ),
)


def _eligible(spec: DiagnosticTestSpec, hypotheses: dict[str, Hypothesis], facts: EvidenceIndex) -> bool:
    owner = hypotheses.get(spec.owner_hypothesis)
    if not owner or owner.status not in spec.trigger_statuses:
        return False
    if spec.require_missing_evidence and not owner.missing_evidence:
        return False
    if facts.any_true(f"test_completed.{spec.id}"):
        return False
    if any(facts.has(key) for key in spec.completion_keys):
        return False
    if any(facts.any_true(key) for key in spec.blocked_by_true):
        return False
    return True


def _score(spec: DiagnosticTestSpec, hypotheses: dict[str, Hypothesis]) -> tuple[int, int]:
    owner = hypotheses[spec.owner_hypothesis]
    active_discriminated = sum(
        1
        for hypothesis_id in spec.discriminates_between
        if hypothesis_id in hypotheses
        and hypotheses[hypothesis_id].status not in {HypothesisStatus.REJECTED, HypothesisStatus.CONFIRMED}
    )
    score = (
        STATUS_BONUS[owner.status]
        + spec.information_value * 2
        + active_discriminated
        + min(len(owner.supporting_evidence), 3)
        - COST_PENALTY.get(spec.cost, 3)
        - INVASIVENESS_PENALTY.get(spec.invasiveness, 3)
        - DURATION_PENALTY.get(spec.duration_class, 2)
    )
    return score, active_discriminated


def rank_candidate_specs(
    candidates: list[DiagnosticTestSpec], hypotheses: list[Hypothesis]
) -> list[tuple[DiagnosticTestSpec, int, int]]:
    """Rank already-eligible test specs deterministically."""
    by_id = {hypothesis.id: hypothesis for hypothesis in hypotheses}
    scored = [(spec, *_score(spec, by_id)) for spec in candidates]
    return sorted(scored, key=lambda item: (-item[1], item[0].id))


def plan_next_test(hypotheses: list[Hypothesis], facts: EvidenceIndex) -> DiagnosticTest | None:
    by_id = {hypothesis.id: hypothesis for hypothesis in hypotheses}
    eligible = [spec for spec in TEST_REGISTRY if _eligible(spec, by_id, facts)]
    if not eligible:
        return None

    ranked = rank_candidate_specs(eligible, hypotheses)
    selected_spec, score, active_discriminated = ranked[0]
    alternatives = tuple(f"{spec.id} (score {candidate_score})" for spec, candidate_score, _ in ranked[1:4])
    owner = by_id[selected_spec.owner_hypothesis]

    reason = (
        f"Selected from {len(ranked)} eligible test(s): owner hypothesis "
        f"{selected_spec.owner_hypothesis} is {owner.status.value}; "
        f"the test separates {active_discriminated} active hypothesis/hypotheses, "
        f"information value={selected_spec.information_value}, cost={selected_spec.cost}, "
        f"invasiveness={selected_spec.invasiveness}, duration={selected_spec.duration_class}."
    )
    if alternatives:
        reason += f" Next alternatives: {', '.join(alternatives)}."

    return DiagnosticTest(
        id=selected_spec.id,
        title=selected_spec.title,
        purpose=selected_spec.purpose,
        command=selected_spec.command,
        cost=selected_spec.cost,
        invasiveness=selected_spec.invasiveness,
        discriminates_between=selected_spec.discriminates_between,
        duration_class=selected_spec.duration_class,
        expected_outcomes=selected_spec.expected_outcomes,
        selection_score=score,
        selection_reason=reason,
        alternatives=alternatives,
    )
