from dataclasses import dataclass

from gputriage.adapter_utils import reconcile_adapter_entities
from gputriage.adapters import parse_dcgm_json, parse_nvidia_system_log
from gputriage.identity import Entity, IdentityGraph, Relation, observation_is_on_affected_path
from gputriage.models import Observation


def values(observations, key):
    return [ob.value for ob in observations if ob.key == key]


def test_dcgm_diag_extracts_entity_scoped_pcie_failure():
    text = '''prefix heading
{
      "categories": [{"category": "Integration", "tests": [{
        "name": "pcie",
        "results": [{"entity_group": "GPU", "entity_id": 2, "status": "Fail",
                     "errors": [{"code": "DCGM_FR_PCIE_REPLAY", "msg": "PCIe replay threshold exceeded"}]}]
      }]}]
    }'''
    observations = parse_dcgm_json(text, "dcgm-diag.json")
    failed = [ob for ob in observations if ob.key == "dcgm_pcie_test_failed"]
    assert len(failed) == 1
    assert failed[0].entity == "gpu-index:2"
    assert values(observations, "dcgm_hardware_failure") == [True]


def test_dcgm_execution_failure_is_not_marked_hardware():
    text = '''{"tests":[{"name":"diagnostic","results":[{
      "entity_group":"GPU","entity_id":0,"status":"Fail",
      "errors":[{"code":"DCGM_FR_CUDA_API","msg":"cuInit failed"}]
    }]}]}'''
    observations = parse_dcgm_json(text)
    assert values(observations, "dcgm_test_execution_issue") == [True]
    assert values(observations, "dcgm_hardware_failure") == []


def test_dcgm_health_incident_inherits_parent_gpu_entity():
    text = '''Report heading
{"entities":[{"entity_group":"GPU","entity_id":1,
       "incidents":[{"system":"PCIe","health":"Failure"}]}]}'''
    observations = parse_dcgm_json(text, "dcgm-health.json")
    incident = next(ob for ob in observations if ob.key == "dcgm_pcie_health_incident")
    assert incident.entity == "gpu-index:1"
    assert values(observations, "gpu_health_clean") == []


def test_xid_uses_preceding_uuid_mapping_and_keeps_line_reference():
    text = '''Aug 14 kernel: NVRM: GPU at 0000:03:00: GPU-b850f46d-d5ea-c752-ddf3-c4453e44d3f7
Aug 14 kernel: NVRM: Xid (0000:03:00): 79, GPU has fallen off the bus.'''
    observations = parse_nvidia_system_log(text, "journal.log")
    xid = next(ob for ob in observations if ob.key == "nvidia_xid_code")
    assert xid.value == 79
    assert xid.entity == "gpu:GPU-b850f46d-d5ea-c752-ddf3-c4453e44d3f7"
    assert xid.raw_ref == "journal.log:L2"
    assert values(observations, "gpu_fallen_off_bus") == [True]


def test_xid_without_uuid_is_scoped_to_pcie_and_sxid_is_preserved():
    text = '''kernel: NVRM: Xid (PCI:0000:ca:00): 74, NVLink Error
kernel: nvidia-nvswitch0: SXid (PCI:0000:aa:00.0): 10003, Fatal, Link 3 error'''
    observations = parse_nvidia_system_log(text, "dmesg.log")
    xid = next(ob for ob in observations if ob.key == "nvidia_xid_code")
    sxid = next(ob for ob in observations if ob.key == "nvidia_sxid_code")
    assert xid.entity == "pcie:0000:ca:00.0"
    assert xid.value == 74
    assert sxid.entity == "pcie:0000:aa:00.0"
    assert sxid.value == 10003


@dataclass
class DummyEntity:
    kind: str
    attributes: dict


class DummyGraph:
    def __init__(self):
        self.entities = {
            "gpu:GPU-a": DummyEntity("gpu", {"index": "0"}),
            "gpu:GPU-b": DummyEntity("gpu", {"index": "0"}),
        }

    def reachable(self, source, target_kind, max_depth=3):
        if source == "rank:0" and target_kind == "gpu":
            return {"gpu:GPU-b"}
        return set()


def test_dcgm_gpu_index_prefers_affected_gpu_without_guessing_other_node():
    observations = parse_dcgm_json('{"tests":[{"name":"pcie","results":[{"entity_group":"GPU","entity_id":0,"status":"Fail"}]}]}')
    resolved, warnings = reconcile_adapter_entities(observations, DummyGraph(), ["rank:0"])
    assert not warnings
    assert {ob.entity for ob in resolved if ob.entity} == {"gpu:GPU-b"}


def test_dcgm_gpu_index_stays_unresolved_when_ambiguous():
    observations = parse_dcgm_json('{"tests":[{"name":"pcie","results":[{"entity_group":"GPU","entity_id":0,"status":"Fail"}]}]}')
    resolved, warnings = reconcile_adapter_entities(observations, DummyGraph(), [])
    assert warnings
    assert "gpu-index:0" in {ob.entity for ob in resolved if ob.entity}


def _scope_graph():
    graph = IdentityGraph()
    for entity in [
        Entity("rank:0", "rank", {}),
        Entity("gpu:GPU-a", "gpu", {"index": "0"}),
        Entity("pcie:0000:03:00.0", "pcie_device", {}),
        Entity("gpu:GPU-b", "gpu", {"index": "1"}),
        Entity("pcie:0000:04:00.0", "pcie_device", {}),
    ]:
        graph.entities[entity.id] = entity
    graph.relations += [
        Relation("rank:0", "uses_gpu", "gpu:GPU-a"),
        Relation("gpu:GPU-a", "attached_via_pcie", "pcie:0000:03:00.0"),
        Relation("gpu:GPU-b", "attached_via_pcie", "pcie:0000:04:00.0"),
    ]
    return graph


def test_xid_on_unrelated_gpu_pcie_is_rejected():
    graph = _scope_graph()
    related = Observation("gpu_xid_or_ecc_error", True, "journal", entity="pcie:0000:03:00.0")
    unrelated = Observation("gpu_xid_or_ecc_error", True, "journal", entity="pcie:0000:04:00.0")
    assert observation_is_on_affected_path(related, graph, ["rank:0"])
    assert not observation_is_on_affected_path(unrelated, graph, ["rank:0"])


def test_unresolved_dcgm_gpu_index_is_not_allowed_through_scope_filter():
    graph = _scope_graph()
    observation = Observation("dcgm_test_failed", True, "dcgm", entity="gpu-index:0")
    assert not observation_is_on_affected_path(observation, graph, ["rank:0"])
