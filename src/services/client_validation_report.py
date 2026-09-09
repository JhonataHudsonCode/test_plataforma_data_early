from __future__ import annotations

from html import escape
import ast
import logging
import os
from pathlib import Path
from datetime import datetime


class _ClientReportLogHandler(logging.Handler):
    def __init__(self, records: list[str]) -> None:
        super().__init__(level=logging.INFO)
        self._records = records

    def emit(self, record: logging.LogRecord) -> None:
        self._records.append(self.format(record))


class ClientValidationReport:
    """Coleta falhas por cliente e gera um relatório textual curado."""

    def __init__(self) -> None:
        self._results: dict[str, dict[str, list[str]]] = {}
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
    ) -> None:
        client_logs = self._log_records[self._log_cursor:]
        self._log_cursor = len(self._log_records)
        self._results[client_id] = {
            "failures": failures or [],
            "infos": infos or [],
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
        failed = [
            client
            for client, result in self._results.items()
            if result["failures"]
        ]
        infos = [
            client
            for client, result in self._results.items()
            if result["infos"] and not result["failures"]
        ]
        passed = [
            client
            for client, result in self._results.items()
            if not result["failures"] and not result["infos"]
        ]
        lines = [
            f"Teste: {test_name}",
            f"Ambiente: {environment}",
            "",
            "BDD:",
            bdd,
            "",
        ]
        lines.extend([f"Falhas ({len(failed)}):"])
        for client in failed:
            lines.append(f"- Cliente: {client}")
            lines.extend(
                f"  Log: {log}"
                for log in self._results[client]["logs"]
            )
            lines.extend(
                f"  Motivo: {failure}"
                for failure in self._results[client]["failures"]
            )
        lines.extend(["", f"Informativos ({len(infos)}):"])
        for client in infos:
            lines.append(f"- Cliente: {client}")
            lines.extend(
                f"  Log: {log}"
                for log in self._results[client]["logs"]
            )
            lines.extend(
                f"  Informação: {info}"
                for info in self._results[client]["infos"]
            )
        lines.extend(["", f"Aprovados ({len(passed)}):"])
        for client in passed:
            lines.append(f"- Cliente: {client}")
            lines.extend(
                f"  Log: {log}"
                for log in self._results[client]["logs"]
            )
        return "\n".join(lines)

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
        bdd_start = lines.index("BDD:") + 1 if "BDD:" in lines else 0
        bdd_lines: list[str] = []
        for line in lines[bdd_start:]:
            if line == "" and bdd_lines:
                break
            if line:
                bdd_lines.append(line)

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
    <p class="meta">Ambiente: <strong>{escape(environment)}</strong> · Gerado em {generated_at}</p>
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
                f'<h2 style="font:700 18px Arial,sans-serif;color:#17202a;margin:26px 0 10px;">'
                f'{name} ({len(clients)})</h2>'
                f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" '
                f'style="border-collapse:collapse;">{content}</table>'
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
        <p style="margin:0;color:#d7e2eb;">Ambiente: <strong>{escape(environment)}</strong> &middot; Gerado em {generated_at}</p>
      </td></tr>
      <tr><td style="padding:20px 22px;">
        <table role="presentation" width="100%" cellspacing="8" cellpadding="0"><tr>{metric_cells}</tr></table>
        {render_section("Falhas", "#b42318", "#fff1f0")}
        {render_section("Informativos", "#9a6700", "#fff8e6")}
        {render_section("Aprovados", "#16734a", "#edf9f2")}
      </td></tr>
    </table>
  </td></tr></table>
</body></html>"""
