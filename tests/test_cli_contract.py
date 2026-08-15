import json

from gputriage import cli


def write_incident(root, symptom, observations):
    root.mkdir(parents=True, exist_ok=True)
    (root / "incident.json").write_text(
        json.dumps({"symptom": symptom, "observations": observations}),
        encoding="utf-8",
    )


def test_json_report_needs_evidence_has_stable_schema_and_provenance(tmp_path, capsys):
    root = tmp_path / "incident"
    write_incident(
        root,
        "localized NCCL slowdown",
        [
            {"key": "communication_regression_localized", "value": True, "source": "operator", "raw_ref": "incident.json:1"},
            {"key": "affected_ranks_share_pcie_path", "value": True, "source": "identity"},
            {"key": "pcie_width", "value": 8, "source": "lspci", "raw_ref": "lspci.txt:4"},
            {"key": "pcie_expected_width", "value": 16, "source": "lspci", "raw_ref": "lspci.txt:3"},
        ],
    )

    code = cli.main(["investigate", str(root), "--format", "json"])
    payload = json.loads(capsys.readouterr().out)

    assert code == cli.EXIT_NEEDS_EVIDENCE
    assert payload["schema_version"] == "gputriage.report.v1"
    assert payload["result_state"] == "needs_evidence"
    assert payload["next_best_test"]["id"] == "targeted_nccl_validation"
    assert any(item["raw_ref"] == "lspci.txt:4" for item in payload["observations"])


def test_confirmed_report_returns_zero(tmp_path, capsys):
    root = tmp_path / "confirmed"
    write_incident(
        root,
        "localized NCCL slowdown",
        [
            {"key": "communication_regression_localized", "value": True},
            {"key": "affected_ranks_share_pcie_path", "value": True},
            {"key": "pcie_width", "value": 8},
            {"key": "pcie_expected_width", "value": 16},
            {"key": "targeted_nccl_validation_failed", "value": True},
        ],
    )

    code = cli.main(["investigate", str(root), "--format", "json"])
    payload = json.loads(capsys.readouterr().out)

    assert code == cli.EXIT_CONFIRMED
    assert payload["result_state"] == "confirmed"
    assert payload["verdict"] == "PCIe path degradation"


def test_unsupported_incident_abstains_with_distinct_exit_code(tmp_path, capsys):
    root = tmp_path / "unsupported"
    write_incident(
        root,
        "runtime bootstrap failure outside current playbooks",
        [{"key": "gpu_health_clean", "value": True}],
    )

    code = cli.main(["investigate", str(root), "--format", "json"])
    payload = json.loads(capsys.readouterr().out)

    assert code == cli.EXIT_ABSTAIN
    assert payload["result_state"] == "abstain"
    assert payload["verdict"] is None
    assert payload["next_best_test"] is None


def test_validate_bundle_rejects_empty_directory(tmp_path, capsys):
    root = tmp_path / "empty"
    root.mkdir()

    code = cli.main(["validate-bundle", str(root), "--format", "json"])
    payload = json.loads(capsys.readouterr().out)

    assert code == cli.EXIT_INVALID_BUNDLE
    assert payload["valid"] is False
    assert any("no recognized" in error for error in payload["errors"])


def test_validate_bundle_reports_malformed_incident_json(tmp_path, capsys):
    root = tmp_path / "malformed"
    root.mkdir()
    (root / "incident.json").write_text("{not-json", encoding="utf-8")

    code = cli.main(["validate-bundle", str(root), "--format", "json"])
    payload = json.loads(capsys.readouterr().out)

    assert code == cli.EXIT_INVALID_BUNDLE
    assert payload["valid"] is False
    assert any("invalid JSON" in error for error in payload["errors"])


def test_validate_bundle_accepts_metadata_only_bundle(tmp_path, capsys):
    root = tmp_path / "valid"
    write_incident(root, "unknown", [{"key": "gpu_health_clean", "value": True}])

    code = cli.main(["validate-bundle", str(root), "--format", "json"])
    payload = json.loads(capsys.readouterr().out)

    assert code == cli.EXIT_CONFIRMED
    assert payload["valid"] is True
    assert "incident.json" in payload["parsed_files"]


def test_legacy_positional_json_input_remains_supported(tmp_path, capsys):
    incident = tmp_path / "incident.json"
    incident.write_text(
        json.dumps({
            "symptom": "unknown",
            "observations": [{"key": "gpu_health_clean", "value": True}],
        }),
        encoding="utf-8",
    )

    code = cli.main([str(incident), "--format", "json"])
    payload = json.loads(capsys.readouterr().out)

    assert code == cli.EXIT_ABSTAIN
    assert payload["schema_version"] == "gputriage.report.v1"
