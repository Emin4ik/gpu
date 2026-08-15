from pathlib import Path

from gputriage.discovery import (
    discover_identity,
    expand_slurm_hostlist,
    parse_nvidia_gpu_csv,
    parse_rank_map_csv,
    reconcile_rank_gpu,
)


def test_expand_slurm_hostlist_supports_ranges_and_members():
    assert expand_slurm_hostlist("gpu[001-003,007],login9") == [
        "gpu001",
        "gpu002",
        "gpu003",
        "gpu007",
        "login9",
    ]


def test_rank_gpu_reconciliation_prefers_uuid_or_visible_index():
    gpu_graph, warnings = parse_nvidia_gpu_csv(
        "node,index,uuid,pci.bus_id\n"
        "gpu001,0,GPU-a,00000000:31:00.0\n"
        "gpu001,1,GPU-b,00000000:41:00.0\n"
    )
    assert not warnings
    rank_graph, rows, warnings = parse_rank_map_csv(
        "rank,node,local_rank,cuda_visible_devices\n"
        "16,gpu001,0,1\n"
    )
    assert not warnings
    gpu_graph.entities.update(rank_graph.entities)
    gpu_graph.relations.extend(rank_graph.relations)
    assert reconcile_rank_gpu(gpu_graph, rows) == []
    assert gpu_graph.reachable("rank:16", "gpu", max_depth=2) == {"gpu:GPU-b"}
    assert gpu_graph.reachable("rank:16", "pcie_device", max_depth=3) == {"pcie:0000:41:00.0"}


def test_discover_identity_builds_rank_gpu_hca_path(tmp_path: Path):
    (tmp_path / "slurm-job.txt").write_text(
        "JobId=8841273 JobState=RUNNING NodeList=gpu001\n",
        encoding="utf-8",
    )
    (tmp_path / "rank-map.csv").write_text(
        "rank,node,local_rank,cuda_visible_devices,affected\n"
        "16,gpu001,0,0,true\n"
        "17,gpu001,0,0,true\n",
        encoding="utf-8",
    )
    (tmp_path / "nvidia-gpus.csv").write_text(
        "node,index,uuid,pci.bus_id\n"
        "gpu001,0,GPU-a,00000000:c1:00.0\n",
        encoding="utf-8",
    )
    (tmp_path / "ib-devices.csv").write_text(
        "node,ibdev,netdev,pci_bdf,guid,port\n"
        "gpu001,mlx5_4,ens6f0,0000:d1:00.0,0x248a0001,1\n",
        encoding="utf-8",
    )
    (tmp_path / "nvidia-topo.txt").write_text(
        "        GPU0 NIC0 CPU Affinity\n"
        "GPU0    X    PIX  0-31\n"
        "NIC0: ibdev=mlx5_4 netdev=ens6f0 PCI=0000:d1:00.0\n",
        encoding="utf-8",
    )

    result = discover_identity(tmp_path)
    assert result.affected_entities == ["rank:16", "rank:17"]
    assert result.graph.common_targets(result.affected_entities, "node") == {"node:gpu001"}
    assert result.graph.common_targets(result.affected_entities, "gpu") == {"gpu:GPU-a"}
    assert result.graph.common_targets(result.affected_entities, "pcie_device") == {"pcie:0000:c1:00.0"}
    assert result.graph.common_targets(result.affected_entities, "nic_hca") == {"hca:gpu001:mlx5_4"}
    assert not [warning for warning in result.warnings if "unresolved" in warning or "ambiguous" in warning]


def test_rank_map_csv_handles_quoted_cuda_visible_devices():
    gpu_graph, _ = parse_nvidia_gpu_csv(
        "node,index,uuid,pci.bus_id\n"
        "gpu001,2,GPU-c,00000000:51:00.0\n"
        "gpu001,3,GPU-d,00000000:61:00.0\n"
    )
    rank_graph, rows, warnings = parse_rank_map_csv(
        'rank,node,local_rank,cuda_visible_devices\n16,gpu001,1,"2,3"\n'
    )
    assert not warnings
    gpu_graph.entities.update(rank_graph.entities)
    gpu_graph.relations.extend(rank_graph.relations)
    assert reconcile_rank_gpu(gpu_graph, rows) == []
    assert gpu_graph.reachable("rank:16", "gpu", max_depth=2) == {"gpu:GPU-d"}
