from __future__ import annotations

from src.connections.opensearch import OpenSearchConnection


class OpenSearchHealthRepository:
    """Expõe verificações de saúde do OpenSearch para os testes."""

    def __init__(self, connection: OpenSearchConnection) -> None:
        self._connection = connection

    def check_connection(self) -> bool:
        """Retorna se o cluster OpenSearch responde ao ping."""
        try:
            return bool(self._connection.client.ping())
        except Exception:
            return False

    def list_indices(self) -> list[str]:
        """Lista os nomes dos índices visíveis para o usuário configurado."""
        indices = self._connection.client.cat.indices(format="json")
        return sorted(item["index"] for item in indices if "index" in item)