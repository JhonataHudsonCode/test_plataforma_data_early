from __future__ import annotations

from opensearchpy import OpenSearch

from src.config.settings import OpenSearchSettings
from src.connections.base import BaseConnection


class OpenSearchConnection(BaseConnection[OpenSearch]):
    """Base extensível para testes de integração com OpenSearch."""

    def __init__(self, settings: OpenSearchSettings) -> None:
        self._settings = settings
        self._client: OpenSearch | None = None

    def connect(self) -> OpenSearch:
        if self._client is None:
            self._client = OpenSearch(
                hosts=[
                    {
                        "host": self._settings.host,
                        "port": self._settings.port,
                    }
                ],
                http_auth=(self._settings.user, self._settings.password),
                use_ssl=self._settings.use_ssl,
                verify_certs=self._settings.verify_certs,
            )

        return self._client

    @property
    def client(self) -> OpenSearch:
        return self.connect()

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None