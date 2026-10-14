from __future__ import annotations

import requests

from src.config.settings import OpenSearchSettings
from src.connections.base import BaseConnection


class OpenSearchDashboardsConnection(BaseConnection[requests.Session]):
    """Gerencia a sessão HTTP da API do OpenSearch Dashboards."""

    def __init__(
        self,
        settings: OpenSearchSettings,
        path_prefix: str = "",
        request_timeout: int = 10,
    ) -> None:
        self._settings = settings
        self._path_prefix = path_prefix.rstrip("/")
        self._request_timeout = request_timeout
        self._client: requests.Session | None = None

    def connect(self) -> requests.Session:
        if self._client is None:
            self._client = requests.Session()
            self._client.auth = (self._settings.user, self._settings.password)

        return self._client

    @property
    def client(self) -> requests.Session:
        return self.connect()

    def get(self, path: str, *, params: dict[str, str | int]) -> requests.Response:
        scheme = "https" if self._settings.use_ssl else "http"
        url = (
            f"{scheme}://{self._settings.host}:{self._settings.port}"
            f"{self._path_prefix}{path}"
        )
        return self.client.get(
            url,
            params=params,
            headers={"osd-xsrf": "true"},
            timeout=self._request_timeout,
            verify=self._settings.verify_certs,
        )

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None