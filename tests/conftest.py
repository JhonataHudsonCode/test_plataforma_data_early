from __future__ import annotations

from collections.abc import Generator

import pytest
import subprocess
import shutil
from time import perf_counter

from pathlib import Path
from src.services.email_service import EmailService
from src.services.client_validation_report import ClientValidationReport

from src.config.settings import (
    ClientOpenSearchCredentials,
    ClientTarget,
    OpenSearchSettings,
    PostgresSettings,
    WazuhCredentials,
    client_selection_source,
    client_credentials_from_env,
    wazuh_credentials_from_env,
)
from src.connections.opensearch import OpenSearchConnection
from src.connections.opensearch_factory import OpenSearchConnectionFactory
from src.connections.opensearch_dashboards import OpenSearchDashboardsConnection
from src.connections.postgres import PostgresConnection
from src.connections.postgres_factory import PostgresConnectionFactory
from src.repositories.opensearch_dashboards_repository import (
    OpenSearchDashboardsRepository,
)
from src.repositories.opensearch_health_repository import OpenSearchHealthRepository
from src.repositories.db_client_repository import DataBaseRepository
from src.repositories.opensearch_vulnerability_repository import (
    OpenSearchVulnerabilityRepository,
)
from src.repositories.opensearch_client_rsa_repository import (
    OpenSearchClientRepository,
)
from src.repositories.postgres_catalog_repository import PostgresCatalogRepository


COGNITO_DATABASE = "cognito"
ASSETS_DATABASE = "assets"
CLIENTS_DATABASE = "clients"


def _report_has_failures(report: str) -> bool:
    """Indica se o relatório curado possui ao menos uma falha."""
    return any(
        line.startswith("Falhas (") and not line.startswith("Falhas (0)")
        for line in report.splitlines()
    )


