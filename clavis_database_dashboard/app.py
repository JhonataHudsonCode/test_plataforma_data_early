from __future__ import annotations

import os
import inspect
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pandas as pd
import altair as alt
import psycopg
import streamlit as st

from src.analysis import (SCENARIO_LABELS, STATUS_LABELS, apply_filters, count_affected_indexes,
                          client_validation_history, daily_validation_history, empty_index_date_details,
                          format_duration, index_results, missing_document_details,
                          missing_index_details, percentage_attribute_details, percentage_failure_details, run_duration_summary, scenario_summary, summarize)
from src.database import (DatabaseSettings, clear_database_cache, load_filter_options,
                          load_results, mapping_results_enabled)


alt.themes.register("clavis_dark", lambda: {
    "config": {
        "background": "#111827",
        "view": {"stroke": None},
        "axis": {
            "gridColor": "#263244", "domainColor": "#475569", "tickColor": "#475569",
            "labelColor": "#CBD5E1", "titleColor": "#E2E8F0", "labelFontSize": 12,
            "titleFontSize": 13,
        },
        "legend": {"labelColor": "#CBD5E1", "titleColor": "#E2E8F0"},
        "title": {"color": "#B6D7A8"},
        "range": {"category": ["#70C1B9", "#B6D7A8", "#F45B69", "#00C087", "#4285F4"]},
    }
})
alt.themes.enable("clavis_dark")


