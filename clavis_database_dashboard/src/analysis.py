"""Operações Pandas compartilhadas pelas telas do dashboard."""
from __future__ import annotations

import pandas as pd
import re


STATUS_LABELS = {"passed": "Aprovado", "failed": "Falha", "info": "Informativo"}
SCENARIO_LABELS = {"passed": "Aprovado", "failed": "Falha", "skipped": "Ignorado", "error": "Erro"}

_MISSING_INDEX = re.compile(
    r"índice(?:\s+(?:de\s+produto|de\s+ativos|histórico))?\s+(?:'(?P<quoted>[^']+)'|(?P<plain>[\w.-]+))\s+(?:não\s+encontrad[oa]|não\s+existe)",
    re.IGNORECASE,
)
_INDEX_NAME = re.compile(r"índice(?:\s+(?:de\s+produto|de\s+ativos|histórico))?\s+(?:'(?P<quoted>[^']+)'|(?P<plain>[\w.-]+))", re.IGNORECASE)
_NO_DOCUMENTS = re.compile(r"(?:não\s+(?:retornou|possui|encontrou)\s+documentos?|nenhum\s+documento\s+(?:retornado|encontrado)|sem\s+documentos?)", re.IGNORECASE)
_EMPTY_DATE = re.compile(r"\b0\s+documento(?:\(s\)|s)?\s+em\s+(\d{4}-\d{2}-\d{2})", re.IGNORECASE)
_EMPTY_SECOND_DATE = re.compile(r"\b\d+\s+documento(?:\(s\)|s)?\s+em\s+\d{4}-\d{2}-\d{2}\s+e\s+0\s+(?:documento(?:\(s\)|s)?\s+)?em\s+(\d{4}-\d{2}-\d{2})", re.IGNORECASE)
_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")


def index_results(frame: pd.DataFrame) -> pd.DataFrame:
    """Agrupa nomes de índices por tipo, removendo o prefixo do próprio cliente."""
    results = frame[frame["result_id"].notna()].copy()
    names = results["message"].fillna("").str.extract(_INDEX_NAME)
    results["index_name"] = names["quoted"].fillna(names["plain"])
    results = results[results["index_name"].notna()].copy()
    results = results[~results["index_name"].str.casefold().isin({"não", "nao", "foi", "com", "do", "da", "de", "para"})].copy()

    def family(row):
        name, client = row["index_name"], row.get("client_id")
        prefix = f"{client}_" if pd.notna(client) and str(client).strip() else ""
        return name[len(prefix):] if prefix and name.casefold().startswith(prefix.casefold()) else name

    results["index_family"] = results.apply(family, axis=1) if not results.empty else pd.Series(dtype="object")
    return results


def missing_index_details(frame: pd.DataFrame) -> pd.DataFrame:
    """Identifica índices explicitamente informados como ausentes pelos testes."""
    failures = frame[frame["result_status"] == "failed"].copy()
    extracted = failures["message"].fillna("").str.extract(_MISSING_INDEX)
    failures["index_name"] = extracted["quoted"].fillna(extracted["plain"])
    failures = failures[failures["index_name"].notna()]
    return failures.drop_duplicates(subset=["project", "environment", "scope_label", "index_name"])


def empty_index_date_details(frame: pd.DataFrame, display_zone) -> pd.DataFrame:
    """Extrai ausências explícitas de documentos para hoje ou ontem da execução."""
    records = []
    for _, row in frame[frame["result_id"].notna()].iterrows():
        message = row.get("message")
        if not isinstance(message, str):
            continue
        index_match = _INDEX_NAME.search(message)
        if not index_match:
            continue
        dates = _EMPTY_DATE.findall(message) + _EMPTY_SECOND_DATE.findall(message)
        if row.get("result_status") == "failed" and _NO_DOCUMENTS.search(message):
            dates.extend(_DATE.findall(message))
        started = pd.to_datetime(row.get("started_at"), utc=True, errors="coerce")
        if pd.isna(started):
            continue
        reference = started.tz_convert(display_zone).date()
        for raw_date in set(dates):
            parsed = pd.to_datetime(raw_date, format="%Y-%m-%d", errors="coerce")
            if pd.isna(parsed):
                continue
            delta = (reference - parsed.date()).days
            if delta in (0, 1):
                record = row.to_dict()
                record.update(index_name=index_match.group("quoted") or index_match.group("plain"),
                              date_role="Hoje" if delta == 0 else "Ontem", document_date=raw_date)
                records.append(record)
    columns = [*frame.columns, "index_name", "date_role", "document_date"]
    result = pd.DataFrame(records, columns=columns)
    return result.drop_duplicates(subset=["project", "environment", "scope_label", "index_name", "date_role"])


def apply_filters(frame: pd.DataFrame, filters: dict[str, list[str]]) -> pd.DataFrame:
    filtered = frame
    for column, selected in filters.items():
        if selected:
            filtered = filtered[filtered[column].isin(selected)]
    return filtered.copy()


def summarize(frame: pd.DataFrame) -> dict[str, int]:
    """Conta cenários e clientes distintos e etapas por cenário/cliente/status."""
    messages = frame[frame["result_id"].notna()]
    stages = messages.drop_duplicates(
        subset=["scenario_id", "scope_type", "scope_label", "validation_type", "result_status"]
    )
    counts = stages["result_status"].value_counts()
    return {
        "runs": int(frame["run_id"].nunique()),
        "scenarios": len(frame.loc[frame["scenario_id"].notna(), ["project", "test_name"]].drop_duplicates()),
        "clients": int(frame.loc[frame["scope_type"] == "client", "client_id"].nunique()),
        "failed": int(counts.get("failed", 0)),
        "passed": int(counts.get("passed", 0)),
        "info": int(counts.get("info", 0)),
    }


def scenario_summary(frame: pd.DataFrame) -> pd.DataFrame:
    columns = ["started_at", "project", "environment", "title", "test_name",
               "pytest_status", "scenario_duration_ms", "run_id", "scenario_id"]
    scenarios = frame[frame["scenario_id"].notna()][columns].drop_duplicates(subset="scenario_id")
    return scenarios.sort_values(["started_at", "scenario_id"], ascending=[False, True])


def format_duration(value) -> str:
    if pd.isna(value):
        return "Não informada"
    seconds = max(0, int(value)) / 1000
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(int(minutes), 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:05.2f}"
