from __future__ import annotations

import os
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pandas as pd
import altair as alt
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
    stages = filtered[filtered["result_id"].notna()].drop_duplicates(
        subset=["scenario_id", "scope_type", "scope_label", "validation_type", "result_status"]
    ).copy()
    failures = stages[stages["result_status"] == "failed"]
    result_column, type_column = st.columns(2)
    result_column.subheader("Resultado das validações")
    validation_counts = pd.DataFrame({
        "Resultado": ["Falhas", "Aprovadas", "Informativas"],
        "Quantidade": [metrics["failed"], metrics["passed"], metrics["info"]],
    })
    chart = alt.Chart(validation_counts).mark_arc(innerRadius=70, outerRadius=120).encode(
        theta=alt.Theta("Quantidade:Q"),
        color=alt.Color("Resultado:N", scale=alt.Scale(
            domain=["Falhas", "Aprovadas", "Informativas"],
            range=["#dc3545", "#198754", "#0d6efd"],
        ), legend=alt.Legend(title="Resultado")),
        tooltip=["Resultado:N", "Quantidade:Q"],
    )
    if validation_counts["Quantidade"].sum() == 0:
        result_column.info("Nenhuma validação registrada para os filtros selecionados.")
    else:
        result_column.altair_chart(chart, use_container_width=True)
    result_column.caption(" · ".join(f"{row.Resultado}: {row.Quantidade}" for row in validation_counts.itertuples(index=False)))
    result_column.caption("Validações contam combinações distintas de cenário, destinatário, tipo e resultado. Um cliente pode aparecer em mais de um resultado.")

    type_column.subheader("Falhas por tipo de validação")
    if failures.empty:
        type_column.info("Nenhuma falha encontrada nos filtros selecionados.")
    else:
        by_type = failures.groupby("validation_type", dropna=False).size().reset_index(name="Falhas")
        by_type["validation_type"] = by_type["validation_type"].fillna("Não informado")
        type_column.altair_chart(alt.Chart(by_type).mark_arc(outerRadius=120).encode(
            theta=alt.Theta("Falhas:Q"), color=alt.Color("validation_type:N", title="Tipo"),
            tooltip=["validation_type:N", "Falhas:Q"],
        ), use_container_width=True)

    st.subheader("Clientes com mais falhas")
    client_failures = failures[(failures["scope_type"] == "client") & failures["client_id"].notna()]
    if client_failures.empty:
        st.info("Nenhuma falha de cliente encontrada nos filtros selecionados.")
    else:
        by_client = client_failures.groupby("client_id").size().nlargest(10).reset_index(name="Falhas")
        st.altair_chart(alt.Chart(by_client).mark_bar(color="#dc3545").encode(
            x=alt.X("client_id:N", title="Cliente", sort="-y", axis=alt.Axis(labelAngle=-45)),
            y=alt.Y("Falhas:Q", title="Falhas"), tooltip=["client_id:N", "Falhas:Q"],
        ), use_container_width=True)
        st.caption("Os 10 clientes com mais falhas no período filtrado.")

    st.subheader("Evolução das falhas por dia")
    daily_runs = filtered[["run_id", "started_at"]].drop_duplicates("run_id").copy()
    daily_runs["Dia"] = pd.to_datetime(daily_runs["started_at"], utc=True).dt.tz_convert(display_zone).dt.date
    daily = daily_runs.groupby("Dia").size().reset_index(name="Execuções")
    daily_failures = failures.copy()
    daily_failures["Dia"] = pd.to_datetime(daily_failures["started_at"], utc=True).dt.tz_convert(display_zone).dt.date
    daily = daily.merge(daily_failures.groupby("Dia").size().reset_index(name="Falhas"), on="Dia", how="left")
    daily["Falhas"] = daily["Falhas"].fillna(0).astype(int)
    st.altair_chart(alt.Chart(daily).mark_line(point=True, color="#dc3545").encode(
        x=alt.X("Dia:T", title="Dia"), y=alt.Y("Falhas:Q", title="Falhas"),
        tooltip=["Dia:T", "Falhas:Q", "Execuções:Q"],
    ), use_container_width=True)
    st.caption("As execuções por dia aparecem ao passar o mouse; mais execuções podem resultar em mais falhas.")

    st.subheader("Validações por cenário")
    if stages.empty:
        st.info("Nenhuma validação encontrada nos filtros selecionados.")
    else:
        by_scenario = stages.groupby(["title", "result_status"]).size().reset_index(name="Quantidade")
        by_scenario["Resultado"] = by_scenario["result_status"].map(STATUS_LABELS).fillna("Não informado")
        st.altair_chart(alt.Chart(by_scenario).mark_bar().encode(
            x=alt.X("title:N", title="Cenário", sort="-y", axis=alt.Axis(labelAngle=-45)), y=alt.Y("Quantidade:Q", title="Validações"),
            color=alt.Color("Resultado:N", scale=alt.Scale(domain=["Falha", "Aprovado", "Informativo"], range=["#dc3545", "#198754", "#0d6efd"])),
            tooltip=["title:N", "Resultado:N", "Quantidade:Q"],
        ), use_container_width=True)

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
