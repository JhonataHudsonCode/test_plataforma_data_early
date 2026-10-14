from __future__ import annotations

from enum import Enum

from src.config.settings import OpenSearchSettings, PostgresSettings
from src.connections.base import BaseConnection
from src.connections.opensearch import OpenSearchConnection
from src.connections.postgres import PostgresConnection


class ConnectionType(str, Enum):
    POSTGRES = "postgres"
    OPENSEARCH = "opensearch"


class ConnectionFactory:
    """Ponto único de criação para clientes suportados pelo repositório."""

    @staticmethod
    def create(
        connection_type: ConnectionType,
        settings: PostgresSettings | OpenSearchSettings,
    ) -> BaseConnection:
        if connection_type is ConnectionType.POSTGRES:
            if not isinstance(settings, PostgresSettings):
                raise TypeError("Postgres requer PostgresSettings.")
            return PostgresConnection(settings)

        if connection_type is ConnectionType.OPENSEARCH:
            if not isinstance(settings, OpenSearchSettings):
                raise TypeError("OpenSearch requer OpenSearchSettings.")
            return OpenSearchConnection(settings)

        raise ValueError(f"Tipo de conexão não suportado: {connection_type}")