import json

from gputriage import cli
from gputriage.sanitize import build_sanitized_bundle


def make_identity_bundle(root):
    root.mkdir(parents=True, exist_ok=True)
    payload = {
        "symptom": "gpu-node-17 GPU-12345678-aaaa-bbbb-cccc-123456789abc PCI 0000:c1:00.0 slowdown",
        "affected_entities": ["rank:37"],
        "identity_graph": {
            "entities": [
                {"id": "rank:37", "kind": "rank", "attributes": {"global_rank": 37}},
                {"id": "node:gpu-node-17", "kind": "node", "attributes": {"hostname": "gpu-node-17"}},
                {
                    "id": "gpu:GPU-12345678-aaaa-bbbb-cccc-123456789abc",
                    "kind": "gpu",
                    "attributes": {
                        "uuid": "GPU-12345678-aaaa-bbbb-cccc-123456789abc",
                        "node": "gpu-node-17",
                        "pci_bdf": "0000:c1:00.0"
                    },
                },
                {"id": "pcie:0000:c1:00.0", "kind": "pcie_device", "attributes": {"bdf": "0000:c1:00.0", "node": "gpu-node-17"}},
                {
                    "id": "hca:gpu-node-17:mlx5_3",
                    "kind": "nic_hca",
                    "attributes": {"ibdev": "mlx5_3", "netdev": "enp9s0", "node": "gpu-node-17", "guid": "abcd:1234"},
                },
            ],
            "relations": [
                {"source": "rank:37", "type": "runs_on", "target": "node:gpu-node-17"},
                {"source": "rank:37", "type": "uses_gpu", "target": "gpu:GPU-12345678-aaaa-bbbb-cccc-123456789abc"},
                {"source": "gpu:GPU-12345678-aaaa-bbbb-cccc-123456789abc", "type": "attached_via_pcie", "target": "pcie:0000:c1:00.0"},
                {"source": "rank:37", "type": "uses_hca", "target": "hca:gpu-node-17:mlx5_3"},
            ],
        },
        "observations": [
            {"key": "communication_regression_localized", "value": True, "source": "operator@gpu-node-17", "raw_ref": "gpu-node-17:incident"},
            {"key": "pcie_width", "value": 8, "source": "lspci-0000:c1:00.0", "entity": "pcie:0000:c1:00.0", "raw_ref": "0000:c1:00.0:LnkSta"},
            {"key": "pcie_expected_width", "value": 16, "source": "lspci-0000:c1:00.0", "entity": "pcie:0000:c1:00.0", "raw_ref": "0000:c1:00.0:LnkCap"},
        ],
    }
    (root / "incident.json").write_text(json.dumps(payload), encoding="utf-8")


def test_sanitized_bundle_removes_known_identity_and_raw_refs(tmp_path):
    root = tmp_path / "bundle"
    make_identity_bundle(root)

    payload = build_sanitized_bundle(root)
    serialized = json.dumps(payload, sort_keys=True)

    assert payload["schema_version"] == "gputriage.sanitized-bundle.v1"
    assert payload["symptom"] == "sanitized incident"
    assert payload["sanitization"]["raw_artifacts_included"] is False
    assert payload["sanitization"]["raw_ref_removed"] is True
    for secret in [
        "gpu-node-17",
        "GPU-12345678-aaaa-bbbb-cccc-123456789abc",
        "0000:c1:00.0",
        "mlx5_3",
        "enp9s0",
        "abcd:1234",
    ]:
        assert secret not in serialized
    assert all(observation["raw_ref"] is None for observation in payload["observations"])
    assert payload["affected_entities"] == ["rank:rank-001"]


def test_exported_normalized_bundle_can_be_reinvestigated(tmp_path, capsys):
    root = tmp_path / "bundle"
    output = tmp_path / "sanitized.json"
    make_identity_bundle(root)

    export_code = cli.main(["export-sanitized", str(root), str(output), "--format", "json"])
    export_summary = json.loads(capsys.readouterr().out)
    assert export_code == cli.EXIT_CONFIRMED
    assert export_summary["raw_artifacts_included"] is False

    investigate_code = cli.main(["investigate", str(output), "--format", "json"])
    report = json.loads(capsys.readouterr().out)
    assert investigate_code == cli.EXIT_NEEDS_EVIDENCE
    assert report["next_best_test"]["id"] == "targeted_nccl_validation"


def test_export_does_not_overwrite_without_force(tmp_path, capsys):
    root = tmp_path / "bundle"
    output = tmp_path / "sanitized.json"
    make_identity_bundle(root)
    output.write_text("existing", encoding="utf-8")

    code = cli.main(["export-sanitized", str(root), str(output), "--format", "json"])
    payload = json.loads(capsys.readouterr().out)

    assert code == cli.EXIT_INVALID_BUNDLE
    assert "--force" in payload["error"]
    assert output.read_text(encoding="utf-8") == "existing"
