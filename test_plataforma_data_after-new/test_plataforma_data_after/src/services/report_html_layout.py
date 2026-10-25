from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from html import escape
from pathlib import Path
import re


SECTIONS = ("Falhas", "Informativos", "Aprovados")
TONES = {"Falhas": "fail", "Informativos": "info", "Aprovados": "pass"}


def render_html_from_text(report_path: str | Path) -> str:
    report = Path(report_path).read_text(encoding="utf-8")
    lines = report.splitlines()
    title = _value(lines, "Teste:", "Relatório de validação")
    environment = _value(lines, "Ambiente:", "hml")
    duration = _value(lines, "Duração:", "00:00:00")
    scenarios = _scenarios(lines, "Resultados por teste:" in report, title, duration)
    categories = _categories(scenarios)
    return _page(title, environment, duration, scenarios, categories)


def _value(lines: list[str], prefix: str, default: str) -> str:
    return next((line.removeprefix(prefix).strip() for line in lines if line.startswith(prefix)), default)


def _scenarios(lines, combined, title, duration):
    if not combined:
        return [(title, duration, _sections(lines))]
    result, name, scenario_duration, buffer = [], None, "00:00:00", []
    for line in lines:
        if line.startswith("Teste executado: "):
            if name is not None:
                result.append((name, scenario_duration, _sections(buffer)))
            name, scenario_duration, buffer = line.removeprefix("Teste executado: ").strip(), "00:00:00", []
        elif name is not None and line.startswith("Duração do cenário:"):
            scenario_duration = line.removeprefix("Duração do cenário:").strip()
        elif name is not None:
            buffer.append(line)
    if name is not None:
        result.append((name, scenario_duration, _sections(buffer)))
    return result


def _sections(lines):
    result = {section: [] for section in SECTIONS}
    current = None
    for line in lines:
        matched = next((section for section in SECTIONS if line.startswith(f"{section} (")), None)
        if matched:
            current = matched
        elif current and line.startswith("- Cliente: "):
            result[current].append((line.removeprefix("- Cliente: ").strip(), []))
        elif current and result[current] and line.startswith("  "):
            result[current][-1][1].append(line.strip())
    return result


def _categories(scenarios):
    result = defaultdict(
        lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    )
    for scenario, duration, sections in scenarios:
        result["__duration__"][scenario]["value"]["value"] = [duration]
        for status, clients in sections.items():
            for client, messages in clients:
                for message in messages:
                    category, detail = _category(message)
                    result[category][scenario][status][client].append(detail)
    return result


def _category(message):
    message = re.sub(r"^(Motivo|Informação|Detalhe):\s*", "", message).strip()
    match = re.match(r"^\[([^\]]+)\]\s*(.*)$", message, re.DOTALL)
    return (match.group(1), match.group(2)) if match else ("Geral", message)


def _page(title, environment, duration, scenarios, categories):
    totals = {section: 0 for section in SECTIONS}
    for category, tests in categories.items():
        if category == "__duration__":
            continue
        for test in tests.values():
            for section in SECTIONS:
                totals[section] += len(test.get(section, {}))
    content = "".join(_render_category(category, tests, categories) for category, tests in sorted(categories.items()) if category != "__duration__")
    metrics = "".join(f'<div class="metric {TONES[s]}">{s}<b>{totals[s]}</b></div>' for s in SECTIONS)
    return f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>{escape(title)}</title><style>
body{{margin:0;background:#eef2f5;color:#17202a;font:14px Arial,sans-serif}}main{{max-width:1180px;margin:auto;padding:30px 20px}}header{{background:#18324a;color:#fff;border-radius:10px;padding:28px}}header p{{color:#d7e2eb}}h1{{margin:6px 0}}.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:20px 0}}.metric,.category,.scenario,.status,.client{{background:#fff;border:1px solid #dfe5ea;border-radius:8px}}.metric{{padding:14px;border-top:4px solid #7591a7;font-weight:bold}}.metric b{{display:block;font-size:28px}}.metric.fail{{border-top-color:#b42318}}.metric.info{{border-top-color:#9a6700}}.metric.pass{{border-top-color:#16734a}}details{{margin-top:12px;padding:14px}}summary{{cursor:pointer;font-weight:bold;list-style:none}}summary::before{{content:'▸';margin-right:8px;color:#64717d}}details[open]>summary::before{{display:inline-block;transform:rotate(90deg)}}.category>summary{{font-size:18px}}.scenario{{background:#fafcfd}}.status.fail{{border-left:4px solid #b42318;background:#fff1f0}}.status.info{{border-left:4px solid #9a6700;background:#fff8e6}}.status.pass{{border-left:4px solid #16734a;background:#edf9f2}}.client{{background:rgba(255,255,255,.6)}}ul{{margin:8px 0 0;padding-left:20px}}.muted{{color:#64717d;font-weight:normal}}@media(max-width:700px){{.grid{{grid-template-columns:repeat(2,1fr)}}}}</style></head><body><main><header><small>RELATÓRIO DE VALIDAÇÃO</small><h1>{escape(title)}</h1><p>Ambiente: <b>{escape(environment)}</b> · Cenários: <b>{len(scenarios)}</b> · Duração geral: <b>{escape(duration)}</b></p></header><section class="grid">{metrics}<div class="metric">Cenários<b>{len(scenarios)}</b></div></section><h2>Resultados por tipo de validação</h2>{content}</main></body></html>'''


def _render_category(category, tests, all_categories):
    scenarios = "".join(_render_scenario(name, values, all_categories) for name, values in sorted(tests.items()))
    return f'<details class="category" open><summary>{escape(category)} · {len(tests)} cenário(s)</summary>{scenarios}</details>'


def _render_scenario(name, values, all_categories):
    duration = all_categories["__duration__"][name]["value"]["value"][0]
    statuses = "".join(_render_status(section, values.get(section, {})) for section in SECTIONS)
    return f'<details class="scenario"><summary>{escape(name)} <span class="muted">· {escape(duration)}</span></summary>{statuses}</details>'


def _render_status(section, clients):
    cards = "".join(f'<details class="client"><summary>{escape(client)}</summary><ul>' + "".join(f'<li>{escape(item)}</li>' for item in details) + '</ul></details>' for client, details in sorted(clients.items()))
    return f'<details class="status {TONES[section]}"><summary>{section} ({len(clients)} cliente(s))</summary>{cards or "<p>Nenhum cliente nesta etapa.</p>"}</details>'
