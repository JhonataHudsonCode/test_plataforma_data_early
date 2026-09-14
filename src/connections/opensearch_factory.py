from __future__ import annotations

from dataclasses import replace

from src.config.settings import OpenSearchSettings
from src.connections.opensearch import OpenSearchConnection


class OpenSearchConnectionFactory:
    """Cria conexões OpenSearch que compartilham as mesmas credenciais."""

    def __init__(self, settings: OpenSearchSettings) -> None:
        self._settings = settings

    def create_for_host(self, host: str) -> OpenSearchConnection:
        return OpenSearchConnection(replace(self._settings, host=host))