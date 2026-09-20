from __future__ import annotations

import inspect

import allure
import pytest

from src.config.settings import ClientTarget
from src.repositories.cognito_client_repository import CognitoClientRepository
from src.repositories.opensearch_vulnerability_repository import OpenSearchVulnerabilityRepository
from src.services.client_validation_report import ClientValidationReport
from src.validators.after_pipeline.opensearch_aliases_validator import (
    OpenSearchAliasesValidator,
)
from src.validators.after_pipeline.product_data_validator import ProductDataValidator


def _save_client_report(report: ClientValidationReport, test_name: str) -> None:
    report_path = f"reports/client-validation/{test_name}.txt"
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


def _assert_validation(
    results: list[tuple[str, list[str], list[str]]],
    test_name: str,
) -> None:
    report = ClientValidationReport()
    for client_id, errors, details in results:
        infos = [detail for detail in details if "índices não aplicáveis" in detail]
        report.add_client_result(
            client_id,
            failures=errors,
            infos=infos,
            details=[detail for detail in details if detail not in infos],
        )
        allure.attach(
            "\n".join(details + errors),
            name=f"Validação pós-pipeline - {client_id}",
            attachment_type=allure.attachment_type.TEXT,
        )
    _save_client_report(report, test_name)
    report.assert_no_failures()


@allure.title("Validar ativos e atualização de índices")
@pytest.mark.integration
@pytest.mark.client_data
@pytest.mark.opensearch
def test_should_validate_assets_and_inventory_variation_after_pipeline(
    cognito_client_repository: CognitoClientRepository,
    product_repository: OpenSearchVulnerabilityRepository,
    client_targets: list[ClientTarget],
) -> None:
    validator = ProductDataValidator(product_repository, cognito_client_repository)
    results = [
        (target.client_id, *validator.validate_assets(target))
        for target in client_targets
    ]
    _assert_validation(results, inspect.currentframe().f_code.co_name)


@allure.title("Validar dados de compliance")
@pytest.mark.integration
@pytest.mark.client_data
@pytest.mark.opensearch
def test_should_validate_compliance_after_pipeline(
    cognito_client_repository: CognitoClientRepository,
    product_repository: OpenSearchVulnerabilityRepository,
    client_targets: list[ClientTarget],
) -> None:
    validator = ProductDataValidator(product_repository, cognito_client_repository)
    results = [
        (target.client_id, *validator.validate_compliance(target))
        for target in client_targets
    ]
    _assert_validation(results, inspect.currentframe().f_code.co_name)


@allure.title("Validar softwares obrigatórios e homologados")
@pytest.mark.integration
@pytest.mark.client_data
@pytest.mark.opensearch
def test_should_validate_software_policies_after_pipeline(
    cognito_client_repository: CognitoClientRepository,
    product_repository: OpenSearchVulnerabilityRepository,
    client_targets: list[ClientTarget],
) -> None:
    validator = ProductDataValidator(product_repository, cognito_client_repository)
    results = [
        (target.client_id, *validator.validate_software_policies(target))
        for target in client_targets
    ]
    _assert_validation(results, inspect.currentframe().f_code.co_name)


@allure.title("Validar índice de score")
@pytest.mark.integration
@pytest.mark.client_data
@pytest.mark.opensearch
def test_should_validate_score_history_after_pipeline(
    cognito_client_repository: CognitoClientRepository,
    product_repository: OpenSearchVulnerabilityRepository,
    client_targets: list[ClientTarget],
) -> None:
    validator = ProductDataValidator(product_repository, cognito_client_repository)
    results = [
        (target.client_id, *validator.validate_score_history(target))
        for target in client_targets
    ]
    _assert_validation(results, inspect.currentframe().f_code.co_name)


@allure.title("Validar índice OTO Dashboard")
@pytest.mark.integration
@pytest.mark.client_data
@pytest.mark.opensearch
def test_should_validate_oto_dashboard_after_pipeline(
    cognito_client_repository: CognitoClientRepository,
    product_repository: OpenSearchVulnerabilityRepository,
    client_targets: list[ClientTarget],
) -> None:
    validator = ProductDataValidator(product_repository, cognito_client_repository)
    results = [
        (target.client_id, *validator.validate_oto_dashboard(target))
        for target in client_targets
    ]
    _assert_validation(results, inspect.currentframe().f_code.co_name)


@allure.title("Validar aliases do OpenSearch")
@pytest.mark.integration
@pytest.mark.opensearch
def test_should_validate_opensearch_aliases_after_pipeline(
    product_repository: OpenSearchVulnerabilityRepository,
) -> None:
    validator = OpenSearchAliasesValidator(product_repository)
    errors, details = validator.validate()
    _assert_validation(
        [("Ambiente OpenSearch", errors, details)],
        inspect.currentframe().f_code.co_name,
    )
