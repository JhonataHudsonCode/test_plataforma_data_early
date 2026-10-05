from __future__ import annotations

from dataclasses import replace
from urllib.parse import urlparse

from src.config.settings import OpenSearchSettings
from src.config.settings import ClientOpenSearchCredentials
from src.connections.opensearch import OpenSearchConnection


class OpenSearchConnectionFactory:
    """Cria conexões OpenSearch que compartilham as mesmas credenciais."""

    def __init__(
        self,
        settings: OpenSearchSettings,
        client_credentials: list[ClientOpenSearchCredentials] | None = None,
    ) -> None:
        self._settings = settings
        self._client_credentials = client_credentials or []

    def create_for_host(self, host: str) -> OpenSearchConnection:
        endpoint = host.strip().rstrip("/")
        parsed = urlparse(
            endpoint if "://" in endpoint else f"https://{endpoint}"
        )
        normalized_host = parsed.hostname or parsed.path
        port = parsed.port or self._settings.port
        credentials = next(
            (
                item
                for item in self._client_credentials
                if item.host == normalized_host
            ),
            None,
        )
        if credentials is None:
            return OpenSearchConnection(
                replace(self._settings, host=normalized_host, port=port)
            )
        return self.create_for_client(credentials)

    def create_for_client(
        self,
        credentials: ClientOpenSearchCredentials,
    ) -> OpenSearchConnection:
        settings = replace(
            self._settings,
            host=credentials.host,
            port=credentials.port or self._settings.port,
            user=credentials.username,
            password=credentials.password,
        )
        return OpenSearchConnection(settings)
