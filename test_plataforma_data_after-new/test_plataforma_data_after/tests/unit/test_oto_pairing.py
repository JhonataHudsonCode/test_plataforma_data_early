from datetime import date, timedelta
from unittest.mock import MagicMock

from src.validators.after_pipeline.product_data_validator import ProductDataValidator


def doc(identifier, timestamp):
    return {"_id": identifier, "_index": "acme_oto_dashboard", "_source": {"@timestamp": timestamp}}


def test_pairs_two_today_with_nearest_of_four_yesterday():
    today = [doc("t1", "2026-10-29T08:15:00Z"), doc("t2", "2026-10-29T15:00:00Z")]
    yesterday = [doc("y1", "2026-10-28T08:00:00Z"), doc("y2", "2026-10-28T10:00:00Z"),
                 doc("y3", "2026-10-28T15:20:00Z"), doc("y4", "2026-10-28T20:00:00Z")]
    pairs, current_unmatched, previous_unmatched, invalid = ProductDataValidator._match_oto_documents(today, yesterday)
    assert [(a["_id"], b["_id"]) for a, b, _ in pairs] == [("t1", "y1"), ("t2", "y3")]
    assert [item["_id"] for item in previous_unmatched] == ["y2", "y4"]
    assert not current_unmatched and not invalid


def test_maximizes_unique_pairs_instead_of_greedy_nearest():
    today = [doc("t1", "2026-10-29T10:00:00Z"), doc("t2", "2026-10-29T10:50:00Z")]
    yesterday = [doc("y1", "2026-10-28T09:10:00Z"), doc("y2", "2026-10-28T10:05:00Z")]
    pairs, _, _, _ = ProductDataValidator._match_oto_documents(today, yesterday)
    assert [(a["_id"], b["_id"]) for a, b, _ in pairs] == [("t1", "y1"), ("t2", "y2")]


def test_tolerance_boundary_timezone_and_invalid_values():
    today = [doc("t1", "2026-10-29T12:00:00+00:00"), doc("bad", "2026-10-29")]
    yesterday = [doc("y1", "2026-10-28T08:00:00-03:00"), doc("y2", "2026-10-28T15:00:00Z")]
    pairs, _, unmatched, invalid = ProductDataValidator._match_oto_documents(today, yesterday)
    assert len(pairs) == 1 and pairs[0][2] == timedelta(hours=1)
    assert [d["_id"] for d in unmatched] == ["y2"]
    assert invalid == [("hoje", "bad")]


def test_exact_index_and_each_pair_reported():
    repo = MagicMock()
    repo.get_documents_by_date_match.side_effect = [
        [doc("t1", "2026-10-29T08:00:00Z"), doc("t2", "2026-10-29T15:00:00Z")],
        [doc("y1", "2026-10-28T08:30:00Z"), doc("y2", "2026-10-28T15:15:00Z"), doc("extra", "2026-10-28T22:00:00Z")],
    ]
    validator = ProductDataValidator(repo, MagicMock(), date(2026, 10, 29))
    validator._validate_mappings_for_documents = MagicMock()
    validator._validate_oto_dashboard_metrics = MagicMock()
    errors, details = [], []
    validator._validate_dated_oto_dashboard_indices("acme", errors, details)
    assert all(call.args[0] == "acme_oto_dashboard" for call in repo.get_documents_by_date_match.call_args_list)
    assert validator._validate_oto_dashboard_metrics.call_count == 2
    assert not errors
    assert any("hoje _id=t1" in line and "ontem _id=y1" in line for line in details)
    assert any("sem par" in line and "extra" in line for line in details)


def test_no_matching_pair_is_failure_not_success():
    validator = ProductDataValidator(MagicMock(), MagicMock(), date(2026, 10, 29))
    validator._validate_oto_dashboard_metrics = MagicMock()
    errors, details = [], []
    validator._compare_oto_document_pairs("idx", [doc("t", "2026-10-29T08:00:00Z")],
        [doc("y", "2026-10-28T10:00:01Z")], errors, details)
    assert errors and "nenhum par" in errors[-1]
    validator._validate_oto_dashboard_metrics.assert_not_called()