def pytest_sessionstart(session):
    """
    Executado quando a sessão de testes começa. Aqui, podemos realizar ações de configuração ou inicialização.
    """

    session._validation_started_at = perf_counter()
    allure_results_path = Path("allure-results")
    if allure_results_path.exists() and allure_results_path.is_dir():
        shutil.rmtree(allure_results_path)
    allure_results_path.mkdir(parents=True, exist_ok=True)

    client_report_path = Path("reports/client-validation")
    client_report_path.mkdir(parents=True, exist_ok=True)
    for report_path in client_report_path.glob("test_*"):
        if report_path.suffix in {".txt", ".html"}:
            report_path.unlink()
    for report_name in ("relatorio_geral.txt", "relatorio_geral.html", "relatorio_geral.zip"):
        report_path = client_report_path / report_name
        if report_path.exists():
            report_path.unlink()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Gera um relatório quando a preparação ou a execução interrompe um teste."""
    outcome = yield
    test_report = outcome.get_result()

    if test_report.when not in {"setup", "call"} or not test_report.failed:
        return
    if getattr(item, "_client_validation_failure_report_written", False):
        return

    test_name = item.originalname or item.name.split("[", maxsplit=1)[0]
    report_path = Path("reports/client-validation") / f"{test_name}.txt"
    # Quando o teste chega ao assert final, seu próprio relatório já foi salvo.
    # Não o substituímos pelo relatório genérico de infraestrutura.
    if report_path.exists():
        return

    item._client_validation_failure_report_written = True
    error_type = (
        call.excinfo.type.__name__
        if call.excinfo is not None
        else "Erro de execução"
    )
    phase_description = "preparação" if test_report.when == "setup" else "execução"
    execution_note = (
        "O corpo do teste não foi executado"
        if test_report.when == "setup"
        else "O relatório funcional não pôde ser concluído"
    )
    report = ClientValidationReport()
    report.add_client_result(
        "Infraestrutura",
        failures=[
            f"Falha durante a {phase_description} do teste "
            f"'{test_name}': {error_type}. "
            f"{execution_note}; verifique a conectividade e as "
            "credenciais das dependências necessárias."
        ],
    )

    try:
        report.write(
            report_path,
            ClientValidationReport.allure_title_from_source(item.path, test_name),
            ClientValidationReport.bdd_from_test_name(test_name),
        )
        ClientValidationReport.write_html_from_text(
            report_path,
            report_path.with_suffix(".html"),
        )
    finally:
        report.close()

def pytest_sessionfinish(session, exitstatus):
    """
    Executado quando toda a sessão de testes termina. Aqui, podemos realizar ações de limpeza ou relatórios finais.
    """

    general_report_name = "relatorio_geral.txt"
    report_paths = sorted(
        path
        for path in Path("reports/client-validation").glob("*.txt")
        if path.name != general_report_name
    )
    if report_paths:
        general_report_path = Path("reports/client-validation") / general_report_name
        ClientValidationReport.write_combined(
            report_paths,
            general_report_path,
            elapsed_seconds=perf_counter() - session._validation_started_at,
        )
        ClientValidationReport.zip_general_report(general_report_path.with_suffix(".html"))

    failed_reports: list[tuple[Path, str]] = []
    for report_path in report_paths:
        body = report_path.read_text(encoding="utf-8")
        html_report_path = report_path.with_suffix(".html")
        ClientValidationReport.write_html_from_text(report_path, html_report_path)
        if _report_has_failures(body):
            failed_reports.append((report_path, body))

    if exitstatus == pytest.ExitCode.OK and not failed_reports:
        print("Nenhuma falha encontrada; envio de e-mail não necessário.")
        return

    try:
        email_service = EmailService()
        for report_path, body in failed_reports:
            subject = f"Relatório de Testes - {report_path.stem}"
            email_sent = email_service.send_email(
                subject,
                body,
                html_body=ClientValidationReport.email_summary_html_from_text(report_path),
                attachment_path=report_path.with_suffix(".html"),
            )
            if email_sent:
                print(f"Relatório aceito pelo servidor SMTP: {report_path.name}")

        if not failed_reports:
            subject = "Relatório de Testes - falha na execução"
            body = (
                "A execução dos testes terminou com erro, mas não foi possível "
                "associá-lo a um relatório por cliente. "
                f"Código de saída do Pytest: {exitstatus}."
            )
            email_service.send_email(subject, body)

    except (OSError, RuntimeError, ValueError) as error:
        print(f"Aviso: não foi possível enviar o relatório por e-mail: {error}")

@pytest.fixture(scope="session")
def postgres_settings() -> PostgresSettings:
    return PostgresSettings.from_env()


@pytest.fixture(scope="session")
def postgres_connection(
    postgres_settings: PostgresSettings,
) -> Generator[PostgresConnection, None, None]:
    connection = PostgresConnection(postgres_settings)
    connection.connect()

    yield connection

    connection.close()


@pytest.fixture(scope="session")
def postgres_repository(
    postgres_connection: PostgresConnection,
) -> PostgresCatalogRepository:
    return PostgresCatalogRepository(postgres_connection)


@pytest.fixture(scope="session")
def postgres_connection_factory(
    postgres_settings: PostgresSettings,
) -> PostgresConnectionFactory:
    return PostgresConnectionFactory(postgres_settings)


@pytest.fixture(scope="session")
def cognito_postgres_connection(
    postgres_connection_factory: PostgresConnectionFactory,
) -> Generator[PostgresConnection, None, None]:
    connection = postgres_connection_factory.create_for_database(COGNITO_DATABASE)
    connection.connect()

    yield connection

    connection.close()


@pytest.fixture(scope="session")
def assets_postgres_connection(
    postgres_connection_factory: PostgresConnectionFactory,
) -> Generator[PostgresConnection, None, None]:
    connection = postgres_connection_factory.create_for_database(ASSETS_DATABASE)
    connection.connect()

    yield connection

    connection.close()


@pytest.fixture(scope="session")
def opensearch_settings() -> OpenSearchSettings:
    return OpenSearchSettings.from_env()


@pytest.fixture(scope="session")
def opensearch_connection(
    opensearch_settings: OpenSearchSettings,
) -> Generator[OpenSearchConnection, None, None]:
    connection = OpenSearchConnection(opensearch_settings)
    connection.connect()

    yield connection

    connection.close()


@pytest.fixture(scope="session")
def opensearch_repository(
    opensearch_connection: OpenSearchConnection,
) -> OpenSearchHealthRepository:
    return OpenSearchHealthRepository(opensearch_connection)


@pytest.fixture(scope="session")
def db_client_repository(
    cognito_postgres_connection: PostgresConnection,
) -> DataBaseRepository:
    return DataBaseRepository(cognito_postgres_connection)

@pytest.fixture(scope="session")
def assets_client_repository(
    assets_postgres_connection: PostgresConnection,
) -> DataBaseRepository:
    return DataBaseRepository(assets_postgres_connection)


@pytest.fixture(scope="session")
def clients_postgres_connection(
    postgres_connection_factory: PostgresConnectionFactory,
) -> Generator[PostgresConnection, None, None]:
    connection = postgres_connection_factory.create_for_database(CLIENTS_DATABASE)
    connection.connect()
    yield connection
    connection.close()


@pytest.fixture(scope="session")
def clients_db_repository(
    clients_postgres_connection: PostgresConnection,
) -> DataBaseRepository:
    return DataBaseRepository(clients_postgres_connection)


@pytest.fixture(scope="session")
def product_repository(
    opensearch_connection: OpenSearchConnection,
) -> OpenSearchVulnerabilityRepository:
    return OpenSearchVulnerabilityRepository(opensearch_connection)


@pytest.fixture(scope="session")
def client_repository(
    opensearch_settings: OpenSearchSettings,
    client_credentials: list[ClientOpenSearchCredentials],
) -> OpenSearchClientRepository:
    connection_factory = OpenSearchConnectionFactory(
        opensearch_settings,
        client_credentials=client_credentials,
    )
    return OpenSearchClientRepository(connection_factory)


@pytest.fixture(scope="session")
def client_credentials() -> list[ClientOpenSearchCredentials]:
    return client_credentials_from_env()


@pytest.fixture(scope="session")
def wazuh_credentials() -> WazuhCredentials | None:
    return wazuh_credentials_from_env()


@pytest.fixture(scope="session")
def client_targets(
    db_client_repository: DataBaseRepository,
    client_credentials: list[ClientOpenSearchCredentials],
) -> list[ClientTarget]:
    if client_selection_source() == "credentials":
        return [
            ClientTarget(
                client_id=item.client_id,
                credentials=item,
            )
            for item in client_credentials
        ]

    return [
        ClientTarget(
            client_id=str(item["client_id"]),
            endpoint=item.get("octopus_endpoint"),
        )
        for item in db_client_repository.get_all_clients(schema_name="public")
    ]


@pytest.fixture(scope="session")
def opensearch_dashboards_connection(
    opensearch_settings: OpenSearchSettings,
) -> Generator[OpenSearchDashboardsConnection, None, None]:
    connection = OpenSearchDashboardsConnection(opensearch_settings)
    connection.connect()

    yield connection

    connection.close()


@pytest.fixture(scope="session")
def opensearch_dashboards_repository(
    opensearch_dashboards_connection: OpenSearchDashboardsConnection,
) -> OpenSearchDashboardsRepository:
    return OpenSearchDashboardsRepository(opensearch_dashboards_connection)
