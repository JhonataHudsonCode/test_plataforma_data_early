from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, Iterable

from src.repositories.opensearch_vulnerability_repository import OpenSearchVulnerabilityRepository


@dataclass(frozen=True, slots=True)
class IndexSnapshot:
    name: str
    today_documents: list[dict[str, Any]]
    yesterday_documents: list[dict[str, Any]]


class ProductDataValidator:
    """Valida os índices de produto produzidos pelo pipeline pós-processamento."""

    def __init__(self, repository: OpenSearchVulnerabilityRepository, reference_date: date | None = None, maximum_variation: float = 0.80) -> None:
        self._repository = repository
        self._reference_date = reference_date or date.today()
        self._maximum_variation = maximum_variation

    def validate_assets(self, client_id: str) -> tuple[list[str], list[str]]:
        errors, details = [], []
        asset = self._snapshot(f"{client_id}_asset", errors, details)
        observability = self._snapshot(f"{client_id}_asset-historical-observability", errors, details)
        software = self._snapshot(f"{client_id}_asset-historical-software", errors, details)
        if asset:
            self._validate_document_variation(asset, errors, details, "ativos inventariados")
            self._validate_asset_classification(asset.today_documents, errors, details)
            self._validate_positive_asset_score(asset.today_documents, errors, details)
        if observability:
            self._validate_document_variation(observability, errors, details, "dados de observabilidade")
        if software:
            self._validate_document_variation(software, errors, details, "histórico de software")
        return errors, details

    def validate_compliance(self, client_id: str) -> tuple[list[str], list[str]]:
        return self._validate_current_indices(client_id, ("asset-compliance", "asset-policy-compliance"))

    def validate_software_policies(self, client_id: str) -> tuple[list[str], list[str]]:
        return self._validate_current_indices(client_id, ("authorized-software", "mandatory-software"))

    def validate_score_history(self, client_id: str, client: dict[str, object]) -> tuple[list[str], list[str]]:
        errors, details = [], []
        snapshot = self._snapshot(f"{client_id}_score_history", errors, details)
        if not snapshot:
            return errors, details
        current = self._source(snapshot.today_documents[0])
        flattened = dict(self._flatten(current))
        enabled_modules = [key.removeprefix("has_") for key, value in client.items() if key.startswith("has_") and bool(value)]
        for module in enabled_modules:
            scores = [value for key, value in flattened.items() if module in key.casefold() and "score" in key.casefold() and isinstance(value, (int, float))]
            if not scores:
                errors.append(f"Score do módulo habilitado '{module}' não encontrado.")
            elif any(value <= 0 or value == -1 for value in scores):
                errors.append(f"Score inválido para o módulo '{module}': {scores}.")
        if not self._has_current_month_document(snapshot.today_documents):
            errors.append("Não foi encontrado documento mensal referente ao mês corrente.")
        if not any("global" in key.casefold() for key in flattened):
            errors.append("Comparativo global não encontrado no score.")
        if not any("sector" in key.casefold() or "setor" in key.casefold() for key in flattened):
            errors.append("Comparativo de setor não encontrado no score.")
        self._validate_numeric_variation(snapshot, errors, details, "score")
        return errors, details

    def validate_oto_dashboard(self, client_id: str) -> tuple[list[str], list[str]]:
        errors, details = [], []
        snapshot = self._snapshot(f"{client_id}_oto_dashboard", errors, details)
        if snapshot:
            self._validate_numeric_variation(snapshot, errors, details, "métricas do OTO Dashboard")
        return errors, details

    def _validate_current_indices(self, client_id: str, suffixes: Iterable[str]) -> tuple[list[str], list[str]]:
        errors, details = [], []
        for suffix in suffixes:
            self._snapshot(f"{client_id}_{suffix}", errors, details)
        return errors, details

    def _snapshot(self, index_name: str, errors: list[str], details: list[str]) -> IndexSnapshot | None:
        try:
            index = next((item for item in self._repository.get_indices(index_name) if item.name == index_name), None)
            if index is None:
                errors.append(f"Índice não encontrado: {index_name}.")
                return None
            if index.document_count <= 0:
                errors.append(f"Índice sem documentos: {index_name}.")
                return None
            start = datetime.combine(self._reference_date, time.min)
            today_documents = self._repository.get_documents_between(index_name, start, start + timedelta(days=1))
            yesterday_documents = self._repository.get_documents_between(index_name, start - timedelta(days=1), start)
        except Exception as error:
            errors.append(f"Erro ao consultar documentos do índice {index_name}: {error}")
            return None
        if not today_documents:
            errors.append(f"O índice {index_name} não possui documentos com @timestamp de hoje.")
            return None
        details.append(f"Índice {index_name}: {len(today_documents)} documento(s) de hoje e {len(yesterday_documents)} de ontem.")
        return IndexSnapshot(index_name, today_documents, yesterday_documents)

    def _validate_document_variation(self, snapshot: IndexSnapshot, errors: list[str], details: list[str], label: str) -> None:
        previous, current = len(snapshot.yesterday_documents), len(snapshot.today_documents)
        if previous and current < previous * (1 - self._maximum_variation):
            errors.append(f"Queda brusca em {label}: ontem={previous}, hoje={current}.")
        else:
            details.append(f"Variação de {label} dentro do limite: ontem={previous}, hoje={current}.")

    def _validate_asset_classification(self, documents: list[dict[str, Any]], errors: list[str], details: list[str]) -> None:
        for field in ("asset.importance", "asset.owner", "asset.tags"):
            populated = sum(bool(self._nested(self._source(document), field)) for document in documents)
            ratio = populated / len(documents)
            details.append(f"Classificação {field}: {populated}/{len(documents)} preenchidos.")
            if ratio < 1 - self._maximum_variation:
                errors.append(f"Campo de classificação '{field}' pouco preenchido: {ratio:.0%}.")

    def _validate_positive_asset_score(self, documents: list[dict[str, Any]], errors: list[str], details: list[str]) -> None:
        scores = [self._nested(self._source(document), "asset.score") for document in documents]
        valid = [score for score in scores if isinstance(score, (int, float)) and score > 0]
        details.append(f"Ativos com score positivo: {len(valid)}/{len(documents)}.")
        if len(valid) != len(documents):
            errors.append("Existem documentos de clavis_asset sem score positivo.")

    def _validate_numeric_variation(self, snapshot: IndexSnapshot, errors: list[str], details: list[str], label: str) -> None:
        if not snapshot.yesterday_documents:
            details.append(f"Sem documentos de ontem para comparar {label}.")
            return
        current = self._numeric_total(self._source(snapshot.today_documents[0]))
        previous = self._numeric_total(self._source(snapshot.yesterday_documents[0]))
        if previous == 0:
            details.append(f"Comparativo de {label} sem base numérica anterior.")
            return
        variation = abs(current - previous) / abs(previous)
        details.append(f"Variação de {label}: {variation:.0%}.")
        if variation > self._maximum_variation:
            errors.append(f"Variação brusca em {label}: {variation:.0%}.")

    def _has_current_month_document(self, documents: list[dict[str, Any]]) -> bool:
        for document in documents:
            timestamp = self._source(document).get("@timestamp")
            if isinstance(timestamp, str):
                parsed = self._parse_timestamp(timestamp)
                if parsed and (parsed.year, parsed.month) == (self._reference_date.year, self._reference_date.month):
                    return True
        return False

    @staticmethod
    def _source(document: dict[str, Any]) -> dict[str, Any]:
        return document.get("_source", document)

    @staticmethod
    def _nested(source: dict[str, Any], path: str) -> Any:
        value: Any = source
        for key in path.split("."):
            if not isinstance(value, dict):
                return None
            value = value.get(key)
        return value

    @classmethod
    def _flatten(cls, value: Any, prefix: str = "") -> Iterable[tuple[str, Any]]:
        if isinstance(value, dict):
            for key, child in value.items():
                yield from cls._flatten(child, f"{prefix}.{key}" if prefix else key)
        else:
            yield prefix, value

    @classmethod
    def _numeric_total(cls, source: dict[str, Any]) -> float:
        return float(sum(value for _, value in cls._flatten(source) if isinstance(value, (int, float))))

    @staticmethod
    def _parse_timestamp(value: str) -> datetime | None:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
