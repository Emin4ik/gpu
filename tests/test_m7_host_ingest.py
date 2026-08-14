from pathlib import Path

from gputriage.engine import investigate
from gputriage.ingest import ingest_directory
from gputriage.models import HypothesisStatus


def test_irq_affinity_example_promotes_host_hypothesis(tmp_path: Path):
    (tmp_path / "incident.json").write_text(
        '{"symptom":"communication wait","observations":['
        '{"key":"communication_waits","value":true,"source":"trace"},'
        '{"key":"gpu_kernel_durations_match_peers","value":true,"source":"trace"}'
        ']}',
        encoding="utf-8",
    )
    (tmp_path / "rank-map.csv").write_text(
        "rank,node,local_rank,cuda_visible_devices,affected\n0,gpu001,0,0,true\n",
        encoding="utf-8",
    )
    (tmp_path / "nvidia-gpus.csv").write_text(
        "node,index,uuid,pci.bus_id\ngpu001,0,GPU-demo,00000000:c1:00.0\n",
        encoding="utf-8",
    )
    (tmp_path / "ib-devices.csv").write_text(
        "node,ibdev,netdev,pci_bdf,guid,port\n"
        "gpu001,mlx5_4,ens6f0,0000:d1:00.0,0x248a0001,1\n",
        encoding="utf-8",
    )
    (tmp_path / "nvidia-topo.txt").write_text(
        "        GPU0 NIC0 CPU Affinity\nGPU0    X    PIX  0-31\n"
        "NIC0: ibdev=mlx5_4 netdev=ens6f0 PCI=0000:d1:00.0\n",
        encoding="utf-8",
    )
    (tmp_path / "proc-interrupts.txt").write_text(
        "           CPU0 CPU1 CPU2 CPU3\n120: 0 0 1523 0 PCI-MSI mlx5_comp0\n",
        encoding="utf-8",
    )
    (tmp_path / "irq-affinity.csv").write_text(
        "irq,cpu_list,effective_cpu_list,ibdev,netdev,pci_bdf\n"
        "120,0-3,2,mlx5_4,ens6f0,0000:d1:00.0\n",
        encoding="utf-8",
    )
    (tmp_path / "process-affinity.csv").write_text(
        "rank,pid,role,cpu_list,node\n0,4242,nccl_comm,2-3,gpu001\n",
        encoding="utf-8",
    )

    ingested = ingest_directory(tmp_path)
    overlap = next(ob for ob in ingested.observations if ob.key == "irq_shares_nccl_cpu")
    assert overlap.entity == "hca:gpu001:mlx5_4"
    assert overlap.value is True

    result = investigate(ingested.symptom, ingested.observations)
    host = next(h for h in result.hypotheses if h.id == "host_cpu_irq_interference")
    assert host.status == HypothesisStatus.PROBABLE
    assert result.next_best_test is not None
    assert result.next_best_test.id == "short_cpu_profile"
