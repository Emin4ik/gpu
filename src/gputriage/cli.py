from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from . import __version__
from .bundle import BundleValidation, validate_bundle
from .engine import investigate
from .models import Observation
from .reporting import build_report, render_text
from .sanitize import export_sanitized_bundle

EXIT_CONFIRMED = 0
EXIT_INVALID_BUNDLE = 2
EXIT_NEEDS_EVIDENCE = 10
EXIT_ABSTAIN = 20


def _load_json(path: Path):
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid incident JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("incident JSON must contain a top-level object")
    raw_observations = payload.get("observations", [])
    if not isinstance(raw_observations, list):
        raise ValueError("observations must be a list")
    try:
        observations = [Observation(**item) for item in raw_observations]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid observation: {exc}") from exc
    return (
        payload.get("symptom", "unspecified incident"),
        observations,
        [path.name],
        [],
        list(payload.get("affected_entities", [])) if isinstance(payload.get("affected_entities", []), list) else [],
    )


def _emit(payload: dict, output_format: str, *, text_renderer=None) -> None:
    if output_format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif text_renderer:
        print(text_renderer(payload))
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))


def _state_exit_code(state: str) -> int:
    if state == "confirmed":
        return EXIT_CONFIRMED
    if state == "needs_evidence":
        return EXIT_NEEDS_EVIDENCE
    return EXIT_ABSTAIN


def _render_validation(validation: BundleValidation) -> str:
    lines = [
        "GPU TRIAGE BUNDLE VALIDATION",
        "=" * 72,
        f"Bundle: {validation.path}",
        f"Status: {'VALID' if validation.valid else 'INVALID'}",
    ]
    for error in validation.errors:
        lines.append(f"ERROR: {error}")
    for warning in validation.warnings:
        lines.append(f"Warning: {warning}")
    if validation.ingest_result:
        lines.append(f"Recognized artifacts: {', '.join(validation.ingest_result.parsed_files) or '(none)'}")
        lines.append(f"Observations: {len(validation.ingest_result.observations)}")
    return "\n".join(lines)


def _validation_payload(validation: BundleValidation) -> dict:
    ingest = validation.ingest_result
    return {
        "schema_version": "gputriage.bundle-validation.v1",
        "valid": validation.valid,
        "path": str(validation.path),
        "errors": list(validation.errors),
        "warnings": list(validation.warnings),
        "parsed_files": list(ingest.parsed_files) if ingest else [],
        "observation_count": len(ingest.observations) if ingest else 0,
        "affected_entities": list(ingest.affected_entities) if ingest else [],
    }


def _run_investigate(path: Path, output_format: str) -> int:
    if path.is_dir():
        validation = validate_bundle(path)
        if not validation.valid or validation.ingest_result is None:
            _emit(_validation_payload(validation), output_format, text_renderer=lambda _: _render_validation(validation))
            return EXIT_INVALID_BUNDLE
        ingest = validation.ingest_result
        symptom = ingest.symptom
        observations = ingest.observations
        parsed_files = ingest.parsed_files
        warnings = validation.warnings
        affected_entities = ingest.affected_entities
    else:
        try:
            symptom, observations, parsed_files, warnings, affected_entities = _load_json(path)
        except ValueError as exc:
            payload = {
                "schema_version": "gputriage.error.v1",
                "error": str(exc),
                "path": str(path),
            }
            _emit(payload, output_format, text_renderer=lambda value: f"GPU TRIAGE\nERROR: {value['error']}")
            return EXIT_INVALID_BUNDLE

    investigation = investigate(symptom, observations)
    report = build_report(
        investigation,
        observations,
        parsed_files=parsed_files,
        warnings=warnings,
        affected_entities=affected_entities,
    )
    _emit(report, output_format, text_renderer=render_text)
    return _state_exit_code(report["result_state"])


def _run_validate(path: Path, output_format: str) -> int:
    validation = validate_bundle(path)
    _emit(_validation_payload(validation), output_format, text_renderer=lambda _: _render_validation(validation))
    return EXIT_CONFIRMED if validation.valid else EXIT_INVALID_BUNDLE


def _run_export_sanitized(
    bundle: Path,
    output: Path,
    *,
    include_symptom: bool,
    force: bool,
    output_format: str,
) -> int:
    try:
        payload = export_sanitized_bundle(
            bundle,
            output,
            include_symptom=include_symptom,
            force=force,
        )
    except (ValueError, FileExistsError, OSError) as exc:
        error = {
            "schema_version": "gputriage.error.v1",
            "error": str(exc),
            "path": str(bundle),
        }
        _emit(error, output_format, text_renderer=lambda value: f"GPU TRIAGE EXPORT\nERROR: {value['error']}")
        return EXIT_INVALID_BUNDLE

    summary = {
        "schema_version": "gputriage.export-result.v1",
        "output": str(output),
        "observation_count": len(payload["observations"]),
        "raw_artifacts_included": False,
        "free_text_symptom_included": bool(payload["sanitization"]["free_text_symptom_included"]),
    }
    _emit(
        summary,
        output_format,
        text_renderer=lambda value: (
            "GPU TRIAGE SANITIZED EXPORT\n"
            f"Output: {value['output']}\n"
            f"Observations: {value['observation_count']}\n"
            "Raw artifacts included: no"
        ),
    )
    return EXIT_CONFIRMED


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gputriage",
        description="Evidence-first AI/GPU infrastructure diagnostic planner",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    investigate_parser = subparsers.add_parser("investigate", help="Investigate an incident bundle or legacy JSON file")
    investigate_parser.add_argument("incident", type=Path, help="Incident directory or legacy incident JSON file")
    investigate_parser.add_argument("--format", choices=("text", "json"), default="text", dest="output_format")

    validate_parser = subparsers.add_parser("validate-bundle", help="Validate an incident directory without diagnosing it")
    validate_parser.add_argument("bundle", type=Path, help="Incident bundle directory")
    validate_parser.add_argument("--format", choices=("text", "json"), default="text", dest="output_format")

    export_parser = subparsers.add_parser(
        "export-sanitized",
        help="Export normalized pseudonymized evidence without copying raw artifacts",
    )
    export_parser.add_argument("bundle", type=Path, help="Source incident bundle directory")
    export_parser.add_argument("output", type=Path, help="Destination JSON file")
    export_parser.add_argument("--include-symptom", action="store_true", help="Include best-effort pseudonymized symptom text")
    export_parser.add_argument("--force", action="store_true", help="Overwrite an existing destination")
    export_parser.add_argument("--format", choices=("text", "json"), default="text", dest="output_format")
    return parser


def _normalize_legacy_argv(argv: Sequence[str]) -> list[str]:
    args = list(argv)
    commands = {"investigate", "validate-bundle", "export-sanitized", "-h", "--help", "--version"}
    if args and args[0] not in commands:
        return ["investigate", *args]
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args_list = _normalize_legacy_argv(sys.argv[1:] if argv is None else argv)
    args = _parser().parse_args(args_list)
    if args.command == "investigate":
        return _run_investigate(args.incident, args.output_format)
    if args.command == "validate-bundle":
        return _run_validate(args.bundle, args.output_format)
    if args.command == "export-sanitized":
        return _run_export_sanitized(
            args.bundle,
            args.output,
            include_symptom=args.include_symptom,
            force=args.force,
            output_format=args.output_format,
        )
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
