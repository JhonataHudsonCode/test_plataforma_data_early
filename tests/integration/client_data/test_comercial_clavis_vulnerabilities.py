from datetime import date
import inspect

import pytest
import allure

from src.queries.assets_client_queries import SELECT_ASSETS_CLIENT_ACTIVATION_KEYS
from src.repositories.db_client_repository import DataBaseRepository
from src.repositories.opensearch_vulnerability_repository import (
    OpenSearchVulnerabilityRepository,
)
from src.repositories.opensearch_client_rsa_repository import OpenSearchClientRepository
from src.services.client_validation_report import ClientValidationReport
from src.validators.client_data.database.activation_key_validator import ActivationKeyValidator
from src.validators.client_data.database.clients_database_validator import ClientsDatabaseValidator
from src.validators.client_data.database.wazuh_key_validator import WazuhKeyValidator
from src.validators.client_data.opensearch_client.alerts_index_validator import AlertsIndexValidator
from src.validators.client_data.opensearch_client.axur_index_validator import AxurIndexValidator
from src.validators.client_data.opensearch_client.rsa_index_validator import RsaIndexValidator
from src.validators.client_data.opensearch_client.rules_index_validator import RulesIndexValidator
from src.validators.client_data.opensearch_product.cve_trends_validator import CveTrendsValidator
from src.validators.client_data.opensearch_product.epss_index_validator import EpssIndexValidator
from src.validators.client_data.opensearch_product.historical_vulnerability_validator import HistoricalVulnerabilityValidator
from src.validators.client_data.opensearch_product.product_vulnerability_validator import ProductVulnerabilityValidator


def _save_client_report(
    report: ClientValidationReport,
    test_name: str,
) -> None:
    report_path = (
        "reports/client-validation/"
        f"{test_name}.txt"
    )
    report.write(
        report_path,
        ClientValidationReport.allure_title_from_source(__file__, test_name),
        ClientValidationReport.bdd_from_test_name(test_name),
    )
    report.close()
    ClientValidationReport.write_html_from_text(
        report_path,
        report_path.removesuffix(".txt") + ".html",
    )

@allure.suite("Integração Opensearch")
@pytest.mark.integration
@pytest.mark.client_data
@pytest.mark.postgres
@pytest.mark.opensearch
@allure.title("Validar dados de superfície de ataque")
def test_should_validate_has_rsa_opensearch_client(
    db_client_repository: DataBaseRepository,
    client_repository: OpenSearchClientRepository,
    client_targets,
) -> None:
    report = ClientValidationReport()
    today = date.today()
    test_name = inspect.currentframe().f_code.co_name

    validator = RsaIndexValidator(db_client_repository, client_repository, today)
    for target in client_targets:
        result = validator.validate(target)
        report.add_client_result(
            result.client_id,
            result.failures,
            result.infos,
            result.details,
        )
    _save_client_report(report, test_name)
    report.assert_no_failures()

@allure.title("Validar dados de alertas")
def test_should_validate_has_alerts_opensearch_client(
    db_client_repository: DataBaseRepository,
    client_repository: OpenSearchClientRepository,
    client_targets,
) -> None:
    report = ClientValidationReport()
    today = date.today()
    test_name = inspect.currentframe().f_code.co_name
    validator = AlertsIndexValidator(db_client_repository, client_repository, today)
    for target in client_targets:
        result = validator.validate(target)
        report.add_client_result(
            result.client_id,
            result.failures,
            result.infos,
            result.details,
        )
    _save_client_report(report, test_name)
    report.assert_no_failures()

@allure.title("Validar dados de regras")
def test_should_validate_rules_opensearch_client(
    db_client_repository: DataBaseRepository,
    client_repository: OpenSearchClientRepository,
    client_targets,
) -> None:
    report = ClientValidationReport()
    test_name = inspect.currentframe().f_code.co_name
    validator = RulesIndexValidator(
        db_client_repository,
        client_repository,
        date.today(),
    )
    for target in client_targets:
        result = validator.validate(target)
        report.add_client_result(
            result.client_id,
            result.failures,
            result.infos,
            result.details,
        )
    _save_client_report(report, test_name)
    report.assert_no_failures()

@allure.title("Validar dados de vulnerabilidades para todos os clientes")
def test_should_validate_vulnerability_opensearch_product(
    db_client_repository: DataBaseRepository,
    product_repository: OpenSearchVulnerabilityRepository,
    client_targets,
) -> None:
    report = ClientValidationReport()
    today = date.today()
    test_name = inspect.currentframe().f_code.co_name

    validator = ProductVulnerabilityValidator(
        db_client_repository,
        product_repository,
        today,
    )
    for target in client_targets:
        result = validator.validate(target)
        report.add_client_result(
            result.client_id,
            result.failures,
            result.infos,
            result.details,
        )
    _save_client_report(report, test_name)
    report.assert_no_failures()
    return


