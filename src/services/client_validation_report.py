from __future__ import annotations

from html import escape
import ast
import logging
import os
from pathlib import Path
from datetime import datetime, timedelta
from time import perf_counter


class _ClientReportLogHandler(logging.Handler):
    def __init__(self, records: list[str]) -> None:
        super().__init__(level=logging.INFO)
        self._records = records

    def emit(self, record: logging.LogRecord) -> None:
        self._records.append(self.format(record))


class ClientValidationReport:
    """Coleta falhas por cliente e gera um relatório textual curado."""

    def __init__(self, elapsed_seconds: float | None = None) -> None:
        self._results: dict[str, dict[str, list[str]]] = {}
        self._started_at = perf_counter()
        self._elapsed_seconds = elapsed_seconds
        self._log_records: list[str] = []
        self._log_cursor = 0
        self._log_handler = _ClientReportLogHandler(self._log_records)
        logging.getLogger().addHandler(self._log_handler)

    def close(self) -> None:
        logging.getLogger().removeHandler(self._log_handler)

    def add_client_result(
        self,
        client_id: str,
        failures: list[str] | None = None,
        infos: list[str] | None = None,
        details: list[str] | None = None,
    ) -> None:
        client_logs = self._log_records[self._log_cursor:]
        self._log_cursor = len(self._log_records)
        self._results[client_id] = {
            "failures": failures or [],
            "infos": infos or [],
            "details": details or [],
            "logs": client_logs,
        }

    def failure_messages(self) -> list[str]:
        return [
            f"{client_id}: {failure}"
            for client_id, result in self._results.items()
            for failure in result["failures"]
        ]

    def assert_no_failures(self) -> None:
        failures = self.failure_messages()
        assert not failures, "\n".join(failures)

    def curate(
        self,
        test_name: str,
        bdd: str,
        environment: str | None = None,
    ) -> str:
        environment = environment or os.getenv("TEST_ENV", "hml").strip().lower()
        sections = self._sections()
        lines = [
            f"Teste: {test_name}",
            f"Ambiente: {environment}",
            f"Duração: {self._execution_duration()}",
            "",
            "BDD:",
            bdd,
            "",
        ]
        for section, label in (
            ("Falhas", "Motivo"),
            ("Informativos", "Informação"),
            ("Aprovados", "Detalhe"),
        ):
            clients = sections[section]
            lines.append(f"{section} ({len(clients)}):")
            for client_id, messages in clients:
                lines.append(f"- Cliente: {client_id}")
                lines.extend(f"  {label}: {message}" for message in messages)
            lines.append("")
        return "\n".join(lines).rstrip()

    def _execution_duration(self) -> str:
        elapsed_seconds = (
            self._elapsed_seconds
            if self._elapsed_seconds is not None
            else perf_counter() - self._started_at
        )
        return str(timedelta(seconds=int(elapsed_seconds)))

    def _sections(self) -> dict[str, list[tuple[str, list[str]]]]:
        """Mantém falhas, informações e validações aprovadas em seções distintas."""
        sections: dict[str, list[tuple[str, list[str]]]] = {
            "Falhas": [],
            "Informativos": [],
            "Aprovados": [],
        }
        for client_id, result in self._results.items():
            if result["failures"]:
                sections["Falhas"].append((client_id, result["failures"]))
            if result["infos"]:
                sections["Informativos"].append((client_id, result["infos"]))
            if result["details"]:
                sections["Aprovados"].append((client_id, result["details"]))
        return sections

    def write(
        self,
        path: str | Path,
        test_name: str,
        bdd: str,
        environment: str | None = None,
    ) -> str:
        report = self.curate(test_name, bdd, environment)
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report + "\n", encoding="utf-8")
        return report

    @classmethod
    def write_combined(
        cls,
        report_paths: list[Path],
        output_path: str | Path,
        elapsed_seconds: float | None = None,
    ) -> str:
        """Consolida os relatórios mantendo todos os clientes sob cada teste."""
        grouped_results: list[tuple[str, dict[str, list[tuple[str, list[str]]]]]] = []
        for report_path in report_paths:
            report_content = report_path.read_text(encoding="utf-8")
            test_name = next(
                (
                    line.removeprefix("Teste: ")
                    for line in report_content.splitlines()
                    if line.startswith("Teste:")
                ),
                report_path.stem,
            )
            grouped_results.append((test_name, cls._parse_sections(report_content)))

        duration = str(timedelta(seconds=int(elapsed_seconds or 0)))
        lines = [
            "Teste: Resumo geral da execução",
            f"Ambiente: {os.getenv('TEST_ENV', 'hml').strip().lower()}",
            f"Duração: {duration}",
            "",
            "BDD:",
            "Consolidado dos resultados de todos os testes executados.",
            "",
            "Resultados por teste:",
        ]
        for test_name, sections in grouped_results:
            lines.extend(("", f"Teste executado: {test_name}"))
            for section, label in (
                ("Falhas", "Motivo"),
                ("Informativos", "Informação"),
                ("Aprovados", "Detalhe"),
            ):
                clients = sections[section]
                lines.append(f"{section} ({len(clients)}):")
                for client_id, messages in clients:
                    lines.append(f"- Cliente: {client_id}")
                    lines.extend(
                        f"  {label}: {message.removeprefix(f'{label}: ')}"
                        for message in messages
                    )

        content = "\n".join(lines).rstrip()
        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content + "\n", encoding="utf-8")
        cls.write_html_from_text(Path(output_path), Path(output_path).with_suffix(".html"))
        return content

    @staticmethod
    def allure_title_from_source(source_path: str | Path, function_name: str) -> str:
        tree = ast.parse(Path(source_path).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name != function_name:
                continue
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call):
                    continue
                if not isinstance(decorator.func, ast.Attribute):
                    continue
                if decorator.func.attr != "title" or not decorator.args:
                    continue
                title = ast.literal_eval(decorator.args[0])
                if isinstance(title, str):
                    return title
        return function_name

    @staticmethod
    def bdd_from_test_name(
        test_name: str,
        gherkin_root: str | Path = "tests/gherkins",
    ) -> str:
        root_path = Path(gherkin_root)
        feature_paths = list(root_path.rglob(f"{test_name}.feature"))
        if not feature_paths:
            return "BDD não encontrado."
        feature_path = feature_paths[0]
        return feature_path.read_text(encoding="utf-8").strip()

    @staticmethod
    def _parse_sections(report: str) -> dict[str, list[tuple[str, list[str]]]]:
        sections: dict[str, list[tuple[str, list[str]]]] = {
            "Falhas": [],
            "Informativos": [],
            "Aprovados": [],
        }
        current: str | None = None
        for line in report.splitlines():
            if line.startswith("Falhas ("):
                current = "Falhas"
            elif line.startswith("Informativos ("):
                current = "Informativos"
            elif line.startswith("Aprovados ("):
                current = "Aprovados"
            elif current and line.startswith("- Cliente: "):
                sections[current].append((line.removeprefix("- Cliente: "), []))
            elif current and sections[current] and line.startswith("  "):
                sections[current][-1][1].append(line.strip())
        return sections

    @staticmethod
    def write_html_from_text(
        report_path: str | Path,
        html_path: str | Path,
    ) -> str:
        """Gera uma versão visual do relatório TXT para revisão e email."""
        source_path = Path(report_path)
        report = source_path.read_text(encoding="utf-8")
        lines = report.splitlines()
        test_name = next(
            (line.removeprefix("Teste: ").strip() for line in lines if line.startswith("Teste:")),
            "Relatório de validação",
        )
        environment = next(
            (
                line.removeprefix("Ambiente: ").strip()
                for line in lines
                if line.startswith("Ambiente:")
            ),
            os.getenv("TEST_ENV", "hml").strip().lower(),
        )
        duration = next(
            (
                line.removeprefix("Duração: ").strip()
                for line in lines
                if line.startswith("Duração:")
            ),
            "00:00:00",
        )
        bdd_start = lines.index("BDD:") + 1 if "BDD:" in lines else 0
        bdd_lines: list[str] = []
        for line in lines[bdd_start:]:
            if line.startswith("Falhas ("):
                break
            bdd_lines.append(line)

        if "Resultados por teste:" in lines:
            html = ClientValidationReport._combined_html_from_text(
                test_name, environment, duration, report
            )
            output_path = Path(html_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(html, encoding="utf-8")
            return html

        sections: dict[str, list[tuple[str, list[str]]]] = {
            "Falhas": [],
            "Informativos": [],
            "Aprovados": [],
        }
        current_section: str | None = None
        current_client: str | None = None
        for line in lines:
            if line.startswith("Falhas ("):
                current_section = "Falhas"
            elif line.startswith("Informativos ("):
                current_section = "Informativos"
            elif line.startswith("Aprovados ("):
                current_section = "Aprovados"
            elif current_section and line.startswith("- Cliente: "):
                current_client = line.removeprefix("- Cliente: ").strip()
                sections[current_section].append((current_client, []))
            elif current_section and current_client and line.startswith("  "):
                sections[current_section][-1][1].append(line.strip())

        counts = {name: len(items) for name, items in sections.items()}

        def render_clients(section_name: str, tone: str, empty_text: str) -> str:
            clients = sections[section_name]
            if not clients:
                return f'<div class="empty">{escape(empty_text)}</div>'
            cards = []
            for client, reasons in clients:
                reason_html = "".join(
                    f"<li>{escape(reason.removeprefix('Motivo: ').removeprefix('Informação: '))}</li>"
                    for reason in reasons
                )
                details = f"<ul>{reason_html}</ul>" if reason_html else ""
                cards.append(
                    f'<details class="client-card {tone}">'
                    f'<summary class="client-name">{escape(client)}</summary>{details}</details>'
                )
            return "".join(cards)

        generated_at = datetime.now().strftime("%d/%m/%Y %H:%M")
        html = f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(test_name)}</title>
  <style>
    :root {{
      --ink: #17202a; --muted: #64717d; --line: #dfe5ea;
      --paper: #ffffff; --canvas: #eef2f5; --navy: #18324a;
      --red: #b42318; --red-bg: #fff1f0; --amber: #9a6700;
      --amber-bg: #fff8e6; --green: #16734a; --green-bg: #edf9f2;
    }}
    * {{ box-sizing: border-box; }}
    body {{ background: var(--canvas); color: var(--ink); font: 14px/1.5 Arial, sans-serif; margin: 0; }}
    .shell {{ margin: 0 auto; max-width: 1180px; padding: 34px 22px 48px; }}
    .hero {{ background: var(--navy); border-radius: 10px; color: white; padding: 30px 34px; }}
    .eyebrow {{ color: #b9c9d7; font-size: 11px; font-weight: bold; letter-spacing: 1.5px; text-transform: uppercase; }}
    h1 {{ font-size: 28px; line-height: 1.2; margin: 8px 0 10px; }}
    .meta {{ color: #d7e2eb; margin: 0; }}
    .summary {{ display: grid; gap: 14px; grid-template-columns: repeat(3, 1fr); margin: 20px 0; }}
    .metric, .panel {{ background: var(--paper); border: 1px solid var(--line); border-radius: 8px; }}
    .metric {{ padding: 18px 20px; }}
    .metric-label {{ color: var(--muted); font-size: 12px; font-weight: bold; text-transform: uppercase; }}
    .metric-value {{ font-size: 30px; font-weight: bold; margin-top: 2px; }}
    .metric.fail {{ border-top: 4px solid var(--red); }} .metric.info {{ border-top: 4px solid var(--amber); }} .metric.pass {{ border-top: 4px solid var(--green); }}
    .metric.fail .metric-value {{ color: var(--red); }} .metric.info .metric-value {{ color: var(--amber); }} .metric.pass .metric-value {{ color: var(--green); }}
    .panel {{ margin-top: 18px; padding: 22px; }}
    h2 {{ font-size: 18px; margin: 0 0 14px; }}
    .bdd {{ background: #f7f9fb; border-left: 4px solid #7591a7; color: #34495a; padding: 15px 18px; white-space: pre-line; }}
    .section-title {{ align-items: center; display: flex; gap: 10px; margin-bottom: 14px; }}
    details > summary {{ cursor: pointer; list-style: none; }}
    details > summary::-webkit-details-marker {{ display: none; }}
    details > summary::before {{ color: var(--muted); content: "▸"; display: inline-block; margin-right: 8px; transition: transform .15s ease; }}
    details[open] > summary::before {{ transform: rotate(90deg); }}
    .section-title h2 {{ margin: 0; }}
    .badge {{ border-radius: 999px; font-size: 12px; font-weight: bold; padding: 3px 9px; }}
    .badge.fail {{ background: var(--red-bg); color: var(--red); }} .badge.info {{ background: var(--amber-bg); color: var(--amber); }} .badge.pass {{ background: var(--green-bg); color: var(--green); }}
    .client-list {{ display: grid; gap: 10px; }}
    .client-card {{ border: 1px solid var(--line); border-left: 4px solid; border-radius: 6px; padding: 13px 16px; }}
    .client-card.fail {{ background: var(--red-bg); border-left-color: var(--red); }}
    .client-card.info {{ background: var(--amber-bg); border-left-color: var(--amber); }}
    .client-card.pass {{ background: var(--green-bg); border-left-color: var(--green); }}
    .client-name {{ font-size: 15px; font-weight: bold; }}
    .client-card ul {{ margin-bottom: 0; }}
    ul {{ color: #4b5863; margin: 7px 0 0; padding-left: 20px; }}
    .empty {{ color: var(--muted); font-style: italic; }}
    footer {{ color: var(--muted); font-size: 12px; margin-top: 20px; text-align: right; }}
    @media (max-width: 700px) {{ .shell {{ padding: 18px 12px 32px; }} .hero {{ padding: 24px; }} h1 {{ font-size: 23px; }} .summary {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body><main class="shell">
  <header class="hero">
    <div class="eyebrow">Relatório de validação por cliente</div>
    <h1>{escape(test_name)}</h1>
    <p class="meta">Ambiente: <strong>{escape(environment)}</strong> · Gerado em {generated_at} · Duração: <strong>{escape(duration)}</strong></p>
  </header>
  <section class="summary">
    <div class="metric fail"><div class="metric-label">Falhas</div><div class="metric-value">{counts['Falhas']}</div></div>
    <div class="metric info"><div class="metric-label">Informativos</div><div class="metric-value">{counts['Informativos']}</div></div>
    <div class="metric pass"><div class="metric-label">Aprovados</div><div class="metric-value">{counts['Aprovados']}</div></div>
  </section>
    <details class="panel"><summary class="section-title"><h2>BDD executado</h2></summary><div class="bdd">{escape(chr(10).join(bdd_lines))}</div></details>
    <details class="panel"><summary class="section-title"><h2>Falhas</h2><span class="badge fail">{counts['Falhas']}</span></summary><div class="client-list">{render_clients('Falhas', 'fail', 'Nenhuma falha registrada.')}</div></details>
    <details class="panel"><summary class="section-title"><h2>Informativos</h2><span class="badge info">{counts['Informativos']}</span></summary><div class="client-list">{render_clients('Informativos', 'info', 'Nenhum registro informativo.')}</div></details>
    <details class="panel"><summary class="section-title"><h2>Aprovados</h2><span class="badge pass">{counts['Aprovados']}</span></summary><div class="client-list">{render_clients('Aprovados', 'pass', 'Nenhum cliente aprovado.')}</div></details>
  <footer>Fonte: relatório TXT gerado pela execução dos testes.</footer>
</main></body>
</html>
"""
        output_path = Path(html_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")
        return html

    @staticmethod
    def _combined_html_from_text(
        title: str,
        environment: str,
        duration: str,
        report: str,
    ) -> str:
        """Renderiza o consolidado agrupando os clientes no respectivo teste."""
        groups: list[tuple[str, dict[str, list[tuple[str, list[str]]]]]] = []
        current_group: dict[str, list[tuple[str, list[str]]]] | None = None
        current_section: str | None = None
        for line in report.splitlines():
            if line.startswith("Teste executado: "):
                current_group = {"Falhas": [], "Informativos": [], "Aprovados": []}
                groups.append((line.removeprefix("Teste executado: "), current_group))
            elif current_group and line.startswith("Falhas ("):
                current_section = "Falhas"
            elif current_group and line.startswith("Informativos ("):
                current_section = "Informativos"
            elif current_group and line.startswith("Aprovados ("):
                current_section = "Aprovados"
            elif current_group and current_section and line.startswith("- Cliente: "):
                current_group[current_section].append(
                    (line.removeprefix("- Cliente: "), [])
                )
            elif (
                current_group
                and current_section
                and current_group[current_section]
                and line.startswith("  ")
            ):
                current_group[current_section][-1][1].append(line.strip())

        tones = {
            "Falhas": ("#b42318", "#fff1f0"),
            "Informativos": ("#9a6700", "#fff8e6"),
            "Aprovados": ("#16734a", "#edf9f2"),
        }
        totals = {
            section: sum(len(sections[section]) for _, sections in groups)
            for section in tones
        }

        def render_clients(section: str, clients: list[tuple[str, list[str]]]) -> str:
            color, background = tones[section]
            if not clients:
                return '<p class="empty">Nenhum registro.</p>'
            return "".join(
                f'<details class="client" style="border-left-color:{color};background:{background}">'
                f'<summary>{escape(client_id)}</summary><ul>'
                + "".join(f"<li>{escape(message)}</li>" for message in messages)
                + "</ul></details>"
                for client_id, messages in clients
            )

        tests_html = "".join(
            f'<section class="test"><h2>{escape(test_name)}</h2>'
            + "".join(
                f'<section class="status"><h3>{section} ({len(sections[section])})</h3>'
                f'{render_clients(section, sections[section])}</section>'
                for section in tones
            )
            + "</section>"
            for test_name, sections in groups
        )
        metrics = "".join(
            f'<div class="metric" style="border-top-color:{color}">{section}'
            f'<b style="color:{color}">{totals[section]}</b></div>'
            for section, (color, _) in tones.items()
        )
        return f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>{escape(title)}</title><style>
body{{margin:0;background:#eef2f5;color:#17202a;font:14px/1.5 Arial,sans-serif}}main{{max-width:1080px;margin:auto;padding:30px 20px}}header{{background:#18324a;color:#fff;border-radius:10px;padding:28px 32px}}header p{{color:#d7e2eb;margin:0}}h1{{margin:7px 0;font-size:28px}}h2{{margin:0 0 18px}}h3{{font-size:15px;margin:0 0 9px}}.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:20px 0}}.metric,.test,.status{{background:#fff;border:1px solid #dfe5ea;border-radius:8px}}.metric{{padding:16px;border-top:4px solid;font-weight:bold}}.metric b{{display:block;font-size:30px}}.test{{padding:22px;margin-top:18px}}.status{{padding:14px;margin-top:12px}}.client{{border:1px solid #dfe5ea;border-left:4px solid;border-radius:6px;margin:8px 0;padding:10px 12px}}details summary{{cursor:pointer;font-weight:bold}}ul{{margin:8px 0 0;padding-left:20px}}.empty{{color:#64717d;font-style:italic}}@media(max-width:700px){{.grid{{grid-template-columns:1fr}}}}</style></head><body><main><header><small>RELATÓRIO GERAL DE VALIDAÇÃO</small><h1>{escape(title)}</h1><p>Ambiente: {escape(environment)} · Duração: {escape(duration)}</p></header><section class="grid">{metrics}</section>{tests_html}</main></body></html>'''

    @staticmethod
    def email_summary_html_from_text(report_path: str | Path) -> str:
        """Gera um resumo compacto para o e-mail; o relatório completo segue anexo."""
        report = Path(report_path).read_text(encoding="utf-8")
        lines = report.splitlines()
        title = next(
            (line.removeprefix("Teste: ").strip() for line in lines if line.startswith("Teste:")),
            "Relatório de validação",
        )
        environment = next(
            (line.removeprefix("Ambiente: ").strip() for line in lines if line.startswith("Ambiente:")),
            "hml",
        )
        duration = next(
            (line.removeprefix("Duração: ").strip() for line in lines if line.startswith("Duração:")),
            "00:00:00",
        )
        sections = ClientValidationReport._parse_sections(report)
        metrics = "".join(
            f'<td style="padding:12px;border-top:4px solid {color};background:{background};">'
            f'<strong>{name}</strong><br><span style="font-size:24px;">{len(sections[name])}</span></td>'
            for name, color, background in (
                ("Falhas", "#b42318", "#fff1f0"),
                ("Informativos", "#9a6700", "#fff8e6"),
                ("Aprovados", "#16734a", "#edf9f2"),
            )
        )
        return f"""<!doctype html><html lang="pt-BR"><body style="margin:0;padding:24px;background:#eef2f5;font-family:Arial,sans-serif;color:#17202a;">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:760px;margin:auto;background:#ffffff;"><tr><td style="padding:28px 30px;background:#18324a;color:#ffffff;"><h1 style="margin:0 0 10px;font-size:24px;">{escape(title)}</h1><p style="margin:0;color:#d7e2eb;">Ambiente: {escape(environment)} &middot; Duração: {escape(duration)}</p></td></tr><tr><td style="padding:20px 22px;"><p style="margin-top:0;">Resumo da execução. O relatório HTML completo está anexado a este e-mail.</p><table role="presentation" width="100%" cellspacing="8" cellpadding="0"><tr>{metrics}</tr></table></td></tr></table>
</body></html>"""

    @staticmethod
    def email_html_from_text(report_path: str | Path) -> str:
        """Gera HTML compatível com clientes de e-mail a partir do relatório TXT."""
        report = Path(report_path).read_text(encoding="utf-8")
        lines = report.splitlines()
        test_name = next(
            (line.removeprefix("Teste: ").strip() for line in lines if line.startswith("Teste:")),
            "Relatório de validação",
        )
        environment = next(
            (
                line.removeprefix("Ambiente: ").strip()
                for line in lines
                if line.startswith("Ambiente:")
            ),
            os.getenv("TEST_ENV", "hml").strip().lower(),
        )
        duration = next(
            (
                line.removeprefix("Duração: ").strip()
                for line in lines
                if line.startswith("Duração:")
            ),
            "00:00:00",
        )
        bdd_start = lines.index("BDD:") + 1 if "BDD:" in lines else None
        bdd_lines: list[str] = []
        if bdd_start is not None:
            for line in lines[bdd_start:]:
                if line.startswith("Falhas ("):
                    break
                bdd_lines.append(line)
        bdd_html = "<br>".join(escape(line) for line in bdd_lines) or "BDD não encontrado."

        sections: dict[str, list[tuple[str, list[str]]]] = {
            "Falhas": [],
            "Informativos": [],
            "Aprovados": [],
        }
        current_section: str | None = None
        for line in lines:
            if line.startswith("Falhas ("):
                current_section = "Falhas"
            elif line.startswith("Informativos ("):
                current_section = "Informativos"
            elif line.startswith("Aprovados ("):
                current_section = "Aprovados"
            elif current_section and line.startswith("- Cliente: "):
                sections[current_section].append(
                    (line.removeprefix("- Cliente: ").strip(), [])
                )
            elif current_section and sections[current_section] and line.startswith("  "):
                sections[current_section][-1][1].append(line.strip())

        def render_section(name: str, color: str, background: str) -> str:
            clients = sections[name]
            rows = []
            for client, details in clients:
                detail_html = "".join(
                    f'<li style="margin:4px 0;">{escape(detail)}</li>'
                    for detail in details
                ) or '<li style="margin:4px 0;">Sem detalhes adicionais.</li>'
                rows.append(
                    f'<tr><td style="padding:14px 16px;border:1px solid #dfe5ea;'
                    f'border-left:4px solid {color};background:{background};">'
                    f'<strong>{escape(client)}</strong><ul style="margin:8px 0 0;padding-left:20px;">'
                    f'{detail_html}</ul></td></tr>'
                )
            content = "".join(rows) or (
                '<tr><td style="padding:14px 16px;border:1px solid #dfe5ea;color:#64717d;">'
                'Nenhum registro.</td></tr>'
            )
            return (
                f'<details style="margin-top:26px;">'
                f'<summary style="cursor:pointer;font:700 18px Arial,sans-serif;color:#17202a;">'
                f'{name} ({len(clients)})</summary>'
                f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" '
                f'style="border-collapse:collapse;margin-top:10px;">{content}</table>'
                '</details>'
            )

        metrics = (
            ("Falhas", "#b42318", "#fff1f0"),
            ("Informativos", "#9a6700", "#fff8e6"),
            ("Aprovados", "#16734a", "#edf9f2"),
        )
        metric_cells = "".join(
            f'<td width="33%" style="padding:14px 12px;border-top:4px solid {color};'
            f'background:{background};font-family:Arial,sans-serif;">'
            f'<div style="font-size:12px;font-weight:bold;color:#64717d;text-transform:uppercase;">{name}</div>'
            f'<div style="font-size:30px;font-weight:bold;color:{color};margin-top:4px;">'
            f'{len(sections[name])}</div></td>'
            for name, color, background in metrics
        )
        generated_at = datetime.now().strftime("%d/%m/%Y %H:%M")
        return f"""<!doctype html>
<html lang="pt-BR"><body style="margin:0;padding:0;background:#eef2f5;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#eef2f5;"><tr><td style="padding:24px 12px;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:760px;margin:0 auto;background:#ffffff;">
      <tr><td style="padding:28px 30px;background:#18324a;font-family:Arial,sans-serif;color:#ffffff;">
        <div style="font-size:11px;font-weight:bold;letter-spacing:1px;text-transform:uppercase;color:#b9c9d7;">Relatório de validação por cliente</div>
        <h1 style="font-size:27px;line-height:1.2;margin:9px 0 10px;color:#ffffff;">{escape(test_name)}</h1>
        <p style="margin:0;color:#d7e2eb;">Ambiente: <strong>{escape(environment)}</strong> &middot; Gerado em {generated_at} &middot; Duração: <strong>{escape(duration)}</strong></p>
      </td></tr>
      <tr><td style="padding:20px 22px;">
        <table role="presentation" width="100%" cellspacing="8" cellpadding="0"><tr>{metric_cells}</tr></table>
        <h2 style="font:700 18px Arial,sans-serif;color:#17202a;margin:26px 0 10px;">BDD executado</h2>
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;"><tr>
          <td style="padding:14px 16px;border:1px solid #dfe5ea;border-left:4px solid #7591a7;background:#f7f9fb;font:14px/1.5 Arial,sans-serif;color:#34495a;">{bdd_html}</td>
        </tr></table>
        {render_section("Falhas", "#b42318", "#fff1f0")}
        {render_section("Informativos", "#9a6700", "#fff8e6")}
        {render_section("Aprovados", "#16734a", "#edf9f2")}
      </td></tr>
    </table>
  </td></tr></table>
</body></html>"""
