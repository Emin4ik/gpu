from __future__ import annotations

import argparse
import json
from pathlib import Path

from .benchmark_eval import evaluate_file, evaluate_payload, read_corpus_bytes, verify_freeze
from .benchmark_types import BenchmarkCounters, BenchmarkReport, evaluate_gates, gate_failed

# Kept as a small public facade so callers and tests do not depend on the
# internal module split.
_read_corpus_bytes = read_corpus_bytes
_gate_failed = gate_failed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the frozen GPU Triage benchmark without exposing future-stage evidence"
    )
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--freeze", type=Path, help="Freeze metadata containing the SHA256 of this corpus")
    parser.add_argument("--enforce-safety", action="store_true", help="Fail only on freeze mismatch or safety gates")
    parser.add_argument("--enforce-gates", action="store_true", help="Fail when any measured project gate is below threshold")
    args = parser.parse_args()

    report = evaluate_file(args.corpus)
    if args.freeze:
        report.freeze_verified = verify_freeze(args.corpus, args.freeze)
    print(json.dumps(report.as_dict(), indent=2, sort_keys=True))

    if args.enforce_gates and gate_failed(report, safety_only=False):
        raise SystemExit(1)
    if args.enforce_safety and gate_failed(report, safety_only=True):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
