from __future__ import annotations

import allure
import pytest

from src.config.settings import ClientTarget
from src.repositories.cognito_client_repository import CognitoClientRepository
from src.repositories.opensearch_vulnerability_repository import OpenSearchVulnerabilityRepository
from src.validators.after_pipeline.product_data_validator import ProductDataValidator


def _assert_validation(results: list[tuple[str, list[str], list[str]]]) -> None:
    for client_id, errors, details in results:
        allure.attach(
            "\n".join(details + errors),
            name=f"Validação pós-pipeline - {client_id}",
            attachment_type=allure.attachment_type.TEXT,
        )
    failures = [f"{client_id}: {error}" for client_id, errors, _ in results for error in errors]
    assert not failures, "\n".join(failures)


@allure.title("Validar ativos e variação de inventário")
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
    _assert_validation(results)


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
    _assert_validation(results)


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
    _assert_validation(results)


@allure.title("Validar score e variação")
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
    _assert_validation(results)


@allure.title("Validar OTO Dashboard e variação")
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
    _assert_validation(results)
