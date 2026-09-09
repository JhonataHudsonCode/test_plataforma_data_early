from datetime import date
import inspect

from psycopg import logger
import pytest
import allure

from src.queries.assets_client_queries import SELECT_ASSETS_CLIENT_ACTIVATION_KEYS
from src.repositories.db_client_repository import DataBaseRepository
from src.repositories.opensearch_vulnerability_repository import (
    OpenSearchVulnerabilityRepository,
)
from src.repositories.opensearch_client_rsa_repository import (
    OpenSearchClientRepository,
)
from src.models.opensearch_client.rules_mapping import EXPECTED_RULES_MAPPING, RULES_INDEX_NAME
from src.models.opensearch_client.rsa_mapping import EXPECTED_RSA_MAPPING
from src.models.opensearch_client.elastalert_status_mapping import EXPECTED_ELASTALERT_STATUS_MAPPING, ELASTALERT_STATUS_INDEX_NAME
from src.models.opensearch_product.vulnerability_vm import EXPECTED_VULNERABILITIES_VM_MAPPING, VULNERABILITY_VM_INDEX_NAME
from src.models.opensearch_product.vulnerability_vm_new_mapping import EXPECTED_VULNERABILITY_VM_NEW_MAPPING, VULNERABILITY_VM_NEW_INDEX_NAME
from src.models.opensearch_product.vulnerability_was_mapping import EXPECTED_VULNERABILITIES_WAS_MAPPING, VULNERABILITY_WAS_INDEX_NAME
from src.models.opensearch_product.epss_mapping import EPSS_INDEX_NAME, EXPECTED_EPSS_MAPPING
from src.models.opensearch_product.vulnerability_historical_mapping import EXPECTED_VULNERABILITY_HISTORICAL_MAPPING, VULNERABILITY_HISTORICAL_INDEX_NAME
from src.models.opensearch_product.cve_trends_mapping import EXPECTED_CVE_TRENDS_MAPPING, CVE_TRENDS_INDEX_NAME
from src.models.opensearch_product.axur_mapping import EXPECTED_AXUR_MAPPING, AXUR_INDEX_NAME
from src.models.opensearch_client.clients_mapping import EXPECTED_CLIENTS_MAPPING, CLIENTS_INDEX_NAME
from src.models.opensearch_client.alert_clients_mapping import EXPECTED_ALERT_CLIENTS_MAPPING, ALERT_CLIENTS_INDEX_NAME
from src.validators.opensearch_mapping_validator import OpenSearchMappingValidator
from src.services.client_validation_report import ClientValidationReport
from src.queries.cognito_client_queries import (
    SELECT_COGNITO_CLIENT_HAS_WAZUH_BY_ID,
    SELECT_COGNITO_CLIENT_HAS_RSA_BY_ID,
    SELECT_COGNITO_CLIENT_HAS_ALERTS_BY_ID,
    SELECT_COGNITO_CLIENT_HAS_BART_BY_ID,
    SELECT_COGNITO_CLIENT_HAS_AXUR_BY_ID,
    SELECT_ID_CLIENTS
)
from src.queries.clients_queries import SELECT_ALERT_CLIENT_BY_ID, SELECT_CLIENT_BY_ID

INDEX_CLIENT_NAME = "comercial"
INDEX_ACTIVATION_KEY_NAME = "Clavis Base"
CLIENT_SCHEMA = "public"
ACTIVE_STATUS = "ativo"

def _save_client_report(
    report: ClientValidationReport,
    test_name: str,
) -> None:
    report_path = (
        "reports/client-validation/"
        f"{test_name}.txt"
    )
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

