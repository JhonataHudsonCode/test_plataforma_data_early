from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import psycopg
from streamlit.testing.v1 import AppTest

from src.database import COLUMNS


def test_dashboard_shows_overview_and_validation_details(monkeypatch):
    for key, value in {
        "REPORT_DB_HOST": "localhost", "REPORT_DB_DATABASE": "reports",
        "REPORT_DB_USER": "reader", "REPORT_DB_PASSWORD": "fake-password",
    }.items():
        monkeypatch.setenv(key, value)
    row = {
        "run_id": "run-1", "project": "after", "environment": "prod",
        "started_at": datetime.now(timezone.utc), "finished_at": datetime.now(timezone.utc),
        "run_duration_ms": 2000, "run_status": "failed", "exit_code": 1,
        "scenario_id": 1, "test_name": "test_mapping", "title": "Validar mapping",
        "scenario_duration_ms": 1500, "pytest_status": "failed", "result_id": 1,
        "scope_type": "client", "client_id": "cliente-a", "scope_label": "cliente-a",
        "validation_type": "Mapping", "result_status": "failed", "message": "campo ausente",
        "raw_message": "[Mapping] campo ausente", "sequence": 1,
    }
    data = pd.DataFrame.from_records([
        row,
        {**row, "result_id": 2, "validation_type": "Timestamp", "message": "data válida", "sequence": 2},
        {**row, "result_id": 3, "validation_type": "Geral", "message": "índice encontrado", "sequence": 3},
    ], columns=COLUMNS)
    with patch("src.database.load_results", return_value=data) as query:
        app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=20).run()
        assert query.call_count == 0
        assert any("clique em Pesquisar" in info.value for info in app.info)
        next(button for button in app.button if button.label == "Pesquisar").click().run()
        assert query.call_count == 1
        assert not app.exception
        next(button for button in app.button if button.label == "Selecionar cenários").click().run()
        assert any(option.label == "Validar mapping" for option in app.checkbox)
        app.checkbox[0].check()
        next(button for button in app.button if button.label == "Confirmar seleção").click().run()
        assert query.call_count == 1
        assert any("1 cenário(s) selecionado(s)" in caption.value for caption in app.caption), ([c.value for c in app.caption], list(app.exception))
        next(widget for widget in app.multiselect if widget.label == "Projeto").set_value(["after"]).run()
        assert query.call_count == 1
        next(widget for widget in app.multiselect if widget.label == "Resultado da validação").set_value(["passed"])
        assert any(item.value == "Resultado das validações" for item in app.subheader)
        next(button for button in app.button if button.label == "Pesquisar").click().run()
        assert query.call_count == 2
        assert any("Nenhum resultado corresponde" in warning.value for warning in app.warning)
        next(widget for widget in app.multiselect if widget.label == "Resultado da validação").set_value([])
        assert query.call_count == 2
        next(button for button in app.button if button.label == "Pesquisar").click().run()
        assert query.call_count == 3
        assert app.selectbox[0].value == "Todas as validações"
        assert all(any(text in item.value for item in app.markdown) for text in
                   ("[Mapping] campo ausente", "[Timestamp] data válida", "[Geral] índice encontrado"))
        app.selectbox[0].set_value("Mapping").run()
        assert query.call_count == 3
        assert not any("data válida" in item.value for item in app.markdown)
        query.side_effect = [psycopg.OperationalError("falha simulada"), data]
        next(button for button in app.button if button.label == "Pesquisar").click().run()
        assert any("Não foi possível consultar" in error.value for error in app.error)
        assert not next(button for button in app.button if button.label == "Pesquisar").disabled
        next(button for button in app.button if button.label == "Pesquisar").click().run()
        assert query.call_count == 5
    assert not app.exception
    assert [tab.label for tab in app.tabs] == ["Visão geral", "Índices", "Validações"]
    assert any(item.value == "Resultado das validações" for item in app.subheader)
    assert any(metric.label == "Bateria completa · After" and metric.value == "00:00:02.00" for metric in app.metric)
    headings = {item.value for item in app.subheader}
    assert {"Falhas por tipo de validação", "Clientes com mais falhas", "Evolução das falhas por dia",
            "Validações por cenário"} <= headings
    assert "Early × After" not in headings
    assert "Duração média por cenário" not in headings
    assert any(expander.label == "cliente-a" for expander in app.expander)
    assert any("campo ausente" in markdown.value for markdown in app.markdown)


