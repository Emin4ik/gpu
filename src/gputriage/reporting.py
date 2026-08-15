from __future__ import annotations

from typing import Any, Iterable

from .models import Investigation, Observation

REPORT_SCHEMA_VERSION = "gputriage.report.v1"


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    return repr(value)


def result_state(result: Investigation) -> str:
    if result.verdict:
        return "confirmed"
    if result.next_best_test:
        return "needs_evidence"
    return "abstain"


def _hypothesis_payload(hypothesis) -> dict[str, Any]:
    return {
        "id": hypothesis.id,
        "title": hypothesis.title,
        "status": hypothesis.status.value,
        "supporting_evidence": list(hypothesis.supporting_evidence),
        "contradicting_evidence": list(hypothesis.contradicting_evidence),
        "missing_evidence": list(hypothesis.missing_evidence),
    }


def _test_payload(test) -> dict[str, Any] | None:
    if test is None:
        return None
    return {
        "id": test.id,
        "title": test.title,
        "purpose": test.purpose,
        "command": test.command,
        "cost": test.cost,
        "invasiveness": test.invasiveness,
        "duration_class": test.duration_class,
        "discriminates_between": list(test.discriminates_between),
        "expected_outcomes": list(test.expected_outcomes),
        "selection_score": test.selection_score,
        "selection_reason": test.selection_reason,
        "alternatives": list(test.alternatives),
    }


def _observation_payload(observation: Observation) -> dict[str, Any]:
    return {
        "key": observation.key,
        "value": _json_value(observation.value),
        "source": observation.source,
        "entity": observation.entity,
        "raw_ref": observation.raw_ref,
    }


def build_report(
    result: Investigation,
    observations: Iterable[Observation],
    *,
    parsed_files: Iterable[str] = (),
    warnings: Iterable[str] = (),
    affected_entities: Iterable[str] = (),
) -> dict[str, Any]:
    """Build the stable v1 machine-readable investigation report."""

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "result_state": result_state(result),
        "symptom": result.symptom,
        "verdict": result.verdict,
        "affected_entities": list(affected_entities),
        "parsed_files": list(parsed_files),
        "warnings": list(warnings),
        "notes": list(result.notes),
        "hypotheses": [_hypothesis_payload(hypothesis) for hypothesis in result.hypotheses],
        "next_best_test": _test_payload(result.next_best_test),
        "observations": [_observation_payload(observation) for observation in observations],
    }


def render_text(report: dict[str, Any]) -> str:
    lines = [
        "GPU TRIAGE",
        "=" * 72,
        f"State: {str(report['result_state']).upper()}",
        f"Symptom: {report['symptom']}",
    ]
    if report.get("affected_entities"):
        lines.append(f"Affected entities: {', '.join(report['affected_entities'])}")
    if report.get("parsed_files"):
        lines.append(f"Artifacts: {', '.join(report['parsed_files'])}")
    for warning in report.get("warnings", []):
        lines.append(f"Warning: {warning}")

    lines.extend(["", "Hypotheses:"])
    for hypothesis in report.get("hypotheses", []):
        visible = (
            hypothesis["status"] != "possible"
            or hypothesis["supporting_evidence"]
            or hypothesis["contradicting_evidence"]
            or hypothesis["missing_evidence"]
        )
        if not visible:
            continue
        lines.append(f"- {hypothesis['status'].upper():9} {hypothesis['title']} [{hypothesis['id']}]")
        for item in hypothesis["supporting_evidence"]:
            lines.append(f"    + {item}")
        for item in hypothesis["contradicting_evidence"]:
            lines.append(f"    - {item}")
        for item in hypothesis["missing_evidence"]:
            lines.append(f"    ? missing: {item}")

    lines.append("")
    verdict = report.get("verdict")
    if verdict:
        lines.append(f"VERDICT: {verdict}")
    elif report["result_state"] == "abstain":
        lines.append("VERDICT: abstain / unsupported by current playbooks")
    else:
        lines.append("VERDICT: insufficient evidence for confirmation")

    test = report.get("next_best_test")
    if test:
        lines.extend([
            "",
            "NEXT BEST TEST",
            test["title"],
            f"Why: {test['purpose']}",
            f"Cost: {test['cost']}; invasiveness: {test['invasiveness']}; duration: {test['duration_class']}",
        ])
        if test.get("selection_reason"):
            lines.append(f"Selection: {test['selection_reason']}")
        if test.get("expected_outcomes"):
            lines.append("Expected outcomes:")
            for outcome in test["expected_outcomes"]:
                lines.append(f"  - {outcome}")
        if test.get("command"):
            lines.append(f"Command: {test['command']}")
        if test.get("alternatives"):
            lines.append("Alternatives:")
            for alternative in test["alternatives"]:
                lines.append(f"  - {alternative}")

    evidence = report.get("observations", [])
    if evidence:
        lines.extend(["", f"Evidence observations: {len(evidence)} (see JSON output for provenance)"])
    return "\n".join(lines)
