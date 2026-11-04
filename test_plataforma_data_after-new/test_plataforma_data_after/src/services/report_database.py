"""Persistência dos relatórios de testes em um PostgreSQL dedicado."""
from __future__ import annotations

import logging
import json
import os
import re
from decimal import Decimal, InvalidOperation
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import psycopg
from psycopg import sql


logger = logging.getLogger(__name__)
_SECTION_STATUS = {"Falhas": "failed", "Informativos": "info", "Aprovados": "passed"}
_SCOPES = {"Infraestrutura": "infrastructure", "Execução do teste": "infrastructure",
           "OpenSearch central": "environment", "OpenSearch Cliente": "environment",
           "Ambiente OpenSearch": "environment", "Cognito": "environment", "produto": "environment"}


@dataclass(frozen=True)
class ReportDatabaseSettings:
    host: str
    port: int
    database: str
    user: str
    password: str
    schema: str
    connect_timeout: int

    @classmethod
    def from_env(cls) -> "ReportDatabaseSettings":
        def required(name: str) -> str:
            value = os.getenv(name, "").strip()
            if not value:
                raise ValueError(f"Variável obrigatória não configurada: {name}")
            return value

        schema = os.getenv("REPORT_DB_SCHEMA", "qa_reports").strip()
        if not schema:
            raise ValueError("REPORT_DB_SCHEMA não pode estar vazio")
        return cls(required("REPORT_DB_HOST"), int(os.getenv("REPORT_DB_PORT", "5432")),
                   required("REPORT_DB_DATABASE"), required("REPORT_DB_USER"),
                   required("REPORT_DB_PASSWORD"), schema,
                   int(os.getenv("REPORT_DB_CONNECT_TIMEOUT", "10")))


