import pandas as pd

from src.analysis import apply_filters, format_duration, scenario_summary, summarize


def sample():
    return pd.DataFrame([
        {"run_id": "r1", "scenario_id": 1, "result_id": 1, "scope_type": "client", "scope_label": "a", "client_id": "a", "validation_type": "Mapping", "result_status": "failed", "project": "early", "environment": "prod", "started_at": "2026-10-27", "title": "Teste A", "test_name": "test_a", "pytest_status": "failed", "scenario_duration_ms": 1500},
        {"run_id": "r1", "scenario_id": 1, "result_id": 2, "scope_type": "client", "scope_label": "a", "client_id": "a", "validation_type": "Mapping", "result_status": "failed", "project": "early", "environment": "prod", "started_at": "2026-10-27", "title": "Teste A", "test_name": "test_a", "pytest_status": "failed", "scenario_duration_ms": 1500},
        {"run_id": "r1", "scenario_id": 1, "result_id": 3, "scope_type": "client", "scope_label": "a", "client_id": "a", "validation_type": "Timestamp", "result_status": "passed", "project": "early", "environment": "prod", "started_at": "2026-10-27", "title": "Teste A", "test_name": "test_a", "pytest_status": "failed", "scenario_duration_ms": 1500},
        {"run_id": "r1", "scenario_id": 2, "result_id": None, "scope_type": None, "scope_label": None, "client_id": None, "validation_type": None, "result_status": None, "project": "early", "environment": "prod", "started_at": "2026-10-27", "title": "Teste B", "test_name": "test_b", "pytest_status": "skipped", "scenario_duration_ms": None},
    ])


def test_summary_counts_stages_not_duplicate_messages_and_keeps_skipped_scenario():
    assert summarize(sample()) == {"runs": 1, "scenarios": 2, "clients": 1, "failed": 1, "passed": 1, "info": 0}
    assert len(scenario_summary(sample())) == 2


def test_filters_allow_same_client_in_failed_and_passed_categories():
    filtered = apply_filters(sample(), {"client_id": ["a"], "result_status": ["passed"]})
    assert len(filtered) == 1
    assert filtered.iloc[0]["validation_type"] == "Timestamp"


def test_duration_and_missing_values():
    assert format_duration(61500) == "00:01:01.50"
    assert format_duration(None) == "Não informada"
