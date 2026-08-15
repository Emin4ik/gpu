from __future__ import annotations

import csv
import io
import re
from typing import Any

from .models import Observation


def _obs(key: str, value: Any, source: str, entity: str | None = None, raw_ref: str | None = None) -> Observation:
    return Observation(key=key, value=value, source=source, entity=entity, raw_ref=raw_ref or source)


def parse_cpu_list(value: str) -> tuple[int, ...]:
    cpus: set[int] = set()
    for token in value.strip().split(","):
        token = token.strip()
        if not token:
            continue
        if "-" in token:
            start_s, end_s = token.split("-", 1)
            if not (start_s.strip().isdigit() and end_s.strip().isdigit()):
                continue
            start, end = int(start_s), int(end_s)
            step = 1 if end >= start else -1
            cpus.update(range(start, end + step, step))
        elif token.isdigit():
            cpus.add(int(token))
    return tuple(sorted(cpus))


def _csv_rows(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in csv.DictReader(io.StringIO(text)):
        rows.append({str(key).strip(): (value or "").strip() for key, value in row.items() if key is not None})
    return rows


def parse_proc_interrupts(text: str, source: str = "proc-interrupts.txt") -> list[Observation]:
    """Parse /proc/interrupts into per-IRQ CPU activity facts."""
    lines = text.splitlines()
    if not lines:
        return []
    cpu_ids = [int(value) for value in re.findall(r"\bCPU(\d+)\b", lines[0])]
    if not cpu_ids:
        return []

    observations: list[Observation] = []
    for line_number, line in enumerate(lines[1:], start=2):
        match = re.match(r"^\s*(\d+):\s+(.*)$", line)
        if not match:
            continue
        irq = match.group(1)
        tokens = match.group(2).split()
        if len(tokens) < len(cpu_ids):
            continue
        count_tokens = tokens[: len(cpu_ids)]
        if not all(re.fullmatch(r"\d+", token) for token in count_tokens):
            continue
        counts = {cpu: int(token) for cpu, token in zip(cpu_ids, count_tokens)}
        total = sum(counts.values())
        active_cpus = tuple(cpu for cpu, count in counts.items() if count > 0)
        label = " ".join(tokens[len(cpu_ids) :])
        entity = f"irq:{irq}"
        raw_ref = f"{source}:L{line_number}"
        activity = {"counts": counts, "total": total, "active_cpus": active_cpus, "label": label}
        observations.extend(
            [
                _obs("irq_activity", activity, source, entity, raw_ref),
                _obs("irq_total_count", total, source, entity, raw_ref),
                _obs("irq_active_cpus", active_cpus, source, entity, raw_ref),
            ]
        )
        if label:
            observations.append(_obs("irq_label", label, source, entity, raw_ref))
    return observations


def parse_irq_affinity_csv(text: str, source: str = "irq-affinity.csv") -> list[Observation]:
    """Parse collected IRQ affinity/device identity into per-IRQ facts.

    Expected columns: irq,cpu_list and optionally effective_cpu_list,ibdev,netdev,pci_bdf.
    """
    observations: list[Observation] = []
    for row_number, row in enumerate(_csv_rows(text), start=2):
        irq = row.get("irq") or row.get("irq_number")
        if not irq or not irq.isdigit():
            continue
        allowed = parse_cpu_list(row.get("cpu_list") or row.get("smp_affinity_list") or "")
        effective = parse_cpu_list(row.get("effective_cpu_list") or row.get("effective_affinity_list") or "")
        value = {
            "allowed_cpus": allowed,
            "effective_cpus": effective,
            "ibdev": row.get("ibdev", ""),
            "netdev": row.get("netdev", ""),
            "pci_bdf": row.get("pci_bdf", "").lower(),
        }
        entity = f"irq:{irq}"
        raw_ref = f"{source}:L{row_number}"
        observations.append(_obs("irq_affinity", value, source, entity, raw_ref))
        if allowed:
            observations.append(_obs("irq_affinity_cpus", allowed, source, entity, raw_ref))
        if effective:
            observations.append(_obs("irq_effective_cpus", effective, source, entity, raw_ref))
        for key in ("ibdev", "netdev", "pci_bdf"):
            if value[key]:
                observations.append(_obs(f"irq_device_{key}", value[key], source, entity, raw_ref))
    return observations


def parse_process_affinity_csv(text: str, source: str = "process-affinity.csv") -> list[Observation]:
    """Parse communication-process CPU affinity captured at job runtime."""
    observations: list[Observation] = []
    for row_number, row in enumerate(_csv_rows(text), start=2):
        rank = row.get("rank") or row.get("global_rank")
        pid = row.get("pid", "")
        role = (row.get("role") or row.get("thread_role") or "").strip().lower()
        cpus = parse_cpu_list(row.get("cpu_list") or row.get("cpus_allowed_list") or "")
        if rank is None or str(rank).strip() == "" or not cpus:
            continue
        entity = f"rank:{str(rank).strip()}"
        raw_ref = f"{source}:L{row_number}"
        value = {"pid": pid, "role": role, "cpus": cpus, "node": row.get("node", "")}
        observations.extend(
            [
                _obs("process_affinity", value, source, entity, raw_ref),
                _obs("process_allowed_cpus", cpus, source, entity, raw_ref),
            ]
        )
        if role:
            observations.append(_obs("process_role", role, source, entity, raw_ref))
        if pid:
            observations.append(_obs("process_pid", pid, source, entity, raw_ref))
    return observations


def _affected_hca_union(graph, affected_entities: list[str]) -> set[str]:
    targets: set[str] = set()
    for source in affected_entities:
        targets.update(graph.reachable(source, "nic_hca", max_depth=4))
    return targets


def _matches_hca(affinity: dict[str, Any], hca) -> bool:
    attrs = hca.attributes
    checks = [
        (affinity.get("ibdev"), attrs.get("ibdev")),
        (affinity.get("netdev"), attrs.get("netdev")),
        (str(affinity.get("pci_bdf", "")).lower(), str(attrs.get("pci_bdf", "")).lower()),
    ]
    return any(left and right and str(left) == str(right) for left, right in checks)


def derive_irq_affinity_facts(observations: list[Observation], graph, affected_entities: list[str]) -> tuple[list[Observation], list[str]]:
    """Correlate active NIC IRQ CPUs with affected communication-process CPUs.

    A positive overlap is emitted only when an IRQ is active, its device maps to an
    affected HCA, and an affected-rank communication process has known CPU affinity.
    """
    warnings: list[str] = []
    derived: list[Observation] = []

    activity_by_irq = {ob.entity: ob for ob in observations if ob.key == "irq_activity" and ob.entity}
    affinity_by_irq = {ob.entity: ob for ob in observations if ob.key == "irq_affinity" and ob.entity}
    process_rows = [ob for ob in observations if ob.key == "process_affinity" and ob.entity in set(affected_entities)]
    process_rows = [
        ob
        for ob in process_rows
        if any(token in str(ob.value.get("role", "")).lower() for token in ("nccl", "comm", "communication"))
    ]

    if not affinity_by_irq:
        return [], []
    if not activity_by_irq:
        warnings.append("IRQ affinity is present but /proc/interrupts activity is missing; overlap was not inferred")
        return [], warnings
    if not process_rows:
        warnings.append("IRQ evidence is present but affected communication-process CPU affinity is missing")
        return [], warnings

    affected_hcas = _affected_hca_union(graph, affected_entities)
    if not affected_hcas:
        warnings.append("IRQ evidence is present but no affected HCA/NIC identity could be resolved")
        return [], warnings

    mapped_irqs: list[tuple[str, Observation, Observation, str]] = []
    for irq_entity, affinity_ob in affinity_by_irq.items():
        activity_ob = activity_by_irq.get(irq_entity)
        if not activity_ob or int(activity_ob.value.get("total", 0)) <= 0:
            continue
        matching_hcas = {
            hca_id
            for hca_id in affected_hcas
            if hca_id in graph.entities and _matches_hca(affinity_ob.value, graph.entities[hca_id])
        }
        if len(matching_hcas) == 1:
            mapped_irqs.append((irq_entity, affinity_ob, activity_ob, next(iter(matching_hcas))))
        elif len(matching_hcas) > 1:
            warnings.append(f"{affinity_ob.source}: {irq_entity} matches multiple affected HCAs; overlap was not inferred")

    if not mapped_irqs:
        warnings.append("No active IRQ could be mapped unambiguously to an affected HCA/NIC")
        return [], warnings

    saw_comparable = False
    overlaps: set[int] = set()
    overlap_refs: list[str] = []
    overlap_hcas: set[str] = set()
    for _, affinity_ob, activity_ob, hca_id in mapped_irqs:
        irq_cpus = tuple(affinity_ob.value.get("effective_cpus") or affinity_ob.value.get("allowed_cpus") or ())
        if not irq_cpus:
            continue
        for process_ob in process_rows:
            process_cpus = tuple(process_ob.value.get("cpus") or ())
            if not process_cpus:
                continue
            saw_comparable = True
            common = set(irq_cpus) & set(process_cpus)
            if common:
                overlaps.update(common)
                overlap_hcas.add(hca_id)
                overlap_refs.extend([affinity_ob.raw_ref or affinity_ob.source, activity_ob.raw_ref or activity_ob.source, process_ob.raw_ref or process_ob.source])

    if overlaps:
        entity = next(iter(overlap_hcas)) if len(overlap_hcas) == 1 else None
        raw_ref = " + ".join(dict.fromkeys(overlap_refs))
        derived.extend(
            [
                _obs("irq_shares_nccl_cpu", True, "derived:irq-affinity", entity, raw_ref),
                _obs("irq_overlap_cpus", tuple(sorted(overlaps)), "derived:irq-affinity", entity, raw_ref),
            ]
        )
    elif saw_comparable:
        derived.append(_obs("irq_affinity_clean", True, "derived:irq-affinity", raw_ref="IRQ and process CPU sets compared with no overlap"))

    return derived, warnings