st.set_page_config(page_title="Clavis | Testes", page_icon="📊", layout="wide")
LOGO_PATH = Path(__file__).resolve().parent / "assets" / "clavis_dashboard_logo.png"
st.markdown(
    """<style>
    :root {
      --clavis-bg: #0B1220;
      --clavis-surface: #111827;
      --clavis-border: #263244;
      --clavis-text: #E2E8F0;
      --clavis-muted: #CBD5E1;
      --clavis-title: #B6D7A8;
      --clavis-accent: #70C1B9;
      --clavis-fail: #F45B69;
      --clavis-pass: #00C087;
    }
    [data-testid="stAppDeployButton"] { display: none !important; }
    [data-testid="stAppViewContainer"], [data-testid="stMain"], [data-testid="stHeader"] { background: radial-gradient(ellipse at 85% 0%, rgba(112, 193, 185, .09), transparent 34%), var(--clavis-bg); color: var(--clavis-text); }
    [data-testid="stMainBlockContainer"] { max-width: 1580px; padding: 2rem clamp(1rem, 3vw, 3rem) 4rem; }
    [data-testid="stSidebar"] { background: var(--clavis-surface); border-right: 1px solid var(--clavis-border); color: var(--clavis-text); }
    [data-testid="stMarkdownContainer"], [data-testid="stWidgetLabel"] { color: var(--clavis-muted); }
    h1, h2, h3 { color: var(--clavis-title); letter-spacing: -.025em; }
    h1 { font-weight: 750; }
    [data-testid="stVerticalBlockBorderWrapper"] { background: linear-gradient(145deg, rgba(17, 24, 39, .98), rgba(11, 18, 32, .96)); border: 1px solid var(--clavis-border) !important; border-radius: 18px !important; box-shadow: 0 12px 32px rgba(0, 0, 0, .22); }
    .indicator-heading { display: flex; align-items: center; gap: 14px; padding: 4px 2px 0; }
    .indicator-icon { display: grid; place-items: center; flex: 0 0 42px; width: 42px; height: 42px; border-radius: 13px; color: var(--indicator-accent); background: color-mix(in srgb, var(--indicator-accent) 13%, #111827); border: 1px solid color-mix(in srgb, var(--indicator-accent) 40%, #263244); font-size: 1.3rem; font-weight: 800; box-shadow: 0 0 20px color-mix(in srgb, var(--indicator-accent) 14%, transparent); }
    .indicator-copy { min-width: 0; }
    .indicator-kicker { color: #94A3B8; font-size: .68rem; font-weight: 750; letter-spacing: .15em; text-transform: uppercase; margin-bottom: 3px; }
    .indicator-title { color: var(--clavis-text); font-size: clamp(1rem, 1.5vw, 1.22rem); font-weight: 700; line-height: 1.25; }
    .indicator-total { margin-left: auto; color: var(--indicator-accent); font-size: clamp(1.8rem, 3vw, 2.55rem); font-weight: 780; line-height: 1; letter-spacing: -.045em; font-variant-numeric: tabular-nums; text-align: right; white-space: nowrap; }
    .indicator-total span { display: block; padding-top: 6px; color: #94A3B8; font-size: .66rem; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; }
    .indicator-description { margin: 10px 0 4px 56px; color: #94A3B8; font-size: .84rem; line-height: 1.45; }
    .indicator-meta { display: flex; flex-wrap: wrap; gap: 8px; margin: 10px 0 2px 56px; }
    .indicator-chip { border: 1px solid var(--clavis-border); border-radius: 999px; background: rgba(11, 18, 32, .72); color: var(--clavis-muted); padding: 5px 10px; font-size: .74rem; }
    .indicator-chip strong { color: var(--clavis-accent); font-variant-numeric: tabular-nums; }
    .indicator-card-chart { margin-top: 8px; padding: 8px 4px 0; border-top: 1px solid rgba(38, 50, 68, .72); }
    [data-testid="stMetric"] { background: linear-gradient(145deg, #111827, #131e2e); border: 1px solid var(--clavis-border); border-radius: 16px; padding: 18px 20px; box-shadow: 0 8px 22px rgba(0, 0, 0, .17); }
    [data-testid="stMetricLabel"] { color: #94A3B8; }
    [data-testid="stMetricValue"] { color: var(--clavis-accent); font-weight: 700; }
    [data-baseweb="tab-list"] { gap: .45rem; border-bottom: 1px solid var(--clavis-border); }
    [data-baseweb="tab"] { border-radius: 10px 10px 0 0; }
    [data-baseweb="tab"][aria-selected="true"] { color: var(--clavis-accent); border-bottom-color: var(--clavis-accent); }
    [data-testid="stExpander"] { background: var(--clavis-surface); border: 1px solid var(--clavis-border); border-radius: 12px; }
    [data-testid="stButton"] > button { background: linear-gradient(145deg, #111827, #172235); color: var(--clavis-text); border-radius: 11px; border: 1px solid #334155; transition: transform .15s ease, border-color .15s ease, box-shadow .15s ease; }
    [data-testid="stButton"] > button:hover { transform: translateY(-1px); border-color: var(--clavis-accent); color: var(--clavis-accent); box-shadow: 0 6px 18px rgba(112, 193, 185, .14); }
    [data-testid="stDataFrame"] { border: 1px solid var(--clavis-border); border-radius: 12px; overflow: hidden; }
    [data-baseweb="select"] > div, [data-baseweb="input"] > div { background: var(--clavis-bg); border-color: #334155; }
    @media (max-width: 760px) {
      [data-testid="stMainBlockContainer"] { padding: 1rem .75rem 2rem; }
      [data-testid="stMetric"] { padding: 13px 14px; }
      .indicator-heading { gap: 10px; }
      .indicator-icon { flex-basis: 36px; width: 36px; height: 36px; border-radius: 11px; }
      .indicator-total { font-size: 1.65rem; }
      .indicator-total span { font-size: .58rem; }
      .indicator-description, .indicator-meta { margin-left: 46px; }
      h1 { font-size: 1.8rem; }
    }
    </style>""",
    unsafe_allow_html=True,
)
st.title("Dashboard de testes Clavis")
st.caption("Resultados persistidos pelo Early e After no PostgreSQL")

try:
    settings = DatabaseSettings.from_env()
    display_zone = ZoneInfo(os.getenv("DASHBOARD_TIMEZONE", "America/Sao_Paulo"))
    show_mapping_results = mapping_results_enabled()
except (ValueError, ZoneInfoNotFoundError) as error:
    st.error(f"Configuração inválida: {error}")
    st.info("Crie o arquivo .env e configure a conexão conforme o README do projeto.")
    st.stop()

today = datetime.now(display_zone).date()
data = st.session_state.get("dashboard_data")
previous_mapping_setting = st.session_state.get("_mapping_setting")
if previous_mapping_setting is not None and previous_mapping_setting != show_mapping_results:
    clear_database_cache()
    for key in ("dashboard_data", "dashboard_filters", "dashboard_filter_options", "selected_scenarios"):
        st.session_state.pop(key, None)
    data = None
