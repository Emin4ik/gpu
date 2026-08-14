from __future__ import annotations

import re
from collections.abc import Iterable

from .models import Observation


def _obs(key: str, value, source: str, entity: str | None = None, raw_ref: str | None = None) -> Observation:
    return Observation(key=key, value=value, source=source, entity=entity, raw_ref=raw_ref or source)


def _first_int(patterns: Iterable[str], text: str) -> int | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            return int(match.group(1))
    return None


def _normalize_bdf(value: str) -> str:
    value = value.strip().lower()
    match = re.fullmatch(r"([0-9a-f]{4,8}):([0-9a-f]{2}):([0-9a-f]{2})\.([0-7])", value)
    if not match:
        return value
    domain, bus, device, function = match.groups()
    return f"{domain[-4:]}:{bus}:{device}.{function}"


def _parse_lspci_section(text: str, source: str, entity: str | None = None, raw_ref: str | None = None) -> list[Observation]:
    observations: list[Observation] = []
    expected_width = _first_int([r"LnkCap:.*?Width\s+x(\d+)"], text)
    current_width = _first_int([r"LnkSta:.*?Width\s+x(\d+)"], text)
    cap = re.search(r"LnkCap:.*?Speed\s+([0-9.]+)GT/s", text, re.IGNORECASE)
    sta = re.search(r"LnkSta:.*?Speed\s+([0-9.]+)GT/s", text, re.IGNORECASE)
    if current_width is not None:
        observations.append(_obs("pcie_width", current_width, source, entity, raw_ref))
    if expected_width is not None:
        observations.append(_obs("pcie_expected_width", expected_width, source, entity, raw_ref))
    if sta:
        observations.append(_obs("pcie_speed_gts", float(sta.group(1)), source, entity, raw_ref))
    if cap:
        observations.append(_obs("pcie_expected_speed_gts", float(cap.group(1)), source, entity, raw_ref))
    return observations


def parse_lspci(text: str, source: str = "lspci") -> list[Observation]:
    header_pattern = re.compile(r"(?m)^(?P<bdf>[0-9A-Fa-f]{4,8}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}\.[0-7])\s+.*$")
    matches = list(header_pattern.finditer(text))
    if not matches:
        return _parse_lspci_section(text, source)
    observations: list[Observation] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        bdf = _normalize_bdf(match.group("bdf"))
        observations.extend(_parse_lspci_section(text[start:end], source, entity=f"pcie:{bdf}", raw_ref=f"{source}#{bdf}"))
    return observations


def _parse_nvidia_smi_section(text: str, source: str, entity: str | None = None, raw_ref: str | None = None) -> list[Observation]:
    observations: list[Observation] = []
    sm_clock = _first_int([r"(?ms)^\s*Clocks\s*\n(?:.*\n){0,8}?\s*SM\s*:\s*(\d+)\s*MHz", r"^\s*SM\s*:\s*(\d+)\s*MHz\s*$"], text)
    temp = _first_int([r"GPU Current Temp\s*:\s*(\d+)\s*C", r"GPU Temperature\s*:\s*(\d+)\s*C"], text)
    if sm_clock is not None:
        observations.append(_obs("gpu_sm_clock_mhz", sm_clock, source, entity, raw_ref))
    if temp is not None:
        observations.append(_obs("gpu_temperature_c", temp, source, entity, raw_ref))
    thermal_active = bool(re.search(r"(?:SW|HW) Thermal Slowdown\s*:\s*(?:Active|Yes)", text, re.IGNORECASE) or re.search(r"Thermal Slowdown\s*:\s*(?:Active|Yes)", text, re.IGNORECASE))
    if thermal_active:
        observations.append(_obs("thermal_throttle_reason", True, source, entity, raw_ref))
    ecc_values = [int(value) for value in re.findall(r"(?:Uncorrected|Uncorrectable)[^:\n]*:\s*(\d+)", text, re.IGNORECASE)]
    if any(value > 0 for value in ecc_values):
        observations.append(_obs("gpu_xid_or_ecc_error", True, source, entity, raw_ref))
    return observations


