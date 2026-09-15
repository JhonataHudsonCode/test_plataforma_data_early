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
        return self._validate_module_indices(
            target,
            "has_asset",
            (
                ("asset", "date"),
                ("asset-historical-observability", "date"),
                ("asset-historical-software", "date"),
            ),
        )

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
            self._validate_index(
                f"{target.client_id}_{suffix}",
                timestamp_field,
                errors,
                details,
            )
        return errors, details

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
            self._validate_monitored_assets_variation(
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

    def _validate_monitored_assets_variation(
        self,
        index_name: str,
        latest_document: dict[str, Any],
        previous_document: dict[str, Any],
        errors: list[str],
        details: list[str],
    ) -> None:
        """Garante que os indicadores monitorados não cresçam mais de 50% ao dia."""
        latest_asset = self._source(latest_document).get("asset")
        previous_asset = self._source(previous_document).get("asset")
        if not isinstance(latest_asset, dict) or not isinstance(previous_asset, dict):
            errors.append(
                f"Índice '{index_name}' | campo asset ausente nos documentos "
                "mais recente ou do dia anterior."
            )
            return

        for field in ("monitored_vulns", "monitored_events"):
            current_value = latest_asset.get(field)
            previous_value = previous_asset.get(field)
            if not self._is_number(current_value) or not self._is_number(previous_value):
                errors.append(
                    f"Índice '{index_name}' | asset.{field} deve ser numérico nos "
                    "documentos mais recente e do dia anterior."
                )
                continue

            current = float(current_value)
            previous = float(previous_value)
            if previous < 0 or current < 0:
                errors.append(
                    f"Índice '{index_name}' | asset.{field} não pode possuir valor negativo "
                    f"(anterior={previous_value}, mais recente={current_value})."
                )
                continue
            if previous == 0:
                if current > 0:
                    errors.append(
                        f"Índice '{index_name}' | asset.{field} aumentou de 0 para "
                        f"{current_value}; excede o limite de 50%."
                    )
                else:
                    details.append(
                        f"Índice '{index_name}' | asset.{field}: sem variação (0 para 0)."
                    )
                continue

            variation = (current - previous) / previous
            details.append(
                f"Índice '{index_name}' | asset.{field}: anterior={previous_value}, "
                f"mais recente={current_value}, variação={variation:.0%}."
            )
            if variation > 0.5:
                errors.append(
                    f"Índice '{index_name}' | asset.{field} aumentou {variation:.0%} "
                    f"(anterior={previous_value}, mais recente={current_value}); "
                    "máximo permitido: 50%."
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
