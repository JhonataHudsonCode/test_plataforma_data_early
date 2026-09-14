from __future__ import annotations

from src.models.client_validation_result import ClientValidationResult
from src.models.opensearch_product.cve_trends_mapping import CVE_TRENDS_INDEX_NAME, EXPECTED_CVE_TRENDS_MAPPING
from src.repositories.opensearch_vulnerability_repository import OpenSearchVulnerabilityRepository
from src.validators.opensearch_mapping_validator import OpenSearchMappingValidator


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
                failures.append(f"Índice de produto '{CVE_TRENDS_INDEX_NAME}' não encontrado.")
            elif index.document_count <= 0:
                failures.append(f"Índice de produto '{CVE_TRENDS_INDEX_NAME}' não contém documentos.")
            else:
                details.append(
                    f"Índice '{CVE_TRENDS_INDEX_NAME}' encontrado com "
                    f"{index.document_count} documento(s)."
                )
                active_documents = self._product_repository.get_documents_by_status(
                    CVE_TRENDS_INDEX_NAME,
                    "ativo",
                    index.document_count,
                )
                if not active_documents:
                    failures.append(
                        f"Nenhum documento com status 'ativo' foi encontrado no "
                        f"índice '{CVE_TRENDS_INDEX_NAME}'."
                    )
                else:
                    details.append(
                        f"Documento(s) ativo(s) encontrado(s): "
                        f"{len(active_documents)}."
                    )

            metadata = self._product_repository.get_index_metadata(CVE_TRENDS_INDEX_NAME)
            if not metadata.mapping:
                failures.append(f"Índice '{CVE_TRENDS_INDEX_NAME}' não possui mapping configurado.")
            else:
                mapping_failures = [
                    f"Índice '{CVE_TRENDS_INDEX_NAME}' | mapping inválido: {error}"
                    for error in OpenSearchMappingValidator().validate(metadata.mapping.get("properties", {}), EXPECTED_CVE_TRENDS_MAPPING)
                ]
                failures.extend(mapping_failures)
                if not mapping_failures:
                    details.append("Mapping do índice validado com sucesso.")
        except Exception as error:
            failures.append(f"Falha ao validar o índice de produto '{CVE_TRENDS_INDEX_NAME}': {error.__class__.__name__}: {error}")
        return ClientValidationResult(report_id, failures=failures, details=details)
