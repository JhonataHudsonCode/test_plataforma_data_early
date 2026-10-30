from __future__ import annotations

import os
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pandas as pd
import psycopg
import streamlit as st

from src.analysis import SCENARIO_LABELS, STATUS_LABELS, apply_filters, format_duration, scenario_summary, summarize
from src.database import DatabaseSettings, load_results


st.set_page_config(page_title="Clavis | Testes", page_icon="📊", layout="wide")
st.markdown(
    '<style>[data-testid="stAppDeployButton"] { display: none !important; }</style>',
    unsafe_allow_html=True,
)
st.title("Dashboard de testes Clavis")
st.caption("Resultados persistidos pelo Early e After no PostgreSQL")

try:
    settings = DatabaseSettings.from_env()
    display_zone = ZoneInfo(os.getenv("DASHBOARD_TIMEZONE", "America/Sao_Paulo"))
except (ValueError, ZoneInfoNotFoundError) as error:
    st.error(f"Configuração inválida: {error}")
    st.info("Crie o arquivo .env e configure a conexão conforme o README do projeto.")
    st.stop()

today = datetime.now(display_zone).date()
data = st.session_state.get("dashboard_data")


def choices(column: str) -> list[str]:
    if data is None or data.empty:
        return []
    return sorted(data[column].dropna().astype(str).unique().tolist(), key=str.casefold)


def close_scenario_dialog() -> None:
    st.session_state["scenario_dialog_open"] = False


@st.dialog("Selecionar cenários", width="large", on_dismiss=close_scenario_dialog)
def select_scenarios() -> None:
    scenarios = choices("title")
    search = st.text_input("Buscar cenário", placeholder="Digite parte do nome")
    selected = set(st.session_state.get("selected_scenarios", []))
    matching = [name for name in scenarios if search.casefold() in name.casefold()]
    if not matching:
        st.info("Nenhum cenário encontrado.")
    with st.form("scenario_selection"):
        for name in matching:
            checked = st.checkbox(name, value=name in selected, key=f"scenario_option_{name}")
            if checked:
                selected.add(name)
            else:
                selected.discard(name)
        if st.form_submit_button("Confirmar seleção", type="primary"):
            st.session_state["selected_scenarios"] = sorted(selected, key=str.casefold)
            close_scenario_dialog()
            st.rerun()


with st.sidebar:
    st.header("Filtros")
    with st.container():
        start_date = st.date_input("Data inicial", value=today - timedelta(days=30))
        end_date = st.date_input("Data final", value=today)
        projects = st.multiselect("Projeto", choices("project"))
        environments = st.multiselect("Ambiente", choices("environment"))
        st.markdown("**Cenário**")
        if st.button("Selecionar cenários", disabled=not choices("title"), use_container_width=True):
            st.session_state["scenario_dialog_open"] = True
        if st.session_state.get("scenario_dialog_open", False):
            select_scenarios()
        test_names = st.session_state.get("selected_scenarios", [])
        st.caption(f"{len(test_names)} cenário(s) selecionado(s)" if test_names else "Todos os cenários")
        client_ids = st.multiselect("Cliente", choices("client_id"))
        validation_types = st.multiselect("Tipo de validação", choices("validation_type"))
        statuses = st.multiselect(
            "Resultado da validação", ["failed", "passed", "info"],
            format_func=lambda value: STATUS_LABELS[value],
        )
        button_area = st.empty()
        submitted = button_area.button("Pesquisar", type="primary")
        search_error = False
        if submitted and start_date <= end_date:
            button_area.button("⏳ Pesquisando...", type="primary", disabled=True)
            start = datetime.combine(start_date, time.min, tzinfo=display_zone).astimezone(timezone.utc)
            end = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=display_zone).astimezone(timezone.utc)
            with st.spinner("Consultando resultados..."):
                try:
                    data = load_results(settings, start, end)
                except (psycopg.Error, OSError):
                    search_error = True
            if search_error:
                st.session_state["dashboard_search_error"] = True
                st.rerun()
    st.caption("As opções de projeto, cenário e cliente são carregadas após a primeira pesquisa. Ajuste os filtros e clique em Pesquisar para aplicá-los.")

if st.session_state.pop("dashboard_search_error", False):
    st.error("Não foi possível consultar o PostgreSQL de relatórios. Confira conexão, permissões e schema.")