@allure.suite("Integração Opensearch")
@pytest.mark.integration
@pytest.mark.client_data
@pytest.mark.postgres
@pytest.mark.opensearch
@allure.title("Validar dados de superfície de ataque")
def test_should_validate_has_rsa_opensearch_client(
    db_client_repository: DataBaseRepository,
    client_repository: OpenSearchClientRepository,
    client_targets,
) -> None:
    report = ClientValidationReport()
    today = date.today()
    test_name = inspect.currentframe().f_code.co_name

    for target in client_targets:
        failures: list[str] = []
        client = db_client_repository.get_table(
            schema_name=CLIENT_SCHEMA,
            client_id=target.client_id,
            query=SELECT_COGNITO_CLIENT_HAS_RSA_BY_ID,
        )
        if not client:
            report.add_client_result(
                target.client_id,
                [f"Cliente '{target.client_id}' não encontrado no Cognito; consulta de has_rsa não retornou registro."],
            )
            continue
        if not client.get("has_rsa"):
            report.add_client_result(
                target.client_id,
                infos=[f"Cliente '{target.client_id}' possui has_rsa desabilitado; índice RSA não aplicável."],
            )
            continue
        try:
            expected_index_name = f"rsa-{today.strftime('%Y.%m.%d')}"
            host = target.host or client["octopus_endpoint"].replace("https://", "")
            indices = client_repository.get_indices_rsa_today(host, today)
            if expected_index_name not in {index.name for index in indices}:
                failures.append(
                    f"Cliente '{target.client_id}' | host '{host}' | índice RSA "
                    f"'{expected_index_name}' não encontrado. Índices encontrados: "
                    f"{', '.join(index.name for index in indices) or 'nenhum'}."
                )
            metadata = client_repository.get_index_metadata(host, expected_index_name)
            if metadata.created_at.date() != today:
                failures.append(
                    f"Cliente '{target.client_id}' | índice RSA '{expected_index_name}' "
                    f"foi criado em '{metadata.created_at:%Y-%m-%d}', mas era esperada "
                    f"a data '{today:%Y-%m-%d}'. Host: '{host}'."
                )
            if not metadata.mapping:
                failures.append(
                    f"Cliente '{target.client_id}' | índice RSA '{expected_index_name}' "
                    f"não possui mapping configurado. Host: '{host}'."
                )
            else:
                failures.extend(OpenSearchMappingValidator().validate(
                    metadata.mapping.get("properties", {}), EXPECTED_RSA_MAPPING
                ))
        except Exception as error:
            failures.append(
                f"Cliente '{target.client_id}' | falha ao validar o índice RSA "
                f"'{expected_index_name}': {error.__class__.__name__}: {error}"
            )
        report.add_client_result(target.client_id, failures)
    _save_client_report(report, test_name)
    report.assert_no_failures()

