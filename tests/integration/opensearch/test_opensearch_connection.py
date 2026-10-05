import pytest

from src.repositories.db_client_repository import DataBaseRepository
from src.repositories.opensearch_client_rsa_repository import OpenSearchClientRepository
from src.repositories.opensearch_health_repository import OpenSearchHealthRepository


@pytest.mark.integration
@pytest.mark.opensearch
def test_should_connect_to_opensearch(
    opensearch_repository: OpenSearchHealthRepository,
) -> None:
    assert opensearch_repository.check_connection() is True


@pytest.mark.integration
@pytest.mark.postgres
@pytest.mark.opensearch
@pytest.mark.client_data
def test_should_connect_to_saas_client_opensearch(
    db_client_repository: DataBaseRepository,
    client_repository: OpenSearchClientRepository,
) -> None:
    """Valida a comunicacao com o OpenSearch de todos os clientes SaaS."""
    clients = db_client_repository.get_client_opensearch_targets(schema_name="public")
    saas_clients = [
        client
        for client in clients
        if str(client.get("client_type", "")).strip().lower() == "saas"
    ]

    assert saas_clients, "Nenhum cliente com client_type = 'saas' foi encontrado no Cognito."

    failures: list[str] = []
    for client in saas_clients:
        client_id = str(client["client_id"])
        endpoint = str(client.get("octopus_endpoint") or "").strip()
        if not endpoint:
            failures.append(
                f"Cliente '{client_id}' | octopus_endpoint nao configurado."
            )
            continue

        if not client_repository.check_connection(endpoint):
            failures.append(
                f"Cliente '{client_id}' | sem comunicacao com o OpenSearch em '{endpoint}'."
            )

    assert not failures, "\n".join(failures)
