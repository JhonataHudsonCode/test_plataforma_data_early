"""Operações Pandas compartilhadas pelas telas do dashboard."""
from __future__ import annotations

import pandas as pd
import re
import math


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
    extracted = names["quoted"].fillna(names["plain"])
    results["index_name"] = results["index_name"].astype("string").fillna(extracted.astype("string")) if "index_name" in results else extracted
    results = results[results["index_name"].notna()].copy()
    results = results[~results["index_name"].str.casefold().isin({"não", "nao", "foi", "com", "do", "da", "de", "para"})].copy()

    def family(row):
        name, client = row["index_name"], row.get("client_id")
        if pd.notna(row.get("index_type")) and str(row.get("index_type")).strip():
            return str(row["index_type"])
        prefix = f"{client}_" if pd.notna(client) and str(client).strip() else ""
        return name[len(prefix):] if prefix and name.casefold().startswith(prefix.casefold()) else name

    results["index_family"] = results.apply(family, axis=1) if not results.empty else pd.Series(dtype="object")
    return results


def missing_index_details(frame: pd.DataFrame, *, deduplicate: bool = True) -> pd.DataFrame:
    """Identifica índices explicitamente informados como ausentes pelos testes."""
    failures = frame[frame["result_status"] == "failed"].copy()
    extracted = failures["message"].fillna("").str.extract(_MISSING_INDEX)
    failures["index_name"] = extracted["quoted"].fillna(extracted["plain"])
    failures = failures[failures["index_name"].notna()]
    if deduplicate:
        failures = failures.drop_duplicates(subset=["project", "environment", "scope_label", "index_name"])
    return failures


def percentage_failure_details(frame: pd.DataFrame) -> pd.DataFrame:
    """Retorna mensagens de falha classificadas como comparação percentual."""
    results = frame if "index_family" in frame.columns else index_results(frame)
    category = results["validation_type"].fillna("").astype(str)
    return results[(results["result_status"] == "failed") & category.str.contains(
        r"percentual|porcentagem", case=False, regex=True,
    )].copy()


def percentage_attribute_details(frame: pd.DataFrame) -> pd.DataFrame:
    """Extrai valores explícitos de mensagens de variação por atributo."""
    number = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
    attribute_pattern = re.compile(r"\btotal\s+de\s+([\w.\-]+)\s+(?:aumentou|reduziu|variou)\b", re.IGNORECASE)
    values_pattern = re.compile(rf"ontem\s*=\s*({number})\s*,\s*hoje\s*=\s*({number})", re.IGNORECASE)
    zero_pattern = re.compile(rf"(?:aumentou|reduziu|variou)\s+de\s+({number})\s+para\s+({number})", re.IGNORECASE)
    records = []
    for _, row in frame.iterrows():
        message = row.get("message")
        if not isinstance(message, str):
            continue
        attribute_name = row.get("attribute_name")
        previous_value, current_value = row.get("previous_value"), row.get("current_value")
        if pd.notna(attribute_name) and pd.notna(previous_value) and pd.notna(current_value):
            previous, current = float(previous_value), float(current_value)
            if math.isfinite(previous) and math.isfinite(current):
                record = row.to_dict()
                stored_variation = row.get("variation_percent")
                change = float(stored_variation) if pd.notna(stored_variation) else None
                record.update(attribute=attribute_name, previous_value=previous, current_value=current,
                              change_percent=change, direction="Aumento" if current > previous else "Redução" if current < previous else "Sem alteração")
                records.append(record)
                continue
        attribute = attribute_pattern.search(message)
        values = values_pattern.search(message) or zero_pattern.search(message)
        if not attribute or not values:
            continue
        previous, current = map(float, values.groups())
        if not math.isfinite(previous) or not math.isfinite(current):
            continue
        change = ((current - previous) / abs(previous) * 100) if previous != 0 else None
        record = row.to_dict()
        record.update(attribute=attribute.group(1), previous_value=previous, current_value=current,
                      change_percent=change, direction="Aumento" if current > previous else "Redução" if current < previous else "Sem alteração")
        records.append(record)
    columns = list(dict.fromkeys([*frame.columns, "attribute", "previous_value", "current_value", "change_percent", "direction"]))
    return pd.DataFrame(records, columns=columns)


def missing_document_details(frame: pd.DataFrame) -> pd.DataFrame:
    """Retorna ausências de documentos explicitamente informadas no relatório."""
    results = frame if "index_family" in frame.columns else index_results(frame)
    messages = results["message"].fillna("").astype(str)
    failed_empty = (results["result_status"] == "failed") & messages.str.contains(_NO_DOCUMENTS, na=False)
    zero_dates = messages.map(lambda message: bool(_EMPTY_DATE.search(message) or _EMPTY_SECOND_DATE.search(message))).astype(bool)
    return results[failed_empty | zero_dates].copy()


