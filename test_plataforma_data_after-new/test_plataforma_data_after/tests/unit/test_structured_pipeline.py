import json
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.services.client_validation_report import ClientValidationReport
from src.services.report_database import _percentage_totals_report_metadata, _oto_report_metadata, parse_report, persist_session_reports
from src.validators.after_pipeline.product_data_validator import ProductDataValidator, _CategorizedMessages
from src.validators.after_pipeline.historical_vulnerability_validator import HistoricalVulnerabilityValidator
from src.validators.after_pipeline.oto_dashboard.asset_data_validator import OtoAssetDataValidator
from src.config.settings import ClientTarget
from src.services.opensearch_concurrency import validate_targets_on_product_opensearch


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


def test_full_oto_client_execution_with_real_section_validator(tmp_path):
    values = {field: 1.0 for field in ("no_monitored_vuln", "total", "no_monitored_events", "monitored_vuln", "monitored_events")}
    current = {"_id": "t", "_source": {"@timestamp": "2026-11-04T10:00:00Z", "asset_data": values}}
    previous = {"_id": "p", "_source": {"@timestamp": "2026-11-03T10:00:00Z", "asset_data": values}}
    repository, cognito = MagicMock(), MagicMock()
    cognito.get_client.return_value = {"client_type": "saas"}
    repository.get_documents_by_date_match.side_effect = [[current], [previous]]
    validator = ProductDataValidator(repository, cognito, date(2026, 11, 4))
    validator._validate_mappings_for_documents = MagicMock()
    results = validate_targets_on_product_opensearch([ClientTarget("acme")], lambda target: (target.client_id, *validator.validate_oto_dashboard(target)))
    report = ClientValidationReport()
    for client, errors, details in results:
        report.add_client_result(client, failures=errors, details=details)
    path = tmp_path / "test_should_validate_oto_dashboard_after_pipeline.txt"
    report.write(path, "OTO", "BDD")
    metadata = json.loads(path.with_suffix(".structured.json").read_text(encoding="utf-8"))
    assert any(value["attribute_name"] == "asset_data.total" for value in metadata.values())


def test_oto_fallback_recovers_explicit_pair_when_sidecar_is_empty(tmp_path, monkeypatch):
    message = ("Índice 'acme_oto_dashboard' | hoje _id=abc (@timestamp=2026-11-04T11:50:28.940287) "
               "e ontem _id=xyz (@timestamp=2026-11-03T11:49:24.472200) | Índice 'acme_oto_dashboard' "
               "| seção **asset_data** | atributo **asset_data.monitored_events**: anterior=0.0, "
               "mais recente=193.0, variação=não calculável; limites: +50%/-50%. "
               "Erro: valor anterior é 0.0 e não permite calcular a diferença percentual.")
    path = tmp_path / "test_should_validate_oto_dashboard_after_pipeline.txt"
    path.write_text(f"Teste: OTO\nBDD:\nDado\nFalhas (1):\n- Cliente: acme\n  [Comparação percentual] {message}\n", encoding="utf-8")
    path.with_suffix(".structured.json").write_text("{}", encoding="utf-8")
    result = parse_report(path.read_text(encoding="utf-8"))["results"][0]
    metadata = _oto_report_metadata(result)
    assert metadata["index_type"] == "oto_dashboard"
    assert metadata["attribute_name"] == "asset_data.monitored_events"
    assert metadata["previous_value"] == 0 and metadata["current_value"] == 193
    assert metadata["variation_percent"] is None
    assert metadata["previous_date"] == date(2026, 11, 3)
    assert metadata["current_date"] == date(2026, 11, 4)
    assert metadata["reason_code"] == "PERCENTAGE_BASE_ZERO"
    for key, value in {"REPORT_DB_ENABLED": "true", "REPORT_DB_HOST": "db", "REPORT_DB_DATABASE": "qa", "REPORT_DB_USER": "u", "REPORT_DB_PASSWORD": "p"}.items():
        monkeypatch.setenv(key, value)
    config = SimpleNamespace(_report_db_outcomes={}, getoption=lambda *args, **kwargs: False)
    session = SimpleNamespace(config=config, _validation_started_at=0, _report_db_started_at=datetime.now(timezone.utc))
    connection = MagicMock()
    cursor = connection.__enter__.return_value.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (123,)
    with patch("src.services.report_database.psycopg.connect", return_value=connection):
        persist_session_reports(session, 1, "after", [path])
    row = cursor.executemany.call_args.args[1][0]
    assert row[9:15] == ("acme_oto_dashboard", "oto_dashboard", "asset_data.monitored_events", 0, 193, None)
    assert row[19:22] == (date(2026, 11, 3), date(2026, 11, 4), "PERCENTAGE_BASE_ZERO")


