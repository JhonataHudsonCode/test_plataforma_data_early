from __future__ import annotations

import os
import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEST_ENV = os.getenv("TEST_ENV", "hml")

# Usa caminhos absolutos para que o VS Code Debugger não dependa do cwd atual.
# O padrão do projeto é .env.hml/.env.prod; o formato legado com _ é mantido
# apenas para não interromper ambientes que ainda o utilizam.
load_dotenv(PROJECT_ROOT / f".env.{TEST_ENV}", override=False)
load_dotenv(PROJECT_ROOT / f".env_{TEST_ENV}", override=False)
load_dotenv(PROJECT_ROOT / ".env", override=False)


def _env(key: str) -> str:
    value = os.getenv(key)
    if value is None or value == "":
        raise ValueError(f"Variável de ambiente obrigatória não configurada: {key}")

    return value


def _to_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _strip_scheme(value: str) -> str:
    """Remove um esquema http(s):// acidentalmente incluído no host."""
    return re.sub(r"^https?://", "", value.strip()).rstrip("/")


@dataclass(frozen=True, slots=True)
class PostgresSettings:
    host: str
    port: int
    database: str
    user: str
    password: str
    connect_timeout: int
    target_schema: str
    target_table: str

    @classmethod
    def from_env(cls) -> "PostgresSettings":
        return cls(
            host=_env("PG_HOST"),
            port=int(_env("PG_PORT")),
            database=_env("PG_DATABASE"),
            user=_env("PG_USER"),
            password=_env("PG_PASSWORD"),
            connect_timeout=int(_env("PG_CONNECT_TIMEOUT")),
            target_schema=_env("PG_TARGET_SCHEMA"),
            target_table=_env("PG_TARGET_TABLE"),
        )


@dataclass(frozen=True, slots=True)
class OpenSearchSettings:
    host: str
    port: int
    user: str
    password: str
    use_ssl: bool
    verify_certs: bool

    @classmethod
    def from_env(cls) -> "OpenSearchSettings":
        return cls(
            host=_strip_scheme(_env("OPENSEARCH_HOST")),
            port=int(_env("OPENSEARCH_PORT")),
            user=_env("OPENSEARCH_USER"),
            password=_env("OPENSEARCH_PASSWORD"),
            use_ssl=_to_bool(_env("OPENSEARCH_USE_SSL")),
            verify_certs=_to_bool(_env("OPENSEARCH_VERIFY_CERTS")),
        )


@dataclass(frozen=True, slots=True)
class ClientOpenSearchCredentials:
    name: str
    endpoint: str
    client_id: str
    username: str
    password: str

    @property
    def host(self) -> str:
        endpoint = self.endpoint.lstrip(":")
        parsed = urlparse(endpoint if "://" in endpoint else f"https://{endpoint}")
        return parsed.hostname or parsed.path

    @property
    def port(self) -> int | None:
        endpoint = self.endpoint.lstrip(":")
        parsed = urlparse(endpoint if "://" in endpoint else f"https://{endpoint}")
        return parsed.port


@dataclass(frozen=True, slots=True)
class WazuhCredentials:
    """Credenciais de acesso à API Wazuh de um ambiente de cliente."""

    name: str
    endpoint: str
    internal_endpoint: str
    username: str
    password: str


@dataclass(frozen=True, slots=True)
class ClientTarget:
    client_id: str
    endpoint: str | None = None
    credentials: ClientOpenSearchCredentials | None = None

    @property
    def host(self) -> str | None:
        return self.credentials.host if self.credentials else self.endpoint


def client_selection_source() -> str:
    source = os.getenv("CLIENT_SELECTION_SOURCE", "database").strip().lower()
    if source not in {"database", "credentials"}:
        raise ValueError("CLIENT_SELECTION_SOURCE deve ser database ou credentials.")
    return source


def _resolve_secret(value: str, fallback_key: str) -> str:
    match = re.fullmatch(r"\$\{([^}]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)", value)
    if not match:
        return value or os.getenv(fallback_key, "")
    return os.getenv(match.group(1) or match.group(2)) or os.getenv(fallback_key, "")


def _ensure_https(endpoint: str) -> str:
    """Prefixa o endpoint com https:// quando nenhum esquema foi informado."""
    endpoint = endpoint.strip()
    if not endpoint or "://" in endpoint:
        return endpoint
    return f"https://{endpoint}"


def client_credentials_from_env() -> list[ClientOpenSearchCredentials]:
    raw = os.getenv("OCTOPUS_CLIENT_CREDENTIALS", "[]")
    try:
        values = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError("OCTOPUS_CLIENT_CREDENTIALS deve ser um JSON válido.") from error

    if not isinstance(values, list):
        raise ValueError("OCTOPUS_CLIENT_CREDENTIALS deve ser uma lista JSON.")

    credentials: list[ClientOpenSearchCredentials] = []
    for value in values:
        if not isinstance(value, dict):
            raise ValueError("Credenciais inválidas em OCTOPUS_CLIENT_CREDENTIALS.")
        host = value.get("host")
        client_id = str(value.get("client_id", "")).strip()
        if not host:
            raise ValueError(f"Host ausente para o cliente {client_id or '?'}.")
        if not client_id:
            raise ValueError("client_id ausente em uma credencial do Octopus.")
        credentials.append(
            ClientOpenSearchCredentials(
                name=client_id,
                endpoint=_ensure_https(str(host)),
                client_id=client_id,
                username=_resolve_secret(
                    str(value.get("user", "")),
                    "OPENSEARCH_USER",
                ),
                password=_resolve_secret(
                    str(value.get("pass", "")),
                    "OPENSEARCH_PASSWORD",
                ),
            )
        )
    return credentials


def wazuh_credentials_from_env() -> list[WazuhCredentials]:
    """Carrega as credenciais Wazuh sem reutilizar os alvos do Octopus."""
    raw = os.getenv("WAZUH_CREDENTIALS", "{}")
    try:
        values = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError("WAZUH_CREDENTIALS deve ser um JSON válido.") from error

    if not isinstance(values, dict):
        raise ValueError("WAZUH_CREDENTIALS deve ser um objeto JSON.")

    credentials: list[WazuhCredentials] = []
    for name, value in values.items():
        if not isinstance(value, dict):
            raise ValueError(f"Credenciais Wazuh inválidas para {name}.")
        endpoint = str(value.get("endpoint", "")).strip()
        internal_endpoint = str(value.get("internal_endpoint", "")).strip()
        if not endpoint or not internal_endpoint:
            raise ValueError(
                f"Endpoints externo e interno são obrigatórios para o Wazuh {name}."
            )
        credentials.append(
            WazuhCredentials(
                name=name,
                endpoint=_ensure_https(endpoint),
                internal_endpoint=_ensure_https(internal_endpoint),
                username=_resolve_secret(str(value.get("username", "")), "WAZUH_USERNAME"),
                password=_resolve_secret(str(value.get("password", "")), "WAZUH_PASSWORD"),
            )
        )
    return credentials