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
    client_credentials_from_env,
    client_selection_source,
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
from src.repositories.cognito_client_repository import CognitoClientRepository
from src.repositories.opensearch_vulnerability_repository import (
    OpenSearchVulnerabilityRepository,
)
from src.repositories.opensearch_client_rsa_repository import (
    OpenSearchClientRepository,
)
from src.repositories.postgres_catalog_repository import PostgresCatalogRepository


COGNITO_DATABASE = "cognito"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ALLURE_RESULTS_DIRECTORY = PROJECT_ROOT / "allure-results"
CLIENT_REPORTS_DIRECTORY = PROJECT_ROOT / "reports" / "client-validation"


def _report_has_failures(report: str) -> bool:
    return any(
        line.startswith("Falhas (") and not line.startswith("Falhas (0)")
        for line in report.splitlines()
    )


def _send_report_email(
    email_service: EmailService,
    subject: str,
    body: str,
    report_path: Path,
) -> bool:
    """Envia resumo HTML e anexa o relatório completo, expansível e baixável."""
    print("Enviando resumo do relatório e HTML completo como anexo.")
    return email_service.send_email(
        subject,
        body,
        html_body=ClientValidationReport.email_summary_html_from_text(report_path),
        attachment_path=report_path.with_suffix(".html"),
    )


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config) -> None:
    """Mantém os arquivos do Allure no projeto after, mesmo em execução pelo IDE."""
    config.option.allure_report_dir = str(ALLURE_RESULTS_DIRECTORY)

def pytest_sessionstart(session):
    """
    Executado quando a sessão de testes começa. Aqui, podemos realizar ações de configuração ou inicialização.
    """

    session._validation_started_at = perf_counter()
    if ALLURE_RESULTS_DIRECTORY.exists() and ALLURE_RESULTS_DIRECTORY.is_dir():
        shutil.rmtree(ALLURE_RESULTS_DIRECTORY)
    ALLURE_RESULTS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    CLIENT_REPORTS_DIRECTORY.mkdir(parents=True, exist_ok=True)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Gera um report mínimo se o teste falhar antes de salvar o próprio relatório."""
    outcome = yield
    test_report = outcome.get_result()
    if test_report.when not in {"setup", "call"} or not test_report.failed:
        return

    report_path = CLIENT_REPORTS_DIRECTORY / f"{item.name}.txt"
    if report_path.exists():
        return

    report = ClientValidationReport()
    report.add_client_result(
        "Execução do teste",
        failures=[f"Falha inesperada: {test_report.longreprtext}"],
    )
    report.write(
        report_path,
        ClientValidationReport.allure_title_from_source(item.path, item.name),
        ClientValidationReport.bdd_from_test_name(
            item.name,
            PROJECT_ROOT / "tests" / "gherkins",
        ),
    )
    report.close()
    ClientValidationReport.write_html_from_text(
        report_path,
        report_path.with_suffix(".html"),
    )

def pytest_sessionfinish(session, exitstatus):
    """
    Executado quando toda a sessão de testes termina. Aqui, podemos realizar ações de limpeza ou relatórios finais.
    """

    general_report_name = "relatorio_geral.txt"
    report_paths = sorted(
        path
        for path in CLIENT_REPORTS_DIRECTORY.glob("*.txt")
        if path.name != general_report_name
    )
    if report_paths:
        ClientValidationReport.write_combined(
            report_paths,
            CLIENT_REPORTS_DIRECTORY / general_report_name,
            elapsed_seconds=perf_counter() - session._validation_started_at,
        )
    else:
        empty_report = ClientValidationReport(
            elapsed_seconds=perf_counter() - session._validation_started_at,
        )
        general_report_path = CLIENT_REPORTS_DIRECTORY / general_report_name
        empty_report.write(
            general_report_path,
            "Resumo geral da execução",
            "Nenhum teste finalizou com resultados para consolidar.",
        )
        empty_report.close()
        ClientValidationReport.write_html_from_text(
            general_report_path,
            general_report_path.with_suffix(".html"),
        )

    failed_reports: list[tuple[Path, str]] = []
    for report_path in report_paths:
        body = report_path.read_text(encoding="utf-8")
        ClientValidationReport.write_html_from_text(
            report_path,
            report_path.with_suffix(".html"),
        )
        if _report_has_failures(body):
            failed_reports.append((report_path, body))

    if exitstatus == pytest.ExitCode.OK and not failed_reports:
        print("Nenhuma falha encontrada; envio de e-mail não necessário.")
        return

    try:
        email_service = EmailService()
        for report_path, body in failed_reports:
            email_sent = _send_report_email(
                email_service,
                f"Relatório de Testes - {report_path.stem}",
                body,
                report_path,
            )
            if email_sent:
                print(f"Relatório aceito pelo servidor SMTP: {report_path.name}")

        if not failed_reports:
            email_service.send_email(
                "Relatório de Testes - falha na execução",
                f"A execução dos testes terminou com erro. Código de saída: {exitstatus}.",
            )

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
def cognito_client_repository(
    cognito_postgres_connection: PostgresConnection,
) -> CognitoClientRepository:
    return CognitoClientRepository(cognito_postgres_connection)


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
def client_targets(
    cognito_client_repository: CognitoClientRepository,
    client_credentials: list[ClientOpenSearchCredentials],
) -> list[ClientTarget]:
    """Seleciona os clientes pelo banco (padrão) ou pelas credenciais do ambiente."""
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
        for item in cognito_client_repository.list_clients("public")
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

