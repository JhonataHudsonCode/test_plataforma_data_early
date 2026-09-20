from __future__ import annotations

import ast
import os
import re
from datetime import datetime
from html import escape
from pathlib import Path


class ClientValidationReport:
    """Agrupa resultados por cliente e gera os relatórios TXT e HTML da execução."""

    def __init__(self) -> None:
        self._results: dict[str, dict[str, list[str]]] = {}

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
    ) -> str:
        """Gera um relatório único preservando o resultado de cada teste."""
        combined_results: dict[str, dict[str, list[str]]] = {}
        section_fields = {
            "Falhas": ("failures", "Motivo: "),
            "Informativos": ("infos", "Informação: "),
            "Aprovados": ("details", "Detalhe: "),
        }

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
            for section, clients in cls._parse_sections(report_content).items():
                field, label = section_fields[section]
                for client_id, messages in clients:
                    result_id = f"{test_name} | {client_id}"
                    result = combined_results.setdefault(
                        result_id,
                        {"failures": [], "infos": [], "details": []},
                    )
                    result[field].extend(
                        message.removeprefix(label) for message in messages
                    )

        combined_report = cls()
        for result_id, result in combined_results.items():
            combined_report.add_client_result(result_id, **result)

        content = combined_report.write(
            output_path,
            "Resumo geral da execução",
            "Consolidado dos resultados de todos os testes executados.",
        )
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
        sections = ClientValidationReport._parse_sections(report)
        bdd = ClientValidationReport._bdd_from_report(report)
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
</style></head><body><main><header><small>RELATÓRIO DE VALIDAÇÃO POR CLIENTE</small><h1>{escape(title)}</h1><p>Ambiente: {escape(environment)} · Gerado em {generated_at}</p></header>
<section class="grid"><div class="metric fail">FALHAS<b>{counts['Falhas']}</b></div><div class="metric info">INFORMATIVOS<b>{counts['Informativos']}</b></div><div class="metric pass">APROVADOS<b>{counts['Aprovados']}</b></div></section>
<section class="panel"><h2>BDD executado</h2><pre>{escape(bdd)}</pre></section>
<section class="panel"><h2>Falhas ({counts['Falhas']})</h2>{cards('Falhas', 'fail', 'Nenhuma falha registrada.')}</section>
<section class="panel"><h2>Informativos ({counts['Informativos']})</h2>{cards('Informativos', 'info', 'Nenhum registro informativo.')}</section>
<section class="panel"><h2>Aprovados ({counts['Aprovados']})</h2>{cards('Aprovados', 'pass', 'Nenhum cliente aprovado.')}</section>
</main></body></html>"""
        output_path = Path(html_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")
        return html

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
                f'<h2 style="font:700 18px Arial,sans-serif;color:#17202a;margin:26px 0 10px;">'
                f'{name} ({len(sections[name])})</h2>'
                f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" '
                f'style="border-collapse:collapse;">{rows}</table>'
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
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#eef2f5;"><tr><td style="padding:24px 12px;"><table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:760px;margin:0 auto;background:#ffffff;"><tr><td style="padding:28px 30px;background:#18324a;font-family:Arial,sans-serif;color:#ffffff;"><div style="font-size:11px;font-weight:bold;letter-spacing:1px;color:#b9c9d7;">RELATÓRIO DE VALIDAÇÃO POR CLIENTE</div><h1 style="font-size:27px;margin:9px 0 10px;color:#ffffff;">{escape(title)}</h1><p style="margin:0;color:#d7e2eb;">Ambiente: <strong>{escape(environment)}</strong> &middot; Gerado em {generated_at}</p></td></tr><tr><td style="padding:20px 22px;"><table role="presentation" width="100%" cellspacing="8" cellpadding="0"><tr>{metrics}</tr></table><h2 style="font:700 18px Arial,sans-serif;color:#17202a;margin:26px 0 10px;">BDD executado</h2><table role="presentation" width="100%" cellspacing="0" cellpadding="0"><tr><td style="padding:14px 16px;border:1px solid #dfe5ea;border-left:4px solid #7591a7;background:#f7f9fb;font:14px/1.5 Arial,sans-serif;color:#34495a;">{bdd}</td></tr></table>{render_section("Falhas")}{render_section("Informativos")}{render_section("Aprovados")}</td></tr></table></td></tr></table></body></html>"""

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
