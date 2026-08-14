from __future__ import annotations

import argparse
import json
from pathlib import Path

from .engine import investigate
from .models import Observation


def _load(path: Path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    observations = [Observation(**item) for item in payload.get("observations", [])]
    return payload.get("symptom", "unspecified incident"), observations


def _render(result) -> str:
    lines = ["GPU TRIAGE", "=" * 72, f"Symptom: {result.symptom}", "", "Hypotheses:"]
    for h in result.hypotheses:
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
    parser.add_argument("incident", type=Path, help="Path to an incident JSON file")
    args = parser.parse_args()

    symptom, observations = _load(args.incident)
    print(_render(investigate(symptom, observations)))


if __name__ == "__main__":
    main()
