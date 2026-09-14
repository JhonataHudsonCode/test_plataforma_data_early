from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


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