if submitted:
    if start_date > end_date:
        st.error("A data inicial deve ser anterior ou igual à data final.")
        st.stop()
    st.session_state["dashboard_data"] = data
    st.session_state["dashboard_filters"] = {
        "project": projects, "environment": environments, "title": test_names,
        "client_id": client_ids, "validation_type": validation_types, "result_status": statuses,
    }
    # Recria os widgets com as opções retornadas pela pesquisa recém-concluída.
    st.rerun()

if data is None:
    st.info("Selecione o período e clique em Pesquisar para consultar os resultados.")
    st.stop()

if data.empty:
    st.info("Nenhuma execução encontrada no período selecionado.")
    st.stop()


filtered = apply_filters(data, st.session_state["dashboard_filters"])
if filtered.empty:
    st.warning("Nenhum resultado corresponde aos filtros selecionados.")
    st.stop()

overview, validations = st.tabs(["Visão geral", "Validações"])
with overview:
    st.subheader("Resumo do período")
    metrics = summarize(filtered)
    row = st.columns(3)
    row[0].metric("Execuções", metrics["runs"])
    row[1].metric("Cenários executados", metrics["scenarios"])
    row[2].metric("Clientes identificados", metrics["clients"])
    row = st.columns(3)
    row[0].metric("Validações com falha", metrics["failed"])
    row[1].metric("Validações aprovadas", metrics["passed"])
    row[2].metric("Validações informativas", metrics["info"])
    st.caption("Validações contam combinações distintas de cenário, destinatário, tipo e resultado. Um cliente pode aparecer em mais de um resultado.")

    st.subheader("Cenários")
    scenarios = scenario_summary(filtered).copy()
    scenarios["started_at"] = pd.to_datetime(scenarios["started_at"], utc=True).dt.tz_convert(display_zone).dt.strftime("%d/%m/%Y %H:%M:%S")
    scenarios["scenario_duration_ms"] = scenarios["scenario_duration_ms"].map(format_duration)
    scenarios["pytest_status"] = scenarios["pytest_status"].map(SCENARIO_LABELS).fillna("Não informado")
    scenarios = scenarios.rename(columns={
        "started_at": "Início", "project": "Projeto", "environment": "Ambiente",
        "title": "Cenário", "test_name": "Teste", "pytest_status": "Status do Pytest",
        "scenario_duration_ms": "Duração", "run_id": "Execução", "scenario_id": "ID do cenário",
    })
    st.dataframe(scenarios, hide_index=True, use_container_width=True)

with validations:
    st.subheader("Resultados por tipo de validação")
    messages = filtered[filtered["result_id"].notna()]
    if messages.empty:
        st.info("Os cenários selecionados não possuem mensagens de validação registradas.")
    else:
        st.caption("Selecione o tipo e o cenário; em seguida, expanda o cliente para ver os detalhes.")
        categories = sorted(messages["validation_type"].dropna().unique().tolist(), key=str.casefold)
        if not categories:
            st.info("Nenhum tipo de validação foi registrado para os filtros selecionados.")
        else:
            category = st.selectbox("Tipo de validação", ["Todas as validações", *categories])
            category_data = messages if category == "Todas as validações" else messages[messages["validation_type"] == category]
            options = category_data.drop_duplicates("scenario_id").set_index("scenario_id")

            def scenario_label(scenario_id):
                item = options.loc[scenario_id]
                started = pd.to_datetime(item["started_at"], utc=True).tz_convert(display_zone).strftime("%d/%m/%Y %H:%M")
                return f"{item['title']} · {item['project']} / {item['environment']} · {started} · #{scenario_id}"

            selected_id = st.selectbox("Cenário", options.index.tolist(), format_func=scenario_label)
            scenario_data = category_data[category_data["scenario_id"] == selected_id]
            first = scenario_data.iloc[0]
            st.caption(f"Duração: {format_duration(first['scenario_duration_ms'])} · Execução: {first['run_id']}")
            for status in ("failed", "passed", "info"):
                status_data = scenario_data[scenario_data["result_status"] == status]
                if status_data.empty:
                    continue
                st.markdown(f"**{STATUS_LABELS[status]}** · {status_data['scope_label'].nunique()} destinatário(s)")
                for scope, scope_data in status_data.groupby("scope_label", sort=True, dropna=False):
                    with st.expander(str(scope) if pd.notna(scope) else "Não informado"):
                        for _, message in scope_data.sort_values("sequence").iterrows():
                            validation_type = message["validation_type"]
                            label = str(validation_type) if pd.notna(validation_type) else "Não informado"
                            st.write(f"[{label}] {message['message']}")
