from __future__ import annotations

import inspect
from pathlib import Path

import allure
import pytest

from src.config.settings import ClientTarget
from src.repositories.cognito_client_repository import CognitoClientRepository
from src.repositories.opensearch_vulnerability_repository import OpenSearchVulnerabilityRepository
from src.services.client_validation_report import ClientValidationReport
from src.services.opensearch_concurrency import validate_targets_on_product_opensearch
from src.validators.after_pipeline.opensearch_aliases_validator import (
    OpenSearchAliasesValidator,
)
from src.validators.after_pipeline.historical_vulnerability_validator import (
    HistoricalVulnerabilityValidator,
)
from src.validators.after_pipeline.product_data_validator import ProductDataValidator


def _save_client_report(report: ClientValidationReport, test_name: str) -> None:
    report_path = (
        Path(__file__).resolve().parents[3]
        / "reports"
        / "client-validation"
        / f"{test_name}.txt"
    )
    report.write(
        report_path,
        ClientValidationReport.allure_title_from_source(__file__, test_name),
        ClientValidationReport.bdd_from_test_name(test_name),
    )
    report.close()
    ClientValidationReport.write_html_from_text(
        report_path,
        report_path.with_suffix(".html"),
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


@allure.title("Realizar comparação percentual entre os documentos de ontem e hoje do indice _asset")
@pytest.mark.integration
@pytest.mark.after_pipeline
@pytest.mark.client_data
@pytest.mark.opensearch
@pytest.mark.opensearch_product
def test_should_validate_current_asset_index_after_pipeline(
    cognito_client_repository: CognitoClientRepository,
    product_repository: OpenSearchVulnerabilityRepository,
    client_targets: list[ClientTarget],
) -> None:
    validator = ProductDataValidator(product_repository, cognito_client_repository)
    results = validate_targets_on_product_opensearch(
        client_targets,
        lambda target: (
            target.client_id,
            *validator.validate_current_asset_index(target),
        ),
    )
    _assert_validation(results, inspect.currentframe().f_code.co_name)


@allure.title("Validar _asset-historical-observability e _asset-historical-software")
@pytest.mark.integration
@pytest.mark.after_pipeline
@pytest.mark.client_data
@pytest.mark.opensearch 
@pytest.mark.opensearch_product
def test_should_validate_assets_observability_software_variation_after_pipeline(
    cognito_client_repository: CognitoClientRepository,
    product_repository: OpenSearchVulnerabilityRepository,
    client_targets: list[ClientTarget],
) -> None:
    validator = ProductDataValidator(product_repository, cognito_client_repository)
    results = validate_targets_on_product_opensearch(
        client_targets,
        lambda target: (target.client_id, *validator.validate_assets(target)),
    )
    _assert_validation(results, inspect.currentframe().f_code.co_name)


@allure.title("Realizar comparação percentual entre os documentos de ontem e hoje do indice _vulnerability-historical")
@pytest.mark.integration
@pytest.mark.after_pipeline
@pytest.mark.client_data
@pytest.mark.opensearch
@pytest.mark.opensearch_product
def test_should_validate_asset_vulnerability_historical_after_pipeline(
    cognito_client_repository: CognitoClientRepository,
    product_repository: OpenSearchVulnerabilityRepository,
    client_targets: list[ClientTarget],
) -> None:
    validator = HistoricalVulnerabilityValidator(
        product_repository,
        cognito_client_repository,
    )
    results = validate_targets_on_product_opensearch(
        client_targets,
        lambda target: (target.client_id, *validator.validate(target)),
    )
    _assert_validation(results, inspect.currentframe().f_code.co_name)


@allure.title("Realizar comparação percentual nos documentos de ontem e de hoje dos indices asset-compliance e asset-policy-compliance")
@pytest.mark.integration
@pytest.mark.after_pipeline
@pytest.mark.client_data
@pytest.mark.opensearch
@pytest.mark.opensearch_product
def test_should_validate_compliance_after_pipeline(
    cognito_client_repository: CognitoClientRepository,
    product_repository: OpenSearchVulnerabilityRepository,
    client_targets: list[ClientTarget],
) -> None:
    validator = ProductDataValidator(product_repository, cognito_client_repository)
    results = validate_targets_on_product_opensearch(
        client_targets,
        lambda target: (target.client_id, *validator.validate_compliance(target)),
    )
    _assert_validation(results, inspect.currentframe().f_code.co_name)


@allure.title("Validar que indice score_history tenha dados do mes e ano atual e que contenha dados de score")
@pytest.mark.integration
@pytest.mark.after_pipeline
@pytest.mark.client_data
@pytest.mark.opensearch
@pytest.mark.opensearch_product
def test_should_validate_score_history_after_pipeline(
    cognito_client_repository: CognitoClientRepository,
    product_repository: OpenSearchVulnerabilityRepository,
    client_targets: list[ClientTarget],
) -> None:
    validator = ProductDataValidator(product_repository, cognito_client_repository)
    results = validate_targets_on_product_opensearch(
        client_targets,
        lambda target: (target.client_id, *validator.validate_score_history(target)),
    )
    _assert_validation(results, inspect.currentframe().f_code.co_name)


@allure.title("Realizar comparação percentual para os atributos monitorados para os documentos do indice OTO Dashboard")
@pytest.mark.integration
@pytest.mark.after_pipeline
@pytest.mark.client_data
@pytest.mark.opensearch
@pytest.mark.opensearch_product
def test_should_validate_oto_dashboard_after_pipeline(
    cognito_client_repository: CognitoClientRepository,
    product_repository: OpenSearchVulnerabilityRepository,
    client_targets: list[ClientTarget],
) -> None:
    validator = ProductDataValidator(product_repository, cognito_client_repository)
    results = validate_targets_on_product_opensearch(
        client_targets,
        lambda target: (target.client_id, *validator.validate_oto_dashboard(target)),
    )
    _assert_validation(results, inspect.currentframe().f_code.co_name)


@allure.title("Validar aliases e índices de destino do OpenSearch")
@pytest.mark.integration
@pytest.mark.after_pipeline
@pytest.mark.opensearch
@pytest.mark.opensearch_product
def test_should_validate_opensearch_aliases_after_pipeline(
    product_repository: OpenSearchVulnerabilityRepository,
) -> None:
    validator = OpenSearchAliasesValidator(product_repository)
    errors, details = validator.validate()
    _assert_validation(
        [("Ambiente OpenSearch", errors, details)],
        inspect.currentframe().f_code.co_name,
    )
