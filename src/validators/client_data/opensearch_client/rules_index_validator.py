from __future__ import annotations

from src.config.settings import ClientTarget
from src.models.client_validation_result import ClientValidationResult
from src.models.opensearch_client.rules_mapping import (
    EXPECTED_RULES_MAPPING,
    RULES_INDEX_NAME,
)
from src.queries.cognito_client_queries import SELECT_COGNITO_CLIENT_HAS_ALERTS_BY_ID
from src.repositories.db_client_repository import DataBaseRepository
from src.repositories.opensearch_client_rsa_repository import OpenSearchClientRepository
from src.validators.opensearch_mapping_validator import OpenSearchMappingValidator


class RulesIndexValidator:
    """Valida documentos e mapping do índice rules por cliente."""

    def __init__(
        self,
        cognito_repository: DataBaseRepository,
        opensearch_repository: OpenSearchClientRepository,
    ) -> None:
        self._cognito_repository = cognito_repository
        self._opensearch_repository = opensearch_repository

    def validate(self, target: ClientTarget) -> ClientValidationResult:
        client = self._cognito_repository.get_table(
            "public", target.client_id, SELECT_COGNITO_CLIENT_HAS_ALERTS_BY_ID
        )
        if not client:
            return ClientValidationResult(
                target.client_id,
                failures=[
                    f"Cliente '{target.client_id}' não encontrado no Cognito; "
                    "consulta de has_alerts não retornou registro."
                ],
            )
        if not client.get("has_alerts"):
            return ClientValidationResult(
                target.client_id,
                infos=[
                    f"Cliente '{target.client_id}' possui has_alerts desabilitado; "
                    "índice rules não aplicável."
                ],
            )

        host = target.host or client["octopus_endpoint"].replace("https://", "")
        try:
            failures: list[str] = []
            if not self._opensearch_repository.get_documents(host, RULES_INDEX_NAME):
                failures.append(
                    f"Cliente '{target.client_id}' | host '{host}' | índice rules "
                    "retornou zero documentos."
                )

            metadata = self._opensearch_repository.get_index_metadata(host, RULES_INDEX_NAME)
            if not metadata.mapping:
                failures.append(
                    f"Cliente '{target.client_id}' | host '{host}' | índice rules "
                    "não possui mapping configurado."
                )
            else:
                failures.extend(
                    f"Cliente '{target.client_id}' | índice '{RULES_INDEX_NAME}' | "
                    f"host '{host}' | mapping inválido: {error}"
                    for error in OpenSearchMappingValidator().validate(
                        metadata.mapping.get("properties", {}), EXPECTED_RULES_MAPPING
                    )
                )
            return ClientValidationResult(target.client_id, failures=failures)
        except Exception as error:
            return ClientValidationResult(
                target.client_id,
                failures=[
                    f"Cliente '{target.client_id}' | host '{host}' | falha ao validar "
                    f"o índice rules: {error.__class__.__name__}: {error}"
                ],
            )
