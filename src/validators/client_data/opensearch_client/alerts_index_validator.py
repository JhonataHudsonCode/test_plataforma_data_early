from __future__ import annotations

from datetime import date

from src.config.settings import ClientTarget
from src.models.client_validation_result import ClientValidationResult
from src.models.opensearch_client.elastalert_status_mapping import (
    ELASTALERT_STATUS_INDEX_NAME,
    EXPECTED_ELASTALERT_STATUS_MAPPING,
)
from src.queries.cognito_client_queries import SELECT_COGNITO_CLIENT_HAS_ALERTS_BY_ID
from src.repositories.db_client_repository import DataBaseRepository
from src.repositories.opensearch_client_rsa_repository import OpenSearchClientRepository
from src.validators.opensearch_mapping_validator import OpenSearchMappingValidator


class AlertsIndexValidator:
    """Valida o índice de status de alertas nos OpenSearch dos clientes."""

    def __init__(
        self,
        cognito_repository: DataBaseRepository,
        opensearch_repository: OpenSearchClientRepository,
        reference_date: date,
    ) -> None:
        self._cognito_repository = cognito_repository
        self._opensearch_repository = opensearch_repository
        self._reference_date = reference_date

    def validate(self, target: ClientTarget) -> ClientValidationResult:
        client = self._cognito_repository.get_table(
            "public", target.client_id, SELECT_COGNITO_CLIENT_HAS_ALERTS_BY_ID
        )
        if not client:
            return ClientValidationResult(
                target.client_id,
                failures=[f"Cliente '{target.client_id}' não encontrado no Cognito."],
            )
        if not client.get("has_alerts"):
            return ClientValidationResult(
                target.client_id,
                infos=[
                    f"Cliente '{target.client_id}' possui has_alerts desabilitado; "
                    "validação do OpenSearch não aplicável."
                ],
            )

        host = target.host or client["octopus_endpoint"].replace("https://", "")
        try:
            indices = self._opensearch_repository.get_indices_elastalerts_status_today(
                host, ELASTALERT_STATUS_INDEX_NAME
            )
            failures: list[str] = []
            if ELASTALERT_STATUS_INDEX_NAME not in {item.name for item in indices}:
                failures.append(
                    f"Cliente '{target.client_id}' | índice '{ELASTALERT_STATUS_INDEX_NAME}' "
                    f"não encontrado no host '{host}'. Índices encontrados: "
                    f"{', '.join(item.name for item in indices) or 'nenhum'}"
                )

            metadata = self._opensearch_repository.get_index_metadata(host, ELASTALERT_STATUS_INDEX_NAME)
            if metadata.created_at.date() != self._reference_date:
                failures.append(
                    f"Cliente '{target.client_id}' | índice '{ELASTALERT_STATUS_INDEX_NAME}' "
                    f"com data de criação '{metadata.created_at:%Y-%m-%d}', mas era esperada "
                    f"a data '{self._reference_date:%Y-%m-%d}'. Host consultado: '{host}'."
                )
            if not metadata.mapping:
                failures.append(
                    f"Cliente '{target.client_id}' | índice '{ELASTALERT_STATUS_INDEX_NAME}' "
                    f"não possui mapping configurado. Host consultado: '{host}'."
                )
            else:
                failures.extend(
                    f"Cliente '{target.client_id}' | índice '{ELASTALERT_STATUS_INDEX_NAME}' | "
                    f"host '{host}' | mapping inválido: {error}"
                    for error in OpenSearchMappingValidator().validate(
                        metadata.mapping.get("properties", {}),
                        EXPECTED_ELASTALERT_STATUS_MAPPING,
                    )
                )
            return ClientValidationResult(target.client_id, failures=failures)
        except Exception as error:
            return ClientValidationResult(
                target.client_id,
                failures=[
                    f"Cliente '{target.client_id}' | endpoint '{host}' | falha inesperada durante "
                    f"a validação de '{ELASTALERT_STATUS_INDEX_NAME}': "
                    f"{error.__class__.__name__}: {error}"
                ],
            )
