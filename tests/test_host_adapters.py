from dataclasses import dataclass

from gputriage.host_adapters import (
    derive_irq_affinity_facts,
    parse_cpu_list,
    parse_irq_affinity_csv,
    parse_proc_interrupts,
    parse_process_affinity_csv,
)


def vals(observations, key):
    return [ob.value for ob in observations if ob.key == key]


def test_parse_cpu_list_ranges():
    assert parse_cpu_list("0-2,5,7-8") == (0, 1, 2, 5, 7, 8)


def test_parse_proc_interrupts_keeps_per_cpu_activity():
    text = """           CPU0       CPU1       CPU2       CPU3
 120:         10          0         30          0  PCI-MSI  mlx5_comp0
"""
    observations = parse_proc_interrupts(text)
    assert vals(observations, "irq_total_count") == [40]
    assert vals(observations, "irq_active_cpus") == [(0, 2)]
    assert vals(observations, "irq_label") == ["PCI-MSI mlx5_comp0"]


def test_parse_irq_affinity_prefers_explicit_effective_cpu_list():
    text = "irq,cpu_list,effective_cpu_list,ibdev,netdev,pci_bdf\n120,0-3,2,mlx5_4,ens6f0,0000:d1:00.0\n"
    observations = parse_irq_affinity_csv(text)
    affinity = next(ob for ob in observations if ob.key == "irq_affinity")
    assert affinity.value["allowed_cpus"] == (0, 1, 2, 3)
    assert affinity.value["effective_cpus"] == (2,)
    assert affinity.value["ibdev"] == "mlx5_4"


def test_parse_process_affinity_is_rank_scoped():
    text = "rank,pid,role,cpu_list,node\n16,4242,nccl_comm,2-3,gpu001\n"
    observations = parse_process_affinity_csv(text)
    process = next(ob for ob in observations if ob.key == "process_affinity")
    assert process.entity == "rank:16"
    assert process.value["cpus"] == (2, 3)


@dataclass
class E:
    kind: str
    attributes: dict


class G:
    def __init__(self):
        self.entities = {
            "hca:gpu001:mlx5_4": E("nic_hca", {"ibdev": "mlx5_4", "netdev": "ens6f0", "pci_bdf": "0000:d1:00.0"}),
            "hca:gpu001:mlx5_5": E("nic_hca", {"ibdev": "mlx5_5", "netdev": "ens7f0", "pci_bdf": "0000:e1:00.0"}),
        }

    def reachable(self, source, kind, max_depth=4):
        if source == "rank:16" and kind == "nic_hca":
            return {"hca:gpu001:mlx5_4"}
        return set()


def _activity():
    return parse_proc_interrupts("""           CPU0 CPU1 CPU2 CPU3
120: 0 0 25 0 PCI-MSI mlx5_comp0
121: 0 0 0 10 PCI-MSI mlx5_comp1
""")


def test_derive_overlap_requires_active_irq_affected_hca_and_process_affinity():
    observations = _activity()
    observations += parse_irq_affinity_csv(
        "irq,cpu_list,effective_cpu_list,ibdev,netdev,pci_bdf\n"
        "120,0-3,2,mlx5_4,ens6f0,0000:d1:00.0\n"
        "121,0-3,3,mlx5_5,ens7f0,0000:e1:00.0\n"
    )
    observations += parse_process_affinity_csv("rank,pid,role,cpu_list,node\n16,4242,nccl_comm,2-4,gpu001\n")
    derived, warnings = derive_irq_affinity_facts(observations, G(), ["rank:16"])
    assert not warnings
    assert vals(derived, "irq_shares_nccl_cpu") == [True]
    assert vals(derived, "irq_overlap_cpus") == [(2,)]


def test_clean_affinity_is_emitted_when_sets_do_not_overlap():
    observations = _activity()
    observations += parse_irq_affinity_csv("irq,cpu_list,effective_cpu_list,ibdev,netdev,pci_bdf\n120,0-3,2,mlx5_4,ens6f0,0000:d1:00.0\n")
    observations += parse_process_affinity_csv("rank,pid,role,cpu_list,node\n16,4242,nccl_comm,6-7,gpu001\n")
    derived, warnings = derive_irq_affinity_facts(observations, G(), ["rank:16"])
    assert not warnings
    assert vals(derived, "irq_affinity_clean") == [True]
    assert vals(derived, "irq_shares_nccl_cpu") == []


def test_missing_process_affinity_does_not_guess_overlap():
    observations = _activity()
    observations += parse_irq_affinity_csv("irq,cpu_list,effective_cpu_list,ibdev,netdev,pci_bdf\n120,0-3,2,mlx5_4,ens6f0,0000:d1:00.0\n")
    derived, warnings = derive_irq_affinity_facts(observations, G(), ["rank:16"])
    assert derived == []
    assert any("process" in warning.lower() for warning in warnings)


def test_unrelated_hca_irq_does_not_count_as_overlap():
    observations = _activity()
    observations += parse_irq_affinity_csv("irq,cpu_list,effective_cpu_list,ibdev,netdev,pci_bdf\n121,0-3,3,mlx5_5,ens7f0,0000:e1:00.0\n")
    observations += parse_process_affinity_csv("rank,pid,role,cpu_list,node\n16,4242,nccl_comm,3,gpu001\n")
    derived, warnings = derive_irq_affinity_facts(observations, G(), ["rank:16"])
    assert derived == []
    assert warnings


def test_overlap_fact_promotes_host_irq_hypothesis_and_requests_profile():
    from gputriage.engine import investigate
    from gputriage.models import HypothesisStatus, Observation

    result = investigate(
        "communication wait with healthy GPU kernels",
        [
            Observation("communication_waits", True, "test"),
            Observation("gpu_kernel_durations_match_peers", True, "test"),
            Observation("irq_shares_nccl_cpu", True, "derived:irq-affinity"),
        ],
    )
    host = next(h for h in result.hypotheses if h.id == "host_cpu_irq_interference")
    assert host.status == HypothesisStatus.PROBABLE
    assert result.next_best_test is not None
    assert result.next_best_test.id == "short_cpu_profile"
