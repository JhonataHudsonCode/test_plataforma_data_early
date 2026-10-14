from __future__ import annotations

import inspect
import os
from dataclasses import replace
from urllib.parse import urlparse

import allure
import pytest

from src.config.settings import WazuhCredentials
from src.connections.wazuh import WazuhAuthenticationError, WazuhConnection
from src.repositories.db_client_repository import DataBaseRepository
from src.services.client_validation_report import ClientValidationReport


def _with_wazuh_api_port(endpoint: str) -> str:
    """Aplica a porta padrão da API somente quando ela não foi informada."""
    parsed = urlparse(endpoint if "://" in endpoint else f"https://{endpoint}")
    if not parsed.hostname:
        return endpoint
    if parsed.port is not None:
        return endpoint

    scheme = parsed.scheme or "https"
    host = parsed.hostname
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    return f"{scheme}://{host}:55000/security/user/authenticate"


@allure.title("Validar comunicação e autenticação dos endpoints da API Wazuh")
@pytest.mark.integration
@pytest.mark.client_data
@pytest.mark.postgres
@pytest.mark.opensearch
def test_should_authenticate_wazuh_clients(
    wazuh_credentials: WazuhCredentials | None,
    request: pytest.FixtureRequest,
) -> None:
    if wazuh_credentials is None:
        pytest.skip("Variáveis WAZUH_USERNAME, WAZUH_PASSWORD, WAZUH_ENDPOINT e WAZUH_INTERNAL_ENDPOINT não foram configuradas.")

    report = ClientValidationReport()
    test_name = inspect.currentframe().f_code.co_name
    all_clients = os.getenv("WAZUH_CLIENTS", "false").strip().lower() == "true"
    if all_clients:
        db_client_repository: DataBaseRepository = request.getfixturevalue(
            "db_client_repository"
        )
        eligible_clients = 0
        for client in db_client_repository.get_wazuh_client_targets(
            schema_name="public"
        ):
            client_id = str(client["client_id"])
            failures: list[str] = []
            infos: list[str] = []
            details: list[str] = []
            client_type = str(client.get("client_type") or "").strip().lower()
            octopus_endpoint = str(client.get("octopus_endpoint") or "").strip()
            has_wazuh = bool(client.get("has_wazuh"))

            if client_type != "saas":
                infos.append("[Geral] Cliente não SaaS; validação Wazuh não aplicável.")
            elif not octopus_endpoint:
                infos.append("[Geral] Cliente SaaS sem octopus_endpoint; validação Wazuh não aplicável.")
            elif not has_wazuh:
                infos.append("[Geral] Cliente SaaS com has_wazuh desabilitado; validação não aplicável.")
            else:
                eligible_clients += 1
                client_wazuh_credentials = replace(
                    wazuh_credentials,
                    endpoint=octopus_endpoint,
                )
                internal_endpoint = _with_wazuh_api_port(
                    client_wazuh_credentials.internal_endpoint,
                )
                try:
                    WazuhConnection(client_wazuh_credentials).authenticate(
                        internal_endpoint
                    )
                    details.append(
                        f"[Autenticação] Endpoint '{octopus_endpoint}' autenticado com sucesso."
                    )
                except WazuhAuthenticationError as error:
                    failures.append(
                        f"[Autenticação] Endpoint interno '{octopus_endpoint}' | {error}."
                    )

            report.add_client_result(
                client_id,
                failures=failures,
                infos=infos,
                details=details,
            )

        if eligible_clients == 0:
            report.add_client_result(
                "Cognito",
                failures=[
                    "[Geral] Nenhum cliente SaaS com has_wazuh habilitado e "
                    "octopus_endpoint foi encontrado."
                ],
            )
    else:
        failures: list[str] = []
        details: list[str] = []
        internal_endpoint = _with_wazuh_api_port(
            wazuh_credentials.internal_endpoint,
        )
        try:
            WazuhConnection(wazuh_credentials).authenticate(internal_endpoint)
            details.append(
                f"[Autenticação] Endpoint '{wazuh_credentials.endpoint}' "
                "autenticado com sucesso."
            )
        except WazuhAuthenticationError as error:
            failures.append(
                f"[Autenticação] Endpoint interno '{wazuh_credentials.endpoint}' "
                f"| {error}."
            )
        report.add_client_result(
            wazuh_credentials.name,
            failures=failures,
            details=details,
        )

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
    report.assert_no_failures()