@allure.title("Validar dados de alertas")
def test_should_validate_has_alerts_opensearch_client(
    db_client_repository: DataBaseRepository,
    client_repository: OpenSearchClientRepository,
    client_targets,
) -> None:
    report = ClientValidationReport()
    today = date.today()
    test_name = inspect.currentframe().f_code.co_name
    for target in client_targets:
        failures: list[str] = []
        try:
            client = db_client_repository.get_table(
                CLIENT_SCHEMA,
                target.client_id,
                SELECT_COGNITO_CLIENT_HAS_ALERTS_BY_ID,
            )
            if not client:
                failures.append(
                    f"Cliente '{target.client_id}' não encontrado no Cognito."
                )
                report.add_client_result(target.client_id, failures)
                continue
            if not client.get("has_alerts"):
                report.add_client_result(
                    target.client_id,
                    infos=[
                        f"Cliente '{target.client_id}' possui has_alerts desabilitado; "
                        "validação do OpenSearch não aplicável."
                    ],
                )
                continue

            host = target.host or client["octopus_endpoint"].replace("https://", "")
            indices = client_repository.get_indices_elastalerts_status_today(
                host, ELASTALERT_STATUS_INDEX_NAME
            )
            if ELASTALERT_STATUS_INDEX_NAME not in {index.name for index in indices}:
                failures.append(
                    f"Cliente '{target.client_id}' | índice "
                    f"'{ELASTALERT_STATUS_INDEX_NAME}' não encontrado no host "
                    f"'{host}'. Índices encontrados: "
                    f"{', '.join(index.name for index in indices) or 'nenhum'}"
                )
            metadata = client_repository.get_index_metadata(host, ELASTALERT_STATUS_INDEX_NAME)
            if metadata.created_at.date() != today:
                failures.append(
                    f"Cliente '{target.client_id}' | índice "
                    f"'{ELASTALERT_STATUS_INDEX_NAME}' com data de criação "
                    f"'{metadata.created_at:%Y-%m-%d}', mas era esperada a data "
                    f"'{today:%Y-%m-%d}'. Host consultado: '{host}'."
                )
            if not metadata.mapping:
                failures.append(
                    f"Cliente '{target.client_id}' | índice "
                    f"'{ELASTALERT_STATUS_INDEX_NAME}' não possui mapping "
                    f"configurado. Host consultado: '{host}'."
                )
            else:
                mapping_errors = OpenSearchMappingValidator().validate(
                    metadata.mapping.get("properties", {}),
                    EXPECTED_ELASTALERT_STATUS_MAPPING,
                )
                failures.extend(
                    f"Cliente '{target.client_id}' | índice "
                    f"'{ELASTALERT_STATUS_INDEX_NAME}' | host '{host}' | "
                    f"mapping inválido: {error}"
                    for error in mapping_errors
                )
        except Exception as error:
            endpoint = target.host or "endpoint do Cognito"
            failures.append(
                f"Cliente '{target.client_id}' | endpoint '{endpoint}' | "
                f"falha inesperada durante a validação de "
                f"'{ELASTALERT_STATUS_INDEX_NAME}': {error.__class__.__name__}: {error}"
            )
        report.add_client_result(target.client_id, failures)
    _save_client_report(report, test_name)
    report.assert_no_failures()

@allure.title("Validar dados de regras")
def test_should_validate_rules_opensearch_client(
    db_client_repository: DataBaseRepository,
    client_repository: OpenSearchClientRepository,
    client_targets,
) -> None:
    report = ClientValidationReport()
    test_name = inspect.currentframe().f_code.co_name
    for target in client_targets:
        failures: list[str] = []
        client = db_client_repository.get_table(
            CLIENT_SCHEMA, target.client_id, SELECT_COGNITO_CLIENT_HAS_ALERTS_BY_ID
        )
        if not client:
            report.add_client_result(
                target.client_id,
                [f"Cliente '{target.client_id}' não encontrado no Cognito; consulta de has_alerts não retornou registro."],
            )
            continue
        if not client.get("has_alerts"):
            report.add_client_result(
                target.client_id,
                infos=[f"Cliente '{target.client_id}' possui has_alerts desabilitado; índice rules não aplicável."],
            )
            continue
        try:
            host = target.host or client["octopus_endpoint"].replace("https://", "")
            documents = client_repository.get_documents(host, RULES_INDEX_NAME)
            if not documents:
                failures.append(
                    f"Cliente '{target.client_id}' | host '{host}' | índice rules "
                    "retornou zero documentos."
                )
            metadata = client_repository.get_index_metadata(host, RULES_INDEX_NAME)
            if not metadata.mapping:
                failures.append(
                    f"Cliente '{target.client_id}' | host '{host}' | índice rules "
                    "não possui mapping configurado."
                )
            else:
                mapping_errors = OpenSearchMappingValidator().validate(
                    metadata.mapping.get("properties", {}),
                    EXPECTED_RULES_MAPPING,
                )
                failures.extend(
                    f"Cliente '{target.client_id}' | índice "
                    f"'{RULES_INDEX_NAME}' | host '{host}' | "
                    f"mapping inválido: {error}"
                    for error in mapping_errors
                )
        except Exception as error:
            failures.append(
                f"Cliente '{target.client_id}' | host '{host}' | falha ao validar "
                f"o índice rules: {error.__class__.__name__}: {error}"
            )
        report.add_client_result(target.client_id, failures)
    _save_client_report(report, test_name)
    report.assert_no_failures()

