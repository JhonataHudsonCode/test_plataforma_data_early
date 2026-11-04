import json
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.services.client_validation_report import ClientValidationReport
from src.services.report_database import parse_report, persist_session_reports
from src.validators.after_pipeline.product_data_validator import ProductDataValidator, _CategorizedMessages
from src.validators.after_pipeline.historical_vulnerability_validator import HistoricalVulnerabilityValidator
from src.validators.after_pipeline.oto_dashboard.asset_data_validator import OtoAssetDataValidator


def test_structured_totals_survive_report_and_insert(tmp_path, monkeypatch):
    validator = ProductDataValidator(None, None, reference_date=date(2026, 11, 4))
    errors, details = [], []
    validator._validate_fifty_percent_variation("acme_asset", (("total_open", 17, 10),),
        _CategorizedMessages(errors, "Comparação percentual"), _CategorizedMessages(details, "Comparação percentual"))
    report = ClientValidationReport()
    report.add_client_result("acme", failures=errors, details=details)
    path = tmp_path / "test_a.txt"
    report.write(path, "Teste A", "BDD")
    parsed = parse_report(path.read_text(encoding="utf-8"))
    metadata = json.loads(path.with_suffix(".structured.json").read_text(encoding="utf-8"))
    assert len(parsed["results"]) == 1
    assert metadata["1"]["previous_value"] == 10
    assert metadata["1"]["current_value"] == 17
    assert metadata["1"]["index_type"] == "asset"
    assert metadata["1"]["variation_percent"] == 70
    for key, value in {"REPORT_DB_ENABLED": "true", "REPORT_DB_HOST": "db", "REPORT_DB_DATABASE": "qa", "REPORT_DB_USER": "u", "REPORT_DB_PASSWORD": "p"}.items():
        monkeypatch.setenv(key, value)
    config = SimpleNamespace(_report_db_outcomes={"test_a.py::test_a": {"node_id": "test_a.py::test_a", "duration_ms": 1, "status": "failed"}}, getoption=lambda *args, **kwargs: False)
    session = SimpleNamespace(config=config, _validation_started_at=0, _report_db_started_at=datetime.now(timezone.utc))
    connection = MagicMock()
    cursor = connection.__enter__.return_value.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (123,)
    with patch("src.services.report_database.psycopg.connect", return_value=connection):
        persist_session_reports(session, 1, "after", [path])
    row = cursor.executemany.call_args.args[1][0]
    assert row[9:15] == ("acme_asset", "asset", "total_open", 10, 17, 70)
    assert row[19:22] == ("2026-11-03", "2026-11-04", "PERCENTAGE_LIMIT_EXCEEDED")


def test_historical_keeps_precise_values_in_metadata():
    validator = HistoricalVulnerabilityValidator(None, None, date(2026, 11, 4))
    failures, details = [], []
    previous = {field: 1.0 for field in validator._PERCENTAGE_FIELDS}
    current = {**previous, "total_open": 2.5}
    validator._run_stage("Comparação percentual", failures, details, lambda: validator._validate_percentage_variation(
        "acme_vulnerability-historical", [{"_source": current}],
        [{"_source": previous}], failures, details))
    assert failures[0].metadata["previous_value"] == 1.0
    assert failures[0].metadata["current_value"] == 2.5
    assert failures[0].startswith("[Comparação percentual]")


def test_oto_captures_independent_increase_and_decrease_limits():
    controller = MagicMock()
    controller.limits_for.return_value = SimpleNamespace(maximum_increase=0.5, maximum_decrease=0.3)
    controller.validate_percentage_variation.return_value = SimpleNamespace(variation=-0.6, is_valid=False, reason="redução")
    validator = OtoAssetDataValidator(date(2026, 11, 4), variation_controller=controller)
    failures, details = [], []
    validator._validate_variation("acme_oto", "asset.score", 4.0, 10.0, "score", failures, details)
    assert failures[0].metadata["max_increase_percent"] == 50
    assert failures[0].metadata["max_decrease_percent"] == 30
    assert failures[0].metadata["comparison_direction"] == "decrease"
    assert failures[0].metadata["comparison_limit_percent"] == 30


