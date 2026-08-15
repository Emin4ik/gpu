from __future__ import annotations

import json
import re
from typing import Any

from .models import Observation


def _obs(key: str, value: Any, source: str, entity: str | None = None, raw_ref: str | None = None) -> Observation:
    return Observation(key=key, value=value, source=source, entity=entity, raw_ref=raw_ref or source)


def _normalize_name(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text


def _normalize_bdf(value: str) -> str:
    text = value.strip().lower().replace("pci:", "")
    match = re.fullmatch(r"([0-9a-f]{4,8}):([0-9a-f]{2}):([0-9a-f]{2})(?:\.([0-7]))?", text)
    if not match:
        return text
    domain, bus, device, function = match.groups()
    return f"{domain[-4:]}:{bus}:{device}.{function or '0'}"


def _json_payload(text: str) -> Any:
    decoder = json.JSONDecoder()
    for marker in ("{", "["):
        start = text.find(marker)
        while start >= 0:
            try:
                payload, _ = decoder.raw_decode(text[start:])
                return payload
            except json.JSONDecodeError:
                start = text.find(marker, start + 1)
    raise ValueError("DCGM artifact does not contain a valid JSON document")


def _entity_from_mapping(item: dict[str, Any]) -> str | None:
    group = item.get("entity_group") or item.get("entityGroup") or item.get("entity_group_name")
    entity_id = item.get("entity_id")
    if entity_id is None:
        entity_id = item.get("entityId")
    if entity_id is None:
        entity_id = item.get("gpu_id")
    if entity_id is None:
        entity_id = item.get("gpuId")
    group_text = str(group or "").upper()
    if entity_id is not None and ("GPU" in group_text or group in {1, "1"} or any(key in item for key in ("gpu_id", "gpuId"))):
        return f"gpu-index:{entity_id}"
    return None


_EXECUTION_CODES = {
    "DCGM_FR_CUDA_API",
    "DCGM_FR_INTERNAL",
    "DCGM_FR_TEST_DISABLED",
    "DCGM_FR_ABORTED",
    "DCGM_FR_CUDA_CONTEXT",
    "DCGM_FR_CUDA_UNBOUND",
}

_HARDWARE_CODE_PARTS = (
    "FAULTY_MEMORY",
    "DBE",
    "UNCORRECTABLE",
    "ROW_REMAP",
    "XID",
    "PCIE",
    "THERMAL",
    "NVLINK",
    "NVSWITCH",
)


def _collect_error_records(value: Any) -> list[tuple[str | None, str | None]]:
    records: list[tuple[str | None, str | None]] = []
    if isinstance(value, str):
        code_match = re.search(r"\b(DCGM_FR_[A-Z0-9_]+)\b", value)
        records.append((code_match.group(1) if code_match else None, value))
    elif isinstance(value, dict):
        code = value.get("code") or value.get("error_code") or value.get("errorCode")
        message = value.get("msg") or value.get("message") or value.get("error") or value.get("info")
        if code is not None or message is not None:
            records.append((str(code) if code is not None else None, str(message) if message is not None else None))
    elif isinstance(value, list):
        for item in value:
            records.extend(_collect_error_records(item))
    return records


def _dcgm_result_observations(test_name: str, result: dict[str, Any], source: str, raw_ref: str) -> list[Observation]:
    observations: list[Observation] = []
    entity = _entity_from_mapping(result)
    status = _normalize_name(result.get("status") or result.get("result") or result.get("health"))
    test_key = _normalize_name(test_name) or "unknown"
    if status:
        observations.append(_obs(f"dcgm_test_status.{test_key}", status, source, entity, raw_ref))

    failed = status in {"fail", "failed", "failure", "error", "warning", "warn"}
    if failed:
        observations.append(_obs("dcgm_test_failed", True, source, entity, raw_ref))
        observations.append(_obs(f"dcgm_test_failed.{test_key}", True, source, entity, raw_ref))
        if "pcie" in test_key:
            observations.append(_obs("dcgm_pcie_test_failed", True, source, entity, raw_ref))
        if test_key in {"memory", "memtest", "memory_bandwidth"} or "memory" in test_key:
            observations.append(_obs("dcgm_memory_test_failed", True, source, entity, raw_ref))
        if "thermal" in test_key or "power" in test_key:
            observations.append(_obs("dcgm_thermal_test_failed", True, source, entity, raw_ref))
        if "nvlink" in test_key or "nvbandwidth" in test_key or "nccl" in test_key:
            observations.append(_obs("dcgm_communication_test_failed", True, source, entity, raw_ref))

    error_values = []
    for key in ("errors", "error", "warnings", "warning"):
        if key in result:
            error_values.extend(_collect_error_records(result[key]))
    for code, message in error_values:
        if code:
            observations.append(_obs("dcgm_failure_code", code, source, entity, raw_ref))
        if message:
            observations.append(_obs("dcgm_failure_message", message, source, entity, raw_ref))
        code_upper = (code or "").upper()
        message_upper = (message or "").upper()
        if code_upper in _EXECUTION_CODES:
            observations.append(_obs("dcgm_test_execution_issue", True, source, entity, raw_ref))
        elif any(part in code_upper or part in message_upper for part in _HARDWARE_CODE_PARTS):
            observations.append(_obs("dcgm_hardware_failure", True, source, entity, raw_ref))
        if "XID" in code_upper or "XID" in message_upper or "ECC" in code_upper or "ECC" in message_upper:
            observations.append(_obs("gpu_xid_or_ecc_error", True, source, entity, raw_ref))
    return observations


def _walk_dcgm(value: Any, source: str, path: str = "$", inherited_entity: str | None = None) -> list[Observation]:
    observations: list[Observation] = []
    if isinstance(value, dict):
        local_entity = _entity_from_mapping(value) or inherited_entity
        tests = value.get("tests")
        if isinstance(tests, list):
            for test_index, test in enumerate(tests):
                if not isinstance(test, dict):
                    continue
                test_name = str(test.get("name") or test.get("test_name") or f"test_{test_index}")
                results = test.get("results")
                if isinstance(results, list):
                    for result_index, result in enumerate(results):
                        if isinstance(result, dict):
                            observations.extend(_dcgm_result_observations(test_name, result, source, f"{source}:{path}.tests[{test_index}].results[{result_index}]"))
                elif isinstance(test.get("status"), (str, int)):
                    observations.extend(_dcgm_result_observations(test_name, test, source, f"{source}:{path}.tests[{test_index}]"))

        # Defensive support for health-style incident objects and future schema variations.
        system = value.get("system") or value.get("subsystem") or value.get("component")
        status = _normalize_name(value.get("health") or value.get("status"))
        if system is not None and status in {"warning", "warn", "failure", "fail", "failed"}:
            entity = local_entity
            system_key = _normalize_name(system)
            observations.append(_obs("dcgm_health_incident", True, source, entity, f"{source}:{path}"))
            observations.append(_obs("dcgm_health_system", system_key, source, entity, f"{source}:{path}"))
            if "pcie" in system_key:
                observations.append(_obs("dcgm_pcie_health_incident", True, source, entity, f"{source}:{path}"))
            if "memory" in system_key:
                observations.append(_obs("dcgm_memory_health_incident", True, source, entity, f"{source}:{path}"))
            if "thermal" in system_key or "power" in system_key:
                observations.append(_obs("dcgm_thermal_health_incident", True, source, entity, f"{source}:{path}"))
            if "nvlink" in system_key:
                observations.append(_obs("dcgm_nvlink_health_incident", True, source, entity, f"{source}:{path}"))
            if "connectx" in system_key:
                observations.append(_obs("dcgm_connectx_health_incident", True, source, entity, f"{source}:{path}"))
            if "nvswitch" in system_key:
                observations.append(_obs("dcgm_nvswitch_health_incident", True, source, entity, f"{source}:{path}"))

        for key, child in value.items():
            if key == "tests":
                continue
            observations.extend(_walk_dcgm(child, source, f"{path}.{key}", local_entity))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            observations.extend(_walk_dcgm(child, source, f"{path}[{index}]", inherited_entity))
    return observations


def parse_dcgm_json(text: str, source: str = "dcgm.json") -> list[Observation]:
    """Parse DCGM diag/health JSON defensively.

    DCGM does not publish the dcgmi JSON as a stable versioned schema, so this
    adapter recognizes semantic result objects instead of pinning to one shape.
    """
    payload = _json_payload(text)
    return _walk_dcgm(payload, source)


def parse_nvidia_system_log(text: str, source: str = "journal.log") -> list[Observation]:
    """Extract NVIDIA Xid/SXid events from kernel/journal text."""
    observations: list[Observation] = []
    gpu_by_bdf: dict[str, str] = {}

    gpu_line = re.compile(
        r"NVRM:\s*GPU at\s+(?P<bdf>[0-9A-Fa-f:.]+):\s*(?P<uuid>GPU-[A-Za-z0-9-]+)",
        re.IGNORECASE,
    )
    xid_line = re.compile(
        r"NVRM:\s*Xid\s*\((?:PCI:)?(?P<bdf>[0-9A-Fa-f:.]+)(?:\s+GPU-I:\d+)?\)\s*:\s*(?P<code>\d+)\s*,?\s*(?P<message>.*)$",
        re.IGNORECASE,
    )
    sxid_line = re.compile(
        r"SXid\s*\((?:PCI:)?(?P<bdf>[0-9A-Fa-f:.]+)\)\s*:\s*(?P<code>\d+)\s*,?\s*(?P<message>.*)$",
        re.IGNORECASE,
    )

    lines = text.splitlines()
    for line_number, line in enumerate(lines, start=1):
        match = gpu_line.search(line)
        if match:
            gpu_by_bdf[_normalize_bdf(match.group("bdf"))] = match.group("uuid")
            continue

        match = xid_line.search(line)
        if match:
            bdf = _normalize_bdf(match.group("bdf"))
            code = int(match.group("code"))
            message = match.group("message").strip()
            entity = f"gpu:{gpu_by_bdf[bdf]}" if bdf in gpu_by_bdf else f"pcie:{bdf}"
            raw_ref = f"{source}:L{line_number}"
            observations.append(_obs("nvidia_xid_code", code, source, entity, raw_ref))
            observations.append(_obs("nvidia_xid_message", message, source, entity, raw_ref))
            observations.append(_obs("gpu_xid_or_ecc_error", True, source, entity, raw_ref))
            if code == 79 or "fallen off the bus" in message.lower():
                observations.append(_obs("gpu_fallen_off_bus", True, source, entity, raw_ref))
            if code in {48, 63, 64, 94, 95} or "ecc" in message.lower():
                observations.append(_obs("gpu_memory_error_event", True, source, entity, raw_ref))
            if code == 74 or "nvlink" in message.lower():
                observations.append(_obs("gpu_nvlink_error_event", True, source, entity, raw_ref))
            continue

        match = sxid_line.search(line)
        if match:
            bdf = _normalize_bdf(match.group("bdf"))
            code = int(match.group("code"))
            message = match.group("message").strip()
            raw_ref = f"{source}:L{line_number}"
            entity = f"pcie:{bdf}"
            observations.append(_obs("nvidia_sxid_code", code, source, entity, raw_ref))
            observations.append(_obs("nvidia_sxid_message", message, source, entity, raw_ref))
            observations.append(_obs("nvidia_sxid_event", True, source, entity, raw_ref))

    return observations