st.session_state["_mapping_setting"] = show_mapping_results
current_week_start = today - timedelta(days=today.weekday())
auto_load_current_week = not st.session_state.get("dashboard_initial_week_loaded", False)
if auto_load_current_week:
    st.session_state["filter_start_date"] = current_week_start
    st.session_state["filter_end_date"] = today
else:
    st.session_state.setdefault("filter_start_date", current_week_start)
    st.session_state.setdefault("filter_end_date", today)


def set_filter_date(widget_key: str, selected_date) -> None:
    st.session_state[widget_key] = selected_date


@st.dialog("Carregando dados do dashboard", dismissible=False)
def load_initial_week() -> None:
    start_date = st.session_state["filter_start_date"]
    end_date = st.session_state["filter_end_date"]
    st.image(str(LOGO_PATH), use_container_width=True)
    st.write("Na primeira abertura, carregamos os dados da semana atual para preparar a visão geral.")
    st.caption(f"Período: {start_date:%d/%m/%Y} a {end_date:%d/%m/%Y}")
    try:
        start = datetime.combine(start_date, time.min, tzinfo=display_zone).astimezone(timezone.utc)
        end = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=display_zone).astimezone(timezone.utc)
        with st.spinner("Consultando o PostgreSQL e montando os filtros..."):
            filter_options = load_filter_options(settings)
            results = load_results(settings, start, end)
    except (psycopg.Error, OSError) as error:
        detail = getattr(getattr(error, "diag", None), "message_primary", None) or str(error)
        sqlstate = getattr(error, "sqlstate", None)
        st.error(f"Não foi possível carregar os dados ({sqlstate or type(error).__name__}): {detail}")
        st.button("Tentar novamente", type="primary", use_container_width=True)
        return

    st.session_state["dashboard_filter_options"] = filter_options
    st.session_state["dashboard_data"] = results
    st.session_state["dashboard_filters"] = {
        "project": [], "environment": [], "title": [], "client_id": [],
        "validation_type": [], "result_status": [],
    }
    st.session_state["dashboard_initial_week_loaded"] = True
    st.rerun()


if auto_load_current_week:
    load_initial_week()
    st.stop()


if "dashboard_filter_options" not in st.session_state:
    try:
        with st.spinner("Carregando opções dos filtros..."):
            st.session_state["dashboard_filter_options"] = load_filter_options(settings)
    except (psycopg.Error, OSError) as error:
        detail = getattr(getattr(error, "diag", None), "message_primary", None) or str(error)
        sqlstate = getattr(error, "sqlstate", None)
        st.error(f"Falha ao carregar filtros do PostgreSQL ({sqlstate or type(error).__name__}): {detail}")
        if st.button("Tentar carregar filtros novamente"):
            st.rerun()
        st.stop()

if not show_mapping_results:
    st.session_state["selected_scenarios"] = [
        value for value in st.session_state.get("selected_scenarios", [])
        if "mapping" not in str(value).casefold()
    ]
    existing_filters = st.session_state.get("dashboard_filters")
    if existing_filters:
        for key in ("title", "validation_type"):
            existing_filters[key] = [
                value for value in existing_filters.get(key, [])
                if "mapping" not in str(value).casefold()
            ]
        st.session_state["dashboard_filters"] = existing_filters

    st.caption("Validações e resultados de testes de mapping ocultos por DASHBOARD_SHOW_MAPPING_RESULTS=false.")


