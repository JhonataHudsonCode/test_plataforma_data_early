from __future__ import annotations

from typing import Any

from psycopg import sql
from psycopg.rows import dict_row

from src.connections.postgres import PostgresConnection
from src.models.client_metadata import ClientMetadata, ClientMetadataAsset
from src.queries.cognito_client_queries import (
    SELECT_ALL_CLIENTS,
    SELECT_ID_CLIENTS
)
from src.queries.assets_client_queries import SELECT_ASSETS_CLIENT_ACTIVATION_KEYS

class DataBaseRepository:
    """Consulta os clientes disponíveis no banco."""

    def __init__(self, connection: PostgresConnection) -> None:
        self._connection = connection

    def get_table(
        self,
        schema_name: str,
        client_id: str,
        query: str
    ) -> dict[str, Any] | None:
        formatted_query = sql.SQL(query).format(
            schema_name=sql.Identifier(schema_name),
        )
        with self._connection.client.cursor(row_factory=dict_row) as cursor:
            cursor.execute(formatted_query, (client_id,))
            return cursor.fetchone()

    def get_all_clients(self, schema_name: str) -> list[dict[str, Any]]:
        query = sql.SQL(SELECT_ALL_CLIENTS).format(
            schema_name=sql.Identifier(schema_name),
        )
        with self._connection.client.cursor(row_factory=dict_row) as cursor:
            cursor.execute(query)
            return list(cursor.fetchall())

    def get_id_clients(self, schema_name: str) -> list[dict[str, Any]]:
        query = sql.SQL(SELECT_ID_CLIENTS).format(
            schema_name=sql.Identifier(schema_name),
        )
        with self._connection.client.cursor(row_factory=dict_row) as cursor:
            cursor.execute(query)
            return list(cursor.fetchall())
    
    def list_clients(self, schema_name: str) -> list[ClientMetadata]:
        """Lista todos os clientes disponíveis para validações em lote."""
        query = sql.SQL(SELECT_ALL_CLIENTS).format(
            schema_name=sql.Identifier(schema_name),
        )
        with self._connection.client.cursor(row_factory=dict_row) as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()

        return [self._to_client_metadata(row) for row in rows]

 
    @staticmethod
    def _to_client_metadata(row: dict[str, Any]) -> ClientMetadata:
        return ClientMetadata(
            client_id=row["client_id"],
            has_rsa=bool(row["has_rsa"]),
            octopus_endpoint=row["octopus_endpoint"],
            has_alerts=row["has_alerts"],
            has_bart=row["has_bart"],
            has_asset=row["has_asset"],
            has_axur=row["has_axur"],
            has_wazuh=row["has_wazuh"],
        )


    @staticmethod
    def _to_client_metadata_asset(row: dict[str, Any]) -> ClientMetadataAsset:
        return ClientMetadataAsset(
            activation_key_id=row["activation_key_id"]
        )


    def get_field_by_client_id(
        self,
        schema_name: str,
        client_id: str,
        field_name: str,
    ) -> Any | None:
    
        query = sql.SQL(
            "SELECT {field} FROM {schema_name}.clients WHERE client_id = %s;"
        ).format(
            field=sql.Identifier(field_name),
            schema_name=sql.Identifier(schema_name),
        )

        with self._connection.client.cursor(row_factory=dict_row) as cursor:
            cursor.execute(query, (client_id,))
            row = cursor.fetchone()

        return None if row is None else row[field_name]

    def has_activation_key(
        self,
        schema_name: str,
        client_id: str,
        activation_key_name: str,
        query_table: str
    ) -> bool:
        query = sql.SQL(query_table).format(
            schema_name=sql.Identifier(schema_name),
        )
        with self._connection.client.cursor(row_factory=dict_row) as cursor:
            cursor.execute(query, (client_id, activation_key_name))
            return cursor.fetchone() is not None

    def has_rsa(self, schema_name: str, client_id: str) -> bool | None:
        """Retorna a flag has_rsa de um cliente, quando ele existe."""
        value = self.get_field_by_client_id(
            schema_name,
            client_id,
            "has_rsa",
        )
        return None if value is None else bool(value)