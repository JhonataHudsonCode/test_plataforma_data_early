from __future__ import annotations

from src.models.client_validation_result import ClientValidationResult
from src.models.opensearch_product.cve_trends_mapping import (
    CVE_TRENDS_INDEX_NAME,
    EXPECTED_CVE_TRENDS_MAPPING,
)
from src.repositories.opensearch_vulnerability_repository import OpenSearchVulnerabilityRepository
from src.validators.client_data.opensearch_product.helpers import (
    OpenSearchProductValidationHelper,
)


class CveTrendsValidator:
    """Valida dados e contrato do índice central de tendências de CVE."""

    def __init__(self, product_repository: OpenSearchVulnerabilityRepository) -> None:
        self._product_repository = product_repository

    def validate(self) -> ClientValidationResult:
        report_id = "produto"
        failures: list[str] = []
        details: list[str] = []
        try:
            indices = self._product_repository.get_indices(CVE_TRENDS_INDEX_NAME)
            index = {item.name: item for item in indices}.get(CVE_TRENDS_INDEX_NAME)
            if index is None:
                failures.append(
                    f"[Geral] Índice de produto '{CVE_TRENDS_INDEX_NAME}' não encontrado."
                )
                return ClientValidationResult(report_id, failures=failures)

            details.append(
                f"[Geral] Índice '{CVE_TRENDS_INDEX_NAME}' encontrado com sucesso."
            )
            mapping_available, mapping_errors = (
                OpenSearchProductValidationHelper.validate_mapping(
                    self._product_repository,
                    CVE_TRENDS_INDEX_NAME,
                    EXPECTED_CVE_TRENDS_MAPPING,
                )
            )
            if not mapping_available:
                failures.append(
                    f"[Mapping] Índice '{CVE_TRENDS_INDEX_NAME}' | consulta GET "
                    f"/{CVE_TRENDS_INDEX_NAME}/_mapping não retornou propriedades "
                    "para validação."
                )
            else:
                failures.extend(
                    f"[Mapping] Índice '{CVE_TRENDS_INDEX_NAME}' | mapping inválido: {error}"
                    for error in mapping_errors
                )
                if not mapping_errors:
                    details.append(
                        f"[Mapping] Índice '{CVE_TRENDS_INDEX_NAME}' | propriedades "
                        f"retornadas por GET /{CVE_TRENDS_INDEX_NAME}/_mapping "
                        "validadas com sucesso."
                    )

            if index.document_count <= 0:
                failures.append(
                    f"[Geral] Índice de produto '{CVE_TRENDS_INDEX_NAME}' não contém documentos."
                )
                return ClientValidationResult(
                    report_id,
                    failures=failures,
                    details=details,
                )

            documents = self._product_repository.get_documents(
                CVE_TRENDS_INDEX_NAME,
                size=index.document_count,
            )

            if not documents:
                failures.append(
                    f"[Geral] Índice '{CVE_TRENDS_INDEX_NAME}' possui documentos na "
                    "listagem, mas a consulta não retornou documentos para validação."
                )
                return ClientValidationResult(report_id, failures=failures, details=details)

            details.append(
                f"[Geral] Índice '{CVE_TRENDS_INDEX_NAME}' com"
                f"{index.document_count} documento(s)."
            )

            self._validate_active_statuses(documents, failures, details)

        except Exception as error:
            failures.append(
                f"[Geral] Falha ao validar o índice de produto '{CVE_TRENDS_INDEX_NAME}': "
                f"{error.__class__.__name__}: {error}"
            )
        return ClientValidationResult(report_id, failures=failures, details=details)

    @staticmethod
    def _validate_active_statuses(
        documents: list[dict],
        failures: list[str],
        details: list[str],
    ) -> None:
        inactive_documents = [
            (
                document.get("_id", "não informado"),
                document.get("_source", {}).get("status", "não informado"),
            )
            for document in documents
            if str(document.get("_source", {}).get("status", "")).casefold() != "ativo"
        ]
        active_count = len(documents) - len(inactive_documents)
        details.append(
            f"[Status ativo] Índice '{CVE_TRENDS_INDEX_NAME}' | resumo da validação: "
            f"{active_count} documento(s) ativo(s) e {len(inactive_documents)} "
            f"documento(s) não ativo(s), de {len(documents)} no total."
        )
        if inactive_documents:
            document_references = ", ".join(
                f"_id={document_id} (status={status})"
                for document_id, status in inactive_documents
            )
            failures.append(
                f"[Status ativo] Índice '{CVE_TRENDS_INDEX_NAME}' | "
                f"{len(inactive_documents)} documento(s) não estão com status 'ativo': "
                f"{document_references}."
            )