def choices(column: str) -> list[str]:
    values = st.session_state["dashboard_filter_options"].get(column, [])
    if not show_mapping_results and column in {"title", "validation_type"}:
        values = [value for value in values if "mapping" not in str(value).casefold()]
    return values


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
    st.image(str(LOGO_PATH), use_container_width=True)
    st.divider()
    st.header("Filtros")
    with st.container():
        start_date = st.date_input("Data inicial", key="filter_start_date")
        st.button(
            "Ontem", key="set_start_yesterday", use_container_width=True,
            on_click=set_filter_date,
            args=("filter_start_date", today - timedelta(days=1)),
        )
        end_date = st.date_input("Data final", key="filter_end_date")
        st.button(
            "Hoje", key="set_end_today", use_container_width=True,
            on_click=set_filter_date, args=("filter_end_date", today),
        )
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
        if st.button("Atualizar do banco", use_container_width=True, help="Ignora o cache atual e busca dados atualizados no PostgreSQL."):
            clear_database_cache()
            st.session_state.pop("dashboard_filter_options", None)
            st.session_state["force_refresh_search"] = True
            st.rerun()
        submitted = (
            submitted
            or st.session_state.pop("force_refresh_search", False)
            or auto_load_current_week
        )
        search_error = None
        if submitted and auto_load_current_week:
            st.session_state["dashboard_initial_week_loaded"] = True
        if submitted and start_date <= end_date:
            button_area.button("⏳ Pesquisando...", type="primary", disabled=True)
            start = datetime.combine(start_date, time.min, tzinfo=display_zone).astimezone(timezone.utc)
            end = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=display_zone).astimezone(timezone.utc)
            with st.spinner("Consultando resultados..."):
                try:
                    data = load_results(settings, start, end)
                except (psycopg.Error, OSError) as error:
                    detail = getattr(getattr(error, "diag", None), "message_primary", None) or str(error)
                    sqlstate = getattr(error, "sqlstate", None)
                    search_error = f"{sqlstate or type(error).__name__}: {detail}"
            if search_error:
                st.session_state["dashboard_search_error"] = search_error
                st.rerun()
    st.caption("As opções abrangem os dados disponíveis no banco. Ajuste os filtros e clique em Pesquisar para aplicá-los.")

search_error = st.session_state.pop("dashboard_search_error", None)
if search_error:
    st.error(f"Não foi possível consultar o PostgreSQL de relatórios: {search_error}")

if submitted:
    if start_date > end_date:
        st.error("A data inicial deve ser anterior ou igual à data final.")
        st.stop()
    st.session_state["dashboard_initial_week_loaded"] = True
    st.session_state["dashboard_data"] = data
    if not data.empty:
        for column, existing in st.session_state["dashboard_filter_options"].items():
            st.session_state["dashboard_filter_options"][column] = sorted(
                set(existing) | set(data[column].dropna().astype(str)), key=str.casefold
            )
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


