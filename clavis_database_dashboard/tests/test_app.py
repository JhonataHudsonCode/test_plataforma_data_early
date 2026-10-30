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
    data = pd.DataFrame.from_records([row], columns=COLUMNS)
    with patch("src.database.load_results", return_value=data) as query:
        app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=20).run()
        assert query.call_count == 0
        assert any("clique em Pesquisar" in info.value for info in app.info)
        app.button[0].click().run()
        assert query.call_count == 1
        assert not app.exception
        app.multiselect[0].set_value(["after"]).run()
        assert query.call_count == 1
        app.multiselect[5].set_value(["passed"])
        assert any(metric.label == "Validações com falha" for metric in app.metric)
        app.button[0].click().run()
        assert query.call_count == 2
        assert any("Nenhum resultado corresponde" in warning.value for warning in app.warning)
        app.multiselect[5].set_value([])
        assert query.call_count == 2
        app.button[0].click().run()
        assert query.call_count == 3
        app.selectbox[0].set_value("Mapping").run()
        assert query.call_count == 3
        query.side_effect = [psycopg.OperationalError("falha simulada"), data]
        app.button[0].click().run()
        assert any("Não foi possível consultar" in error.value for error in app.error)
        assert not app.button[0].disabled
        app.button[0].click().run()
        assert query.call_count == 5
    assert not app.exception
    assert [tab.label for tab in app.tabs] == ["Visão geral", "Validações"]
    assert any(metric.label == "Validações com falha" and metric.value == "1" for metric in app.metric)
    assert any(expander.label == "cliente-a" for expander in app.expander)
    assert any("campo ausente" in markdown.value for markdown in app.markdown)