def report_database_enabled() -> bool:
    return os.getenv("REPORT_DB_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}


def _oto_report_metadata(result: dict) -> dict:
    """Recupera comparações OTO explícitas quando o relatório não trouxe metadados."""
    message = result.get("message", "")
    if not isinstance(message, str):
        return {}
    number = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
    index = re.search(r"índice\s+'([^']+_oto_dashboard)'", message, re.IGNORECASE)
    attribute = re.search(r"atributo\s+\*\*([^*]+)\*\*\s*:\s*anterior\s*=\s*(" + number + r")\s*,\s*mais\s+recente\s*=\s*(" + number + r")", message, re.IGNORECASE)
    if not index or not attribute:
        return {}
    try:
        previous, current = Decimal(attribute.group(2)), Decimal(attribute.group(3))
        if not previous.is_finite() or not current.is_finite():
            return {}
    except InvalidOperation:
        return {}
    name = index.group(1)
    client = result.get("client_id") or ""
    prefix = f"{client}_" if client else ""
    family = name[len(prefix):] if prefix and name.casefold().startswith(prefix.casefold()) else name
    limits = re.search(r"limites:\s*\+\s*(" + number + r")\s*%\s*/\s*-\s*(" + number + r")\s*%", message, re.IGNORECASE)
    maximum_increase, maximum_decrease = (Decimal(limits.group(1)), Decimal(limits.group(2))) if limits else (None, None)
    direction = "increase" if current > previous else "decrease" if current < previous else "unchanged"
    dates = re.search(r"hoje\s+_id=.*?@timestamp=(\d{4}-\d{2}-\d{2}).*?ontem\s+_id=.*?@timestamp=(\d{4}-\d{2}-\d{2})", message, re.IGNORECASE | re.DOTALL)
    if dates:
        try:
            current_date = datetime.strptime(dates.group(1), "%Y-%m-%d").date()
            previous_date = datetime.strptime(dates.group(2), "%Y-%m-%d").date()
        except ValueError:
            current_date = previous_date = None
    else:
        current_date = previous_date = None
    return {
        "index_name": name, "index_type": family, "attribute_name": attribute.group(1),
        "previous_value": previous, "current_value": current,
        "variation_percent": (current - previous) / abs(previous) * 100 if previous else None,
        "comparison_direction": direction,
        "comparison_limit_percent": maximum_increase if direction == "increase" else maximum_decrease if direction == "decrease" else None,
        "max_increase_percent": maximum_increase, "max_decrease_percent": maximum_decrease,
        "previous_date": previous_date, "current_date": current_date,
        "reason_code": ("PERCENTAGE_BASE_ZERO" if not previous and current else "PERCENTAGE_LIMIT_EXCEEDED") if result.get("status") == "failed" else None,
    }


def parse_report(content: str) -> dict:
    """Lê o TXT individual, preservando todas as mensagens de cada seção."""
    lines = content.splitlines()
    metadata: dict[str, str] = {}
    for line in lines:
        for key in ("Teste", "Ambiente", "Duração"):
            prefix = f"{key}: "
            if line.startswith(prefix) and key not in metadata:
                metadata[key] = line[len(prefix):]
    bdd: list[str] = []
    in_bdd = False
    status: str | None = None
    label: str | None = None
    results: list[dict] = []
    for line in lines:
        if line == "BDD:":
            in_bdd = True
            continue
        section = next((name for name in _SECTION_STATUS if line.startswith(f"{name} (")), None)
        if section:
            in_bdd = False
            status = _SECTION_STATUS[section]
            label = None
            continue
        if in_bdd:
            bdd.append(line)
        elif status and line.startswith("- Cliente: "):
            label = line.removeprefix("- Cliente: ").strip()
        elif status and label is not None and line.startswith("  "):
            raw = line.strip()
            message = re.sub(r"^(Motivo|Informação|Detalhe):\s*", "", raw)
            match = re.match(r"^\[([^\]]+)\]\s*(.*)$", message, re.DOTALL)
            results.append({"scope_type": _SCOPES.get(label, "client"),
                            "client_id": None if label in _SCOPES else label,
                            "scope_label": label, "validation_type": match.group(1) if match else "Geral",
                            "status": status, "message": match.group(2) if match else message,
                            "raw_message": raw})
        elif status and results and line.strip() and not line.startswith("Teste:"):
            # Detalhes em múltiplas linhas pertencem à mensagem anterior.
            results[-1]["message"] += "\n" + line
            results[-1]["raw_message"] += "\n" + line
    return {"title": metadata.get("Teste", ""), "environment": metadata.get("Ambiente", ""),
            "duration_ms": _duration_ms(metadata.get("Duração")),
            "bdd": "\n".join(bdd).strip(), "results": results}


def _duration_ms(value: str | None) -> int | None:
    if not value:
        return None
    match = re.fullmatch(r"(?:(\d+) days?,\s*)?(\d+):(\d+):(\d+(?:\.\d+)?)", value.strip())
    if not match:
        return None
    days, hours, minutes, seconds = match.groups()
    return round((int(days or 0) * 86400 + int(hours) * 3600 + int(minutes) * 60 + float(seconds)) * 1000)


def record_pytest_outcome(outcomes: dict, report) -> None:
    """Captura estados no controlador, inclusive resultados dos workers xdist."""
    item = outcomes.setdefault(report.nodeid, {"node_id": report.nodeid, "duration_ms": 0, "status": None})
    item["duration_ms"] += round(report.duration * 1000)
    if report.failed:
        item["status"] = "failed" if report.when == "call" else "error"
    elif report.skipped and item["status"] not in {"failed", "error"}:
        item["status"] = "skipped"
    elif report.when == "call" and item["status"] is None:
        item["status"] = "passed"


def persist_session_reports(session, exitstatus: int, project: str, report_paths: list[Path]) -> None:
    """Insere uma execução concluída e suas evidências em uma transação."""
    if not report_database_enabled() or session.config.getoption("collectonly", default=False):
        return
    settings = ReportDatabaseSettings.from_env()
    ended_at = datetime.now(timezone.utc)
    started_at = getattr(session, "_report_db_started_at", ended_at)
    elapsed_ms = round((perf_counter() - session._validation_started_at) * 1000)
    run_id = uuid4()
    outcomes = getattr(session.config, "_report_db_outcomes", {})
    reports = {}
    for path in report_paths:
        parsed = parse_report(path.read_text(encoding="utf-8"))
        sidecar = path.with_suffix(".structured.json")
        parsed["structured"] = json.loads(sidecar.read_text(encoding="utf-8")) if sidecar.is_file() else {}
        reports[path.stem] = parsed
    scenario_rows: list[tuple[str, dict, dict]] = []
    matched: set[str] = set()
    for node_id, outcome in outcomes.items():
        name = node_id.rsplit("::", 1)[-1].split("[", 1)[0]
        report = reports.get(name)
        if report is not None:
            matched.add(name)
        scenario_rows.append((name, outcome, report or {"title": name, "bdd": "", "results": []}))
    for name, report in reports.items():
        if name not in matched:
            scenario_rows.append((name, {"node_id": None, "status": None, "duration_ms": None}, report))

    table = lambda name: sql.Identifier(settings.schema, name)
    with psycopg.connect(host=settings.host, port=settings.port, dbname=settings.database,
                         user=settings.user, password=settings.password,
                         connect_timeout=settings.connect_timeout) as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql.SQL("INSERT INTO {} (id, project, environment, started_at, finished_at, duration_ms, status, exit_code) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)").format(table("qa_test_runs")),
                           (run_id, project, os.getenv("TEST_ENV", "hml").strip().lower(), started_at,
                            ended_at, elapsed_ms, "passed" if int(exitstatus) == 0 else "failed", int(exitstatus)))
            for name, outcome, report in scenario_rows:
                cursor.execute(sql.SQL("INSERT INTO {} (run_id, test_node_id, test_name, title, bdd, duration_ms, pytest_status) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id").format(table("qa_test_scenarios")),
                               (run_id, outcome.get("node_id"), name, report.get("title") or name,
                                report.get("bdd"), outcome.get("duration_ms") if outcome.get("node_id") else report.get("duration_ms"), outcome.get("status")))
                scenario_id = cursor.fetchone()[0]
                rows = []
                for sequence, result in enumerate(report.get("results", []), start=1):
                    structured = report.get("structured", {}).get(str(sequence))
                    if not structured and name == "test_should_validate_oto_dashboard_after_pipeline":
                        structured = _oto_report_metadata(result)
                    structured = structured or {}
                    rows.append((scenario_id, result["scope_type"], result["client_id"], result["scope_label"],
                                 result["validation_type"], result["status"], result["message"], result["raw_message"], sequence,
                                 *(structured.get(field) for field in (
                                     "index_name", "index_type", "attribute_name", "previous_value", "current_value",
                                     "variation_percent", "comparison_direction", "comparison_limit_percent", "max_increase_percent",
                                     "max_decrease_percent", "previous_date", "current_date", "reason_code"))))
                if rows:
                    cursor.executemany(
                        sql.SQL('INSERT INTO {} (scenario_id, scope_type, client_id, scope_label, validation_type, status, message, raw_message, sequence, index_name, index_type, attribute_name, previous_value, current_value, variation_percent, comparison_direction, comparison_limit_percent, max_increase_percent, max_decrease_percent, previous_date, comparison_current_date, reason_code) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)').format(table("qa_test_results")),
                        rows,
                    )
    logger.info("Resultados da execução %s gravados no PostgreSQL (%s).", run_id, project)


def persist_session_safely(session, exitstatus: int, project: str, report_paths: list[Path]) -> None:
    if not report_database_enabled():
        return
    try:
        persist_session_reports(session, exitstatus, project, report_paths)
    except Exception as error:
        # Persistência habilitada é parte da execução: não mascarar sua falha.
        logger.error("Falha ao gravar resultados no PostgreSQL de relatórios: %s: %s", type(error).__name__, error)
        print(f"ERRO: resultados não foram gravados no PostgreSQL de relatórios ({type(error).__name__}).")
        session.exitstatus = 1
