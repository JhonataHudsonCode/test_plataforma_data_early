import json
from datetime import datetime
from pathlib import Path

class AllureService:

    def __init__(self, results_path: str = "allure-results"):
        self.results_path = Path(results_path)

    def get_results(self) -> list[dict]:
        results = []

        if not self.results_path.is_dir():
            raise FileNotFoundError(f"Allure results directory '{self.results_path}' not found.")

        for file in self.results_path.glob("*-result.json"):
            try:
                with file.open("r", encoding="utf-8") as json_file:
                    data = json.load(json_file)
                    results.append(data)
            except (json.JSONDecodeError, OSError) as error:
                print(f"Warning: Could not read or parse '{file}': {error}")

        return results

    def get_results_summary(self) -> list[dict]:
        results = self.get_results()
        scenarios = []

        for result in results:
            status = result.get("status", "unknown")
            start = result.get("start")
            execution_date = self._format_date(start)
            error_reason = self._get_error_reason(result)

            scenarios.append(
                {
                    "scenario": result.get(
                        "name",
                        "Cenario não informado"
                    ),
                    "status": status,
                    "execution_date": execution_date,
                    "error_reason": error_reason,
                }
            )

        return scenarios

    def generate_html_table(self) -> str:
        results = self.get_results_summary()

        rows = []

        for result in results:
            status = result["status"]
            if status == "passed":
                status_text = "Aprovado"
            elif status == "failed":
                status_text = "Falhou"
            elif status == "broken":
                status_text = "Quebrado"
            elif status == "skipped":
                status_text = "Ignorado"
            else:
                status_text = status.upper()

            rows.append(
                f"""
                <tr>
                    <td>{result['scenario']}</td>
                    <td>{status_text}</td>
                    <td>{result['execution_date']}</td>
                    <td>{result['error_reason']}</td>
                </tr>
                """
            )

        return f"""
        <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%;">
            <thead>
                <tr>
                    <th>Cenário</th>
                    <th>Status</th>
                    <th>Data de Execução</th>
                    <th>Motivo do Erro</th>
                </tr>
            </thead>
            <tbody>
                {''.join(rows)}
            </tbody>
        </table>
        """

    @staticmethod
    def _format_date(timestamp: int | None) -> str:
        if timestamp is None:
            return "Data não informada"

        try:
            dt = datetime.fromtimestamp(timestamp / 1000)
            return dt.strftime("%d/%m/%Y %H:%M:%S")
        except (OSError, ValueError) as error:
            print(f"Warning: Could not format timestamp '{timestamp}': {error}")
            return "Data inválida"

    @staticmethod
    def _get_error_reason(result: dict) -> str:
        status = result.get("status")

        if status not in ("failed", "broken"):
            return "-"

        status_details = result.get("statusDetails", {})
        message = status_details.get("message")

        if message:
            return message

        trace = status_details.get("trace")
        if trace:
            return trace.splitlines()[0]

        return "Erro não informado"

    
                