from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Iterable

from src.config.settings import ClientTarget
from src.models.opensearch_product.vulnerability_index import VulnerabilityIndex
from src.repositories.cognito_client_repository import CognitoClientRepository
from src.repositories.opensearch_vulnerability_repository import OpenSearchVulnerabilityRepository


@dataclass(frozen=True, slots=True)
class _IndexDocuments:
    """Documentos já consultados durante a validação de um índice."""

    latest: dict[str, Any]
    previous: dict[str, Any] | None


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

        self._validate_dated_asset_indices(
            target.client_id,
            "@timestamp",
            errors,
            details,
        )
        for suffix in ("asset-historical-observability", "asset-historical-software"):
            index_name = f"{target.client_id}_{suffix}"
            documents = self._validate_index(index_name, "date", errors, details)
            if documents is not None and documents.previous is not None:
                self._validate_assets_variation(
                    index_name,
                    documents.latest,
                    documents.previous,
                    errors,
                    details,
                )
        return errors, details

    def validate_compliance(self, target: ClientTarget) -> tuple[list[str], list[str]]:
        return self._validate_module_indices(
            target,
            "has_wazuh",
            (("asset-compliance", "@timestamp"), ("asset-policy-compliance", "@timestamp")),
            validate_creation_date=True,
        )

    def validate_software_policies(self, target: ClientTarget) -> tuple[list[str], list[str]]:
        return self._validate_module_indices(
            target,
            "has_asset",
            (("authorized-software", "lastupdated"), ("mandatory-software", "lastupdated")),
            compare_previous_day=False,
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
        validate_creation_date: bool = False,
        compare_previous_day: bool = True,
    ) -> tuple[list[str], list[str]]:
        client, errors, details = self._get_applicable_client(target, expected_flag)
        if client is None:
            return errors, details

        for suffix, timestamp_field in index_definitions:
            index_name = f"{target.client_id}_{suffix}"
            self._validate_index_with_optional_date_suffix(
                index_name,
                timestamp_field,
                errors,
                details,
                validate_creation_date,
                compare_previous_day,
            )
        return errors, details

    def _validate_index_with_optional_date_suffix(
        self,
        index_name: str,
        timestamp_field: str,
        errors: list[str],
        details: list[str],
        validate_creation_date: bool = False,
        compare_previous_day: bool = True,
    ) -> None:
        """Valida o índice fixo ou sua versão diária com data no sufixo."""
        try:
            candidate_indices = self._repository.get_indices_with_optional_date(
                index_name,
                self._reference_date,
            )
        except Exception as error:
            errors.append(
                f"Índice '{index_name}' | erro ao localizar candidatos: "
                f"{error.__class__.__name__}: {error}"
            )
            return

        if not candidate_indices:
            errors.append(
                f"Índice '{index_name}' não encontrado, nem versão com data "
                f"para {self._reference_date.isoformat()}."
            )
            return

        details.append(
            f"Índice '{index_name}' | candidatos selecionados: "
            f"{', '.join(candidate.name for candidate in candidate_indices)}."
        )
        for candidate_index in candidate_indices:
            if validate_creation_date:
                self._validate_index_creation_date(candidate_index, errors, details)
            else:
                self._validate_index(
                    candidate_index,
                    timestamp_field,
                    errors,
                    details,
                    compare_previous_day,
                )

    def _validate_index_creation_date(
        self,
        index: VulnerabilityIndex,
        errors: list[str],
        details: list[str],
    ) -> None:
        """Valida somente a data de criação do índice já encontrado."""
        try:
            metadata = self._repository.get_index_metadata(index.name)
        except Exception as error:
            errors.append(
                f"Índice '{index.name}' | erro ao consultar data de criação: "
                f"{error.__class__.__name__}: {error}"
            )
            return

        creation_date = metadata.created_at.date()
        if creation_date != self._reference_date:
            errors.append(
                f"Índice '{index.name}' | criado em {metadata.created_at.isoformat()}; "
                f"último dia encontrado: {creation_date.isoformat()}; "
                f"esperado {self._reference_date.isoformat()}."
            )
            return

        details.append(
            f"Índice '{index.name}' | creation_date validado: "
            f"{metadata.created_at.isoformat()}."
        )

    def _validate_dated_asset_indices(
        self,
        client_id: str,
        timestamp_field: str,
        errors: list[str],
        details: list[str],
    ) -> None:
        index_prefix = f"{client_id}_asset-"
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
            timestamp_field,
            errors,
            details,
        )
        previous_document = self._validate_dated_index_document(
            previous_index_name,
            previous_date,
            timestamp_field,
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
        timestamp_field: str,
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
            document = self._repository.get_latest_document(index_name, timestamp_field)
        except Exception as error:
            errors.append(
                f"Índice '{index_name}' | erro ao consultar documento mais recente: "
                f"{error.__class__.__name__}: {error}"
            )
            return None

        if document is None:
            errors.append(f"Índice '{index_name}' não retornou documento mais recente.")
            return None

        timestamp = self._source(document).get(timestamp_field)
        document_date = self._parse_date(timestamp)
        if document_date != expected_date:
            errors.append(
                f"Índice '{index_name}' | documento mais recente com {timestamp_field} "
                f"{timestamp or 'não informado'}; esperado "
                f"{expected_date.isoformat()}."
            )
            return None
        details.append(
            f"Índice '{index_name}' validado: {index.document_count} documento(s); "
            f"{timestamp_field} mais recente: {timestamp}."
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
        index_or_name: VulnerabilityIndex | str,
        timestamp_field: str,
        errors: list[str],
        details: list[str],
        compare_previous_day: bool = True,
    ) -> _IndexDocuments | None:
        """Orquestra a validação genérica de atualização de um índice."""
        index_name = (
            index_or_name.name
            if isinstance(index_or_name, VulnerabilityIndex)
            else index_or_name
        )
        index = self._get_available_index(index_or_name, errors)
        if index is None:
            return None

        document = self._get_latest_document(index.name, timestamp_field, errors)
        if document is None:
            return None

        timestamp_and_date = self._validate_latest_document_date(
            index.name,
            document,
            timestamp_field,
            errors,
        )
        if timestamp_and_date is None:
            return None
        timestamp, document_date = timestamp_and_date

        if not compare_previous_day:
            details.append(
                f"Índice '{index_name}' possui {index.document_count} documento(s); "
                f"lastupdated mais recente é de hoje: {timestamp}."
            )
            return _IndexDocuments(latest=document, previous=None)

        previous_day_documents = self._get_previous_day_documents(
            index_name,
            timestamp,
            timestamp_field,
            document_date,
            errors,
        )
        if previous_day_documents is None:
            return None

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
            previous_document = None
        else:
            previous_document = previous_day_documents[0]
        details.append(
            f"Índice '{index_name}' possui {index.document_count} documento(s); "
            "documento mais recente é de hoje."
        )
        return _IndexDocuments(latest=document, previous=previous_document)

    def _get_available_index(
        self,
        index_or_name: VulnerabilityIndex | str,
        errors: list[str],
    ) -> VulnerabilityIndex | None:
        """Obtém o índice já candidato ou o localiza pelo nome."""
        if isinstance(index_or_name, VulnerabilityIndex):
            index = index_or_name
        else:
            try:
                index = next(
                    (
                        item
                        for item in self._repository.get_indices(index_or_name)
                        if item.name == index_or_name
                    ),
                    None,
                )
            except Exception as error:
                errors.append(
                    f"Índice '{index_or_name}' | erro ao consultar índice: "
                    f"{error.__class__.__name__}: {error}"
                )
                return None

        if index is None:
            errors.append(f"Índice '{index_or_name}' não encontrado.")
            return None
        if index.document_count <= 0:
            errors.append(f"Índice '{index.name}' não possui documentos.")
            return None
        return index

    def _get_latest_document(
        self,
        index_name: str,
        timestamp_field: str,
        errors: list[str],
    ) -> dict[str, Any] | None:
        """Consulta o documento mais recente uma única vez."""
        try:
            document = self._repository.get_latest_document(index_name, timestamp_field)
        except Exception as error:
            errors.append(
                f"Índice '{index_name}' | erro ao consultar documento mais recente: "
                f"{error.__class__.__name__}: {error}"
            )
            return None
        if document is None:
            errors.append(f"Índice '{index_name}' não retornou documento mais recente.")
        return document

    def _validate_latest_document_date(
        self,
        index_name: str,
        document: dict[str, Any],
        timestamp_field: str,
        errors: list[str],
    ) -> tuple[str, date] | None:
        """Garante que o campo temporal do documento mais recente seja de hoje."""
        timestamp = self._source(document).get(timestamp_field)
        document_date = self._parse_date(timestamp)
        if document_date is None:
            errors.append(
                f"Índice '{index_name}' | documento mais recente sem {timestamp_field} válido."
            )
            return None
        if document_date != self._reference_date:
            errors.append(
                f"Índice '{index_name}' | documento mais recente com {timestamp_field} "
                f"{timestamp}; último dia encontrado: {document_date.isoformat()}; "
                f"esperado {self._reference_date.isoformat()}."
            )
            return None
        return timestamp, document_date

    def _get_previous_day_documents(
        self,
        index_name: str,
        timestamp: str,
        timestamp_field: str,
        document_date: date,
        errors: list[str],
    ) -> list[dict[str, Any]] | None:
        """Consulta os documentos do dia anterior quando a regra exigir histórico."""
        try:
            return self._repository.get_previous_day_documents(
                index_name,
                timestamp,
                timestamp_field,
            )
        except Exception as error:
            errors.append(
                f"Índice '{index_name}' | erro ao consultar documentos do dia anterior "
                f"a {document_date.isoformat()}: {error.__class__.__name__}: {error}"
            )
            return None

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
            self._validate_fifty_percent_variation(
                index_name,
                self._variation_fields(latest_values, previous_values, fields, field_prefix),
                errors,
                details,
            )
        elif index_name.endswith("_asset-historical-observability"):
            latest_values = self._source(latest_document).get("asset")
            previous_values = self._source(previous_document).get("asset")
            fields = ("monitored_vulns", "monitored_events")
            field_prefix = "asset."
            self._validate_fifty_percent_variation(
                index_name,
                self._variation_fields(latest_values, previous_values, fields, field_prefix),
                errors,
                details,
            )
        else:
            latest_values = self._source(latest_document).get("asset")
            previous_values = self._source(previous_document).get("asset")
            if not isinstance(latest_values, dict) or not isinstance(previous_values, dict):
                errors.append(
                    f"Índice '{index_name}' | campo asset ausente nos documentos "
                    "mais recente ou do dia anterior."
                )
                return
            self._validate_asset_events_equality(
                index_name,
                latest_values,
                previous_values,
                errors,
                details,
            )

    @staticmethod
    def _variation_fields(
        latest_values: object,
        previous_values: object,
        fields: tuple[str, ...],
        field_prefix: str,
    ) -> tuple[tuple[str, object, object], ...]:
        if not isinstance(latest_values, dict) or not isinstance(previous_values, dict):
            return tuple((f"{field_prefix}{field}", None, None) for field in fields)
        return tuple(
            (
                f"{field_prefix}{field}",
                latest_values.get(field),
                previous_values.get(field),
            )
            for field in fields
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

        latest_technology = latest_events.get(
            "technology",
            latest_compliance.get("technology"),
        )
        previous_technology = previous_events.get(
            "technology",
            previous_compliance.get("technology"),
        )
        if latest_technology is None or previous_technology is None:
            errors.append(
                f"Índice '{index_name}' | asset_events.technology ausente nos documentos "
                "mais recente ou do dia anterior."
            )
        elif latest_technology != previous_technology:
            errors.append(
                f"Índice '{index_name}' | asset_events.technology divergente entre os índices: "
                f"anterior={previous_technology!r}, mais recente={latest_technology!r}."
            )
        else:
            details.append(
                f"Índice '{index_name}' | asset_events.technology igual nos índices de hoje "
                f"e ontem: {latest_technology!r}."
            )

        self._validate_score_maximum_decrease(
            index_name,
            latest_compliance.get("score"),
            previous_compliance.get("score"),
            errors,
            details,
        )

    def _validate_score_maximum_decrease(
        self,
        index_name: str,
        current_value: object,
        previous_value: object,
        errors: list[str],
        details: list[str],
    ) -> None:
        """Falha quando o score mais recente cai 50% ou mais em relação ao anterior."""
        field_name = "asset_events.compliance.score"
        if not self._is_number(current_value) or not self._is_number(previous_value):
            errors.append(
                f"Índice '{index_name}' | {field_name} deve ser numérico nos documentos "
                "mais recente e do dia anterior."
            )
            return

        current = float(current_value)
        previous = float(previous_value)
        if current < 0 or previous < 0:
            errors.append(
                f"Índice '{index_name}' | {field_name} não pode possuir valor negativo "
                f"(anterior={previous_value}, mais recente={current_value})."
            )
            return
        if previous == 0:
            details.append(
                f"Índice '{index_name}' | {field_name}: anterior=0, mais recente={current_value}; "
                "não há redução percentual a validar."
            )
            return

        variation = (current - previous) / previous
        details.append(
            f"Índice '{index_name}' | {field_name}: anterior={previous_value}, "
            f"mais recente={current_value}, variação={variation:.0%}."
        )
        if variation <= -0.5:
            errors.append(
                f"Índice '{index_name}' | {field_name} reduziu {abs(variation):.0%} "
                f"(anterior={previous_value}, mais recente={current_value}); "
                "redução máxima permitida: menos de 50%."
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