@allure.title("Validar dados de vulnerabilidades para todos os clientes")
def test_should_validate_vulnerability_opensearch_product(
    db_client_repository: DataBaseRepository,
    product_repository: OpenSearchVulnerabilityRepository,
    client_targets,
) -> None:
    report = ClientValidationReport()
    today = date.today()
    test_name = inspect.currentframe().f_code.co_name

    for target in client_targets:
        client_id = target.client_id
        client = db_client_repository.get_table(
            CLIENT_SCHEMA,
            client_id,
            SELECT_COGNITO_CLIENT_HAS_BART_BY_ID,
        )
        failures: list[str] = []

        if client and client.get("has_bart"):
            index_contracts = (
                (
                    f"{client_id}_{VULNERABILITY_WAS_INDEX_NAME}-{today.strftime('%Y.%m.%d')}",
                    EXPECTED_VULNERABILITIES_WAS_MAPPING,
                ),
                (
                    f"{client_id}_{VULNERABILITY_VM_INDEX_NAME}-{today.strftime('%Y.%m.%d')}",
                    EXPECTED_VULNERABILITIES_VM_MAPPING,
                ),
                (
                    f"{client_id}_{VULNERABILITY_VM_NEW_INDEX_NAME}",
                    EXPECTED_VULNERABILITY_VM_NEW_MAPPING,
                ),
            )

            for expected_index_name, expected_mapping in index_contracts:
                try:
                    indices = product_repository.get_indices_vulnerability(
                        index_name=expected_index_name,
                    )
                    index = {item.name: item for item in indices}.get(expected_index_name)
                    if index is None:
                        failures.append(
                            f"Cliente '{client_id}' | índice '{expected_index_name}' "
                            "não encontrado no OpenSearch de produto."
                        )
                    elif index.document_count <= 0:
                        failures.append(
                            f"Cliente '{client_id}' | índice '{expected_index_name}' "
                            "não contém documentos."
                        )
                except Exception as error:
                    failures.append(
                        f"Cliente '{client_id}' | falha ao consultar o índice "
                        f"'{expected_index_name}': {error.__class__.__name__}: {error}"
                    )

                try:
                    metadata = product_repository.get_index_metadata(
                        index_name=expected_index_name,
                    )
                    if not metadata.mapping:
                        failures.append(
                            f"Cliente '{client_id}' | índice '{expected_index_name}' "
                            "não possui mapping configurado."
                        )
                    else:
                        mapping_errors = OpenSearchMappingValidator().validate(
                            actual_properties=metadata.mapping.get("properties", {}),
                            expected_properties=expected_mapping,
                        )
                        failures.extend(
                            f"Cliente '{client_id}' | índice '{expected_index_name}' | "
                            f"mapping inválido: {error}"
                            for error in mapping_errors
                        )
                except Exception as error:
                    failures.append(
                        f"Cliente '{client_id}' | falha ao consultar o mapping de "
                        f"'{expected_index_name}': {error.__class__.__name__}: {error}"
                    )

            report.add_client_result(client_id, failures)   

        else:
            info: list[str] = []
            if not client:
                info.append(f"Cliente '{client_id}' não encontrado no Cognito.")
            elif not client.get("has_bart"):
                info.append(
                    f"Cliente '{client_id}' possui has_bart desabilitado; "
                    "índices de vulnerabilidade não aplicáveis."
                )
            report.add_client_result(client_id, infos=info)
            continue

    curated_report = report.write(
        "reports/client-validation/test_should_validate_vulnerability_opensearch_product.txt",
        ClientValidationReport.allure_title_from_source(__file__, test_name),
        ClientValidationReport.bdd_from_test_name(test_name),
    )
    ClientValidationReport.write_html_from_text(
        "reports/client-validation/test_should_validate_vulnerability_opensearch_product.txt",
        "reports/client-validation/test_should_validate_vulnerability_opensearch_product.html",
    )
    print(curated_report)
    report.close()
    report.assert_no_failures()