def render_daily_history(frame: pd.DataFrame, title: str, chart_key: str) -> None:
    """Exibe falhas e aprovações por dia, com uma única categoria por data."""
    with st.container(border=True):
        st.subheader(title)
        history = daily_validation_history(frame, display_zone)
        if history.empty:
            st.info("Não há execuções no período e projeto selecionados para compor este histórico.")
            return

        history["day_label"] = pd.to_datetime(history["execution_day"]).dt.strftime("%d/%m/%Y")
        day_order = history["day_label"].drop_duplicates().tolist()
        history["Resultado"] = history["result_status"].map({"failed": "Falhas", "passed": "Aprovadas"})
        colors = alt.Scale(
            domain=["Falhas", "Aprovadas"],
            range=["#F45B69", "#00C087"],
        )
        x = alt.X(
            "day_label:O", title="Dia da execução", sort=day_order,
            axis=alt.Axis(labelAngle=-30, labelOverlap=True, tickSize=0, domain=False),
        )
        y = alt.Y(
            "validations:Q", title="Quantidade de validações",
            scale=alt.Scale(domainMin=0), stack=None,
        )
        base = alt.Chart(history).encode(
            x=x,
            y=y,
            color=alt.Color("Resultado:N", title=None, scale=colors),
            detail=alt.Detail("Resultado:N"),
            tooltip=[
                alt.Tooltip("day_label:N", title="Dia"),
                alt.Tooltip("Resultado:N"),
                alt.Tooltip("validations:Q", title="Validações"),
            ],
        )
        glow = base.mark_line(interpolate="monotone", strokeWidth=9, opacity=0.12)
        line = base.mark_line(interpolate="monotone", strokeWidth=2.8)
        halo = base.mark_point(filled=True, size=260, opacity=0.11)
        points = base.mark_point(
            filled=True, size=72, stroke="#0B1220", strokeWidth=1.5,
        )
        chart = glow + line + halo + points
        st.altair_chart(
            chart.properties(height=290, padding={"left": 8, "right": 16, "top": 10, "bottom": 4})
            .configure(background="#111827")
            .configure_view(stroke="#263244", strokeWidth=1)
            .configure_axis(
                gridColor="#263244", gridOpacity=0.42, domain=False, tickSize=0,
                labelColor="#CBD5E1", titleColor="#94A3B8", labelFontSize=11,
                titleFontSize=11,
            )
            .configure_legend(
                orient="top", direction="horizontal", symbolType="circle",
                labelColor="#CBD5E1", titleColor="#E2E8F0",
            ),
            use_container_width=True,
            key=chart_key,
        )


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
        if detail_key == "percentage":
            index_options = sorted(details["index_family"].dropna().unique().tolist(), key=str.casefold)
            chosen_index = st.selectbox("Filtrar por índice", index_options)
            details = details[details["index_family"] == chosen_index]
            client_options = sorted(details["scope_label"].dropna().astype(str).unique().tolist(), key=str.casefold)
            selected_clients = st.multiselect("Filtrar clientes ou origens", client_options)
            if selected_clients:
                details = details[details["scope_label"].isin(selected_clients)]
            attribute_details = percentage_attribute_details(details)
            st.caption("Os valores exibidos correspondem a cada falha registrada, sem somar clientes ou execuções diferentes.")
            if attribute_details.empty:
                st.info("As falhas selecionadas não informam valores de ontem e hoje em um formato reconhecido.")
            else:
                for attribute in sorted(attribute_details["attribute"].unique(), key=str.casefold):
                    values = attribute_details[attribute_details["attribute"] == attribute].copy()
                    st.subheader(f"Atributo: {attribute}")
                    values["Execução"] = pd.to_datetime(values["started_at"], utc=True).dt.tz_convert(display_zone).dt.strftime("%d/%m/%Y %H:%M:%S")
                    values["Comparação"] = values["scope_label"].fillna("Não informado").astype(str) + " · " + values["Execução"] + " · " + values["index_name"] + " · " + values["scenario_id"].astype(str) + " / " + values["result_id"].astype(str)
                    values["Variação"] = values["change_percent"].map(lambda value: "Não calculável (ontem = 0)" if pd.isna(value) else f"{value:+.1f}%")
                    chart_values = values.melt(id_vars=["Comparação", "direction", "Variação"], value_vars=["previous_value", "current_value"], var_name="Período", value_name="Valor")
                    chart_values["Período"] = chart_values["Período"].map({"previous_value": "Ontem", "current_value": "Hoje"})
                    st.altair_chart(alt.Chart(chart_values).mark_bar().encode(
                        x=alt.X("Comparação:N", title="Cliente ou origem · execução · índice", axis=alt.Axis(labelAngle=-45)),
                        xOffset=alt.XOffset("Período:N", sort=["Ontem", "Hoje"]),
                        y=alt.Y("Valor:Q", title="Valor"),
                        color=alt.Color("Período:N", scale=alt.Scale(domain=["Ontem", "Hoje"], range=["#709C99", "#2C6966"])),
                        tooltip=["Comparação:N", "Período:N", "Valor:Q", alt.Tooltip("direction:N", title="Direção"), "Variação:N"],
                    ), use_container_width=True)
                    st.dataframe(values[["scope_label", "index_name", "Execução", "direction", "previous_value", "current_value", "Variação"]].rename(columns={
                        "scope_label": "Cliente ou origem", "index_name": "Índice", "direction": "Direção",
                        "previous_value": "Ontem", "current_value": "Hoje",
                    }), hide_index=True, use_container_width=True)
            st.subheader("Detalhes das falhas")
        display = details[["project", "environment", "started_at", "title", "scope_label", "index_name", "validation_type", "message"]].copy()
        display["started_at"] = pd.to_datetime(display["started_at"], utc=True).dt.tz_convert(display_zone).dt.strftime("%d/%m/%Y %H:%M")
        display = display.rename(columns={"project": "Projeto", "environment": "Ambiente", "started_at": "Execução", "title": "Cenário", "scope_label": "Cliente ou origem", "index_name": "Índice", "validation_type": "Validação", "message": "Detalhe"})
        st.dataframe(display, hide_index=True, use_container_width=True)
    st.stop()

