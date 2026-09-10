from __future__ import annotations

import logging
from datetime import date
from typing import Any

from src.repositories.opensearch_client_rsa_repository import OpenSearchClientRepository
from src.validators.opensearch_mapping_validator import OpenSearchMappingValidator


logger = logging.getLogger(__name__)


class OpenSearchClientValidationHelper:
    """Regras reutilizáveis para documentos e mappings de índices por cliente."""

    @staticmethod
    def validate_latest_document(
        repository: OpenSearchClientRepository,
        client_id: str,
        host: str,
        index_name: str,
        reference_date: date,
    ) -> tuple[list[str], list[str]]:
        document = repository.get_latest_document(host, index_name)
        if document is None:
            return [f"Cliente '{client_id}' | índice '{index_name}' | nenhum documento encontrado."], []

        source = document.get("_source", {})
        timestamp = str(source.get("@timestamp", ""))
        details = [f"Última leitura (@timestamp): {timestamp or 'não informado'}."
        ]
        logger.info("Cliente %s | índice %s | %s", client_id, index_name, " | ".join(details))
        if timestamp.startswith(reference_date.isoformat()):
            return [], details
        return [
            f"Cliente '{client_id}' | índice '{index_name}' | o documento mais recente "
            f"possui @timestamp '{timestamp or 'não informado'}', mas era esperada a data "
            f"'{reference_date:%Y-%m-%d}'."
        ], details

    @staticmethod
    def validate_mapping(
        repository: OpenSearchClientRepository,
        host: str,
        index_name: str,
        expected_mapping: dict[str, Any],
    ) -> tuple[bool, list[str]]:
        metadata = repository.get_index_metadata(host, index_name)
        if not metadata.mapping:
            return False, []
        return True, OpenSearchMappingValidator().validate(
            metadata.mapping.get("properties", {}), expected_mapping
        )