@allure.title("Validar dados de EPSS")
def test_should_validate_epss_opensearch_product(
    product_repository: OpenSearchVulnerabilityRepository,
    client_targets,
) -> None:
    report = ClientValidationReport()
    test_name = inspect.currentframe().f_code.co_name
    today = date.today()
    for target in client_targets:
        failures: list[str] = []
        try:
            indices = product_repository.get_indices_epss(EPSS_INDEX_NAME)
            index = {item.name: item for item in indices}.get(EPSS_INDEX_NAME)
            if index is None:
                failures.append(
                    f"Cliente '{target.client_id}' | índice de produto "
                    f"'{EPSS_INDEX_NAME}' não encontrado."
                )
            elif index.document_count <= 0:
                failures.append(
                    f"Cliente '{target.client_id}' | índice de produto "
                    f"'{EPSS_INDEX_NAME}' não contém documentos."
                )
                
            metadata = product_repository.get_index_metadata(EPSS_INDEX_NAME)
            if not metadata.mapping:
                failures.append(
                    f"Cliente '{target.client_id}' | índice '{EPSS_INDEX_NAME}' "
                    "não possui mapping configurado no OpenSearch de produto."
                )
            else:
                failures.extend(
                    f"Cliente '{target.client_id}' | índice '{EPSS_INDEX_NAME}' | "
                    f"mapping inválido: {error}"
                    for error in OpenSearchMappingValidator().validate(
                        metadata.mapping.get("properties", {}), EXPECTED_EPSS_MAPPING
                    )
                )
            if metadata.created_at.date() != today:
                failures.append(
                    f"Cliente '{target.client_id}' | índice '{EPSS_INDEX_NAME}' "
                    f"foi criado em '{metadata.created_at:%Y-%m-%d}', esperada "
                    f"'{today:%Y-%m-%d}'."
                )
        except Exception as error:
            failures.append(
                f"Cliente '{target.client_id}' | falha ao validar o índice de "
                f"produto '{EPSS_INDEX_NAME}': {error.__class__.__name__}: {error}"
            )
        report.add_client_result(target.client_id, failures)
    _save_client_report(report, test_name)
    report.assert_no_failures()


@allure.title("Validar dados históricos de vulnerabilidades")
def test_should_validate_asset_vulnerability_historical_opensearch_product(
    db_client_repository: DataBaseRepository,
    product_repository: OpenSearchVulnerabilityRepository,
    client_targets,
) -> None:
    report = ClientValidationReport()
    today = date.today()
    test_name = inspect.currentframe().f_code.co_name
    for target in client_targets:
        client_id = target.client_id
        client = db_client_repository.get_table(
            CLIENT_SCHEMA,
            client_id,
            SELECT_COGNITO_CLIENT_HAS_BART_BY_ID,
        )
        if not client or not client.get("has_bart"):
            info = []
            if not client:
                info.append(
                    f"Cliente '{client_id}' não encontrado no Cognito; "
                    "índice histórico não aplicável."
                )
            elif not client.get("has_bart"):
                info.append(
                    f"Cliente '{client_id}' possui has_bart desabilitado; "
                    "índice histórico não aplicável."
                )
            report.add_client_result(client_id, infos=info)
            continue

        failures: list[str] = []
        expected_index_name = f"{client_id}_{VULNERABILITY_HISTORICAL_INDEX_NAME}"
        try:
            indices = product_repository.get_indices_vulnerability(
                index_name=expected_index_name,
            )
            index = {item.name: item for item in indices}.get(expected_index_name)
            if index is None:
                failures.append(
                    f"Cliente '{client_id}' | índice histórico "
                    f"'{expected_index_name}' não encontrado."
                )
            elif index.document_count <= 0:
                failures.append(
                    f"Cliente '{client_id}' | índice histórico "
                    f"'{expected_index_name}' não contém documentos."
                )
            metadata = product_repository.get_index_metadata(expected_index_name)
            if not metadata.mapping:
                failures.append(
                    f"Cliente '{client_id}' | índice histórico "
                    f"'{expected_index_name}' não possui mapping configurado."
                )
            else:
                failures.extend(
                    f"Cliente '{client_id}' | índice histórico "
                    f"'{expected_index_name}' | mapping inválido: {error}"
                    for error in OpenSearchMappingValidator().validate(
                        metadata.mapping.get("properties", {}),
                        EXPECTED_VULNERABILITY_HISTORICAL_MAPPING,
                    )
                )
            if metadata.created_at.date() != today:
                failures.append(
                    f"Cliente '{client_id}' | índice histórico "
                    f"'{expected_index_name}' foi criado em "
                    f"'{metadata.created_at:%Y-%m-%d}', esperada "
                    f"'{today:%Y-%m-%d}'."
                )
        except Exception as error:
            failures.append(
                f"Cliente '{client_id}' | falha ao validar o índice histórico "
                f"'{expected_index_name}': {error.__class__.__name__}: {error}"
            )
        report.add_client_result(client_id, failures)
    _save_client_report(report, test_name)
    report.assert_no_failures()

