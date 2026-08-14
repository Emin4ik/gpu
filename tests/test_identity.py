from gputriage.identity import IdentityGraph, derive_identity_observations, observation_is_on_affected_path
from gputriage.models import Observation


def graph_payload():
    return {
        "entities": [
            {"id": "rank:16", "kind": "rank"},
            {"id": "rank:17", "kind": "rank"},
            {"id": "node:gpu201", "kind": "node"},
            {"id": "gpu:GPU-a", "kind": "gpu"},
            {"id": "gpu:GPU-b", "kind": "gpu"},
            {"id": "pcie:0000:c1:00.0", "kind": "pcie_device"},
            {"id": "pcie:0000:d1:00.0", "kind": "pcie_device"},
            {"id": "hca:mlx5_4", "kind": "nic_hca"},
        ],
        "relations": [
            {"source": "rank:16", "type": "runs_on", "target": "node:gpu201"},
            {"source": "rank:17", "type": "runs_on", "target": "node:gpu201"},
            {"source": "rank:16", "type": "uses_gpu", "target": "gpu:GPU-a"},
            {"source": "rank:17", "type": "uses_gpu", "target": "gpu:GPU-a"},
            {"source": "gpu:GPU-a", "type": "attached_via_pcie", "target": "pcie:0000:c1:00.0"},
            {"source": "gpu:GPU-b", "type": "attached_via_pcie", "target": "pcie:0000:d1:00.0"},
            {"source": "rank:16", "type": "uses_nic_hca", "target": "hca:mlx5_4"},
            {"source": "rank:17", "type": "uses_nic_hca", "target": "hca:mlx5_4"},
        ],
    }


def test_identity_graph_derives_shared_pcie_hca_and_node():
    graph = IdentityGraph.from_payload(graph_payload())
    observations = derive_identity_observations(graph, ["rank:16", "rank:17"])
    by_key = {ob.key: ob for ob in observations}

    assert by_key["affected_ranks_share_pcie_path"].entity == "pcie:0000:c1:00.0"
    assert by_key["affected_ranks_share_hca"].entity == "hca:mlx5_4"
    assert by_key["affected_ranks_share_node"].entity == "node:gpu201"


def test_unrelated_pcie_artifact_is_not_on_affected_path():
    graph = IdentityGraph.from_payload(graph_payload())
    unrelated = Observation("pcie_width", 8, "lspci.txt", entity="pcie:0000:d1:00.0")
    relevant = Observation("pcie_width", 8, "lspci.txt", entity="pcie:0000:c1:00.0")

    assert not observation_is_on_affected_path(unrelated, graph, ["rank:16", "rank:17"])
    assert observation_is_on_affected_path(relevant, graph, ["rank:16", "rank:17"])


def test_broken_relation_is_reported():
    payload = graph_payload()
    payload["relations"].append({"source": "rank:16", "type": "uses_nic_hca", "target": "hca:missing"})
    graph = IdentityGraph.from_payload(payload)
    assert graph.validation_errors() == ["relation target is missing: hca:missing"]
