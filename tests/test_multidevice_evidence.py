import json
from pathlib import Path

from gputriage import investigate
from gputriage.ingest import ingest_directory
from gputriage.models import HypothesisStatus, Observation
from gputriage.parsers import parse_lspci, parse_nvidia_smi_q


def by_id(result, hypothesis_id):
    return next(h for h in result.hypotheses if h.id == hypothesis_id)


def test_full_lspci_dump_preserves_device_entities():
    observations = parse_lspci(
        "0000:c1:00.0 VGA compatible controller: NVIDIA Device\n"
        "    LnkCap: Port #0, Speed 32GT/s, Width x16\n"
        "    LnkSta: Speed 32GT/s, Width x16\n"
        "0000:d1:00.0 Network controller: Mellanox Device\n"
        "    LnkCap: Port #0, Speed 32GT/s, Width x16\n"
        "    LnkSta: Speed 32GT/s, Width x8\n",
        source="lspci-full.txt",
    )
    widths = {(ob.entity, ob.value) for ob in observations if ob.key == "pcie_width"}
    assert widths == {("pcie:0000:c1:00.0", 16), ("pcie:0000:d1:00.0", 8)}
    assert all(ob.raw_ref for ob in observations)


def test_multi_gpu_nvidia_smi_sections_preserve_gpu_entities():
    observations = parse_nvidia_smi_q(
        "GPU 00000000:C1:00.0\n"
        "    UUID : GPU-a\n"
        "    GPU Current Temp : 60 C\n"
        "    Clocks\n"
        "        SM : 1800 MHz\n"
        "GPU 00000000:D1:00.0\n"
        "    UUID : GPU-b\n"
        "    GPU Current Temp : 84 C\n"
        "    Clocks\n"
        "        SM : 1200 MHz\n"
        "    SW Thermal Slowdown : Active\n",
        source="nvidia-smi-q.txt",
    )
    clocks = {(ob.entity, ob.value) for ob in observations if ob.key == "gpu_sm_clock_mhz"}
    assert clocks == {("gpu:GPU-a", 1800), ("gpu:GPU-b", 1200)}
    assert any(ob.key == "thermal_throttle_reason" and ob.entity == "gpu:GPU-b" for ob in observations)


def test_engine_never_pairs_pcie_width_with_expected_width_from_another_device():
    observations = [
        Observation("communication_regression_localized", True, "test"),
        Observation("affected_ranks_share_pcie_path", True, "test"),
        Observation("pcie_width", 8, "lspci", entity="pcie:a"),
        Observation("pcie_expected_width", 16, "lspci", entity="pcie:b"),
    ]
    result = investigate("localized slowdown", observations)
    hypothesis = by_id(result, "pcie_path_degradation")
    assert hypothesis.status == HypothesisStatus.SUPPORTED
    assert hypothesis.missing_evidence
    assert result.next_best_test is not None
    assert result.next_best_test.id == "collect_pcie_link_state"


def test_engine_matches_pcie_values_on_same_entity():
    observations = [
        Observation("communication_regression_localized", True, "test"),
        Observation("affected_ranks_share_pcie_path", True, "test"),
        Observation("pcie_width", 8, "lspci", entity="pcie:a"),
        Observation("pcie_expected_width", 16, "lspci", entity="pcie:a"),
        Observation("pcie_width", 16, "lspci", entity="pcie:b"),
        Observation("pcie_expected_width", 16, "lspci", entity="pcie:b"),
    ]
    result = investigate("localized slowdown", observations)
    hypothesis = by_id(result, "pcie_path_degradation")
    assert hypothesis.status == HypothesisStatus.PROBABLE
    assert any("pcie:a" in item for item in hypothesis.supporting_evidence)


def test_ingest_keeps_same_key_for_multiple_entities_without_identity_scope(tmp_path: Path):
    (tmp_path / "lspci.txt").write_text(
        "0000:c1:00.0 VGA compatible controller: NVIDIA Device\n"
        "    LnkCap: Speed 32GT/s, Width x16\n"
        "    LnkSta: Speed 32GT/s, Width x16\n"
        "0000:d1:00.0 VGA compatible controller: NVIDIA Device\n"
        "    LnkCap: Speed 32GT/s, Width x16\n"
        "    LnkSta: Speed 32GT/s, Width x8\n",
        encoding="utf-8",
    )
    result = ingest_directory(tmp_path)
    widths = [ob for ob in result.observations if ob.key == "pcie_width"]
    assert len(widths) == 2
    assert {ob.entity for ob in widths} == {"pcie:0000:c1:00.0", "pcie:0000:d1:00.0"}


def test_identity_scoping_filters_unrelated_device_from_full_dump(tmp_path: Path):
    payload = {
        "symptom": "localized NCCL slowdown",
        "affected_entities": ["rank:16", "rank:17"],
        "observations": [{"key": "communication_regression_localized", "value": True, "source": "context"}],
        "identity_graph": {
            "entities": [
                {"id": "rank:16", "kind": "rank"},
                {"id": "rank:17", "kind": "rank"},
                {"id": "gpu:GPU-a", "kind": "gpu"},
                {"id": "pcie:0000:c1:00.0", "kind": "pcie_device"},
                {"id": "gpu:GPU-b", "kind": "gpu"},
                {"id": "pcie:0000:d1:00.0", "kind": "pcie_device"},
            ],
            "relations": [
                {"source": "rank:16", "type": "uses_gpu", "target": "gpu:GPU-a"},
                {"source": "rank:17", "type": "uses_gpu", "target": "gpu:GPU-a"},
                {"source": "gpu:GPU-a", "type": "attached_via_pcie", "target": "pcie:0000:c1:00.0"},
                {"source": "gpu:GPU-b", "type": "attached_via_pcie", "target": "pcie:0000:d1:00.0"},
            ],
        },
    }
    (tmp_path / "incident.json").write_text(json.dumps(payload), encoding="utf-8")
    (tmp_path / "lspci.txt").write_text(
        "0000:c1:00.0 VGA compatible controller: NVIDIA Device\n"
        "    LnkCap: Speed 32GT/s, Width x16\n"
        "    LnkSta: Speed 32GT/s, Width x16\n"
        "0000:d1:00.0 VGA compatible controller: NVIDIA Device\n"
        "    LnkCap: Speed 32GT/s, Width x16\n"
        "    LnkSta: Speed 32GT/s, Width x8\n",
        encoding="utf-8",
    )
    incident = ingest_directory(tmp_path)
    widths = [ob for ob in incident.observations if ob.key == "pcie_width"]
    assert [(ob.entity, ob.value) for ob in widths] == [("pcie:0000:c1:00.0", 16)]
    result = investigate(incident.symptom, incident.observations)
    hypothesis = by_id(result, "pcie_path_degradation")
    assert hypothesis.status in {HypothesisStatus.POSSIBLE, HypothesisStatus.SUPPORTED}
    assert not any("x8" in item for item in hypothesis.supporting_evidence)
