import pytest
import allure
import inspect

from src.config.settings import client_selection_source
from src.repositories.db_client_repository import DataBaseRepository
from src.repositories.opensearch_client_rsa_repository import OpenSearchClientRepository
from src.repositories.opensearch_health_repository import OpenSearchHealthRepository
from src.services.client_validation_report import ClientValidationReport
from src.services.opensearch_concurrency import validate_client_targets


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
@pytest.mark.opensearch_product
@allure.title("Validar a comunicação com o OpenSearch de produto")
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
@allure.title("Validar a comunicação com o OpenSearch dos clientes SaaS")
def test_should_connect_to_saas_client_opensearch(
    client_repository: OpenSearchClientRepository,
    request: pytest.FixtureRequest,
) -> None:
    """Valida a comunicacao com o OpenSearch de todos os clientes SaaS."""

    report = ClientValidationReport()
    test_name = inspect.currentframe().f_code.co_name
    details = []

    if client_selection_source() == "database":
        db_client_repository: DataBaseRepository = request.getfixturevalue(
            "db_client_repository"
        )
        clients = db_client_repository.get_client_opensearch_targets(
            schema_name="public"
        )
        saas_clients = [
            client
            for client in clients
            if str(client.get("client_type", "")).strip().lower() == "saas"
        ]
        assert saas_clients, "Nenhum cliente com client_type = 'saas' foi encontrado no Cognito."
        targets = [
            (
                str(client["client_id"]),
                str(client.get("octopus_endpoint") or "").strip(),
            )
            for client in saas_clients
        ]
    else:
        client_credentials = request.getfixturevalue("client_credentials")
        targets = [
            (credentials.client_id, credentials.endpoint)
            for credentials in client_credentials
        ]
        assert targets, "Nenhuma credencial foi configurada em OCTOPUS_CLIENT_CREDENTIALS."

    failures: list[str] = []
    valid_targets: list[tuple[str, str]] = []
    for client_id, endpoint in targets:
        if not endpoint:
            failures.append(
                f"Cliente '{client_id}' | octopus_endpoint nao configurado."
            )
            continue
        valid_targets.append((client_id, endpoint))

    def validate_target(target: tuple[str, str]) -> tuple[bool, str]:
        client_id, endpoint = target
        if client_repository.check_connection(endpoint):
            return (
                True,
                f"Cliente '{client_id}' | comunicacao com o OpenSearch em "
                f"'{endpoint}' validada com sucesso.",
            )
        return (
            False,
            f"Cliente '{client_id}' | sem comunicacao com o OpenSearch em "
            f"'{endpoint}'.",
        )

    for is_connected, message in validate_client_targets(valid_targets, validate_target):
        (details if is_connected else failures).append(message)

    report.add_client_result(
        "OpenSearch Cliente",
        failures=failures,
        details=details,
    )
    _save_opensearch_report(report, test_name)
    report.assert_no_failures()
    assert not failures, "\n".join(failures)
