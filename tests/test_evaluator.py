from pathlib import Path

from gputriage.evaluator import evaluate_file


def test_staged_corpus_replays_without_future_evidence_leaks():
    corpus = Path(__file__).parents[1] / "data" / "staged_incidents_v0.1.json"
    report = evaluate_file(corpus)

    assert report.cases == 7
    assert report.checked_stages == 21
    assert report.next_test_checks == 14
    assert report.next_test_hits == 14
    assert report.premature_confirmations == 0
    assert report.final_confirmation_checks == 7
    assert report.final_confirmation_hits == 7
    assert report.failures == []
