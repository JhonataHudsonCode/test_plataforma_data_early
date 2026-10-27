from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.services.report_database import _duration_ms, parse_report, persist_session_reports, record_pytest_outcome


def test_parse_report_preserves_status_categories_and_global_scope():
    report = parse_report("""Teste: Cenário A
Ambiente: prod
Duração: 0:00:01.250000

BDD:
Dado um cliente

Falhas (1):
- Cliente: cliente_a
  Motivo: [Mapping] campo inválido
Aprovados (1):
- Cliente: cliente_a
  Detalhe: [Timestamp] válido
Informativos (1):
- Cliente: OpenSearch central
  Informação: sem dados
""")
    assert report["duration_ms"] == 1250
    assert report["bdd"] == "Dado um cliente"
    assert [(item["validation_type"], item["status"]) for item in report["results"]] == [
        ("Mapping", "failed"), ("Timestamp", "passed"), ("Geral", "info")
    ]
    assert report["results"][0]["client_id"] == "cliente_a"
    assert report["results"][2]["client_id"] is None
    assert report["results"][2]["scope_type"] == "environment"


def test_duration_does_not_invent_value():
    assert _duration_ms("1 day, 0:00:01.500000") == 86401500
    assert _duration_ms("desconhecida") is None


def test_pytest_failure_is_not_overwritten_by_teardown():
    outcomes = {}
    for when, failed in (("setup", False), ("call", True), ("teardown", False)):
        record_pytest_outcome(outcomes, SimpleNamespace(nodeid="test_a.py::test_a", duration=0.1,
            failed=failed, skipped=False, when=when))
    assert outcomes["test_a.py::test_a"]["status"] == "failed"
    assert outcomes["test_a.py::test_a"]["duration_ms"] == 300


def test_session_writes_one_transaction_and_uses_dedicated_settings(tmp_path, monkeypatch):
    for name, value in {"REPORT_DB_ENABLED": "true", "REPORT_DB_HOST": "db",
                        "REPORT_DB_DATABASE": "qa", "REPORT_DB_USER": "user",
                        "REPORT_DB_PASSWORD": "secret", "REPORT_DB_SCHEMA": "qa_reports"}.items():
        monkeypatch.setenv(name, value)
    path = tmp_path / "test_a.txt"
    path.write_text("Teste: A\nDuração: 0:00:01\nBDD:\nDado\nFalhas (1):\n- Cliente: c1\n  [Mapping] erro\n", encoding="utf-8")
    config = SimpleNamespace(_report_db_outcomes={"test_a.py::test_a": {"node_id": "test_a.py::test_a", "duration_ms": 123, "status": "failed"}}, getoption=lambda *a, **kw: False)
    session = SimpleNamespace(config=config, _validation_started_at=0, _report_db_started_at=datetime.now(timezone.utc))
    connection = MagicMock()
    cursor = connection.__enter__.return_value.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (42,)
    with patch("src.services.report_database.psycopg.connect", return_value=connection) as connect:
        persist_session_reports(session, 1, "early", [path])
    assert connect.call_args.kwargs["dbname"] == "qa"
    assert cursor.execute.call_count == 2
    assert cursor.executemany.call_args.args[1][0][0] == 42


def test_disabled_or_collect_only_never_connects(monkeypatch):
    monkeypatch.setenv("REPORT_DB_ENABLED", "false")
    session = SimpleNamespace(config=SimpleNamespace(getoption=lambda *a, **kw: True))
    with patch("src.services.report_database.psycopg.connect") as connect:
        persist_session_reports(session, 0, "after", [])
        connect.assert_not_called()
