from __future__ import annotations

import ast
import os
import re
from contextvars import ContextVar, Token
from datetime import datetime, timedelta
from time import perf_counter
from html import escape
from pathlib import Path


_CURRENT_TEST_STARTED_AT: ContextVar[float | None] = ContextVar(
    "current_validation_test_started_at",
    default=None,
)


class ClientValidationReport:
    """Agrupa resultados por cliente e gera os relatórios TXT e HTML da execução."""

    def __init__(self, elapsed_seconds: float | None = None) -> None:
        self._results: dict[str, dict[str, list[str]]] = {}
        self._started_at = _CURRENT_TEST_STARTED_AT.get() or perf_counter()
        self._elapsed_seconds = elapsed_seconds

    @staticmethod
    def start_current_test_timer() -> Token[float | None]:
        """Marca o início do teste para medir também suas validações."""
        return _CURRENT_TEST_STARTED_AT.set(perf_counter())

    @staticmethod
    def reset_current_test_timer(token: Token[float | None]) -> None:
        _CURRENT_TEST_STARTED_AT.reset(token)

    def close(self) -> None:
        """Mantém a mesma interface do relatório usado pelo projeto early."""

    def add_client_result(
        self,
        client_id: str,
        failures: list[str] | None = None,
        infos: list[str] | None = None,
        details: list[str] | None = None,
    ) -> None:
        self._results[client_id] = {
            "failures": failures or [],
            "infos": infos or [],
            "details": details or [],
        }

    def assert_no_failures(self) -> None:
        failures = [
            f"{client_id}: {failure}"
            for client_id, result in self._results.items()
            for failure in result["failures"]
        ]
        assert not failures, "\n".join(failures)

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
        """Gera um relatório único agrupando todos os clientes por teste."""
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

        duration = cls._format_duration(elapsed_seconds or 0)
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
        for title, label in (
            ("Falhas", "Motivo"),
            ("Informativos", "Informação"),
            ("Aprovados", "Detalhe"),
        ):
            clients = sections[title]
            lines.append(f"{title} ({len(clients)}):")
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
        return self._format_duration(elapsed_seconds)

    @staticmethod
    def _format_duration(elapsed_seconds: float) -> str:
        """Preserva centésimos para a duração não parecer ausente em testes rápidos."""
        return str(timedelta(seconds=round(elapsed_seconds, 2)))

    def _sections(self) -> dict[str, list[tuple[str, list[str]]]]:
        """Separa falhas, informações e sucessos sem misturar seus conteúdos.

        Um mesmo cliente pode aparecer em mais de uma seção: por exemplo, uma
        falha em um índice não deve esconder as validações aprovadas dos demais.
        """
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

    @staticmethod
    def allure_title_from_source(source_path: str | Path, function_name: str) -> str:
        tree = ast.parse(Path(source_path).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name != function_name:
                continue
            for decorator in node.decorator_list:
                if (
                    isinstance(decorator, ast.Call)
                    and isinstance(decorator.func, ast.Attribute)
                    and decorator.func.attr == "title"
                    and decorator.args
                ):
                    title = ast.literal_eval(decorator.args[0])
                    if isinstance(title, str):
                        return title
        return function_name

    @staticmethod
    def bdd_from_test_name(
        test_name: str,
        gherkin_root: str | Path = "tests/gherkins",
    ) -> str:
        feature_paths = list(Path(gherkin_root).rglob(f"{test_name}.feature"))
        return (
            feature_paths[0].read_text(encoding="utf-8").strip()
            if feature_paths
            else "BDD não encontrado."
        )

    @staticmethod
    def write_html_from_text(report_path: str | Path, html_path: str | Path) -> str:
        report = Path(report_path).read_text(encoding="utf-8")
        title = next(
            (line.removeprefix("Teste: ") for line in report.splitlines() if line.startswith("Teste:")),
            "Relatório de validação",
        )
        environment = next(
            (line.removeprefix("Ambiente: ") for line in report.splitlines() if line.startswith("Ambiente:")),
            "hml",
        )
        duration = next(
            (line.removeprefix("Duração: ") for line in report.splitlines() if line.startswith("Duração:")),
            "00:00:00",
        )
        sections = ClientValidationReport._parse_sections(report)
        bdd = ClientValidationReport._bdd_from_report(report)

        if "Resultados por teste:" in report.splitlines():
            html = ClientValidationReport._combined_html_from_text(
                title, environment, duration, report
            )
            output_path = Path(html_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(html, encoding="utf-8")
            return html

        counts = {name: len(clients) for name, clients in sections.items()}

        def cards(section: str, tone: str, empty: str) -> str:
            clients = sections[section]
            if not clients:
                return f'<p class="empty">{escape(empty)}</p>'
            return "".join(
                f'<details class="card {tone}"><summary>{escape(client_id)}</summary><ul>'
                + "".join(f"<li>{ClientValidationReport._render_message(message)}</li>" for message in messages)
                + "</ul></details>"
                for client_id, messages in clients
            )

        generated_at = datetime.now().strftime("%d/%m/%Y %H:%M")
        html = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title><style>
body{{margin:0;background:#eef2f5;color:#17202a;font:14px/1.5 Arial,sans-serif}}main{{max-width:1080px;margin:auto;padding:30px 20px}}header{{background:#18324a;color:#fff;border-radius:10px;padding:28px 32px}}header p{{color:#d7e2eb;margin:0}}h1{{margin:7px 0;font-size:28px}}.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:20px 0}}.metric,.panel{{background:#fff;border:1px solid #dfe5ea;border-radius:8px}}.metric{{padding:16px;border-top:4px solid}}.metric b{{display:block;font-size:30px}}.fail{{border-color:#b42318}}.info{{border-color:#9a6700}}.pass{{border-color:#16734a}}.panel{{padding:20px;margin-top:16px}}details summary{{cursor:pointer;font-weight:bold;font-size:16px}}.card{{border:1px solid #dfe5ea;border-left:4px solid;border-radius:6px;margin:10px 0;padding:12px 14px}}.empty{{color:#64717d;font-style:italic}}pre{{white-space:pre-wrap;background:#f7f9fb;border-left:4px solid #7591a7;padding:14px}}@media(max-width:700px){{.grid{{grid-template-columns:1fr}}}}
</style></head><body><main><header><small>RELATÓRIO DE VALIDAÇÃO POR CLIENTE</small><h1>{escape(title)}</h1><p>Ambiente: {escape(environment)} · Gerado em {generated_at} · Duração: {escape(duration)}</p></header>
<section class="grid"><div class="metric fail">FALHAS<b>{counts['Falhas']}</b></div><div class="metric info">INFORMATIVOS<b>{counts['Informativos']}</b></div><div class="metric pass">APROVADOS<b>{counts['Aprovados']}</b></div></section>
<section class="panel"><h2>BDD executado</h2><pre>{escape(bdd)}</pre></section>
<details class="panel section"><summary>Falhas ({counts['Falhas']})</summary>{cards('Falhas', 'fail', 'Nenhuma falha registrada.')}</details>
<details class="panel section"><summary>Informativos ({counts['Informativos']})</summary>{cards('Informativos', 'info', 'Nenhum registro informativo.')}</details>
<details class="panel section"><summary>Aprovados ({counts['Aprovados']})</summary>{cards('Aprovados', 'pass', 'Nenhum cliente aprovado.')}</details>
</main></body></html>"""
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
                + "".join(
                    f"<li>{ClientValidationReport._render_message(message)}</li>"
                    for message in messages
                )
                + "</ul></details>"
                for client_id, messages in clients
            )

        tests_html = "".join(
            f'<section class="test"><h2>{escape(test_name)}</h2>'
            + "".join(
                f'<details class="status"><summary>{section} ({len(sections[section])})</summary>'
                f'{render_clients(section, sections[section])}</details>'
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
    def _bdd_from_report(report: str) -> str:
        lines = report.splitlines()
        try:
            start = lines.index("BDD:") + 1
        except ValueError:
            return "BDD não encontrado."
        bdd_lines: list[str] = []
        for line in lines[start:]:
            if line.startswith("Falhas ("):
                break
            bdd_lines.append(line)
        return "\n".join(bdd_lines).strip()

    @staticmethod
    def email_summary_html_from_text(report_path: str | Path) -> str:
        """Gera um resumo compacto; o HTML completo é enviado como anexo."""
        report = Path(report_path).read_text(encoding="utf-8")
        lines = report.splitlines()
        title = next(
            (line.removeprefix("Teste: ") for line in lines if line.startswith("Teste:")),
            "Relatório de validação",
        )
        environment = next(
            (line.removeprefix("Ambiente: ") for line in lines if line.startswith("Ambiente:")),
            "hml",
        )
        duration = next(
            (line.removeprefix("Duração: ") for line in lines if line.startswith("Duração:")),
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
        """Versão com estilos inline para clientes de e-mail."""
        report = Path(report_path).read_text(encoding="utf-8")
        title = next(
            (line.removeprefix("Teste: ") for line in report.splitlines() if line.startswith("Teste:")),
            "Relatório de validação",
        )
        environment = next(
            (line.removeprefix("Ambiente: ") for line in report.splitlines() if line.startswith("Ambiente:")),
            "hml",
        )
        duration = next(
            (line.removeprefix("Duração: ") for line in report.splitlines() if line.startswith("Duração:")),
            "00:00:00",
        )
        sections = ClientValidationReport._parse_sections(report)
        tones = {
            "Falhas": ("#b42318", "#fff1f0"),
            "Informativos": ("#9a6700", "#fff8e6"),
            "Aprovados": ("#16734a", "#edf9f2"),
        }

        def render_section(name: str) -> str:
            color, background = tones[name]
            rows = "".join(
                f'<tr><td style="padding:14px 16px;border:1px solid #dfe5ea;'
                f'border-left:4px solid {color};background:{background};font-family:Arial,sans-serif;">'
                f'<strong>{escape(client_id)}</strong><ul style="margin:8px 0 0;padding-left:20px;">'
                + "".join(
                    f"<li style=\"margin:4px 0;\">"
                    f"{ClientValidationReport._render_message(message)}</li>"
                    for message in messages
                )
                + "</ul></td></tr>"
                for client_id, messages in sections[name]
            ) or '<tr><td style="padding:14px 16px;border:1px solid #dfe5ea;color:#64717d;">Nenhum registro.</td></tr>'
            return (
                f'<details style="margin-top:26px;">'
                f'<summary style="cursor:pointer;font:700 18px Arial,sans-serif;color:#17202a;">'
                f'{name} ({len(sections[name])})</summary>'
                f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" '
                f'style="border-collapse:collapse;margin-top:10px;">{rows}</table>'
                '</details>'
            )

        metrics = "".join(
            f'<td width="33%" style="padding:14px 12px;border-top:4px solid {color};background:{background};font-family:Arial,sans-serif;">'
            f'<div style="font-size:12px;font-weight:bold;color:#64717d;">{name.upper()}</div>'
            f'<div style="font-size:30px;font-weight:bold;color:{color};margin-top:4px;">{len(sections[name])}</div></td>'
            for name, (color, background) in tones.items()
        )
        generated_at = datetime.now().strftime("%d/%m/%Y %H:%M")
        bdd = escape(ClientValidationReport._bdd_from_report(report)).replace("\n", "<br>")
        return f"""<!doctype html><html lang="pt-BR"><body style="margin:0;padding:0;background:#eef2f5;">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#eef2f5;"><tr><td style="padding:24px 12px;"><table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:760px;margin:0 auto;background:#ffffff;"><tr><td style="padding:28px 30px;background:#18324a;font-family:Arial,sans-serif;color:#ffffff;"><div style="font-size:11px;font-weight:bold;letter-spacing:1px;color:#b9c9d7;">RELATÓRIO DE VALIDAÇÃO POR CLIENTE</div><h1 style="font-size:27px;margin:9px 0 10px;color:#ffffff;">{escape(title)}</h1><p style="margin:0;color:#d7e2eb;">Ambiente: <strong>{escape(environment)}</strong> &middot; Gerado em {generated_at} &middot; Duração: <strong>{escape(duration)}</strong></p></td></tr><tr><td style="padding:20px 22px;"><table role="presentation" width="100%" cellspacing="8" cellpadding="0"><tr>{metrics}</tr></table><h2 style="font:700 18px Arial,sans-serif;color:#17202a;margin:26px 0 10px;">BDD executado</h2><table role="presentation" width="100%" cellspacing="0" cellpadding="0"><tr><td style="padding:14px 16px;border:1px solid #dfe5ea;border-left:4px solid #7591a7;background:#f7f9fb;font:14px/1.5 Arial,sans-serif;color:#34495a;">{bdd}</td></tr></table>{render_section("Falhas")}{render_section("Informativos")}{render_section("Aprovados")}</td></tr></table></td></tr></table></body></html>"""

    @staticmethod
    def _render_message(message: str) -> str:
        """Escapa a mensagem e converte a notação **texto** em negrito seguro."""
        escaped_message = escape(message)
        return re.sub(
            r"\*\*(.+?)\*\*",
            r"<strong>\1</strong>",
            escaped_message,
        )

    @staticmethod
    def _parse_sections(report: str) -> dict[str, list[tuple[str, list[str]]]]:
        sections: dict[str, list[tuple[str, list[str]]]] = {
            "Falhas": [], "Informativos": [], "Aprovados": []
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
