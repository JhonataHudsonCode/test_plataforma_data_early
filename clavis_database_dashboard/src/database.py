"""Consulta somente os resultados persistidos pelos testes."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd
import psycopg
from dotenv import load_dotenv
from psycopg import sql
from psycopg.rows import dict_row


@dataclass(frozen=True)
class DatabaseSettings:
    host: str
    port: int
    database: str
    user: str
    password: str = field(repr=False)
    schema: str = "qa_reports"
    connect_timeout: int = 10

    @classmethod
    def from_env(cls) -> "DatabaseSettings":
        load_dotenv()

        def required(name: str) -> str:
            value = os.getenv(name, "").strip()
            if not value:
                raise ValueError(f"Configure a variável {name} no arquivo .env.")
            return value

        schema = os.getenv("REPORT_DB_SCHEMA", "qa_reports").strip()
        if not schema:
            raise ValueError("REPORT_DB_SCHEMA não pode estar vazio.")
        try:
            port = int(os.getenv("REPORT_DB_PORT", "5432"))
            timeout = int(os.getenv("REPORT_DB_CONNECT_TIMEOUT", "10"))
        except ValueError as error:
            raise ValueError("Porta e tempo de conexão devem ser números inteiros.") from error
        if not 1 <= port <= 65535 or timeout < 1:
            raise ValueError("Confira a porta e o tempo de conexão do PostgreSQL.")
        return cls(
            host=required("REPORT_DB_HOST"),
            port=port,
            database=required("REPORT_DB_DATABASE"),
            user=required("REPORT_DB_USER"),
            password=required("REPORT_DB_PASSWORD"),
            schema=schema,
            connect_timeout=timeout,
        )


COLUMNS = [
    "run_id", "project", "environment", "started_at", "finished_at",
    "run_duration_ms", "run_status", "exit_code", "scenario_id", "test_node_id",
    "test_name", "title", "bdd", "scenario_duration_ms", "pytest_status",
    "result_id", "scope_type", "client_id", "scope_label", "validation_type",
    "result_status", "message", "raw_message", "sequence", "recorded_at",
]


def load_results(settings: DatabaseSettings, start: datetime, end: datetime) -> pd.DataFrame:
    """Carrega uma linha por mensagem; preserva cenários sem mensagens."""
    query = sql.SQL("""
        SELECT r.id AS run_id, r.project, r.environment, r.started_at, r.finished_at,
               r.duration_ms AS run_duration_ms, r.status AS run_status, r.exit_code,
               s.id AS scenario_id, s.test_node_id, s.test_name, s.title, s.bdd,
               s.duration_ms AS scenario_duration_ms, s.pytest_status,
               v.id AS result_id, v.scope_type, v.client_id, v.scope_label,
               v.validation_type, v.status AS result_status, v.message, v.raw_message,
               v.sequence, v.recorded_at
        FROM {runs} AS r
        LEFT JOIN {scenarios} AS s ON s.run_id = r.id
        LEFT JOIN {results} AS v ON v.scenario_id = s.id
        WHERE r.started_at >= %s AND r.started_at < %s
        ORDER BY r.started_at DESC, s.id, v.sequence
    """).format(
        runs=sql.Identifier(settings.schema, "qa_test_runs"),
        scenarios=sql.Identifier(settings.schema, "qa_test_scenarios"),
        results=sql.Identifier(settings.schema, "qa_test_results"),
    )
    with psycopg.connect(
        host=settings.host, port=settings.port, dbname=settings.database,
        user=settings.user, password=settings.password,
        connect_timeout=settings.connect_timeout, row_factory=dict_row,
    ) as connection:
        connection.read_only = True
        with connection.cursor() as cursor:
            cursor.execute(query, (start, end))
            rows = cursor.fetchall()
    return pd.DataFrame.from_records(rows, columns=COLUMNS)
