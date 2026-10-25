from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from html import escape
from pathlib import Path
import re


_SECTIONS = ("Falhas", "Informativos", "Aprovados")
_STATUS = {
    "Falhas": ("Falhas", "fail"),
    "Informativos": ("Informativos", "info"),
    "Aprovados": ("Aprovados", "pass"),
}


def render_html_from_text(report_path: str | Path) -> str:
    """Renderiza relatórios por categoria, cenário, status e cliente."""
    report = Path(report_path).read_text(encoding="utf-8")
    if "Resultados por teste:" in report:
        title, environment, duration, scenarios = _parse_combined_report(report)
    else:
        title, environment, duration, sections = _parse_individual_report(report)
        scenarios = [(title, duration, sections)]

    categories = _categorize_scenarios(scenarios)
    return _render_page(title, environment, duration, categories, len(scenarios))


def _parse_individual_report(
    report: str,
) -> tuple[str, str, str, dict[str, list[tuple[str, list[str]]]]]:
    lines = report.splitlines()
    return (
        _value(lines, "Teste:", "Relatório de validação"),
        _value(lines, "Ambiente:", "hml"),
        _value(lines, "Duração:", "00:00:00"),
        _parse_sections(lines),
    )


def _parse_combined_report(
    report: str,
) -> tuple[str, str, str, list[tuple[str, str, dict[str, list[tuple[str, list[str]]]]]]]:
    lines = report.splitlines()
    scenarios: list[tuple[str, str, dict[str, list[tuple[str, list[str]]]]]] = []
    current_name: str | None = None
    current_duration = "00:00:00"
    current_lines: list[str] = []

    def append_current() -> None:
        if current_name is not None:
            scenarios.append((current_name, current_duration, _parse_sections(current_lines)))

    for line in lines:
        if line.startswith("Teste executado: "):
            append_current()
            current_name = line.removeprefix("Teste executado: ").strip()
            current_duration = "00:00:00"
            current_lines = []
        elif current_name is not None and line.startswith("Duração do cenário:"):
            current_duration = line.removeprefix("Duração do cenário:").strip()
        elif current_name is not None:
            current_lines.append(line)
    append_current()

    return (
        _value(lines, "Teste:", "Resumo geral da execução"),
        _value(lines, "Ambiente:", "hml"),
        _value(lines, "Duração:", "00:00:00"),
        scenarios,
    )


def _value(lines: list[str], prefix: str, default: str) -> str:
    return next(
        (line.removeprefix(prefix).strip() for line in lines if line.startswith(prefix)),
        default,
    )


def _parse_sections(lines: list[str]) -> dict[str, list[tuple[str, list[str]]]]:
    sections: dict[str, list[tuple[str, list[str]]]] = {section: [] for section in _SECTIONS}
    current_section: str | None = None
    for line in lines:
        for section in _SECTIONS:
            if line.startswith(f"{section} ("):
                current_section = section
                break
        else:
            if current_section and line.startswith("- Cliente: "):
                sections[current_section].append((line.removeprefix("- Cliente: ").strip(), []))
            elif current_section and sections[current_section] and line.startswith("  "):
                sections[current_section][-1][1].append(line.strip())
    return sections


def _categorize_scenarios(
    scenarios: list[tuple[str, str, dict[str, list[tuple[str, list[str]]]]]],
) -> dict[str, dict[str, dict[str, dict[str, list[str]]]]]:
    categories: dict[str, dict[str, dict[str, dict[str, list[str]]]]] = {}
    for scenario_name, duration, sections in scenarios:
        for section, clients in sections.items():
            for client_id, messages in clients:
                for message in messages:
                    category, content = _split_category(message)
                    scenario = categories.setdefault(category, {}).setdefault(
                        scenario_name,
                        {"__duration__": {"value": [duration]}},
                    )
                    scenario.setdefault(section, {}).setdefault(client_id, []).append(content)
    return categories


def _split_category(message: str) -> tuple[str, str]:
    content = re.sub(r"^(Motivo|Informação|Detalhe):\s*", "", message).strip()
    match = re.match(r"^\[([^\]]+)\]\s*(.*)$", content, flags=re.DOTALL)
    if match is None:
        return "Geral", content
    return match.group(1), match.group(2)


def _render_page(
    title: str,
    environment: str,
    duration: str,
    categories: dict[str, dict[str, dict[str, dict[str, list[str]]]]],
    scenario_count: int,
) -> str:
    totals = {section: 0 for section in _SECTIONS}
    for scenarios in categories.values():
        for scenario in scenarios.values():
            for section in _SECTIONS:
                totals[section] += len(scenario.get(section, {}))

    categories_html = "".join(
        _render_category(category, scenarios)
        for category, scenarios in sorted(categories.items(), key=lambda item: item[0].casefold())
    ) or '<p class="empty">Nenhum resultado foi registrado.</p>'
    generated_at = datetime.now().strftime("%d/%m/%Y %H:%M")
    metrics = "".join(
        f'<div class="metric {tone}"><span>{label}</span><b>{totals[section]}</b></div>'
        for section, (label, tone) in _STATUS.items()
    )
    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title><style>
