from __future__ import annotations

import allure
import pytest

from src.repositories.cognito_client_repository import CognitoClientRepository
from src.repositories.opensearch_vulnerability_repository import OpenSearchVulnerabilityRepository
from src.validators.after_pipeline.product_data_validator import ProductDataValidator


CLIENT_SCHEMA = "public"


def _eligible_clients(repository: CognitoClientRepository, required_flag: str) -> list[dict[str, object]]:
    return [client for client in repository.list_clients(CLIENT_SCHEMA) if bool(client.get(required_flag))]


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
) -> None:
    validator = ProductDataValidator(product_repository)
    results = [
        (str(client["client_id"]), *validator.validate_assets(str(client["client_id"])))
        for client in _eligible_clients(cognito_client_repository, "has_asset")
    ]
    _assert_validation(results)


@allure.title("Validar dados de compliance")
@pytest.mark.integration
@pytest.mark.client_data
@pytest.mark.opensearch
def test_should_validate_compliance_after_pipeline(
    cognito_client_repository: CognitoClientRepository,
    product_repository: OpenSearchVulnerabilityRepository,
) -> None:
    validator = ProductDataValidator(product_repository)
    results = [
        (str(client["client_id"]), *validator.validate_compliance(str(client["client_id"])))
        for client in _eligible_clients(cognito_client_repository, "has_wazuh")
    ]
    _assert_validation(results)


@allure.title("Validar softwares obrigatórios e homologados")
@pytest.mark.integration
@pytest.mark.client_data
@pytest.mark.opensearch
def test_should_validate_software_policies_after_pipeline(
    cognito_client_repository: CognitoClientRepository,
    product_repository: OpenSearchVulnerabilityRepository,
) -> None:
    validator = ProductDataValidator(product_repository)
    results = [
        (str(client["client_id"]), *validator.validate_software_policies(str(client["client_id"])))
        for client in _eligible_clients(cognito_client_repository, "has_asset")
    ]
    _assert_validation(results)


@allure.title("Validar score e variação")
@pytest.mark.integration
@pytest.mark.client_data
@pytest.mark.opensearch
def test_should_validate_score_history_after_pipeline(
    cognito_client_repository: CognitoClientRepository,
    product_repository: OpenSearchVulnerabilityRepository,
) -> None:
    validator = ProductDataValidator(product_repository)
    results = [
        (str(client["client_id"]), *validator.validate_score_history(str(client["client_id"]), client))
        for client in cognito_client_repository.list_clients(CLIENT_SCHEMA)
        if client.get("is_in_platform", True)
    ]
    _assert_validation(results)


@allure.title("Validar OTO Dashboard e variação")
@pytest.mark.integration
@pytest.mark.client_data
@pytest.mark.opensearch
def test_should_validate_oto_dashboard_after_pipeline(
    cognito_client_repository: CognitoClientRepository,
    product_repository: OpenSearchVulnerabilityRepository,
) -> None:
    validator = ProductDataValidator(product_repository)
    results = [
        (str(client["client_id"]), *validator.validate_oto_dashboard(str(client["client_id"])))
        for client in cognito_client_repository.list_clients(CLIENT_SCHEMA)
        if bool(client.get("is_saas"))
    ]
    _assert_validation(results)