selected_index = st.session_state.get("index_detail")
if selected_index is not None:
    st.subheader(f"Falhas do índice: {selected_index}")
    if st.button("← Voltar aos índices"):
        st.session_state.pop("index_detail", None)
        st.session_state["return_to_indices"] = True
        st.rerun()
    index_data = index_results(filtered)
    failures_for_index = index_data[(index_data["index_family"] == selected_index) & (index_data["result_status"] == "failed")]
    if failures_for_index.empty:
        st.info("Nenhuma falha registrada para este índice nos filtros selecionados.")
    else:
        st.caption("Falhas organizadas por cliente ou origem. Os filtros aplicados continuam válidos.")
        for scope, scope_data in failures_for_index.groupby("scope_label", sort=True, dropna=False):
            with st.expander(str(scope) if pd.notna(scope) else "Não informado"):
                for _, item in scope_data.sort_values(["started_at", "sequence"], ascending=[False, True]).iterrows():
                    started = pd.to_datetime(item["started_at"], utc=True).tz_convert(display_zone).strftime("%d/%m/%Y %H:%M")
                    st.write(f"{started} · {item['project']} / {item['environment']} · {item['title']} · {item['index_name']} · [{item['validation_type']}] {item['message']}")
    st.stop()

if st.session_state.get("failure_history_detail"):
    st.subheader("Histórico de validações por cliente")
    if st.button("← Voltar à visão geral"):
        st.session_state.pop("failure_history_detail", None)
        st.rerun()
    client_rows = filtered[
        filtered["result_id"].notna()
        & filtered["scope_type"].eq("client")
        & filtered["client_id"].notna()
        & filtered["result_status"].isin(["failed", "passed"])
    ]
    client_options = sorted(client_rows["client_id"].astype(str).unique(), key=str.casefold)
    if not client_options:
        st.info("Não há resultados aprovados ou com falha por cliente nos filtros selecionados.")
    else:
        selected_client = st.selectbox("Cliente", client_options, key="history_client")
        history = client_validation_history(filtered, selected_client, display_zone)
        if history.empty:
            st.info("Nao ha historico de validacoes para este cliente no periodo selecionado.")
        else:
            history["day_label"] = pd.to_datetime(history["execution_day"]).dt.strftime("%d/%m/%Y")
            day_order = history["day_label"].drop_duplicates().tolist()
            history["Resultado"] = history["result_status"].map({"failed": "Falhas", "passed": "Aprovadas"})
            client_chart = alt.Chart(history).mark_bar(cornerRadiusTopLeft=5, cornerRadiusTopRight=5, size=22).encode(
                x=alt.X("day_label:O", title="Dia da execucao", sort=day_order, axis=alt.Axis(labelAngle=-35, labelOverlap=False)),
                xOffset=alt.XOffset("Resultado:N", sort=["Falhas", "Aprovadas"]),
                y=alt.Y("validations:Q", title="Quantidade de validacoes", scale=alt.Scale(domainMin=0)),
                color=alt.Color("Resultado:N", title="Resultado", scale=alt.Scale(
                    domain=["Falhas", "Aprovadas"], range=["#F45B69", "#00C087"]
                )),
                tooltip=[
                    alt.Tooltip("day_label:N", title="Dia"),
                    alt.Tooltip("Resultado:N"), alt.Tooltip("validations:Q", title="Validacoes"),
                ],
            )
            st.altair_chart(
                client_chart.properties(height=360).configure(background="#111827").configure_view(stroke=None).configure_axis(
                    gridColor="#263244", domainColor="#475569", tickColor="#475569",
                    labelColor="#CBD5E1", titleColor="#E2E8F0",
                ).configure_legend(labelColor="#CBD5E1", titleColor="#E2E8F0"),
                use_container_width=True,
            )
            chart_table = history.pivot(index="day_label", columns="result_status", values="validations").rename(columns={
                "failed": "Falhas", "passed": "Aprovadas",
            }).reset_index().rename(columns={"day_label": "Dia"})
            chart_table = chart_table[["Dia", "Falhas", "Aprovadas"]]
            st.dataframe(chart_table, hide_index=True, use_container_width=True)
    st.stop()

tab_options = {}
if st.session_state.pop("return_to_indices", False) and "default" in inspect.signature(st.tabs).parameters:
    tab_options["default"] = "Índices"
