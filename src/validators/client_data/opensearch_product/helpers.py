from __future__ import annotations

from datetime import date

from src.repositories.opensearch_vulnerability_repository import OpenSearchVulnerabilityRepository


class OpenSearchProductValidationHelper:
    """Regras reutilizáveis para documentos dos índices de produto."""

    @staticmethod
    def get_latest_document(
        repository: OpenSearchVulnerabilityRepository,
        index_name: str,
    ) -> dict | None:
        """Busca o documento mais recente pelo campo @timestamp."""
        documents = repository.get_recent_documents(index_name, size=1)
        return documents[0] if documents else None

    @staticmethod
    def validate_latest_document(
        repository: OpenSearchVulnerabilityRepository,
        client_id: str,
        index_name: str,
        reference_date: date,
    ) -> tuple[list[str], list[str]]:
        document = OpenSearchProductValidationHelper.get_latest_document(
            repository,
            index_name,
        )
        if document is None:
            return [f"Cliente '{client_id}' | índice '{index_name}' | nenhum documento encontrado."], []

        timestamp = str(document.get("_source", {}).get("@timestamp", ""))
        detail = f"Índice '{index_name}' | última leitura (@timestamp): {timestamp or 'não informado'}."
        if timestamp.startswith(reference_date.isoformat()):
            return [], [detail]
        return [
            f"Cliente '{client_id}' | índice '{index_name}' | o documento mais recente "
            f"possui @timestamp '{timestamp or 'não informado'}', mas era esperada a data "
            f"'{reference_date:%Y-%m-%d}'."
        ], []