#DUVIDA: todos os documentos devem estar com o status ativo? atualmente o metodo
@allure.title("Validar dados de tendências de CVE")
def test_should_validate_cve_trends_opensearch_product(
    product_repository: OpenSearchVulnerabilityRepository,
    client_targets,
) -> None:
    report = ClientValidationReport()
    test_name = inspect.currentframe().f_code.co_name
    for target in client_targets:
        failures: list[str] = []
        try:
            indices = product_repository.get_indices(CVE_TRENDS_INDEX_NAME)
            index = {item.name: item for item in indices}.get(CVE_TRENDS_INDEX_NAME)
            if index is None:
                failures.append(
                    f"Cliente '{target.client_id}' | índice de produto "
                    f"'{CVE_TRENDS_INDEX_NAME}' não encontrado."
                )
            elif index.document_count <= 0:
                failures.append(
                    f"Cliente '{target.client_id}' | índice de produto "
                    f"'{CVE_TRENDS_INDEX_NAME}' não contém documentos."
                )
            else:
                active_documents = product_repository.get_documents_by_status(
                    CVE_TRENDS_INDEX_NAME, ACTIVE_STATUS, index.document_count
                )
                if not active_documents:
                    failures.append(
                        f"Cliente '{target.client_id}' | nenhum documento com status "
                        f"'{ACTIVE_STATUS}' foi encontrado no índice "
                        f"'{CVE_TRENDS_INDEX_NAME}'."
                    )
            metadata = product_repository.get_index_metadata(CVE_TRENDS_INDEX_NAME)
            if not metadata.mapping:
                failures.append(
                    f"Cliente '{target.client_id}' | índice "
                    f"'{CVE_TRENDS_INDEX_NAME}' não possui mapping configurado."
                )
            else:
                failures.extend(
                    f"Cliente '{target.client_id}' | índice "
                    f"'{CVE_TRENDS_INDEX_NAME}' | mapping inválido: {error}"
                    for error in OpenSearchMappingValidator().validate(
                        metadata.mapping.get("properties", {}),
                        EXPECTED_CVE_TRENDS_MAPPING,
                    )
                )
        except Exception as error:
            failures.append(
                f"Cliente '{target.client_id}' | falha ao validar o índice de "
                f"produto '{CVE_TRENDS_INDEX_NAME}': "
                f"{error.__class__.__name__}: {error}"
            )
        report.add_client_result(target.client_id, failures)
    _save_client_report(report, test_name)
    report.assert_no_failures()

