from pathlib import Path

from gputriage.ingest import ingest_directory


def test_auto_identity_example_requires_no_manual_graph_or_artifact_entity():
    root = Path(__file__).parents[1] / "examples" / "auto_identity_case"
    result = ingest_directory(root)
    by_key = {ob.key: ob for ob in result.observations}

    assert result.affected_entities == ["rank:16", "rank:17"]
    assert result.identity_graph.common_targets(result.affected_entities, "node") == {"node:gpu001"}
    assert result.identity_graph.common_targets(result.affected_entities, "gpu") == {"gpu:GPU-demo"}
    assert result.identity_graph.common_targets(result.affected_entities, "nic_hca") == {"hca:gpu001:mlx5_4"}
    assert by_key["affected_ranks_share_pcie_path"].entity == "pcie:0000:c1:00.0"
    assert by_key["pcie_width"].value == 8
    assert by_key["pcie_width"].entity == "pcie:0000:c1:00.0"
    assert "slurm-job.txt" in result.parsed_files
    assert "rank-map.csv" in result.parsed_files
    assert "nvidia-gpus.csv" in result.parsed_files
    assert "ib-devices.csv" in result.parsed_files
    assert "nvidia-topo.txt" in result.parsed_files
    assert not [warning for warning in result.warnings if "unresolved" in warning or "ambiguous" in warning]
