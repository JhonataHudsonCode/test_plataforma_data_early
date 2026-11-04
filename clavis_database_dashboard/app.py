from __future__ import annotations

import os
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pandas as pd
import altair as alt
import psycopg
import streamlit as st

from src.analysis import (SCENARIO_LABELS, STATUS_LABELS, apply_filters, count_affected_indexes,
                          empty_index_date_details, format_duration, index_results, missing_document_details,
                          missing_index_details, percentage_failure_details, run_duration_summary, scenario_summary, summarize)
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

indicator_data = {
    "missing_index": ("Índices não encontrados", missing_index_details(filtered, deduplicate=False)),
    "percentage": ("Índices com falha na comparação percentual", percentage_failure_details(filtered)),
    "missing_document": ("Índices sem documentos encontrados", missing_document_details(filtered)),
}
detail_key = st.session_state.get("indicator_detail")
if detail_key in indicator_data:
    title, details = indicator_data[detail_key]
    st.subheader(title)
    if st.button("← Voltar à visão geral"):
        st.session_state.pop("indicator_detail", None)
        st.rerun()
    st.caption("Resultados dos filtros aplicados, identificados nas mensagens registradas pelos testes.")
    if details.empty:
        st.info("Nenhum resultado encontrado para os filtros selecionados.")
    else:
        display = details[["project", "environment", "started_at", "title", "scope_label", "index_name", "validation_type", "message"]].copy()
        display["started_at"] = pd.to_datetime(display["started_at"], utc=True).dt.tz_convert(display_zone).dt.strftime("%d/%m/%Y %H:%M")
        display = display.rename(columns={"project": "Projeto", "environment": "Ambiente", "started_at": "Execução", "title": "Cenário", "scope_label": "Cliente ou origem", "index_name": "Índice", "validation_type": "Validação", "message": "Detalhe"})
        st.dataframe(display, hide_index=True, use_container_width=True)
    st.stop()

overview, validations = st.tabs(["Visão geral", "Validações"])
with overview:
    st.subheader("Resumo do período")
    metrics = summarize(filtered)
    row = st.columns(3)
    row[0].metric("Execuções", metrics["runs"])
    row[1].metric("Cenários distintos", metrics["scenarios"])
    row[2].metric("Clientes distintos", metrics["clients"])
    st.caption("Cenários são contados por projeto e nome do teste; clientes, pelo identificador, sem duplicação entre execuções.")
    st.subheader("Duração da bateria completa por projeto")
    run_filters = {key: st.session_state["dashboard_filters"].get(key, []) for key in ("project", "environment")}
    runs = run_duration_summary(apply_filters(data, run_filters))
    maximums = runs.groupby("project")["scenario_count"].transform("max")
    complete_runs = runs[(runs["scenario_count"] > 0) & (runs["scenario_count"] == maximums)]
    complete_runs = complete_runs[complete_runs["run_id"].isin(filtered["run_id"])].drop_duplicates(subset=["project"])
    if complete_runs.empty:
        st.info("Nenhuma execução com a maior quantidade de cenários encontrada nos filtros selecionados.")
    else:
        duration_columns = st.columns(len(complete_runs))
        for column, (_, run) in zip(duration_columns, complete_runs.iterrows()):
            started = pd.to_datetime(run["started_at"], utc=True).tz_convert(display_zone).strftime("%d/%m/%Y %H:%M")
            column.metric(f"Bateria completa · {run['project'].capitalize()}", format_duration(run["run_duration_ms"]))
            column.caption(f"{run['scenario_count']} cenários · {run['environment']} · {started}")
        st.caption("Critério: maior quantidade de cenários registrados no período por projeto; em caso de empate, a execução mais recente. O banco não informa explicitamente se a bateria foi completa.")
    st.subheader("Problemas nos índices")
    indicator_columns = st.columns(3)
    for column, (key, (title, details)) in zip(indicator_columns, indicator_data.items()):
        with column:
            count = count_affected_indexes(details)
            if st.button(f"{title}: {count}", key=f"indicator_{key}", use_container_width=True):
                st.session_state["indicator_detail"] = key
                st.rerun()
            if key == "missing_document":
                dated = empty_index_date_details(filtered, display_zone)
                st.caption(f"Hoje: {(dated['date_role'] == 'Hoje').sum()} · Ontem: {(dated['date_role'] == 'Ontem').sum()} (referentes a cada execução)")
            if details.empty:
                st.caption("Nenhum índice identificado.")
            else:
                unique = details.drop_duplicates(subset=["project", "environment", "scope_label", "index_name"])
                chart_data = unique.groupby("index_name").size().nlargest(5).reset_index(name="Clientes ou origens")
                st.altair_chart(alt.Chart(chart_data).mark_bar(color="#dc3545").encode(
                    x=alt.X("Clientes ou origens:Q", title="Clientes ou origens"),
                    y=alt.Y("index_name:N", title=None, sort="-x"),
                    tooltip=["index_name:N", "Clientes ou origens:Q"],
                ).properties(height=140), use_container_width=True)
    st.caption("Totais de índices distintos por projeto, ambiente e cliente ou origem. Clique em um indicador para ver os detalhes. A identificação depende das mensagens dos testes.")
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
    view = st.radio("Visualização", ["Por cenário", "Por índice"], horizontal=True)
    if view == "Por índice":
        indexed = index_results(filtered)
        st.subheader("Resultados por índice")
        st.caption("O tipo de índice é identificado nas mensagens; o prefixo do cliente é removido quando corresponde ao seu identificador. Os filtros da barra lateral continuam aplicados.")
        if indexed.empty:
            st.info("Nenhum índice identificado nas mensagens dos resultados selecionados.")
        else:
            families = sorted(indexed["index_family"].unique(), key=str.casefold)
            index_name = st.selectbox("Índice", families)
            selected = indexed[indexed["index_family"] == index_name]
            for status in ("failed", "passed", "info"):
                status_data = selected[selected["result_status"] == status]
                if status_data.empty:
                    continue
                st.markdown(f"**{STATUS_LABELS[status]}** · {status_data['scope_label'].nunique()} destinatário(s)")
                for scope, scope_data in status_data.groupby("scope_label", sort=True, dropna=False):
                    with st.expander(str(scope) if pd.notna(scope) else "Não informado"):
                        for _, item in scope_data.sort_values(["started_at", "sequence"], ascending=[False, True]).iterrows():
                            started = pd.to_datetime(item["started_at"], utc=True).tz_convert(display_zone).strftime("%d/%m/%Y %H:%M")
                            st.write(f"{started} · {item['title']} · {item['index_name']} · [{item['validation_type']}] {item['message']}")
    else:
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
