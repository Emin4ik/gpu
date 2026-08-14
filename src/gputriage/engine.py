from __future__ import annotations

from collections.abc import Iterable

from .models import DiagnosticTest, Hypothesis, HypothesisStatus, Investigation, Observation


def _index(observations: Iterable[Observation]) -> dict[str, Observation]:
    return {ob.key: ob for ob in observations}


def _truth(facts: dict[str, Observation], key: str) -> bool:
    ob = facts.get(key)
    return bool(ob and ob.value is True)


def _value(facts: dict[str, Observation], key: str):
    ob = facts.get(key)
    return None if ob is None else ob.value


def _pcie_hypothesis(facts: dict[str, Observation]) -> Hypothesis:
    h = Hypothesis("pcie_path_degradation", "PCIe path degradation")

    if _truth(facts, "communication_regression_localized"):
        h.supporting_evidence.append("communication regression is localized")
    if _truth(facts, "affected_ranks_share_pcie_path"):
        h.supporting_evidence.append("affected ranks share a PCIe path")

    width = _value(facts, "pcie_width")
    expected = _value(facts, "pcie_expected_width")
    if isinstance(width, int) and isinstance(expected, int):
        if width < expected:
            h.supporting_evidence.append(f"PCIe width is x{width}, expected x{expected}")
            h.status = HypothesisStatus.PROBABLE
        else:
            h.contradicting_evidence.append("PCIe width matches expected value")

    if _truth(facts, "targeted_nccl_validation_failed") and h.status == HypothesisStatus.PROBABLE:
        h.status = HypothesisStatus.CONFIRMED
    elif len(h.supporting_evidence) >= 2 and h.status == HypothesisStatus.POSSIBLE:
        h.status = HypothesisStatus.SUPPORTED

    if width is None or expected is None:
        h.missing_evidence.append("PCIe link width/speed for affected GPU/HCA path")

    return h


def _fabric_hypothesis(facts: dict[str, Observation]) -> Hypothesis:
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

    if not (_truth(facts, "fabric_error_counters_rising") or _truth(facts, "fabric_counters_clean")):
        h.missing_evidence.append("IB/RoCE/HCA error and retry counters")

    return h


def _gpu_hardware_hypothesis(facts: dict[str, Observation]) -> Hypothesis:
    h = Hypothesis("gpu_hardware_degradation", "GPU hardware degradation")
    if _truth(facts, "gpu_xid_or_ecc_error"):
        h.supporting_evidence.append("GPU XID/ECC evidence is present")
        h.status = HypothesisStatus.SUPPORTED
    if _truth(facts, "gpu_health_clean"):
        h.contradicting_evidence.append("GPU health checks are clean")
        h.status = HypothesisStatus.REJECTED
    return h


def _software_hypothesis(facts: dict[str, Observation]) -> Hypothesis:
    h = Hypothesis("software_config_regression", "Software / configuration regression")
    if _truth(facts, "regression_after_change"):
        h.supporting_evidence.append("regression started after a software/configuration change")
    if _truth(facts, "all_ranks_slow_uniformly"):
        h.supporting_evidence.append("slowdown is uniform across ranks")
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


def _choose_next_test(hypotheses: list[Hypothesis], facts: dict[str, Observation]) -> DiagnosticTest | None:
    pcie = next(h for h in hypotheses if h.id == "pcie_path_degradation")
    fabric = next(h for h in hypotheses if h.id == "fabric_link_degradation")

    active = {HypothesisStatus.POSSIBLE, HypothesisStatus.SUPPORTED, HypothesisStatus.PROBABLE}

    if pcie.status in active and pcie.missing_evidence:
        return DiagnosticTest(
            id="collect_pcie_link_state",
            title="Collect PCIe link state on the affected path",
            purpose="Separate PCIe degradation from fabric/NCCL hypotheses using a cheap read-only check.",
            command="lspci -vv -s <GPU_OR_HCA_BDF>",
            cost="low",
            invasiveness="read_only",
            discriminates_between=("pcie_path_degradation", "fabric_link_degradation"),
        )

    if fabric.status in active and fabric.missing_evidence:
        return DiagnosticTest(
            id="collect_fabric_counters",
            title="Collect HCA / fabric error counters",
            purpose="Check whether the localized communication regression follows a physical or congested fabric path.",
            command="ibqueryerrors -rR || ethtool -S <NETDEV>",
            cost="low",
            invasiveness="read_only",
            discriminates_between=("fabric_link_degradation", "software_config_regression"),
        )

    if pcie.status == HypothesisStatus.PROBABLE and not _truth(facts, "targeted_nccl_validation_failed"):
        return DiagnosticTest(
            id="targeted_nccl_validation",
            title="Run a targeted NCCL validation on affected nodes",
            purpose="Confirm that the observed PCIe-path abnormality produces the workload communication regression.",
            command="<targeted nccl-tests command>",
            cost="medium",
            invasiveness="low_impact",
            discriminates_between=("pcie_path_degradation", "software_config_regression"),
        )

    return None


def investigate(symptom: str, observations: Iterable[Observation]) -> Investigation:
    facts = _index(observations)
    hypotheses = [
        _pcie_hypothesis(facts),
        _fabric_hypothesis(facts),
        _gpu_hardware_hypothesis(facts),
        _software_hypothesis(facts),
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

    return Investigation(
        symptom=symptom,
        hypotheses=hypotheses,
        next_best_test=next_test,
        verdict=verdict,
        notes=notes,
    )