def parse_nvidia_smi_q(text: str, source: str = "nvidia-smi-q") -> list[Observation]:
    header_pattern = re.compile(r"(?m)^\s*GPU\s+(?P<bdf>[0-9A-Fa-f]{4,8}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}\.[0-7])\s*$")
    matches = list(header_pattern.finditer(text))
    if not matches:
        uuid_match = re.search(r"^\s*UUID\s*:\s*(GPU-[A-Za-z0-9-]+)\s*$", text, re.IGNORECASE | re.MULTILINE)
        entity = f"gpu:{uuid_match.group(1)}" if uuid_match else None
        return _parse_nvidia_smi_section(text, source, entity=entity, raw_ref=source)
    observations: list[Observation] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        section = text[start:end]
        uuid_match = re.search(r"^\s*UUID\s*:\s*(GPU-[A-Za-z0-9-]+)\s*$", section, re.IGNORECASE | re.MULTILINE)
        entity = f"gpu:{uuid_match.group(1)}" if uuid_match else None
        bdf = _normalize_bdf(match.group("bdf"))
        observations.extend(_parse_nvidia_smi_section(section, source, entity=entity, raw_ref=f"{source}#{bdf}"))
    return observations


_IB_ERROR_KEYS = {"symbol_error_counter", "link_error_recovery_counter", "link_downed_counter", "port_rcv_errors", "port_rcv_remote_physical_errors", "port_rcv_switch_relay_errors", "port_xmit_discards", "local_link_integrity_errors", "excessive_buffer_overrun_errors", "vl15_dropped", "rx_errors", "tx_errors", "rx_discards", "tx_discards"}


def _normalize_counter_name(name: str) -> str:
    name = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name.strip())
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def parse_ib_counters(text: str, source: str = "ib-counters") -> list[Observation]:
    observations: list[Observation] = []
    total_errors = 0
    parsed = 0
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"([^:=]+?)\s*(?::|=|\s)\s*(-?\d+)\s*$", line)
        if not match:
            continue
        name = _normalize_counter_name(match.group(1))
        value = int(match.group(2))
        parsed += 1
        observations.append(_obs(f"ib_counter.{name}", value, source, raw_ref=f"{source}:L{line_number}"))
        if name in _IB_ERROR_KEYS and value > 0:
            total_errors += value
    if parsed:
        observations.append(_obs("fabric_error_counter_total", total_errors, source, raw_ref=source))
    return observations


def parse_nccl_log(text: str, source: str = "nccl-log") -> list[Observation]:
    observations: list[Observation] = []
    socket_transport = bool(re.search(r"NET/(?:Socket|Sockets)", text, re.IGNORECASE) or re.search(r"Using network\s+Socket", text, re.IGNORECASE))
    ib_transport = bool(re.search(r"NET/(?:IB|OFI)", text, re.IGNORECASE) or re.search(r"Using network\s+(?:IB|OFI)", text, re.IGNORECASE))
    timeout_present = bool(re.search(r"collective operation timeout|watchdog.*timeout|operation timed out|NCCL.*timeout", text, re.IGNORECASE))
    gdr_disabled = bool(re.search(r"GDR.*(?:disabled|not available|off)", text, re.IGNORECASE) or re.search(r"GPU Direct RDMA.*(?:disabled|not available)", text, re.IGNORECASE))
    if socket_transport:
        observations.append(_obs("nccl_socket_transport", True, source))
    if ib_transport:
        observations.append(_obs("nccl_ib_transport", True, source))
    if timeout_present:
        observations.append(_obs("nccl_timeout_present", True, source))
        observations.append(_obs("communication_waits", True, source))
    if gdr_disabled:
        observations.append(_obs("nccl_gdr_disabled", True, source))
    ranks = {int(rank) for rank in re.findall(r"\brank\s*[=:]?\s*(\d+)\b", text, re.IGNORECASE)}
    if ranks:
        observations.append(_obs("nccl_log_rank_count", len(ranks), source))
    return observations
