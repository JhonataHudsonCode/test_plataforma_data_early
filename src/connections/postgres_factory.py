from __future__ import annotations

from dataclasses import replace

from src.config.settings import PostgresSettings
from src.connections.postgres import PostgresConnection


class PostgresConnectionFactory:
    """Cria conexões PostgreSQL com as mesmas credenciais e database variável."""

    def __init__(self, settings: PostgresSettings) -> None:
        self._settings = settings

    def create_for_database(self, database: str) -> PostgresConnection:
        return PostgresConnection(replace(self._settings, database=database))