from __future__ import annotations

from typing import Any

from psycopg import sql
from psycopg.rows import dict_row

from src.connections.postgres import PostgresConnection
from src.models.client_metadata import ClientMetadata
from src.queries.cognito_client_queries import (
    SELECT_ALL_CLIENTS,
    SELECT_CLIENT_BY_ID,
    SELECT_COGNITO_CLIENT_BY_ID,
)


class CognitoClientRepository:
    """Consulta os clientes disponíveis no banco Cognito."""

    _ALLOWED_FIELDS = frozenset(
        {
            "client_id",
            "has_rsa",
            "octopus_endpoint",
            "has_alerts",
            "has_bart",
            "has_asset"
        }
    )

    def __init__(self, connection: PostgresConnection) -> None:
        self._connection = connection

    def get_cognito_by_client_id(
        self,
        schema_name: str,
        client_id: str,
    ) -> ClientMetadata | None:
        query = sql.SQL(SELECT_COGNITO_CLIENT_BY_ID).format(
            schema_name=sql.Identifier(schema_name),
        )
        with self._connection.client.cursor(row_factory=dict_row) as cursor:
            cursor.execute(query, (client_id,))
            row = cursor.fetchone()

        if row is None:
            return None

        return self._to_client_metadata(row)

    def list_clients(self, schema_name: str) -> list[dict[str, Any]]:
        """Lista os clientes e os módulos habilitados para validações em lote."""
        query = sql.SQL(SELECT_ALL_CLIENTS).format(
            schema_name=sql.Identifier(schema_name),
        )
        with self._connection.client.cursor(row_factory=dict_row) as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def get_client(self, schema_name: str, client_id: str) -> dict[str, Any] | None:
        """Retorna os dados e as flags de um cliente para validar sua aplicabilidade."""
        query = sql.SQL(SELECT_CLIENT_BY_ID).format(
            schema_name=sql.Identifier(schema_name),
        )
        with self._connection.client.cursor(row_factory=dict_row) as cursor:
            cursor.execute(query, (client_id,))
            row = cursor.fetchone()

        return None if row is None else dict(row)

 
    @staticmethod
    def _to_client_metadata(row: dict[str, Any]) -> ClientMetadata:
        return ClientMetadata(
            client_id=row["client_id"],
            has_rsa=bool(row["has_rsa"]),
            octopus_endpoint=row["octopus_endpoint"],
            has_alerts=bool(row.get("has_alerts", False)),
            has_bart=bool(row.get("has_bart", False)),
            has_asset=bool(row.get("has_asset", False)),
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

    def has_rsa(self, schema_name: str, client_id: str) -> bool | None:
        """Retorna a flag has_rsa de um cliente, quando ele existe."""
        value = self.get_field_by_client_id(
            schema_name,
            client_id,
            "has_rsa",
        )
        return None if value is None else bool(value)
