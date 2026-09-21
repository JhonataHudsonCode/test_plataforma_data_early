from __future__ import annotations

import inspect

import allure
import pytest

from src.config.settings import WazuhCredentials
from src.connections.wazuh import WazuhAuthenticationError, WazuhConnection
from src.services.client_validation_report import ClientValidationReport


@allure.suite("Integração Wazuh")
@allure.title("Validar comunicação e autenticação da API Wazuh na porta 55000")
@pytest.mark.integration
@pytest.mark.wazuh
def test_should_authenticate_wazuh_clients(
    wazuh_credentials: list[WazuhCredentials],
) -> None:
    if not wazuh_credentials:
        pytest.skip("WAZUH_CREDENTIALS não foi configurada.")

    report = ClientValidationReport()
    test_name = inspect.currentframe().f_code.co_name
    for credentials in wazuh_credentials:
        connection = WazuhConnection(credentials)
        failures: list[str] = []
        details: list[str] = []
        for endpoint_name, endpoint in (
            ("externo", credentials.endpoint),
            ("interno", credentials.internal_endpoint),
        ):
            try:
                connection.authenticate(endpoint)
                details.append(
                    f"Wazuh '{credentials.name}' | endpoint {endpoint_name} autenticado na porta 55000."
                )
            except WazuhAuthenticationError as error:
                failures.append(
                    f"Wazuh '{credentials.name}' | endpoint {endpoint_name} '{endpoint}' | {error}."
                )
        report.add_client_result(credentials.name, failures=failures, details=details)

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