def test_metadata_follows_report_order_for_multiple_clients_and_statuses(tmp_path):
    validator = ProductDataValidator(None, None, reference_date=date(2026, 11, 4))
    errors, details = [], []
    validator._validate_fifty_percent_variation("beta_asset", (("total_open", 5, 10),),
        _CategorizedMessages(errors, "Comparação percentual"), _CategorizedMessages(details, "Comparação percentual"))
    report = ClientValidationReport()
    report.add_client_result("acme", failures=["[Geral] erro comum"])
    report.add_client_result("beta", details=details)
    path = tmp_path / "test_a.txt"
    report.write(path, "Teste", "BDD")
    metadata = json.loads(path.with_suffix(".structured.json").read_text(encoding="utf-8"))
    parsed = parse_report(path.read_text(encoding="utf-8"))["results"]
    assert metadata["2"]["index_name"] == "beta_asset"
    assert parsed[1]["client_id"] == "beta"
    assert parsed[1]["status"] == "passed"


def test_oto_pair_comparison_preserves_metadata_until_database(tmp_path, monkeypatch):
    controller = MagicMock()
    controller.limits_for.return_value = SimpleNamespace(maximum_increase=0.5, maximum_decrease=0.3)
    controller.validate_percentage_variation.return_value = SimpleNamespace(variation=-0.6, is_valid=False, reason="redução")
    oto = OtoAssetDataValidator(date(2026, 11, 4), variation_controller=controller)
    validator = ProductDataValidator(MagicMock(), MagicMock(), date(2026, 11, 4))
    validator._validate_oto_dashboard_metrics = lambda index, current, previous, errors, details: oto._validate_variation(index, "asset_data.score", 4.0, 10.0, "score", errors, details)
    current = [{"_id": "today", "_source": {"@timestamp": "2026-11-04T10:00:00Z"}}]
    previous = [{"_id": "yesterday", "_source": {"@timestamp": "2026-11-03T10:10:00Z"}}]
    errors, details = [], []
    validator._run_validation_stage("Comparação percentual", errors, details, lambda e, d: validator._compare_oto_document_pairs("acme_oto_dashboard", current, previous, e, d))
    report = ClientValidationReport()
    report.add_client_result("acme", failures=errors, details=details)
    path = tmp_path / "test_oto.txt"
    report.write(path, "OTO", "BDD")
    metadata = json.loads(path.with_suffix(".structured.json").read_text(encoding="utf-8"))
    parsed = parse_report(path.read_text(encoding="utf-8"))["results"]
    structured_rows = [(parsed[int(sequence) - 1], value) for sequence, value in metadata.items()]
    assert {row[0]["status"] for row in structured_rows} == {"failed", "passed"}
    assert all(row[1]["attribute_name"] == "asset_data.score" for row in structured_rows)
    assert all(row[1]["previous_value"] == 10.0 and row[1]["current_value"] == 4.0 for row in structured_rows)
    for key, value in {"REPORT_DB_ENABLED": "true", "REPORT_DB_HOST": "db", "REPORT_DB_DATABASE": "qa", "REPORT_DB_USER": "u", "REPORT_DB_PASSWORD": "p"}.items():
        monkeypatch.setenv(key, value)
    config = SimpleNamespace(_report_db_outcomes={"test_oto.py::test_oto": {"node_id": "test_oto.py::test_oto", "duration_ms": 1, "status": "failed"}}, getoption=lambda *args, **kwargs: False)
    session = SimpleNamespace(config=config, _validation_started_at=0, _report_db_started_at=datetime.now(timezone.utc))
    connection = MagicMock()
    cursor = connection.__enter__.return_value.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (123,)
    with patch("src.services.report_database.psycopg.connect", return_value=connection):
        persist_session_reports(session, 1, "after", [path])
    rows = cursor.executemany.call_args.args[1]
    assert [row[11] for row in rows].count("asset_data.score") == 2
