from __future__ import annotations

from datetime import date

from src.models.client_validation_result import ClientValidationResult
from src.models.opensearch_product.epss_mapping import EPSS_INDEX_NAME, EXPECTED_EPSS_MAPPING
from src.repositories.opensearch_vulnerability_repository import OpenSearchVulnerabilityRepository
from src.validators.client_data.opensearch_product.helpers import OpenSearchProductValidationHelper


class EpssIndexValidator:
    """Valida disponibilidade, contrato e atualidade do índice EPSS."""

    def __init__(
        self,
        product_repository: OpenSearchVulnerabilityRepository,
        reference_date: date,
    ) -> None:
        self._product_repository = product_repository
        self._reference_date = reference_date

    def validate(self, client_id: str) -> ClientValidationResult:
        failures: list[str] = []
        details: list[str] = []
        try:
            indices = self._product_repository.get_indices_epss(EPSS_INDEX_NAME)
            index = {item.name: item for item in indices}.get(EPSS_INDEX_NAME)
            if index is None:
                return ClientValidationResult(
                    client_id,
                    failures=[
                        f"[Geral] Cliente '{client_id}' | índice de produto "
                        f"'{EPSS_INDEX_NAME}' não encontrado."
                    ],
                )

            details.append(
                f"[Geral] Cliente '{client_id}' | índice de produto "
                f"'{EPSS_INDEX_NAME}' encontrado com {index.document_count} documento(s)."
            )
            if index.document_count <= 0:
                failures.append(
                    f"[Geral] Cliente '{client_id}' | índice de produto "
                    f"'{EPSS_INDEX_NAME}' não contém documentos."
                )

            mapping_available, mapping_errors = (
                OpenSearchProductValidationHelper.validate_mapping(
                    self._product_repository,
                    EPSS_INDEX_NAME,
                    EXPECTED_EPSS_MAPPING,
                )
            )
            if not mapping_available:
                failures.append(
                    f"[Mapping] Cliente '{client_id}' | índice '{EPSS_INDEX_NAME}' | "
                    f"consulta GET /{EPSS_INDEX_NAME}/_mapping não retornou propriedades "
                    "para validação."
                )
            else:
                failures.extend(
                    f"[Mapping] Cliente '{client_id}' | índice '{EPSS_INDEX_NAME}' | "
                    f"mapping inválido: {error}"
                    for error in mapping_errors
                )
                if not mapping_errors:
                    details.append(
                        f"[Mapping] Índice '{EPSS_INDEX_NAME}' | propriedades retornadas por "
                        f"GET /{EPSS_INDEX_NAME}/_mapping validadas com sucesso."
                    )

            metadata = self._product_repository.get_index_metadata(EPSS_INDEX_NAME)
            if metadata.created_at.date() != self._reference_date:
                failures.append(
                    f"[Geral] Cliente '{client_id}' | índice '{EPSS_INDEX_NAME}' foi "
                    f"criado em '{metadata.created_at:%Y-%m-%d}', esperada "
                    f"'{self._reference_date:%Y-%m-%d}'."
                )
            else:
                details.append(
                    f"[Geral] Índice '{EPSS_INDEX_NAME}' | creation_date "
                    f"{metadata.created_at:%Y-%m-%d} validada com sucesso."
                )
        except Exception as error:
            failures.append(
                f"[Geral] Cliente '{client_id}' | falha ao validar o índice de produto "
                f"'{EPSS_INDEX_NAME}': {error.__class__.__name__}: {error}"
            )
        return ClientValidationResult(client_id, failures=failures, details=details)
