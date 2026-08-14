from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .models import Observation
from .parsers import parse_ib_counters, parse_lspci, parse_nccl_log, parse_nvidia_smi_q


@dataclass
class IngestResult:
    symptom: str
    observations: list[Observation]
    parsed_files: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _load_context(path: Path) -> tuple[str, list[Observation]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    observations = [Observation(**item) for item in payload.get("observations", [])]
    return payload.get("symptom", "unspecified incident"), observations


def _find_first(root: Path, names: tuple[str, ...]) -> Path | None:
    for name in names:
        candidate = root / name
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _by_key(observations: list[Observation]) -> dict[str, Observation]:
    return {ob.key: ob for ob in observations}


def _derive_baseline_facts(current: list[Observation], baseline: list[Observation]) -> list[Observation]:
    derived: list[Observation] = []
    cur = _by_key(current)
    base = _by_key(baseline)

    current_clock = cur.get("gpu_sm_clock_mhz")
    baseline_clock = base.get("gpu_sm_clock_mhz")
    if current_clock and baseline_clock and isinstance(current_clock.value, int) and isinstance(baseline_clock.value, int):
        if baseline_clock.value > 0 and current_clock.value < baseline_clock.value * 0.90:
            derived.append(Observation("gpu_clock_below_peer", True, "derived:nvidia-smi-baseline"))

    current_errors = cur.get("fabric_error_counter_total")
    baseline_errors = base.get("fabric_error_counter_total")
    if current_errors and baseline_errors and isinstance(current_errors.value, int) and isinstance(baseline_errors.value, int):
        if current_errors.value > baseline_errors.value:
            derived.append(Observation("fabric_error_counters_rising", True, "derived:ib-baseline"))
        else:
            derived.append(Observation("fabric_counters_clean", True, "derived:ib-baseline"))

    return derived


def ingest_directory(root: Path) -> IngestResult:
    if not root.is_dir():
        raise ValueError(f"not a directory: {root}")

    context_path = _find_first(root, ("incident.json", "context.json"))
    if context_path:
        symptom, observations = _load_context(context_path)
        parsed_files = [context_path.name]
    else:
        symptom, observations, parsed_files = "unspecified incident", [], []

    baseline_dir = root / "baseline"
    parser_specs = [
        (("nvidia-smi-q.txt", "nvidia_smi_q.txt"), parse_nvidia_smi_q),
        (("lspci.txt", "lspci-vv.txt"), parse_lspci),
        (("nccl.log", "nccl.txt"), parse_nccl_log),
        (("ib-counters.txt", "ib_counters.txt", "ibqueryerrors.txt"), parse_ib_counters),
    ]

    for names, parser in parser_specs:
        current_path = _find_first(root, names)
        if not current_path:
            continue
        current_obs = parser(current_path.read_text(encoding="utf-8", errors="replace"), source=current_path.name)
        observations.extend(current_obs)
        parsed_files.append(current_path.name)

        if baseline_dir.is_dir():
            baseline_path = _find_first(baseline_dir, names)
            if baseline_path:
                baseline_obs = parser(
                    baseline_path.read_text(encoding="utf-8", errors="replace"),
                    source=f"baseline/{baseline_path.name}",
                )
                observations.extend(_derive_baseline_facts(current_obs, baseline_obs))
                parsed_files.append(f"baseline/{baseline_path.name}")

    deduped: dict[str, Observation] = {}
    for observation in observations:
        deduped[observation.key] = observation

    warnings: list[str] = []
    if not parsed_files:
        warnings.append("No recognized incident artifacts were found.")

    return IngestResult(symptom=symptom, observations=list(deduped.values()), parsed_files=parsed_files, warnings=warnings)
