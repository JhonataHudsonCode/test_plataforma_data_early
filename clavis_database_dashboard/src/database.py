"""Consulta somente os resultados persistidos pelos testes."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd
import psycopg
import streamlit as st
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
    "index_name", "index_type", "attribute_name", "previous_value", "current_value",
    "variation_percent", "comparison_direction", "comparison_limit_percent", "max_increase_percent",
    "max_decrease_percent", "previous_date", "current_date", "reason_code",
]


def mapping_results_enabled() -> bool:
    """Retorna se resultados de validação de mapping devem ser exibidos."""
    value = os.getenv("DASHBOARD_SHOW_MAPPING_RESULTS", "true").strip().casefold()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError("DASHBOARD_SHOW_MAPPING_RESULTS deve ser true ou false.")


@st.cache_data(ttl=900, max_entries=16, show_spinner=False)
def _load_filter_options_cached(settings: DatabaseSettings, show_mapping: bool) -> dict[str, list[str]]:
    """Cache de 15 minutos das opções, separado pela flag de mapping."""
    scenario_filter = sql.SQL("") if show_mapping else sql.SQL("""
        AND COALESCE(s.title, '') NOT ILIKE '%mapping%'
        AND COALESCE(s.test_name, '') NOT ILIKE '%mapping%'
    """)
    result_filter = sql.SQL("") if show_mapping else sql.SQL("""
        AND COALESCE(v.validation_type, '') NOT ILIKE '%mapping%'
    """)
    run_filter = sql.SQL("") if show_mapping else sql.SQL("""
        AND EXISTS (
            SELECT 1 FROM {scenarios} AS eligible
            WHERE eligible.run_id = r.id
              AND COALESCE(eligible.title, '') NOT ILIKE '%mapping%'
              AND COALESCE(eligible.test_name, '') NOT ILIKE '%mapping%'
        )
    """).format(scenarios=sql.Identifier(settings.schema, "qa_test_scenarios"))
    query = sql.SQL("""
        SELECT DISTINCT 'project' AS kind, r.project AS value
        FROM {runs} AS r WHERE r.project IS NOT NULL {run_filter}
        UNION ALL
        SELECT DISTINCT 'environment' AS kind, r.environment AS value
        FROM {runs} AS r WHERE r.environment IS NOT NULL {run_filter}
        UNION ALL
        SELECT DISTINCT 'title' AS kind, s.title AS value
        FROM {scenarios} AS s WHERE s.title IS NOT NULL {scenario_filter}
        UNION ALL
        SELECT DISTINCT 'client_id' AS kind, v.client_id AS value
        FROM {results} AS v
        JOIN {scenarios} AS s ON s.id = v.scenario_id
        WHERE v.client_id IS NOT NULL {scenario_filter} {result_filter}
        UNION ALL
        SELECT DISTINCT 'validation_type' AS kind, v.validation_type AS value
        FROM {results} AS v
        JOIN {scenarios} AS s ON s.id = v.scenario_id
        WHERE v.validation_type IS NOT NULL {scenario_filter} {result_filter}
    """).format(
        runs=sql.Identifier(settings.schema, "qa_test_runs"),
        scenarios=sql.Identifier(settings.schema, "qa_test_scenarios"),
        results=sql.Identifier(settings.schema, "qa_test_results"),
        scenario_filter=scenario_filter,
        result_filter=result_filter,
        run_filter=run_filter,
    )
    options = {key: [] for key in ("project", "environment", "title", "client_id", "validation_type")}
    with psycopg.connect(
        host=settings.host, port=settings.port, dbname=settings.database,
        user=settings.user, password=settings.password,
        connect_timeout=settings.connect_timeout, row_factory=dict_row,
    ) as connection:
        connection.read_only = True
        with connection.cursor() as cursor:
            cursor.execute(query)
            for row in cursor.fetchall():
                if row["kind"] in options and row["value"]:
                    options[row["kind"]].append(str(row["value"]))
    return {key: sorted(set(values), key=str.casefold) for key, values in options.items()}


def load_filter_options(settings: DatabaseSettings) -> dict[str, list[str]]:
    """Carrega opções dos filtros reutilizando cache de 15 minutos."""
    return _load_filter_options_cached(settings, mapping_results_enabled())


@st.cache_data(ttl=900, max_entries=8, show_spinner=False)
def _load_results_cached(settings: DatabaseSettings, start: datetime, end: datetime, show_mapping: bool) -> pd.DataFrame:
    """Cache de resultados de 15 minutos; considera a flag de mapping na chave."""
    result_filter = sql.SQL("") if show_mapping else sql.SQL("""
        AND COALESCE(v.validation_type, '') NOT ILIKE '%mapping%'
    """)
    if show_mapping:
        scenario_join = sql.SQL("LEFT JOIN {scenarios} AS s ON s.run_id = r.id").format(
            scenarios=sql.Identifier(settings.schema, "qa_test_scenarios")
        )
    else:
        scenario_join = sql.SQL("""
            JOIN {scenarios} AS s ON s.run_id = r.id
             AND COALESCE(s.title, '') NOT ILIKE '%mapping%'
             AND COALESCE(s.test_name, '') NOT ILIKE '%mapping%'
        """).format(scenarios=sql.Identifier(settings.schema, "qa_test_scenarios"))
    query = sql.SQL("""
        SELECT r.id AS run_id, r.project, r.environment, r.started_at, r.finished_at,
               r.duration_ms AS run_duration_ms, r.status AS run_status, r.exit_code,
               s.id AS scenario_id, s.test_node_id, s.test_name, s.title, s.bdd,
               s.duration_ms AS scenario_duration_ms, s.pytest_status,
               v.id AS result_id, v.scope_type, v.client_id, v.scope_label,
               v.validation_type, v.status AS result_status, v.message, v.raw_message,
               v.sequence, v.recorded_at, v.index_name, v.index_type, v.attribute_name,
               v.previous_value, v.current_value, v.variation_percent, v.comparison_direction,
               v.comparison_limit_percent, v.max_increase_percent, v.max_decrease_percent,
               v.previous_date, v.comparison_current_date AS "current_date", v.reason_code
        FROM {runs} AS r
        {scenario_join}
        LEFT JOIN {results} AS v ON v.scenario_id = s.id {result_filter}
        WHERE r.started_at >= %s AND r.started_at < %s
        ORDER BY r.started_at DESC, s.id, v.sequence
    """).format(
        runs=sql.Identifier(settings.schema, "qa_test_runs"),
        scenarios=sql.Identifier(settings.schema, "qa_test_scenarios"),
        results=sql.Identifier(settings.schema, "qa_test_results"),
        scenario_join=scenario_join,
        result_filter=result_filter,
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


def load_results(settings: DatabaseSettings, start: datetime, end: datetime) -> pd.DataFrame:
    """Busca resultados, reutilizando cache por até 15 minutos."""
    return _load_results_cached(settings, start, end, mapping_results_enabled())


def clear_database_cache() -> None:
    """Limpa os caches para forçar uma nova leitura do PostgreSQL."""
    _load_filter_options_cached.clear()
    _load_results_cached.clear()
