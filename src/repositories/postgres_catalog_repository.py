from __future__ import annotations

from typing import Any, Sequence

from psycopg.rows import dict_row

from src.connections.postgres import PostgresConnection
from src.models.table_metadata import TableMetadata
from src.queries.postgres_queries import (
    CHECK_CONNECTION,
    SELECT_TABLE_FROM_PG_TABLES,
)


class PostgresCatalogRepository:
    """
    Camada responsável por executar queries do catálogo PostgreSQL.

    Os testes consomem apenas os métodos públicos desta classe
    """

    def __init__(self, connection: PostgresConnection) -> None:
        self._connection = connection

    def _fetch_one(
        self,
        query: str,
        params: Sequence[Any] | None = None,
    ) -> dict[str, Any] | None:
        with self._connection.client.cursor(row_factory=dict_row) as cursor:
            cursor.execute(query, params)
            return cursor.fetchone()

    def check_connection(self) -> bool:
        row = self._fetch_one(CHECK_CONNECTION)
        return bool(row and row.get("health") == 1)

    def get_pg_table(
        self,
        schema_name: str,
        table_name: str,
    ) -> TableMetadata | None:
        row = self._fetch_one(
            SELECT_TABLE_FROM_PG_TABLES,
            (schema_name, table_name),
        )

        if row is None:
            return None

        return TableMetadata(
            schema_name=row["schemaname"],
            table_name=row["tablename"],
            owner=row["tableowner"],
            tablespace=row["tablespace"],
            has_indexes=row["hasindexes"],
            has_rules=row["hasrules"],
            has_triggers=row["hastriggers"],
            row_security=row["rowsecurity"],
        )