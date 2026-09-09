from __future__ import annotations

import os
import json
import re
from dataclasses import dataclass
from urllib.parse import urlparse

from dotenv import load_dotenv


load_dotenv(f".env_{os.getenv('TEST_ENV', 'hml')}", override=False)
load_dotenv(override=False)


def _env(key: str) -> str:
    value = os.getenv(key)
    if value is None or value == "":
        raise ValueError(f"Variável de ambiente obrigatória não configurada: {key}")

    return value


def _to_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


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
            host=_env("OPENSEARCH_HOST"),
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
    activation_key_name: str
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
class ClientTarget:
    client_id: str
    activation_key_name: str | None = None
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


def client_credentials_from_env() -> list[ClientOpenSearchCredentials]:
    raw = os.getenv("OCTOPUS_CLIENT_CREDENTIALS", "{}")
    try:
        values = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError("OCTOPUS_CLIENT_CREDENTIALS deve ser um JSON válido.") from error

    if not isinstance(values, dict):
        raise ValueError("OCTOPUS_CLIENT_CREDENTIALS deve ser um objeto JSON.")

    credentials: list[ClientOpenSearchCredentials] = []
    for name, value in values.items():
        if not isinstance(value, dict):
            raise ValueError(f"Credenciais inválidas para o cliente {name}.")
        endpoint = value.get("endpoint") or value.get("host")
        if not endpoint:
            raise ValueError(f"Endpoint ausente para o cliente {name}.")
        credentials.append(
            ClientOpenSearchCredentials(
                name=name,
                endpoint=endpoint,
                client_id=str(value.get("client_id", name)),
                activation_key_name=str(value.get("activation_key_name", "")),
                username=_resolve_secret(
                    str(value.get("username", "")),
                    "OPENSEARCH_USER",
                ),
                password=_resolve_secret(
                    str(value.get("password", "")),
                    "OPENSEARCH_PASSWORD",
                ),
            )
        )
    return credentials