#Qual o prazo para validação do índice AXUR? Hoje ou algum outro prazo?
@allure.title("Validar dados do Axur")
def test_should_validate_axur_opensearch_client(
    db_client_repository: DataBaseRepository,
    client_repository: OpenSearchClientRepository,
    client_targets,
) -> None:
    report = ClientValidationReport()
    today = date.today()
    test_name = inspect.currentframe().f_code.co_name
    for target in client_targets:
        failures: list[str] = []
        client = db_client_repository.get_table(
            CLIENT_SCHEMA, target.client_id, SELECT_COGNITO_CLIENT_HAS_AXUR_BY_ID
        )
        if not client:
            report.add_client_result(
                target.client_id,
                [f"Cliente '{target.client_id}' não encontrado no Cognito; consulta de has_axur não retornou registro."],
            )
            continue
        if not client.get("has_axur"):
            report.add_client_result(
                target.client_id,
                infos=[f"Cliente '{target.client_id}' possui has_axur desabilitado; índice Axur não aplicável."],
            )
            continue
        try:
            host = target.host or client["octopus_endpoint"].replace("https://", "")
            indices = client_repository.get_indices_axur(host, AXUR_INDEX_NAME)
            index = {item.name: item for item in indices}.get(AXUR_INDEX_NAME)
            if index is None:
                failures.append(
                    f"Cliente '{target.client_id}' | índice Axur '{AXUR_INDEX_NAME}' "
                    "não encontrado no OpenSearch do cliente."
                )
            elif index.document_count <= 0:
                failures.append(
                    f"Cliente '{target.client_id}' | índice Axur '{AXUR_INDEX_NAME}' "
                    "não contém documentos."
                )
            metadata = client_repository.get_index_metadata(host, AXUR_INDEX_NAME)
            if metadata.created_at.date() != today:
                failures.append(
                    f"Cliente '{target.client_id}' | índice Axur '{AXUR_INDEX_NAME}' "
                    f"foi criado em '{metadata.created_at:%Y-%m-%d}', esperada "
                    f"'{today:%Y-%m-%d}'. Host: '{host}'."
                )
            if not metadata.mapping:
                failures.append(
                    f"Cliente '{target.client_id}' | índice Axur '{AXUR_INDEX_NAME}' "
                    f"não possui mapping configurado. Host: '{host}'."
                )
            else:
                failures.extend(OpenSearchMappingValidator().validate(
                    metadata.mapping.get("properties", {}), EXPECTED_AXUR_MAPPING
                ))
        except Exception as error:
            failures.append(
                f"Cliente '{target.client_id}' | host '{target.host or 'Cognito'}' | "
                f"falha ao validar o índice Axur: {error.__class__.__name__}: {error}"
            )
        report.add_client_result(target.client_id, failures)
    _save_client_report(report, test_name)
    report.assert_no_failures()

@allure.title("Validar chaves de ativação")
def test_should_validate_activation_keys(
    db_client_repository: DataBaseRepository,
    assets_client_repository: DataBaseRepository,
    client_targets,
) -> None:
    report = ClientValidationReport()
    test_name = inspect.currentframe().f_code.co_name
    for target in client_targets:
        client = db_client_repository.get_table(
            CLIENT_SCHEMA, target.client_id, SELECT_COGNITO_CLIENT_HAS_BART_BY_ID
        )
        if not client:
            report.add_client_result(
                target.client_id,
                [f"Cliente '{target.client_id}' não encontrado no Cognito; consulta de has_bart não retornou registro."],
            )
        elif not client.get("has_bart"):
            report.add_client_result(
                target.client_id,
                infos=[f"Cliente '{target.client_id}' possui has_bart desabilitado; chave de ativação não aplicável."],
            )
        else:
            failures = [] if assets_client_repository.has_activation_key(
                "public", target.client_id, target.activation_key_name, SELECT_ASSETS_CLIENT_ACTIVATION_KEYS
            ) else [f"Chave de ativação '{target.activation_key_name}' não encontrada."]

        report.add_client_result(target.client_id, failures)

    _save_client_report(report, test_name)
    report.assert_no_failures()

