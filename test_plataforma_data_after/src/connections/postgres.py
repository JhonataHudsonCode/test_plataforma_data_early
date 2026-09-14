from __future__ import annotations

from psycopg import Connection, connect

from src.config.settings import PostgresSettings
from src.connections.base import BaseConnection


class PostgresConnection(BaseConnection[Connection]):
    """Gerencia exclusivamente o ciclo de vida da conexão PostgreSQL."""

    def __init__(self, settings: PostgresSettings) -> None:
        self._settings = settings
        self._connection: Connection | None = None

    def connect(self) -> Connection:
        if self._connection is None or self._connection.closed:
            self._connection = connect(
                host=self._settings.host,
                port=self._settings.port,
                dbname=self._settings.database,
                user=self._settings.user,
                password=self._settings.password,
                connect_timeout=self._settings.connect_timeout,
                autocommit=True,
            )

        return self._connection

    @property
    def client(self) -> Connection:
        return self.connect()

    def close(self) -> None:
        if self._connection is not None and not self._connection.closed:
            self._connection.close()

    def __enter__(self) -> "PostgresConnection":
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()