"""Operações Pandas compartilhadas pelas telas do dashboard."""
from __future__ import annotations

import pandas as pd


STATUS_LABELS = {"passed": "Aprovado", "failed": "Falha", "info": "Informativo"}
SCENARIO_LABELS = {"passed": "Aprovado", "failed": "Falha", "skipped": "Ignorado", "error": "Erro"}


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
        "scenarios": int(frame["scenario_id"].nunique()),
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
