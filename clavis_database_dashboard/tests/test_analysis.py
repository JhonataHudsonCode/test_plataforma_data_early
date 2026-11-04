from zoneinfo import ZoneInfo

import pandas as pd

from src.analysis import apply_filters, empty_index_date_details, format_duration, index_results, missing_index_details, scenario_summary, summarize


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


def test_scenarios_and_clients_are_distinct_across_runs_and_projects():
    first = sample().iloc[0].to_dict()
    repeated = {**first, "run_id": "r2", "scenario_id": 3, "result_id": 4, "started_at": "2026-10-28"}
    another_project = {**repeated, "scenario_id": 4, "result_id": 5, "project": "after"}
    another_client = {**repeated, "result_id": 6, "client_id": "b", "scope_label": "b"}
    result = summarize(pd.DataFrame([first, repeated, another_project, another_client]))
    assert result["runs"] == 2
    assert result["scenarios"] == 2
    assert result["clients"] == 2


def test_duration_and_missing_values():
    assert format_duration(61500) == "00:01:01.50"
    assert format_duration(None) == "Não informada"


def test_missing_indexes_count_only_explicit_failures_once_per_client():
    base = sample().iloc[0].to_dict()
    records = [
        {**base, "message": "Índice 'cliente_asset' não encontrado."},
        {**base, "run_id": "r2", "scenario_id": 4, "message": "Índice 'cliente_asset' não encontrado."},
        {**base, "message": "Índice 'cliente_asset' não retornou documentos com @timestamp em 2026-10-27."},
        {**base, "result_status": "passed", "message": "Índice 'outro' não encontrado."},
        {**base, "scope_label": "b", "message": "Índice 'cliente_asset' não encontrado."},
    ]
    assert len(missing_index_details(pd.DataFrame(records))) == 2


def test_empty_index_dates_use_each_execution_and_ignore_unrelated_failures():
    base = {**sample().iloc[0].to_dict(), "started_at": "2026-10-28T15:00:00Z"}
    frame = pd.DataFrame([
        {**base, "message": "Índice 'asset' não retornou documentos com date em 2026-10-28."},
        {**base, "message": "Índice 'asset' não retornou documentos com date em 2026-10-27."},
        {**base, "message": "Índice 'asset' não retornou documentos com date em 2026-10-27."},
        {**base, "result_status": "passed", "message": "Índice 'other' | consulta retornou 0 documento(s) em 2026-10-28 e 3 em 2026-10-27."},
        {**base, "result_status": "passed", "message": "Índice 'other' | consulta retornou 2 documento(s) em 2026-10-28 e 0 em 2026-10-27."},
        {**base, "message": "Índice 'ignored' não retornou documentos com date em 2026-10-20."},
        {**base, "message": "Índice 'failed_query' | erro ao consultar documentos em 2026-10-28."},
    ])
    result = empty_index_date_details(frame, ZoneInfo("America/Sao_Paulo"))
    assert set(zip(result["index_name"], result["date_role"])) == {("asset", "Hoje"), ("asset", "Ontem"), ("other", "Hoje"), ("other", "Ontem")}


def test_index_view_groups_client_prefix_and_preserves_distinct_results():
    base = sample().iloc[0].to_dict()
    frame = pd.DataFrame([
        {**base, "client_id": "a", "message": "Índice 'a_asset' não encontrado."},
        {**base, "client_id": "b", "scope_label": "b", "result_status": "passed", "message": "Índice 'b_asset' encontrado."},
        {**base, "message": "Falha sem nome do índice."},
        {**base, "message": "Índice não encontrado."},
    ])
    selected = index_results(frame)
    assert list(selected["index_family"]) == ["asset", "asset"]
    assert set(selected["result_status"]) == {"passed", "failed"}
    assert set(selected["client_id"]) == {"a", "b"}
