from __future__ import annotations

import base64
import ssl
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from src.config.settings import WazuhCredentials


class WazuhAuthenticationError(RuntimeError):
    """Indica falha de comunicação ou autenticação na API Wazuh."""


class WazuhConnection:
    """Cliente mínimo para validar comunicação e autenticação na API Wazuh."""

    _AUTHENTICATION_PATH = "/security/user/authenticate?raw=true"

    def __init__(self, credentials: WazuhCredentials, timeout: int = 20) -> None:
        self._credentials = credentials
        self._timeout = timeout
        self._ssl_context = ssl._create_unverified_context()

    def authenticate(self, endpoint: str) -> None:
        """Autentica no endpoint informado sem expor o token retornado."""
        request = Request(
            self._authentication_url(endpoint),
            headers={
                "Authorization": self._basic_authorization(),
                "Accept": "text/plain",
            },
            method="GET",
        )
        try:
            with urlopen(
                request,
                timeout=self._timeout,
                context=self._ssl_context,
            ) as response:
                token = response.read().decode("utf-8").strip()
        except HTTPError as error:
            if error.code in {401, 403}:
                raise WazuhAuthenticationError(
                    f"autenticação recusada (HTTP {error.code})"
                ) from error
            raise WazuhAuthenticationError(
                f"API Wazuh retornou HTTP {error.code}"
            ) from error
        except (URLError, TimeoutError, OSError) as error:
            raise WazuhAuthenticationError(
                f"não foi possível comunicar com a API Wazuh: {error}"
            ) from error

        if not token:
            raise WazuhAuthenticationError("API Wazuh retornou token de autenticação vazio")

    def _basic_authorization(self) -> str:
        raw_credentials = f"{self._credentials.username}:{self._credentials.password}"
        encoded_credentials = base64.b64encode(raw_credentials.encode("utf-8")).decode("ascii")
        return f"Basic {encoded_credentials}"

    @classmethod
    def _authentication_url(cls, endpoint: str) -> str:
        parsed = urlparse(endpoint if "://" in endpoint else f"https://{endpoint}")
        if not parsed.hostname:
            raise WazuhAuthenticationError(f"endpoint Wazuh inválido: '{endpoint}'")
        host = parsed.hostname
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        port = f":{parsed.port}" if parsed.port is not None else ""
        return f"{parsed.scheme or 'https'}://{host}{port}{cls._AUTHENTICATION_PATH}"
