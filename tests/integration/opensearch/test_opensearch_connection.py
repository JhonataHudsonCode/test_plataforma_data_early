import inspect

import pytest

from src.repositories.db_client_repository import DataBaseRepository
from src.repositories.opensearch_client_rsa_repository import OpenSearchClientRepository
from src.repositories.opensearch_health_repository import OpenSearchHealthRepository
from src.services.client_validation_report import ClientValidationReport


def _save_opensearch_report(
    report: ClientValidationReport,
    test_name: str,
) -> None:
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


@pytest.mark.integration
@pytest.mark.opensearch
def test_should_connect_to_opensearch(
    opensearch_repository: OpenSearchHealthRepository,
) -> None:
    report = ClientValidationReport()
    test_name = inspect.currentframe().f_code.co_name
    is_connected = opensearch_repository.check_connection()
    failures = []
    details = []

    if is_connected:
        details.append("[Geral] Comunicação com o OpenSearch central validada com sucesso.")
    else:
        failures.append("[Geral] Não foi possível comunicar com o OpenSearch central.")

    report.add_client_result(
        "OpenSearch central",
        failures=failures,
        details=details,
    )
    _save_opensearch_report(report, test_name)
    report.assert_no_failures()


@pytest.mark.integration
@pytest.mark.postgres
@pytest.mark.opensearch
@pytest.mark.client_data
def test_should_connect_to_saas_client_opensearch(
    db_client_repository: DataBaseRepository,
    client_repository: OpenSearchClientRepository,
) -> None:
    """Valida a comunicacao com o OpenSearch de todos os clientes SaaS."""
    report = ClientValidationReport()
    test_name = inspect.currentframe().f_code.co_name
    clients = db_client_repository.get_client_opensearch_targets(schema_name="public")
    saas_clients = [
        client
        for client in clients
        if str(client.get("client_type", "")).strip().lower() == "saas"
    ]

    failures: list[str] = []
    if not saas_clients:
        failures.append("Nenhum cliente com client_type = 'saas' foi encontrado no Cognito.")

    for client in saas_clients:
        client_id = str(client["client_id"])
        endpoint = str(client.get("octopus_endpoint") or "").strip()
        client_failures: list[str] = []
        client_details: list[str] = []
        if not endpoint:
            client_failures.append(
                "[Geral] octopus_endpoint não configurado para o cliente SaaS."
            )
        elif client_repository.check_connection(endpoint):
            client_details.append(
                f"[Geral] Comunicação com o OpenSearch validada pelo octopus_endpoint '{endpoint}'."
            )
        else:
            client_failures.append(
                f"[Geral] Sem comunicação com o OpenSearch pelo octopus_endpoint '{endpoint}'."
            )

        failures.extend(f"Cliente '{client_id}' | {failure}" for failure in client_failures)
        report.add_client_result(
            client_id,
            failures=client_failures,
            details=client_details,
        )

    if not saas_clients:
        report.add_client_result("Cognito", failures=failures)

    _save_opensearch_report(report, test_name)
    assert not failures, "\n".join(failures)
