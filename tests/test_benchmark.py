from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import gputriage.benchmark as benchmark
import gputriage.benchmark_eval as benchmark_eval
from gputriage.models import HypothesisStatus


ROOT = Path(__file__).resolve().parents[1]


def _result(*, status=HypothesisStatus.POSSIBLE, next_test=None, verdict=None):
    hypothesis = SimpleNamespace(
        id="dummy",
        status=status,
        supporting_evidence=[],
        contradicting_evidence=[],
    )
    diagnostic = SimpleNamespace(id=next_test) if next_test else None
    return SimpleNamespace(hypotheses=[hypothesis], next_best_test=diagnostic, verdict=verdict)


def test_manifest_and_frozen_split_counts():
    manifest = json.loads((ROOT / "data/benchmark_manifest_v0.1.json").read_text())
    holdout = json.loads(benchmark._read_corpus_bytes(ROOT / "data/benchmark_holdout_v0.1.json.gz").decode("utf-8"))

    assert manifest["scenario_count"] == 30
    assert manifest["public_source_incident_count"] == 21
    assert manifest["mutation_count"] == 9
    assert manifest["development_count"] == 18
    assert manifest["frozen_holdout_count"] == 12
    assert len(holdout["cases"]) == 12
    assert all(case["split"] == "frozen_holdout" for case in holdout["cases"])


def test_holdout_freeze_matches_bytes():
    corpus = ROOT / "data/benchmark_holdout_v0.1.json.gz"
    freeze = ROOT / "data/benchmark_holdout_v0.1.freeze.json"
    metadata = json.loads(freeze.read_text())

    assert benchmark.verify_freeze(corpus, freeze)
    assert hashlib.sha256(benchmark._read_corpus_bytes(corpus)).hexdigest() == metadata["sha256"]


def test_freeze_detects_mutated_corpus(tmp_path):
    corpus = tmp_path / "holdout.json"
    corpus.write_text('{"cases": []}\n')
    freeze = tmp_path / "freeze.json"
    freeze.write_text(json.dumps({"sha256": hashlib.sha256(corpus.read_bytes()).hexdigest()}))
    assert benchmark.verify_freeze(corpus, freeze)

    corpus.write_text('{"cases": [{"id": "changed"}]}\n')
    assert not benchmark.verify_freeze(corpus, freeze)


def test_abstention_is_not_scored_as_next_test_utility(monkeypatch):
    monkeypatch.setattr(benchmark_eval, "investigate", lambda symptom, observations: _result())
    payload = {
        "cases": [
            {
                "id": "abstain",
                "split": "test",
                "symptom": "unknown",
                "stages": [
                    {
                        "name": "T1",
                        "add_observations": [],
                        "expect_abstention": True,
                        "next_test_utility": {"*": 0},
                    }
                ],
            }
        ]
    }

    report = benchmark.evaluate_payload(payload)
    assert report.abstention_checks == 1
    assert report.abstention_hits == 1
    assert report.next_test_checks == 0


def test_premature_confirmation_is_a_safety_failure(monkeypatch):
    monkeypatch.setattr(
        benchmark_eval,
        "investigate",
        lambda symptom, observations: _result(status=HypothesisStatus.CONFIRMED, verdict="dummy"),
    )
    payload = {
        "cases": [
            {
                "id": "premature",
                "split": "test",
                "symptom": "unknown",
                "stages": [{"name": "T1", "add_observations": []}],
            }
        ]
    }

    report = benchmark.evaluate_payload(payload)
    assert report.premature_confirmations == 1
    assert benchmark._gate_failed(report, safety_only=True)


def test_forbidden_hypothesis_is_quality_not_safety_gate(monkeypatch):
    monkeypatch.setattr(
        benchmark_eval,
        "investigate",
        lambda symptom, observations: _result(status=HypothesisStatus.SUPPORTED),
    )
    payload = {
        "cases": [
            {
                "id": "red-herring",
                "split": "test",
                "symptom": "unknown",
                "forbidden_hypotheses": ["dummy"],
                "stages": [{"name": "T1", "add_observations": []}],
            }
        ]
    }

    report = benchmark.evaluate_payload(payload)
    assert report.forbidden_hypothesis_errors == 1
    assert not benchmark._gate_failed(report, safety_only=True)
    assert benchmark.evaluate_gates(report)["forbidden_hypothesis_error_rate"]["status"] == "fail"
