from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Iterable

from src.config.settings import ClientTarget
from src.repositories.cognito_client_repository import CognitoClientRepository
from src.repositories.opensearch_vulnerability_repository import OpenSearchVulnerabilityRepository


class ProductDataValidator:
    """Valida a aplicação do módulo no Cognito e a atualização de seus índices."""

    def __init__(
        self,
        repository: OpenSearchVulnerabilityRepository,
        cognito_repository: CognitoClientRepository,
        reference_date: date | None = None,
    ) -> None:
        self._repository = repository
        self._cognito_repository = cognito_repository
        self._reference_date = reference_date or date.today()

    def validate_assets(self, target: ClientTarget) -> tuple[list[str], list[str]]:
        client, errors, details = self._get_applicable_client(target, "has_asset")
        if client is None:
            return errors, details

        self._validate_dated_asset_indices(target.client_id, errors, details)
        for suffix in ("asset-historical-observability", "asset-historical-software"):
            self._validate_index(f"{target.client_id}_{suffix}", "date", errors, details)
        return errors, details

    def validate_compliance(self, target: ClientTarget) -> tuple[list[str], list[str]]:
        return self._validate_module_indices(
            target,
            "has_wazuh",
            (("asset-compliance", "@timestamp"), ("asset-policy-compliance", "@timestamp")),
        )

    def validate_software_policies(self, target: ClientTarget) -> tuple[list[str], list[str]]:
        return self._validate_module_indices(
            target,
            "has_asset",
            (("authorized-software", "@timestamp"), ("mandatory-software", "@timestamp")),
        )

    def validate_score_history(self, target: ClientTarget) -> tuple[list[str], list[str]]:
        return self._validate_module_indices(
            target,
            "is_in_platform",
            (("score_history", "@timestamp"),),
        )

    def validate_oto_dashboard(self, target: ClientTarget) -> tuple[list[str], list[str]]:
        return self._validate_module_indices(
            target,
            "is_saas",
            (("oto_dashboard", "@timestamp"),),
        )

    def _validate_module_indices(
        self,
        target: ClientTarget,
        expected_flag: str,
        index_definitions: Iterable[tuple[str, str]],
    ) -> tuple[list[str], list[str]]:
        client, errors, details = self._get_applicable_client(target, expected_flag)
        if client is None:
            return errors, details

        for suffix, timestamp_field in index_definitions:
            index_name = f"{target.client_id}_{suffix}"
            self._validate_index(
                index_name,
                timestamp_field,
                errors,
                details,
            )
        return errors, details

    def _validate_dated_asset_indices(
        self,
        client_id: str,
        errors: list[str],
        details: list[str],
    ) -> None:
        index_prefix = f"{client_id}_asset_"
        previous_date = self._reference_date - timedelta(days=1)
        try:
            index_names = self._repository.get_index_names_for_dates(
                index_prefix,
                (self._reference_date, previous_date),
            )
        except Exception as error:
            errors.append(
                f"Índices de ativos com prefixo '{index_prefix}' | erro ao localizar "
                f"as datas {self._reference_date.isoformat()} e {previous_date.isoformat()}: "
                f"{error.__class__.__name__}: {error}"
            )
            return

        current_index_name = index_names.get(self._reference_date)
        previous_index_name = index_names.get(previous_date)
        if current_index_name is None:
            errors.append(
                f"Índice de ativos não encontrado para o prefixo '{index_prefix}' e data "
                f"{self._reference_date.isoformat()}."
            )
        if previous_index_name is None:
            errors.append(
                f"Índice de ativos não encontrado para o prefixo '{index_prefix}' e data "
                f"{previous_date.isoformat()}."
            )
        if current_index_name is None or previous_index_name is None:
            return

        current_document = self._validate_dated_index_document(
            current_index_name,
            self._reference_date,
            errors,
            details,
        )
        previous_document = self._validate_dated_index_document(
            previous_index_name,
            previous_date,
            errors,
            details,
        )
        if current_document is not None and previous_document is not None:
            self._validate_assets_variation(
                current_index_name,
                current_document,
                previous_document,
                errors,
                details,
            )

    def _validate_dated_index_document(
        self,
        index_name: str,
        expected_date: date,
        errors: list[str],
        details: list[str],
    ) -> dict[str, Any] | None:
        try:
            index = next(
                (item for item in self._repository.get_indices(index_name) if item.name == index_name),
                None,
            )
            if index is None:
                errors.append(f"Índice '{index_name}' não encontrado.")
                return None
            if index.document_count <= 0:
                errors.append(f"Índice '{index_name}' não possui documentos.")
                return None
            document = self._repository.get_latest_document(index_name, "date")
        except Exception as error:
            errors.append(
                f"Índice '{index_name}' | erro ao consultar documento mais recente: "
                f"{error.__class__.__name__}: {error}"
            )
            return None

        if document is None:
            errors.append(f"Índice '{index_name}' não retornou documento mais recente.")
            return None

        document_date = self._parse_date(self._source(document).get("date"))
        if document_date != expected_date:
            errors.append(
                f"Índice '{index_name}' | documento mais recente com date "
                f"{self._source(document).get('date', 'não informado')}; esperado "
                f"{expected_date.isoformat()}."
            )
            return None
        details.append(
            f"Índice '{index_name}' validado: {index.document_count} documento(s); "
            f"date mais recente: {self._source(document).get('date')}."
        )
        return document

    def _get_applicable_client(
        self,
        target: ClientTarget,
        expected_flag: str,
    ) -> tuple[dict[str, Any] | None, list[str], list[str]]:
        try:
            client = self._cognito_repository.get_client("public", target.client_id)
        except Exception as error:
            return None, [
                f"Cliente '{target.client_id}' | erro ao consultar o Cognito: "
                f"{error.__class__.__name__}: {error}"
            ], []

        if client is None:
            return None, [], [
                f"Cliente '{target.client_id}' não encontrado no Cognito; "
                "índices não aplicáveis."
            ]
        if not bool(client.get(expected_flag)):
            return None, [], [
                f"Cliente '{target.client_id}' possui {expected_flag} desabilitado no Cognito; "
                "índices não aplicáveis."
            ]
        return client, [], [
            f"Cliente '{target.client_id}' | Cognito validado: {expected_flag} habilitado."
        ]

    def _validate_index(
        self,
        index_name: str,
        timestamp_field: str,
        errors: list[str],
        details: list[str],
    ) -> None:
        try:
            index = next(
                (item for item in self._repository.get_indices(index_name) if item.name == index_name),
                None,
            )
            if index is None:
                errors.append(f"Índice '{index_name}' não encontrado.")
                return
            if index.document_count <= 0:
                errors.append(f"Índice '{index_name}' não possui documentos.")
                return

            document = self._repository.get_latest_document(index_name, timestamp_field)
        except Exception as error:
            errors.append(
                f"Índice '{index_name}' | erro ao consultar documento mais recente: "
                f"{error.__class__.__name__}: {error}"
            )
            return

        if document is None:
            errors.append(f"Índice '{index_name}' não retornou documento mais recente.")
            return

        timestamp = self._source(document).get(timestamp_field)
        document_date = self._parse_date(timestamp)
        if document_date is None:
            errors.append(
                f"Índice '{index_name}' | documento mais recente sem {timestamp_field} válido."
            )
            return
        try:
            previous_day_documents = self._repository.get_previous_day_documents(
                index_name,
                timestamp,
                timestamp_field,
            )
        except Exception as error:
            errors.append(
                f"Índice '{index_name}' | erro ao consultar documentos do dia anterior "
                f"a {document_date.isoformat()}: {error.__class__.__name__}: {error}"
            )
            return

        previous_day = document_date - timedelta(days=1)
        details.append(
            f"Índice '{index_name}' | {timestamp_field} mais recente: {timestamp}; "
            f"documentos em {previous_day.isoformat()}: {len(previous_day_documents)}."
        )
        if not previous_day_documents:
            errors.append(
                f"Índice '{index_name}' não possui documentos no dia anterior "
                f"ao mais recente ({previous_day.isoformat()})."
            )
        else:
            self._validate_assets_variation(
                index_name,
                document,
                previous_day_documents[0],
                errors,
                details,
            )
        if document_date != self._reference_date:
            errors.append(
                f"Índice '{index_name}' | documento mais recente com {timestamp_field} "
                f"{timestamp}; último dia encontrado: {document_date.isoformat()}; "
                f"esperado {self._reference_date.isoformat()}."
            )
            return

        details.append(
            f"Índice '{index_name}' possui {index.document_count} documento(s); "
            "documento mais recente é de hoje."
        )

    def _validate_assets_variation(
        self,
        index_name: str,
        latest_document: dict[str, Any],
        previous_document: dict[str, Any],
        errors: list[str],
        details: list[str],
    ) -> None:
        """Garante que os indicadores do índice não cresçam mais de 50% ao dia."""
        if index_name.endswith("_asset-historical-software"):
            latest_values = self._source(latest_document)
            previous_values = self._source(previous_document)
            fields = (
                "assets_total",
                "assets_missing_mandatory_softwares",
                "assets_with_unauthorized_softwares",
            )
            field_prefix = ""
        else:
            latest_values = self._source(latest_document).get("asset")
            previous_values = self._source(previous_document).get("asset")
            fields = ("monitored_vulns", "monitored_events")
            field_prefix = "asset."

        if not isinstance(latest_values, dict) or not isinstance(previous_values, dict):
            errors.append(
                f"Índice '{index_name}' | dados esperados ausentes nos documentos "
                "mais recente ou do dia anterior."
            )
            return

        variation_fields = tuple(
            (
                f"{field_prefix}{field}",
                latest_values.get(field),
                previous_values.get(field),
            )
            for field in fields
        )
        self._validate_fifty_percent_variation(
            index_name,
            variation_fields,
            errors,
            details,
        )

        if "_asset_" in index_name:
            self._validate_asset_events_equality(
                index_name,
                latest_values,
                previous_values,
                errors,
                details,
            )

    def _validate_fifty_percent_variation(
        self,
        index_name: str,
        fields: tuple[tuple[str, object, object], ...],
        errors: list[str],
        details: list[str],
    ) -> None:
        """Falha quando um indicador numérico cresce mais de 50% entre dois documentos."""
        for field_name, current_value, previous_value in fields:
            if not self._is_number(current_value) or not self._is_number(previous_value):
                errors.append(
                    f"Índice '{index_name}' | {field_name} deve ser numérico nos "
                    "documentos mais recente e do dia anterior."
                )
                continue

            current = float(current_value)
            previous = float(previous_value)
            if previous < 0 or current < 0:
                errors.append(
                    f"Índice '{index_name}' | {field_name} não pode possuir valor negativo "
                    f"(anterior={previous_value}, mais recente={current_value})."
                )
                continue
            if previous == 0:
                if current > 0:
                    errors.append(
                        f"Índice '{index_name}' | {field_name} aumentou de 0 para "
                        f"{current_value}; excede o limite de 50%."
                    )
                else:
                    details.append(
                        f"Índice '{index_name}' | {field_name}: sem variação (0 para 0)."
                    )
                continue

            variation = (current - previous) / previous
            details.append(
                f"Índice '{index_name}' | {field_name}: anterior={previous_value}, "
                f"mais recente={current_value}, variação={variation:.0%}."
            )
            if variation > 0.5:
                errors.append(
                    f"Índice '{index_name}' | {field_name} aumentou {variation:.0%} "
                    f"(anterior={previous_value}, mais recente={current_value}); "
                    "máximo permitido: 50%."
                )

    def _validate_asset_events_equality(
        self,
        index_name: str,
        latest_asset: dict[str, Any],
        previous_asset: dict[str, Any],
        errors: list[str],
        details: list[str],
    ) -> None:
        """Valida campos estáveis de asset_events entre os índices diários de ativos."""
        latest_events = latest_asset.get("asset_events", latest_asset.get("assets_events"))
        previous_events = previous_asset.get("asset_events", previous_asset.get("assets_events"))
        if not isinstance(latest_events, dict) or not isinstance(previous_events, dict):
            errors.append(
                f"Índice '{index_name}' | asset_events ausente nos documentos "
                "mais recente ou do dia anterior."
            )
            return

        latest_compliance = latest_events.get("compliance")
        previous_compliance = previous_events.get("compliance")
        if not isinstance(latest_compliance, dict) or not isinstance(previous_compliance, dict):
            errors.append(
                f"Índice '{index_name}' | asset_events.compliance ausente nos documentos "
                "mais recente ou do dia anterior."
            )
            return

        fields = (
            (
                "asset_events.compliance.score",
                latest_compliance.get("score"),
                previous_compliance.get("score"),
            ),
            (
                "asset_events.technology",
                latest_events.get("technology", latest_compliance.get("technology")),
                previous_events.get("technology", previous_compliance.get("technology")),
            ),
        )
        for field_name, current_value, previous_value in fields:
            if current_value is None or previous_value is None:
                errors.append(
                    f"Índice '{index_name}' | {field_name} ausente nos documentos "
                    "mais recente ou do dia anterior."
                )
            elif current_value != previous_value:
                errors.append(
                    f"Índice '{index_name}' | {field_name} divergente entre os índices: "
                    f"anterior={previous_value!r}, mais recente={current_value!r}."
                )
            else:
                details.append(
                    f"Índice '{index_name}' | {field_name} igual nos índices de hoje e ontem: "
                    f"{current_value!r}."
                )

        self._validate_fifty_percent_variation(
            index_name,
            (
                (
                    "asset_events.compliance.score",
                    latest_compliance.get("score"),
                    previous_compliance.get("score"),
                ),
            ),
            errors,
            details,
        )

    @staticmethod
    def _source(document: dict[str, Any]) -> dict[str, Any]:
        return document.get("_source", document)

    @staticmethod
    def _is_number(value: object) -> bool:
        return isinstance(value, (int, float)) and not isinstance(value, bool)

    @staticmethod
    def _parse_date(value: object) -> date | None:
        if not isinstance(value, str):
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        except ValueError:
            return None