def count_affected_indexes(frame: pd.DataFrame) -> int:
    """Conta índices distintos por projeto, ambiente e cliente ou origem."""
    return len(frame.drop_duplicates(subset=["project", "environment", "scope_label", "index_name"]))


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
    columns = list(dict.fromkeys([*frame.columns, "index_name", "date_role", "document_date"]))
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


def run_duration_summary(frame: pd.DataFrame) -> pd.DataFrame:
    """Consolida o tempo total de cada execução sem duplicar mensagens ou cenários."""
    columns = ["run_id", "project", "environment", "started_at", "run_duration_ms"]
    runs = frame.loc[frame["run_id"].notna(), columns].drop_duplicates(subset="run_id").copy()
    runs["run_duration_ms"] = pd.to_numeric(runs["run_duration_ms"], errors="coerce")
    counts = frame.groupby("run_id")["scenario_id"].nunique().rename("scenario_count")
    runs = runs.join(counts, on="run_id")
    return runs.sort_values("started_at", ascending=False)


def daily_failure_history(frame: pd.DataFrame, display_zone) -> pd.DataFrame:
    """Conta validações distintas com falha em cada dia de execução.

    Inclui dias com execução e zero falhas para o gráfico mostrar a série completa.
    A contagem segue a mesma granularidade dos indicadores gerais.
    """
    columns = ["execution_day", "failures", "runs"]
    if frame.empty:
        return pd.DataFrame(columns=columns)

    runs = frame.loc[frame["run_id"].notna(), ["run_id", "started_at"]].drop_duplicates("run_id").copy()
    runs["execution_day"] = (
        pd.to_datetime(runs["started_at"], utc=True, errors="coerce")
        .dt.tz_convert(display_zone)
        .dt.date
    )
    runs = runs.dropna(subset=["execution_day"])
    if runs.empty:
        return pd.DataFrame(columns=columns)
    daily_runs = runs.groupby("execution_day").size().rename("runs")

    messages = frame.loc[
        frame["result_id"].notna() & frame["result_status"].eq("failed")
    ].drop_duplicates(
        subset=["run_id", "scenario_id", "scope_type", "scope_label", "validation_type", "result_status"]
    ).copy()
    if not messages.empty:
        messages["execution_day"] = (
            pd.to_datetime(messages["started_at"], utc=True, errors="coerce")
            .dt.tz_convert(display_zone)
            .dt.date
        )
        daily_failures = messages.dropna(subset=["execution_day"]).groupby("execution_day").size().rename("failures")
    else:
        daily_failures = pd.Series(dtype="int64", name="failures")
    history = pd.concat([daily_runs, daily_failures], axis=1).fillna(0).reset_index()
    history[["failures", "runs"]] = history[["failures", "runs"]].astype(int)
    return history[columns].sort_values("execution_day")


def client_validation_history(frame: pd.DataFrame, client_id: str, display_zone) -> pd.DataFrame:
    """Conta resultados aprovados e com falha por dia para um cliente."""
    return daily_validation_history(frame, display_zone, client_id=client_id)


def daily_validation_history(
    frame: pd.DataFrame,
    display_zone,
    *,
    client_id: str | None = None,
) -> pd.DataFrame:
    """Conta resultados distintos aprovados e com falha por dia."""
    columns = ["execution_day", "result_status", "validations"]
    if frame.empty:
        return pd.DataFrame(columns=columns)

    mask = frame["result_id"].notna() & frame["result_status"].isin(["failed", "passed"])
    if client_id is not None:
        mask &= frame["scope_type"].eq("client") & frame["client_id"].astype("string").eq(str(client_id))
    messages = frame.loc[mask].drop_duplicates(
        subset=["run_id", "scenario_id", "scope_type", "scope_label", "validation_type", "result_status"]
    ).copy()
    messages["execution_day"] = (
        pd.to_datetime(messages["started_at"], utc=True, errors="coerce")
        .dt.tz_convert(display_zone)
        .dt.date
    )
    messages = messages.dropna(subset=["execution_day"])

    if client_id is None:
        runs = frame.loc[frame["run_id"].notna(), ["run_id", "started_at"]].drop_duplicates("run_id").copy()
        runs["execution_day"] = (
            pd.to_datetime(runs["started_at"], utc=True, errors="coerce")
            .dt.tz_convert(display_zone)
            .dt.date
        )
        days = sorted(runs["execution_day"].dropna().unique())
    else:
        days = sorted(messages["execution_day"].unique())
    if not days:
        return pd.DataFrame(columns=columns)

    counts = messages.groupby(["execution_day", "result_status"]).size()
    all_statuses = pd.MultiIndex.from_product(
        [days, ["failed", "passed"]], names=["execution_day", "result_status"]
    )
    return counts.reindex(all_statuses, fill_value=0).rename("validations").reset_index()


def format_duration(value) -> str:
    if pd.isna(value):
        return "Não informada"
    seconds = max(0, int(value)) / 1000
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(int(minutes), 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:05.2f}"
