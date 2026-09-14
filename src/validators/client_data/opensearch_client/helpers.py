from __future__ import annotations

import logging
from calendar import monthrange
from datetime import date, datetime
from typing import Any

from src.repositories.opensearch_client_rsa_repository import OpenSearchClientRepository
from src.validators.opensearch_mapping_validator import OpenSearchMappingValidator


logger = logging.getLogger(__name__)


class OpenSearchClientValidationHelper:
    """Regras reutilizáveis para documentos e mappings de índices por cliente."""

    @staticmethod
    def get_latest_document(
        repository: OpenSearchClientRepository,
        host: str,
        index_name: str,
    ) -> dict[str, Any] | None:
        """Busca o documento mais recente pelo campo @timestamp."""
        documents = repository.get_documents(
            host,
            index_name,
            size=1,
            sort_by_timestamp=True,
        )
        return documents[0] if documents else None

    @staticmethod
    def validate_latest_document(
        repository: OpenSearchClientRepository,
        client_id: str,
        host: str,
        index_name: str,
        reference_date: date,
    ) -> tuple[list[str], list[str]]:
        document = OpenSearchClientValidationHelper.get_latest_document(
            repository,
            host,
            index_name,
        )
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

    @staticmethod
    def validate_document_minimum_age(
        repository: OpenSearchClientRepository,
        client_id: str,
        host: str,
        index_name: str,
        minimum_months: int = 1,
        date_field: str = "@timestamp",
        reference_date: date | None = None,
    ) -> list[str]:
        """Valida se um documento possui data de criação mínima parametrizada."""
        if minimum_months < 1:
            raise ValueError("minimum_months deve ser maior ou igual a 1.")

        document = OpenSearchClientValidationHelper.get_latest_document(
            repository,
            host,
            index_name,
        )
        if document is None:
            return [
                f"Cliente '{client_id}' | índice '{index_name}' | nenhum documento encontrado."
            ]

        value = str(document.get("_source", {}).get(date_field, ""))
        if not value:
            return [
                f"Cliente '{client_id}' | índice '{index_name}' | campo "
                f"'{date_field}' não informado no documento."
            ]

        try:
            document_date = datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        except ValueError:
            return [
                f"Cliente '{client_id}' | índice '{index_name}' | campo "
                f"'{date_field}' possui data inválida: '{value}'."
            ]

        comparison_date = reference_date or date.today()
        cutoff_date = OpenSearchClientValidationHelper._subtract_months(
            comparison_date,
            minimum_months,
        )
        if document_date <= cutoff_date:
            return []
        return [
            f"Cliente '{client_id}' | índice '{index_name}' | documento com "
            f"'{date_field}' em '{document_date:%Y-%m-%d}' possui menos de "
            f"{minimum_months} mês(es) de criação. Data limite: "
            f"'{cutoff_date:%Y-%m-%d}'."
        ]

    @staticmethod
    def _subtract_months(reference_date: date, months: int) -> date:
        month_index = reference_date.year * 12 + reference_date.month - 1 - months
        year, month_zero_based = divmod(month_index, 12)
        month = month_zero_based + 1
        return date(year, month, min(reference_date.day, monthrange(year, month)[1]))
