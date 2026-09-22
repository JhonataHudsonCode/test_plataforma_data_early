from __future__ import annotations

from datetime import date

from src.config.settings import ClientTarget
from src.models.client_validation_result import ClientValidationResult
from src.models.opensearch_client.rsa_mapping import (
    EXPECTED_RSA_MAPPING,
    RSA_INDEX_NAME,
)
from src.queries.cognito_client_queries import SELECT_COGNITO_CLIENT_HAS_RSA_BY_ID
from src.repositories.db_client_repository import DataBaseRepository
from src.repositories.opensearch_client_rsa_repository import OpenSearchClientRepository
from src.validators.client_data.opensearch_client.helpers import OpenSearchClientValidationHelper


CLIENT_SCHEMA = "public"


class RsaIndexValidator:
    """Valida a disponibilidade, atualidade e contrato do índice RSA por cliente."""

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
            schema_name=CLIENT_SCHEMA,
            client_id=target.client_id,
            query=SELECT_COGNITO_CLIENT_HAS_RSA_BY_ID,
        )
        if not client:
            return ClientValidationResult(
                target.client_id,
                failures=[
                    f"Cliente '{target.client_id}' não encontrado no Cognito; "
                    "consulta de has_rsa não retornou registro."
                ],
            )
        if not client.get("has_rsa"):
            return ClientValidationResult(
                target.client_id,
                infos=[
                    f"Cliente '{target.client_id}' possui has_rsa desabilitado; "
                    "índice RSA não aplicável."
                ],
            )

        host = target.host or client["octopus_endpoint"].replace("https://", "")
        try:
            indices = self._opensearch_repository.get_indices_rsa(host, RSA_INDEX_NAME)
            index = {item.name: item for item in indices}.get(RSA_INDEX_NAME)
            if index is None:
                return ClientValidationResult(
                    target.client_id,
                    failures=[
                        f"Cliente '{target.client_id}' | host '{host}' | índice RSA "
                        f"'{RSA_INDEX_NAME}' não encontrado. Índices encontrados: "
                        f"{', '.join(item.name for item in indices) or 'nenhum'}."
                    ],
                )

            failures, details = OpenSearchClientValidationHelper.validate_latest_document(
                self._opensearch_repository, target.client_id, host, RSA_INDEX_NAME,
                self._reference_date,
            )
            has_mapping, mapping_errors = OpenSearchClientValidationHelper.validate_mapping(
                self._opensearch_repository, host, RSA_INDEX_NAME, EXPECTED_RSA_MAPPING
            )
            if not has_mapping:
                failures.append(f"Cliente '{target.client_id}' | índice RSA '{RSA_INDEX_NAME}' não possui mapping configurado. Host: '{host}'.")
            failures.extend(mapping_errors)
            return ClientValidationResult(target.client_id, failures=failures, details=details)
        except Exception as error:
            return ClientValidationResult(
                target.client_id,
                failures=[
                    f"Cliente '{target.client_id}' | falha ao validar o índice RSA "
                    f"'{RSA_INDEX_NAME}': {error.__class__.__name__}: {error}"
                ],
            )
