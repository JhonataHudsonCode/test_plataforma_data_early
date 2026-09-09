from datetime import date

import pytest
import allure

from src.repositories.cognito_client_repository import DataBaseRepository
from src.repositories.opensearch_vulnerability_repository import (
    OpenSearchVulnerabilityRepository,
)


SPECIAL_CLIENT_ID = "comercial-clavis"
CLIENT_SCHEMA = "public"

@allure.feature("Integração OpenSearch")
@pytest.mark.integration
@pytest.mark.client_data
@pytest.mark.postgres
@pytest.mark.opensearch
def test_should_validate_vulnerability_indices_for_all_rsa_enabled_clients(
    cognito_client_repository: DataBaseRepository,
    opensearch_vulnerability_repository: OpenSearchVulnerabilityRepository,
) -> None:
    clients = cognito_client_repository.list_clients(schema_name=CLIENT_SCHEMA)

    assert clients, "Nenhum cliente foi retornado por public.clients."

    clients_to_validate = [
        client for client in clients if client.client_id != SPECIAL_CLIENT_ID
    ]
    assert clients_to_validate, "Nenhum cliente disponível para validação em lote."

    today = date.today()
    rsa_enabled_clients = [
        client for client in clients_to_validate if client.has_rsa
    ]
    indices = opensearch_vulnerability_repository.get_indices_for_date(
        client_names=[client.client_id for client in rsa_enabled_clients],
        reference_date=today,
    )
    indices_by_name = {index.name: index for index in indices}
    failures: list[str] = []

    for client in rsa_enabled_clients:
        expected_index_name = (
            f"{client.client_id}_vulnerability-was-{today.strftime('%y.%m.%d')}"
        )
        index = indices_by_name.get(expected_index_name)

        if index is None:
            failures.append(f"Índice não encontrado: {expected_index_name}")
        elif index.document_count <= 0:
            failures.append(
                f"Índice sem documentos: {expected_index_name}"
            )

    assert not failures, "\n".join(failures)