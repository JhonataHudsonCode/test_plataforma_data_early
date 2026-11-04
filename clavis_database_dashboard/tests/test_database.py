from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.database import DatabaseSettings, load_filter_options, load_results


def test_query_uses_read_only_connection_and_parameterized_dates():
    settings = DatabaseSettings("localhost", 5432, "reports", "reader", "secret", "qa_reports")
    connection = MagicMock()
    active_connection = connection.__enter__.return_value
    cursor = active_connection.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = []
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 2, 1, tzinfo=timezone.utc)
    with patch("src.database.psycopg.connect", return_value=connection) as connect:
        result = load_results(settings, start, end)
    assert active_connection.read_only is True
    assert cursor.execute.call_args.args[1] == (start, end)
    assert connect.call_args.kwargs["dbname"] == "reports"
    assert result.empty
    assert "secret" not in repr(settings)


def test_missing_credentials_produce_actionable_error(monkeypatch):
    monkeypatch.setenv("REPORT_DB_HOST", "localhost")
    monkeypatch.delenv("REPORT_DB_DATABASE", raising=False)
    with patch("src.database.load_dotenv"):
        with pytest.raises(ValueError, match="REPORT_DB_DATABASE"):
            DatabaseSettings.from_env()


def test_filter_options_are_loaded_once_with_read_only_connection():
    settings = DatabaseSettings("localhost", 5432, "reports", "reader", "secret", "qa_reports")
    connection = MagicMock()
    active = connection.__enter__.return_value
    cursor = active.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = [
        {"kind": "client_id", "value": "Cliente B"}, {"kind": "client_id", "value": "cliente a"},
        {"kind": "project", "value": "after"}, {"kind": "title", "value": "Cenário"},
    ]
    with patch("src.database.psycopg.connect", return_value=connection):
        options = load_filter_options(settings)
    assert active.read_only is True
    assert cursor.execute.call_count == 1
    assert options["client_id"] == ["cliente a", "Cliente B"]
    assert options["title"] == ["Cenário"]
    assert options["environment"] == []
