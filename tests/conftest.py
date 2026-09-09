from __future__ import annotations

from collections.abc import Generator

import pytest
import subprocess
import shutil

from pathlib import Path
from src.services.email_service import EmailService
from src.services.client_validation_report import ClientValidationReport

from src.config.settings import (
    ClientOpenSearchCredentials,
    ClientTarget,
    OpenSearchSettings,
    PostgresSettings,
    client_selection_source,
    client_credentials_from_env,
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

def pytest_sessionstart(session):
    """
    Executado quando a sessão de testes começa. Aqui, podemos realizar ações de configuração ou inicialização.
    """

    allure_results_path = Path("allure-results")
    if allure_results_path.exists() and allure_results_path.is_dir():
        shutil.rmtree(allure_results_path)
    allure_results_path.mkdir(parents=True, exist_ok=True)

    client_report_path = Path("reports/client-validation")
    client_report_path.mkdir(parents=True, exist_ok=True)

def pytest_sessionfinish(session, exitstatus):
    """
    Executado quando toda a sessão de testes termina. Aqui, podemos realizar ações de limpeza ou relatórios finais.
    """

    try:
        email_service = EmailService()
        report_paths = sorted(Path("reports/client-validation").glob("*.txt"))
        for report_path in report_paths:
            html_report_path = report_path.with_suffix(".html")
            body = report_path.read_text(encoding="utf-8")
            html_body = ClientValidationReport.write_html_from_text(
                report_path,
                html_report_path,
            )
            subject = f"Relatório de Testes - {report_path.stem}"
            email_sent = email_service.send_email(
                subject,
                body,
                html_body=html_body,
            )
            if email_sent:
                print(f"Relatório aceito pelo servidor SMTP: {report_path.name}")

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
def client_targets(
    db_client_repository: DataBaseRepository,
    client_credentials: list[ClientOpenSearchCredentials],
) -> list[ClientTarget]:
    if client_selection_source() == "credentials":
        return [
            ClientTarget(
                client_id=item.client_id,
                activation_key_name=item.activation_key_name,
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

