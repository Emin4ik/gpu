from __future__ import annotations

import argparse
import json
from pathlib import Path

from .engine import investigate
from .ingest import ingest_directory
from .models import Observation


def _load_json(path: Path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    observations = [Observation(**item) for item in payload.get("observations", [])]
    return payload.get("symptom", "unspecified incident"), observations, [path.name], []


def _load(path: Path):
    if path.is_dir():
        result = ingest_directory(path)
        return result.symptom, result.observations, result.parsed_files, result.warnings
    return _load_json(path)


def _render(result, parsed_files: list[str] | None = None, warnings: list[str] | None = None) -> str:
    lines = ["GPU TRIAGE", "=" * 72, f"Symptom: {result.symptom}"]
    if parsed_files:
        lines.append(f"Artifacts: {', '.join(parsed_files)}")
    if warnings:
        for warning in warnings:
            lines.append(f"Warning: {warning}")
    lines.extend(["", "Hypotheses:"])
    for h in result.hypotheses:
        if not (h.supporting_evidence or h.contradicting_evidence or h.missing_evidence or h.status.value != "possible"):
            continue
        lines.append(f"- {h.status.value.upper():9} {h.title}")
        for item in h.supporting_evidence:
            lines.append(f"    + {item}")
        for item in h.contradicting_evidence:
            lines.append(f"    - {item}")
        for item in h.missing_evidence:
            lines.append(f"    ? missing: {item}")

    lines.append("")
    if result.verdict:
        lines.append(f"VERDICT: {result.verdict}")
    else:
        lines.append("VERDICT: insufficient evidence")

    if result.next_best_test:
        test = result.next_best_test
        lines.extend([
            "",
            "NEXT BEST TEST",
            f"{test.title}",
            f"Why: {test.purpose}",
            f"Cost: {test.cost}; invasiveness: {test.invasiveness}",
        ])
        if test.command:
            lines.append(f"Command: {test.command}")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evidence-first AI/GPU infrastructure diagnostic planner")
    parser.add_argument("incident", type=Path, help="Incident JSON file or directory of raw artifacts")
    args = parser.parse_args()

    symptom, observations, parsed_files, warnings = _load(args.incident)
    print(_render(investigate(symptom, observations), parsed_files, warnings))


if __name__ == "__main__":
    main()
