from __future__ import annotations

import logging
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
from src.validators.opensearch_mapping_validator import OpenSearchMappingValidator


logger = logging.getLogger(__name__)
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

            failures, details = self._validate_latest_document(target.client_id, host)
            failures.extend(self._validate_mapping(target.client_id, host))
            return ClientValidationResult(target.client_id, failures=failures, details=details)
        except Exception as error:
            return ClientValidationResult(
                target.client_id,
                failures=[
                    f"Cliente '{target.client_id}' | falha ao validar o índice RSA "
                    f"'{RSA_INDEX_NAME}': {error.__class__.__name__}: {error}"
                ],
            )

    def _validate_latest_document(
        self,
        client_id: str,
        host: str,
    ) -> tuple[list[str], list[str]]:
        document = self._opensearch_repository.get_latest_document(host, RSA_INDEX_NAME)
        if document is None:
            return [f"Cliente '{client_id}' | índice RSA '{RSA_INDEX_NAME}' | nenhum documento encontrado."], []

        source = document.get("_source", {})
        last_read_at = str(source.get("@timestamp", ""))
        first_scan_at = str(source.get("first_scan", ""))
        details = [
            f"Última leitura (@timestamp): {last_read_at or 'não informado'}.",
            f"Primeira leitura (first_scan): {first_scan_at or 'não informado'}.",
        ]
        logger.info("Cliente %s | índice rsa | %s | %s", client_id, *details)

        if last_read_at.startswith(self._reference_date.isoformat()):
            return [], details
        return [
            f"Cliente '{client_id}' | índice RSA '{RSA_INDEX_NAME}' | "
            f"o documento mais recente possui @timestamp '{last_read_at or 'não informado'}', "
            f"mas era esperada a data '{self._reference_date:%Y-%m-%d}'."
        ], details

    def _validate_mapping(self, client_id: str, host: str) -> list[str]:
        metadata = self._opensearch_repository.get_index_metadata(host, RSA_INDEX_NAME)
        if not metadata.mapping:
            return [
                f"Cliente '{client_id}' | índice RSA '{RSA_INDEX_NAME}' "
                f"não possui mapping configurado. Host: '{host}'."
            ]
        return OpenSearchMappingValidator().validate(
            metadata.mapping.get("properties", {}),
            EXPECTED_RSA_MAPPING,
        )