def test_oto_fallback_rejects_non_comparison_messages():
    assert _oto_report_metadata({"message": "Índice 'acme_oto_dashboard' | seção **asset_data** ausente.", "status": "failed"}) == {}
    assert _oto_report_metadata({"message": "Índice 'acme_oto_dashboard' | atributo **score**: current=1, past=2", "status": "passed"}) == {}


def test_historical_asset_fallback_recovers_two_indexes_without_guessing_dates(tmp_path, monkeypatch):
    path = tmp_path / "test_should_validate_assets_observability_software_variation_after_pipeline.txt"
    path.write_text("Teste: Históricos\nBDD:\nDado\nFalhas (1):\n- Cliente: acme\n"
        "  [Comparação percentual] Índice 'acme_asset-historical-observability' | total de assets.monitored_vulns aumentou 60% (ontem=10.0, hoje=16.0); máximo permitido: 50%.\n"
        "  [Comparação percentual] Índice 'acme_asset-historical-software' | total de assets_total aumentou de 0 para 9.0; excede o limite de 50%.\n"
        "Aprovados (1):\n- Cliente: acme\n"
        "  [Comparação percentual] Índice 'acme_asset-historical-software' | total de assets_with_unauthorized_softwares: sem variação (0 para 0).\n", encoding="utf-8")
    path.with_suffix(".structured.json").write_text("{}", encoding="utf-8")
    for key, value in {"REPORT_DB_ENABLED": "true", "REPORT_DB_HOST": "db", "REPORT_DB_DATABASE": "qa", "REPORT_DB_USER": "u", "REPORT_DB_PASSWORD": "p"}.items():
        monkeypatch.setenv(key, value)
    config = SimpleNamespace(_report_db_outcomes={}, getoption=lambda *args, **kwargs: False)
    session = SimpleNamespace(config=config, _validation_started_at=0, _report_db_started_at=datetime.now(timezone.utc))
    connection = MagicMock()
    cursor = connection.__enter__.return_value.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (123,)
    with patch("src.services.report_database.psycopg.connect", return_value=connection):
        persist_session_reports(session, 1, "after", [path])
    rows = cursor.executemany.call_args.args[1]
    assert rows[0][9:15] == ("acme_asset-historical-observability", "asset-historical-observability", "assets.monitored_vulns", 10, 16, 60)
    assert rows[1][9:15] == ("acme_asset-historical-software", "asset-historical-software", "assets_total", 0, 9, None)
    assert rows[1][21] == "PERCENTAGE_BASE_ZERO"
    assert rows[2][12:15] == (0, 0, None)
    assert all(row[19] is None and row[20] is None for row in rows)


def test_totals_fallback_rejects_unrecognized_values_and_supports_other_indexes():
    base = {"validation_type": "Comparação percentual", "status": "failed", "client_id": "acme"}
    assert _percentage_totals_report_metadata({**base, "message": "Índice 'acme_asset-historical-software' | total de assets_total deve ser numérico."}) == {}
    assert _percentage_totals_report_metadata({**base, "message": "Índice 'acme_asset' | total de assets_total aumentou 60% (ontem=10, hoje=16)."})["variation_percent"] == 60


def test_both_asset_history_validations_produce_structured_messages(tmp_path):
    repository, cognito = MagicMock(), MagicMock()
    cognito.get_client.return_value = {"has_asset": True}
    observability = {"assets": {"monitored_vulns": 10, "monitored_events": 10}}
    software = {"assets_total": 10, "assets_missing_mandatory_softwares": 10, "assets_with_unauthorized_softwares": 10}
    repository.get_documents_between.side_effect = [
        [{"_source": observability}], [{"_source": observability}],
        [{"_source": software}], [{"_source": software}],
    ]
    validator = ProductDataValidator(repository, cognito, date(2026, 11, 4))
    validator._validate_mapping = MagicMock()
    errors, details = validator.validate_assets(ClientTarget("acme"))
    report = ClientValidationReport()
    report.add_client_result("acme", failures=errors, details=details)
    path = tmp_path / "test_assets.txt"
    report.write(path, "Históricos", "BDD")
    metadata = json.loads(path.with_suffix(".structured.json").read_text(encoding="utf-8"))
    assert {item["index_type"] for item in metadata.values()} == {"asset-historical-observability", "asset-historical-software"}
    assert {item["attribute_name"] for item in metadata.values()} == {
        "assets.monitored_vulns", "assets.monitored_events", "assets_total",
        "assets_missing_mandatory_softwares", "assets_with_unauthorized_softwares"}