overview, indices_tab, validations = st.tabs(["Visão geral", "Índices", "Validações"], **tab_options)
with overview:
    st.subheader("Resumo do período")
    metrics = summarize(filtered)
    row = st.columns(3)
    row[0].metric("Execuções", metrics["runs"])
    row[1].metric("Cenários distintos", metrics["scenarios"])
    row[2].metric("Clientes distintos", metrics["clients"])
    st.caption("Cenários são contados por projeto e nome do teste; clientes, pelo identificador, sem duplicação entre execuções.")
    render_daily_history(filtered, "Histórico geral de falhas e aprovações", "history_general")
    for project in ("after", "early"):
        project_rows = filtered[filtered["project"].astype("string").str.casefold().eq(project)]
        render_daily_history(project_rows, f"Histórico do projeto {project.capitalize()}", f"history_{project}")
    st.caption("Barras vermelhas mostram falhas e verdes, aprovações. Cada data aparece uma única vez, sem horários.")
    if st.button("Detalhar histórico de sucessos e falhas por cliente", type="secondary"):
        st.session_state["failure_history_detail"] = True
        st.rerun()

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
    indicator_presentation = {
        "missing_index": {
            "kicker": "01 / Integridade do índice", "icon": "!", "accent": "#F45B69",
            "description": "Índices que o teste esperava encontrar e não localizou.",
            "count_label": "índices afetados",
        },
        "percentage": {
            "kicker": "02 / Variação dos dados", "icon": "↗", "accent": "#F45B69",
            "description": "Índices com valores fora da variação percentual permitida.",
            "count_label": "índices com falha",
        },
        "missing_document": {
            "kicker": "03 / Cobertura da ingestão", "icon": "◌", "accent": "#D83026",
            "description": "Índices sem documentos nas datas recentes verificadas.",
            "count_label": "índices afetados",
        },
    }
    for key, (title, details) in indicator_data.items():
        presentation = indicator_presentation[key]
        count = count_affected_indexes(details)
        with st.container(border=True, key=f"indicator_card_{key}"):
            st.markdown(
                f"""
                <div class="indicator-heading" style="--indicator-accent: {presentation['accent']}">
                  <div class="indicator-icon">{presentation['icon']}</div>
                  <div class="indicator-copy">
                    <div class="indicator-kicker">{presentation['kicker']}</div>
                    <div class="indicator-title">{title}</div>
                  </div>
                  <div class="indicator-total" style="--indicator-accent: {presentation['accent']}">
                    {count}<span>{presentation['count_label']}</span>
                  </div>
                </div>
                <div class="indicator-description">{presentation['description']}</div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Explorar clientes e ocorrências  →", key=f"indicator_{key}", use_container_width=True):
                st.session_state["indicator_detail"] = key
                st.rerun()
            if key == "missing_document":
                dated = empty_index_date_details(filtered, display_zone)
                st.markdown(
                    f"""
                    <div class="indicator-meta">
                      <span class="indicator-chip">Hoje <strong>{(dated['date_role'] == 'Hoje').sum()}</strong></span>
                      <span class="indicator-chip">Ontem <strong>{(dated['date_role'] == 'Ontem').sum()}</strong></span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            if details.empty:
                st.caption("Nenhuma ocorrência registrada para este indicador no período selecionado.")
            else:
                unique = details.drop_duplicates(subset=["project", "environment", "scope_label", "index_name"])
                chart_data = unique.groupby("index_name").size().nlargest(5).reset_index(name="Clientes ou origens")
                accent = presentation["accent"]
                x_encoding = alt.X(
                    "Clientes ou origens:Q", title="Clientes ou origens",
                    scale=alt.Scale(domainMin=0, nice=True),
                    axis=alt.Axis(gridColor="#263244", domain=False, tickColor="#475569"),
                )
                y_encoding = alt.Y(
                    "index_name:N", title=None, sort="-x",
                    axis=alt.Axis(domain=False, ticks=False, labelLimit=340),
                )
                base_chart = alt.Chart(chart_data)
                lollipop_line = base_chart.mark_rule(
                    color=accent, opacity=.7, strokeWidth=3, strokeCap="round"
                ).encode(x=x_encoding, x2=alt.datum(0), y=y_encoding)
                lollipop_point = base_chart.mark_point(
                    filled=True, color=accent, size=105, stroke="#E2E8F0", strokeWidth=1.2
                ).encode(
                    x=x_encoding, y=y_encoding,
                    tooltip=[alt.Tooltip("index_name:N", title="Índice"),
                             alt.Tooltip("Clientes ou origens:Q", title="Clientes ou origens")],
                )
                value_label = base_chart.mark_text(
                    align="left", dx=10, color="#E2E8F0", fontWeight=700
                ).encode(
                    x=x_encoding, y=y_encoding,
                    text=alt.Text("Clientes ou origens:Q", format="d"),
                )
                indicator_chart = (lollipop_line + lollipop_point + value_label).properties(
                    height=max(125, min(240, len(chart_data) * 42))
                ).configure(
                    background="#111827"
                ).configure_view(stroke=None).configure_axis(
                    labelColor="#CBD5E1", titleColor="#E2E8F0",
                )
                st.altair_chart(indicator_chart, use_container_width=True, key=f"chart_{key}")
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
            range=["#D83026", "#274E13", "#1972E8"],
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
            theta=alt.Theta("Falhas:Q"), color=alt.Color("validation_type:N", title="Tipo", scale=alt.Scale(range=["#2C6966", "#709C99", "#1972E8", "#4285F4", "#D83026", "#274E13", "#434343"])),
            tooltip=["validation_type:N", "Falhas:Q"],
        ), use_container_width=True)

    st.subheader("Clientes com mais falhas")
    client_failures = failures[(failures["scope_type"] == "client") & failures["client_id"].notna()]
    if client_failures.empty:
        st.info("Nenhuma falha de cliente encontrada nos filtros selecionados.")
    else:
        by_client = client_failures.groupby("client_id").size().nlargest(10).reset_index(name="Falhas")
        st.altair_chart(alt.Chart(by_client).mark_bar(color="#D83026").encode(
            x=alt.X("client_id:N", title="Cliente", sort="-y", axis=alt.Axis(labelAngle=-45)),
            y=alt.Y("Falhas:Q", title="Falhas"), tooltip=["client_id:N", "Falhas:Q"],
        ), use_container_width=True)
        st.caption("Os 10 clientes com mais falhas no período filtrado.")

    st.subheader("Validações por cenário")
    if stages.empty:
        st.info("Nenhuma validação encontrada nos filtros selecionados.")
    else:
        by_scenario = stages.groupby(["title", "result_status"]).size().reset_index(name="Quantidade")
        by_scenario["Resultado"] = by_scenario["result_status"].map(STATUS_LABELS).fillna("Não informado")
        st.altair_chart(alt.Chart(by_scenario).mark_bar().encode(
            x=alt.X("title:N", title="Cenário", sort="-y", axis=alt.Axis(labelAngle=-45)), y=alt.Y("Quantidade:Q", title="Validações"),
            color=alt.Color("Resultado:N", scale=alt.Scale(domain=["Falha", "Aprovado", "Informativo"], range=["#D83026", "#274E13", "#1972E8"])),
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

with indices_tab:
    st.subheader("Resultados por índice")
    indexed = index_results(filtered)
    st.caption("Índices identificados nas mensagens dos testes do Early e After, conforme os filtros aplicados. Nomes com o prefixo do cliente são agrupados pelo tipo de índice.")
    if indexed.empty:
        st.info("Nenhum índice identificado nas mensagens dos resultados selecionados.")
    else:
        index_families = sorted(indexed["index_family"].unique(), key=str.casefold)
        chosen_indexes = st.multiselect("Filtrar índices", index_families)
        visible = indexed[indexed["index_family"].isin(chosen_indexes)] if chosen_indexes else indexed
        for family in sorted(visible["index_family"].unique(), key=str.casefold):
            family_data = visible[visible["index_family"] == family]
            stages_for_index = family_data.drop_duplicates(subset=["scenario_id", "scope_type", "scope_label", "validation_type", "result_status"])
            counts = stages_for_index["result_status"].value_counts()
            chart_data = pd.DataFrame({"Resultado": ["Falha", "Aprovado", "Informativo"], "Quantidade": [int(counts.get(status, 0)) for status in ("failed", "passed", "info")]})
            st.markdown(f"**{family}**")
            st.altair_chart(alt.Chart(chart_data).mark_bar().encode(
                x=alt.X("Resultado:N", title=None, sort=None), y=alt.Y("Quantidade:Q", title="Validações"),
                color=alt.Color("Resultado:N", scale=alt.Scale(domain=["Falha", "Aprovado", "Informativo"], range=["#D83026", "#274E13", "#1972E8"]), legend=None),
                tooltip=["Resultado:N", "Quantidade:Q"],
            ).properties(height=160), use_container_width=True)
            if st.button(f"Ver falhas · {family}", key=f"index_failures_{family}"):
                st.session_state["index_detail"] = family
                st.rerun()
        st.caption("Cada barra conta validações distintas por cenário, cliente ou origem, tipo e resultado; mensagens sem índice identificável não são incluídas.")

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
