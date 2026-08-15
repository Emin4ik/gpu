import json
from pathlib import Path

from gputriage.ingest import ingest_directory


def _write_case(root: Path, pcie_entity: str):
    payload = {
        "symptom": "localized NCCL slowdown",
        "affected_entities": ["rank:16", "rank:17"],
        "artifact_entities": {"lspci.txt": pcie_entity},
        "identity_graph": {
            "entities": [
                {"id": "rank:16", "kind": "rank"},
                {"id": "rank:17", "kind": "rank"},
                {"id": "gpu:GPU-a", "kind": "gpu"},
                {"id": "pcie:0000:c1:00.0", "kind": "pcie_device"},
                {"id": "pcie:0000:d1:00.0", "kind": "pcie_device"},
                {"id": "hca:mlx5_4", "kind": "nic_hca"},
            ],
            "relations": [
                {"source": "rank:16", "type": "uses_gpu", "target": "gpu:GPU-a"},
                {"source": "rank:17", "type": "uses_gpu", "target": "gpu:GPU-a"},
                {"source": "gpu:GPU-a", "type": "attached_via_pcie", "target": "pcie:0000:c1:00.0"},
                {"source": "rank:16", "type": "uses_nic_hca", "target": "hca:mlx5_4"},
                {"source": "rank:17", "type": "uses_nic_hca", "target": "hca:mlx5_4"},
            ],
        },
    }
    (root / "incident.json").write_text(json.dumps(payload), encoding="utf-8")
    (root / "lspci.txt").write_text(
        "LnkCap: Port #0, Speed 32GT/s, Width x16\nLnkSta: Speed 32GT/s, Width x8\n",
        encoding="utf-8",
    )


def test_ingest_keeps_pcie_evidence_when_artifact_matches_affected_path(tmp_path):
    _write_case(tmp_path, "pcie:0000:c1:00.0")
    result = ingest_directory(tmp_path)
    by_key = {ob.key: ob for ob in result.observations}

    assert by_key["affected_ranks_share_pcie_path"].entity == "pcie:0000:c1:00.0"
    assert by_key["pcie_width"].value == 8
    assert by_key["pcie_width"].entity == "pcie:0000:c1:00.0"


def test_ingest_rejects_pcie_evidence_from_unrelated_device(tmp_path):
    _write_case(tmp_path, "pcie:0000:d1:00.0")
    result = ingest_directory(tmp_path)
    keys = {ob.key for ob in result.observations}

    assert "affected_ranks_share_pcie_path" in keys
    assert "pcie_width" not in keys
    assert any("Ignored unscoped or unrelated evidence pcie_width" in warning for warning in result.warnings)