@allure.title("Validar chaves do Wazuh")
def test_should_validate_wazuh_keys(
    db_client_repository: DataBaseRepository,
    assets_client_repository: DataBaseRepository,
    client_targets,
) -> None:
    report = ClientValidationReport()
    test_name = inspect.currentframe().f_code.co_name
    for target in client_targets:
        client = db_client_repository.get_table(
            CLIENT_SCHEMA, target.client_id, SELECT_COGNITO_CLIENT_HAS_WAZUH_BY_ID
        )
        if not client:
            report.add_client_result(
                target.client_id,
                [f"Cliente '{target.client_id}' não encontrado no Cognito; consulta de has_wazuh não retornou registro."],
            )
        elif not client.get("has_wazuh"):
            report.add_client_result(
                target.client_id,
                infos=[f"Cliente '{target.client_id}' possui has_wazuh desabilitado; chave de ativação não aplicável."],
            )
        else:
            failures = [] if assets_client_repository.has_activation_key(
                "public", target.client_id, target.activation_key_name, SELECT_ASSETS_CLIENT_ACTIVATION_KEYS
            ) else [f"Chave de ativação '{target.activation_key_name}' não encontrada."]
            report.add_client_result(target.client_id, failures)
    _save_client_report(report, test_name)
    report.assert_no_failures()

@allure.title("Validar clientes e clientes de alertas")
def test_should_validate_clients_alert_clients(
    db_client_repository: DataBaseRepository,
    clients_db_repository: DataBaseRepository,
    client_targets,
) -> None:
    report = ClientValidationReport()
    test_name = inspect.currentframe().f_code.co_name
    for target in client_targets:
        client = db_client_repository.get_table(
            CLIENT_SCHEMA, target.client_id, SELECT_COGNITO_CLIENT_HAS_BART_BY_ID
        )
        if not client:
            report.add_client_result(
                target.client_id,
                [f"Cliente '{target.client_id}' não encontrado no Cognito; consulta de has_bart não retornou registro."],
            )
            continue
        if not client.get("has_bart"):
            report.add_client_result(
                target.client_id,
                infos=[f"Cliente '{target.client_id}' possui has_bart desabilitado; tabelas clients e alertClients não aplicáveis."],
            )
            continue

        failures: list[str] = []
        id_client_row = clients_db_repository.get_table(
            CLIENT_SCHEMA,
            target.client_id,
            SELECT_ID_CLIENTS,
        )
        if not id_client_row or id_client_row.get("id") is None:
            failures.append(
                f"Cliente '{target.client_id}' | tabela 'clients' | "
                "não foi possível obter o id para consultar alertClients."
            )
            report.add_client_result(target.client_id, failures)
            continue

        id_client = id_client_row["id"]
        for table_name, query in (
            (CLIENTS_INDEX_NAME, SELECT_CLIENT_BY_ID),
            (ALERT_CLIENTS_INDEX_NAME, SELECT_ALERT_CLIENT_BY_ID),
        ):
            lookup_value = (
                id_client
                if query == SELECT_ALERT_CLIENT_BY_ID
                else target.client_id
            )
            row = clients_db_repository.get_table(
                CLIENT_SCHEMA,
                lookup_value,
                query,
            )
            if not row:
                failures.append(
                    f"Cliente '{target.client_id}' | tabela '{table_name}' | "
                    "nenhum registro encontrado no database clients."
                )
                continue
            if row.get("createdAt") is None:
                failures.append(
                    f"Cliente '{target.client_id}' | tabela '{table_name}' | "
                    "coluna 'createdAt' sem dados."
                )
            if row.get("updatedAt") is None:
                failures.append(
                    f"Cliente '{target.client_id}' | tabela '{table_name}' | "
                    "coluna 'updatedAt' sem dados."
                )
        report.add_client_result(target.client_id, failures)
    _save_client_report(report, test_name)
    report.assert_no_failures()

            