def test_index_view_displays_failures_and_successes_for_all_clients(monkeypatch):
    for key, value in {"REPORT_DB_HOST": "localhost", "REPORT_DB_DATABASE": "reports", "REPORT_DB_USER": "reader", "REPORT_DB_PASSWORD": "fake"}.items():
        monkeypatch.setenv(key, value)
    base = {"run_id": "r1", "project": "after", "environment": "prod", "started_at": datetime.now(timezone.utc), "finished_at": datetime.now(timezone.utc), "run_duration_ms": 1000, "run_status": "failed", "exit_code": 1, "scenario_id": 1, "test_name": "test_asset", "title": "Teste asset", "scenario_duration_ms": 1000, "pytest_status": "failed", "scope_type": "client", "validation_type": "Geral", "sequence": 1}
    data = pd.DataFrame.from_records([
        {**base, "result_id": 1, "client_id": "a", "scope_label": "a", "result_status": "failed", "message": "Índice 'a_asset' não encontrado."},
        {**base, "result_id": 2, "client_id": "b", "scope_label": "b", "result_status": "passed", "message": "Índice 'b_asset' encontrado."},
        {**base, "result_id": 3, "client_id": "b", "scope_label": "b", "result_status": "passed", "message": "Índice 'b_score' encontrado."},
    ], columns=COLUMNS)
    with patch("src.database.load_results", return_value=data) as query:
        app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=20).run()
        next(button for button in app.button if button.label == "Pesquisar").click().run()
        assert [tab.label for tab in app.tabs] == ["Visão geral", "Índices", "Validações"]
        next(widget for widget in app.multiselect if widget.label == "Filtrar índices").set_value(["asset"]).run()
        assert not any(button.label == "Ver falhas · score" for button in app.button)
        next(button for button in app.button if button.label == "Ver falhas · asset").click().run()
        assert any(header.value == "Falhas do índice: asset" for header in app.subheader)
        assert any(expander.label == "a" for expander in app.expander)
        assert not any(expander.label == "b" for expander in app.expander)
        next(button for button in app.button if button.label == "← Voltar aos índices").click().run()
        assert next(widget for widget in app.multiselect if widget.label == "Filtrar índices").value == ["asset"]
        app.radio[0].set_value("Por índice").run()
        assert not app.exception
        assert app.selectbox[0].value == "asset"
        assert {expander.label for expander in app.expander} >= {"a", "b"}
        assert query.call_count == 1


def test_indicator_buttons_open_details_and_return_without_query(monkeypatch):
    for key, value in {"REPORT_DB_HOST": "localhost", "REPORT_DB_DATABASE": "reports", "REPORT_DB_USER": "reader", "REPORT_DB_PASSWORD": "fake"}.items():
        monkeypatch.setenv(key, value)
    base = {"run_id": "r1", "project": "after", "environment": "prod", "started_at": datetime.now(timezone.utc), "finished_at": datetime.now(timezone.utc), "run_duration_ms": 1000, "run_status": "failed", "exit_code": 1, "scenario_id": 1, "test_name": "test_asset", "title": "Teste asset", "scenario_duration_ms": 1000, "pytest_status": "failed", "scope_type": "client", "client_id": "cliente-a", "scope_label": "cliente-a", "result_status": "failed", "sequence": 1}
    data = pd.DataFrame.from_records([
        {**base, "result_id": 1, "validation_type": "Geral", "message": "Índice 'asset' não encontrado."},
        {**base, "result_id": 2, "validation_type": "Comparação percentual", "message": "Índice 'asset' | variação acima de 50%."},
        {**base, "result_id": 3, "validation_type": "Timestamp", "message": "Índice 'asset' não retornou documentos em 2026-11-04."},
    ], columns=COLUMNS)
    with patch("src.database.load_results", return_value=data) as query:
        app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=20).run()
        next(button for button in app.button if button.label == "Pesquisar").click().run()
        for label in ("Índices não encontrados", "Índices com falha na comparação percentual", "Índices sem documentos encontrados"):
            next(button for button in app.button if button.label == f"{label}: 1").click().run()
            assert not app.exception
            assert any(header.value == label for header in app.subheader)
            assert len(app.dataframe) == 1
            table = app.dataframe[0].value
            assert table.iloc[0]["Índice"] == "asset"
            assert table.iloc[0]["Cliente ou origem"] == "cliente-a"
            next(button for button in app.button if "Voltar à visão geral" in button.label).click().run()
        assert query.call_count == 1


def test_complete_run_uses_most_scenarios_then_most_recent(monkeypatch):
    for key, value in {"REPORT_DB_HOST": "localhost", "REPORT_DB_DATABASE": "reports", "REPORT_DB_USER": "reader", "REPORT_DB_PASSWORD": "fake"}.items():
        monkeypatch.setenv(key, value)
    base = {"project": "early", "environment": "prod", "finished_at": datetime.now(timezone.utc), "run_status": "passed", "exit_code": 0, "test_name": "test_asset", "title": "Teste", "scenario_duration_ms": 1000, "pytest_status": "passed", "scope_type": "client", "client_id": "a", "scope_label": "a", "result_status": "passed", "validation_type": "Geral", "message": "ok", "sequence": 1}
    records = [
        {**base, "run_id": "older", "started_at": "2026-10-01T12:00:00Z", "run_duration_ms": 10000, "scenario_id": 1, "result_id": 1},
        {**base, "run_id": "older", "started_at": "2026-10-01T12:00:00Z", "run_duration_ms": 10000, "scenario_id": 2, "result_id": 2},
        {**base, "run_id": "latest_full", "started_at": "2026-10-02T12:00:00Z", "run_duration_ms": 20000, "scenario_id": 3, "result_id": 3},
        {**base, "run_id": "latest_full", "started_at": "2026-10-02T12:00:00Z", "run_duration_ms": 20000, "scenario_id": 4, "result_id": 4},
        {**base, "run_id": "partial", "started_at": "2026-10-03T12:00:00Z", "run_duration_ms": 5000, "scenario_id": 5, "result_id": 5},
    ]
    with patch("src.database.load_results", return_value=pd.DataFrame.from_records(records, columns=COLUMNS)):
        app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=20).run()
        next(button for button in app.button if button.label == "Pesquisar").click().run()
        assert not app.exception
        assert any(metric.label == "Bateria completa · Early" and metric.value == "00:00:20.00" for metric in app.metric)