@allure.title("Validar dados de EPSS")
def test_should_validate_epss_opensearch_product(
    product_repository: OpenSearchVulnerabilityRepository,
    client_targets,
) -> None:
    report = ClientValidationReport()
    test_name = inspect.currentframe().f_code.co_name
    today = date.today()
    validator = EpssIndexValidator(product_repository, today)
    for target in client_targets:
        result = validator.validate(target.client_id)
        report.add_client_result(
            result.client_id,
            result.failures,
            result.infos,
            result.details,
        )
    _save_client_report(report, test_name)
    report.assert_no_failures()
    return


@allure.title("Validar dados históricos de vulnerabilidades")
def test_should_validate_asset_vulnerability_historical_opensearch_product(
    db_client_repository: DataBaseRepository,
    product_repository: OpenSearchVulnerabilityRepository,
    client_targets,
) -> None:
    report = ClientValidationReport()
    today = date.today()
    test_name = inspect.currentframe().f_code.co_name
    validator = HistoricalVulnerabilityValidator(
        db_client_repository,
        product_repository,
        today,
    )
    for target in client_targets:
        result = validator.validate(target)
        report.add_client_result(result.client_id, result.failures, result.infos, result.details)
    _save_client_report(report, test_name)
    report.assert_no_failures()
    return

#DUVIDA: todos os documentos devem estar com o status ativo? atualmente o metodo
@allure.title("Validar dados de tendências de CVE")
def test_should_validate_cve_trends_opensearch_product(
    product_repository: OpenSearchVulnerabilityRepository,
    client_targets,
) -> None:
    report = ClientValidationReport()
    test_name = inspect.currentframe().f_code.co_name
    validator = CveTrendsValidator(product_repository)
    for target in client_targets:
        result = validator.validate(target.client_id)
        report.add_client_result(result.client_id, result.failures, result.infos, result.details)
    _save_client_report(report, test_name)
    report.assert_no_failures()
    return


#Qual o prazo para validação do índice AXUR? Hoje ou algum outro prazo?
@allure.title("Validar dados do Axur")
def test_should_validate_axur_opensearch_client(
    db_client_repository: DataBaseRepository,
    client_repository: OpenSearchClientRepository,
    client_targets,
) -> None:
    report = ClientValidationReport()
    today = date.today()
    test_name = inspect.currentframe().f_code.co_name
    validator = AxurIndexValidator(db_client_repository, client_repository, today)
    for target in client_targets:
        result = validator.validate(target)
        report.add_client_result(result.client_id, result.failures, result.infos, result.details)
    _save_client_report(report, test_name)
    report.assert_no_failures()
    return

@allure.title("Validar chaves de ativação")
def test_should_validate_activation_keys(
    db_client_repository: DataBaseRepository,
    assets_client_repository: DataBaseRepository,
    client_targets,
) -> None:
    report = ClientValidationReport()
    test_name = inspect.currentframe().f_code.co_name
    validator = ActivationKeyValidator(db_client_repository, assets_client_repository)
    for target in client_targets:
        result = validator.validate(target)
        report.add_client_result(result.client_id, result.failures, result.infos, result.details)
    _save_client_report(report, test_name)
    report.assert_no_failures()
    return


@allure.title("Validar chaves do Wazuh")
def test_should_validate_wazuh_keys(
    db_client_repository: DataBaseRepository,
    assets_client_repository: DataBaseRepository,
    client_targets,
) -> None:
    report = ClientValidationReport()
    test_name = inspect.currentframe().f_code.co_name
    validator = WazuhKeyValidator(db_client_repository, assets_client_repository)
    for target in client_targets:
        result = validator.validate(target)
        report.add_client_result(result.client_id, result.failures, result.infos, result.details)
    _save_client_report(report, test_name)
    report.assert_no_failures()
    return


@allure.title("Validar clientes e clientes de alertas")
def test_should_validate_clients_alert_clients(
    db_client_repository: DataBaseRepository,
    clients_db_repository: DataBaseRepository,
    client_targets,
) -> None:
    report = ClientValidationReport()
    test_name = inspect.currentframe().f_code.co_name
    validator = ClientsDatabaseValidator(db_client_repository, clients_db_repository)
    for target in client_targets:
        result = validator.validate(target)
        report.add_client_result(result.client_id, result.failures, result.infos, result.details)
    _save_client_report(report, test_name)
    report.assert_no_failures()
    return

            
