from pathlib import Path

from gputriage.evaluator import evaluate_file


def test_holdout_smoke_set_tracks_generalization_and_abstention():
    corpus = Path(__file__).parents[1] / "data" / "holdout_incidents_v0.1.json"
    report = evaluate_file(corpus)

    assert report.failures == []
    assert report.by_split["holdout"].cases == 2
    assert report.by_split["holdout"].next_test_hits == 4
    assert report.by_split["holdout"].final_confirmation_hits == 2
    assert report.by_split["holdout-gap"].abstention_checks == 2
    assert report.by_split["holdout-gap"].abstention_hits == 2
    assert report.premature_confirmations == 0