:root{{--ink:#17202a;--muted:#64717d;--line:#dfe5ea;--canvas:#eef2f5;--paper:#fff;--navy:#18324a;--red:#b42318;--red-bg:#fff1f0;--amber:#9a6700;--amber-bg:#fff8e6;--green:#16734a;--green-bg:#edf9f2}}*{{box-sizing:border-box}}body{{margin:0;background:var(--canvas);color:var(--ink);font:14px/1.5 Arial,sans-serif}}main{{max-width:1180px;margin:auto;padding:30px 20px 48px}}header{{background:var(--navy);color:#fff;border-radius:10px;padding:28px 32px}}header small{{letter-spacing:1.3px;color:#b9c9d7;font-weight:bold}}h1{{margin:7px 0;font-size:28px}}header p{{margin:0;color:#d7e2eb}}.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:20px 0}}.metric{{background:var(--paper);border:1px solid var(--line);border-top:4px solid;border-radius:8px;padding:15px}}.metric span{{color:var(--muted);font-size:12px;font-weight:bold;text-transform:uppercase}}.metric b{{display:block;font-size:28px}}.metric.fail{{border-top-color:var(--red)}}.metric.info{{border-top-color:var(--amber)}}.metric.pass{{border-top-color:var(--green)}}.metric.fail b{{color:var(--red)}}.metric.info b{{color:var(--amber)}}.metric.pass b{{color:var(--green)}}details{{background:var(--paper)}}details summary{{cursor:pointer;list-style:none}}details summary::-webkit-details-marker{{display:none}}details summary::before{{content:'▸';display:inline-block;color:var(--muted);margin-right:8px}}details[open]>summary::before{{transform:rotate(90deg)}}.category{{border:1px solid var(--line);border-radius:9px;margin:16px 0;padding:18px}}.category>summary{{font-size:18px;font-weight:bold}}.scenario{{border:1px solid var(--line);border-radius:7px;margin:13px 0 0;padding:14px;background:#fafcfd}}.scenario>summary{{font-weight:bold;font-size:15px}}.duration{{color:var(--muted);font-weight:normal}}.status{{border:1px solid var(--line);border-left:4px solid;border-radius:6px;margin:10px 0 0;padding:11px}}.status.fail{{border-left-color:var(--red);background:var(--red-bg)}}.status.info{{border-left-color:var(--amber);background:var(--amber-bg)}}.status.pass{{border-left-color:var(--green);background:var(--green-bg)}}.client{{background:rgba(255,255,255,.55);border:1px solid var(--line);border-radius:5px;margin:8px 0 0;padding:9px 11px}}.client summary{{font-weight:bold}}ul{{margin:7px 0 0;padding-left:20px}}.empty{{color:var(--muted);font-style:italic}}footer{{color:var(--muted);font-size:12px;text-align:right;margin-top:20px}}@media(max-width:700px){{main{{padding:18px 12px 32px}}header{{padding:24px}}h1{{font-size:23px}}.grid{{grid-template-columns:repeat(2,1fr)}}}}
</style></head><body><main><header><small>RELATÓRIO DE VALIDAÇÃO</small><h1>{escape(title)}</h1><p>Ambiente: <strong>{escape(environment)}</strong> · Cenários: <strong>{scenario_count}</strong> · Duração geral: <strong>{escape(duration)}</strong></p></header><section class="grid">{metrics}<div class="metric"><span>Cenários</span><b>{scenario_count}</b></div></section><section><h2>Resultados por tipo de validação</h2>{categories_html}</section><footer>Gerado em {generated_at}</footer></main></body></html>"""


def _render_category(
    category: str,
    scenarios: dict[str, dict[str, dict[str, list[str]]]],
) -> str:
    scenario_html = "".join(
        _render_scenario(name, content)
        for name, content in sorted(scenarios.items(), key=lambda item: item[0].casefold())
    )
    return f'<details class="category" open><summary>{escape(category)} · {len(scenarios)} cenário(s)</summary>{scenario_html}</details>'


def _render_scenario(name: str, content: dict[str, dict[str, list[str]]]) -> str:
    duration = content.get("__duration__", {}).get("value", ["00:00:00"])[0]
    statuses = "".join(
        _render_status(section, content.get(section, {})) for section in _SECTIONS
    )
    return f'<details class="scenario"><summary>{escape(name)} <span class="duration">· {escape(duration)}</span></summary>{statuses}</details>'


def _render_status(section: str, clients: dict[str, list[str]]) -> str:
    label, tone = _STATUS[section]
    if not clients:
        body = '<p class="empty">Nenhum cliente nesta etapa.</p>'
    else:
        body = "".join(
            f'<details class="client"><summary>{escape(client)}</summary><ul>'
            + "".join(f"<li>{escape(message)}</li>" for message in messages)
            + "</ul></details>"
            for client, messages in sorted(clients.items(), key=lambda item: item[0].casefold())
        )
    return f'<details class="status {tone}"><summary>{label} ({len(clients)} cliente(s))</summary>{body}</details>'
