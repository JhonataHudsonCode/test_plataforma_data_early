from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import json
from pathlib import Path
import re
from typing import Any, Iterable

from src.config.settings import ClientTarget
from src.models.opensearch_product.asset_compliance_mapping import (
    EXPECTED_ASSET_COMPLIANCE_MAPPING,
)
from src.models.opensearch_product.asset_historical_observability_mapping import (
    EXPECTED_ASSET_HISTORICAL_OBSERVABILITY_MAPPING,
)
from src.models.opensearch_product.asset_historical_software_mapping import (
    EXPECTED_ASSET_HISTORICAL_SOFTWARE_MAPPING,
)
from src.models.opensearch_product.asset_policy_compliance_mapping import (
    EXPECTED_ASSET_POLICY_COMPLIANCE_MAPPING,
)
from src.models.opensearch_product.client_asset_mapping import EXPECTED_CLIENT_ASSET_MAPPING
from src.models.opensearch_product.software_policy_mapping import (
    EXPECTED_SOFTWARE_POLICY_MAPPING,
)
from src.models.opensearch_product.score_history_mapping import (
    EXPECTED_SCORE_HISTORY_MAPPING,
)
from src.models.opensearch_product.oto_dashboard_mapping import (
    EXPECTED_OTO_DASHBOARD_MAPPING,
)
from src.models.opensearch_product.vulnerability_index import VulnerabilityIndex
from src.repositories.cognito_client_repository import CognitoClientRepository
from src.repositories.opensearch_vulnerability_repository import OpenSearchVulnerabilityRepository
from src.validators.after_pipeline.oto_dashboard.document_validator import (
    OtoDashboardDocumentValidator,
)
from src.validators.opensearch_mapping_validator import OpenSearchMappingValidator


@dataclass(frozen=True, slots=True)
class _IndexDocuments:
    """Documentos já consultados durante a validação de um índice."""

    latest: dict[str, Any]
    previous: dict[str, Any] | None


class ProductDataValidator:
    """Valida a aplicação do módulo no Cognito e a atualização de seus índices."""

    _SCORE_HISTORY_FIELDS: tuple[tuple[str, str | None], ...] = (
        ("score", None),
        ("vulnerabilities", None),
        ("rsa", "has_rsa"),
        ("siem", "has_wazuh"),
        ("cls", None),
        ("cls_alta", None),
        ("cls_media", None),
    )
    def __init__(
        self,
        repository: OpenSearchVulnerabilityRepository,
        cognito_repository: CognitoClientRepository,
        reference_date: date | None = None,
    ) -> None:
        self._repository = repository
        self._cognito_repository = cognito_repository
        self._reference_date = reference_date or date.today()
        self._oto_dashboard_document_validator = OtoDashboardDocumentValidator(
            self._reference_date
        )

    def validate_assets(self, target: ClientTarget) -> tuple[list[str], list[str]]:
        client, errors, details = self._get_applicable_client(target, "has_asset")
        if client is None:
            return errors, details

        historical_mappings = {
            "asset-historical-observability": EXPECTED_ASSET_HISTORICAL_OBSERVABILITY_MAPPING,
            "asset-historical-software": EXPECTED_ASSET_HISTORICAL_SOFTWARE_MAPPING,
        }
        for suffix, expected_mapping in historical_mappings.items():
            index_name = f"{target.client_id}_{suffix}"
            self._validate_mapping(index_name, expected_mapping, errors, details)
            self._validate_assets_variation(index_name, errors, details)
        return errors, details

    def validate_current_asset_index(
        self,
        target: ClientTarget,
    ) -> tuple[list[str], list[str]]:
        """Valida todos os documentos do índice diário de ativos atual."""
        client, errors, details = self._get_applicable_client(target, "has_asset")
        if client is None:
            return errors, details

        self._validate_current_asset_index(
            target.client_id,
            "@timestamp",
            EXPECTED_CLIENT_ASSET_MAPPING,
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
            expected_mappings={
                "asset-compliance": EXPECTED_ASSET_COMPLIANCE_MAPPING,
                "asset-policy-compliance": EXPECTED_ASSET_POLICY_COMPLIANCE_MAPPING,
            },
        )

    def validate_software_policies(self, target: ClientTarget) -> tuple[list[str], list[str]]:
        return self._validate_module_indices(
            target,
            "has_asset",
            (("authorized-software", "lastupdated"), ("mandatory-software", "lastupdated")),
            compare_previous_day=False,
            expected_mappings={
                "authorized-software": EXPECTED_SOFTWARE_POLICY_MAPPING,
                "mandatory-software": EXPECTED_SOFTWARE_POLICY_MAPPING,
            },
        )

    def validate_score_history(self, target: ClientTarget) -> tuple[list[str], list[str]]:
        client, errors, details = self._get_applicable_client(target, "is_in_platform")
        if client is None:
            return errors, details

        index_name = f"{target.client_id}_score_history"
        self._validate_mapping(
            index_name,
            EXPECTED_SCORE_HISTORY_MAPPING,
            errors,
            details,
        )
        self._validate_score_history(
            index_name,
            client,
            errors,
            details,
        )
        return errors, details

    def validate_oto_dashboard(self, target: ClientTarget) -> tuple[list[str], list[str]]:
        client, errors, details = self._get_applicable_client(
            target,
            "client_type",
            "saas",
        )
        if client is None:
            return errors, details

        self._validate_dated_oto_dashboard_indices(target.client_id, errors, details)
        return errors, details

    def _validate_score_history(
        self,
        index_name: str,
        client: dict[str, Any],
        errors: list[str],
        details: list[str],
    ) -> None:
        """Valida os scores atual e anterior, mesmo quando o atual está atrasado."""
        try:
            candidates = self._repository.get_indices_with_optional_date(
                index_name,
                self._reference_date,
            )
        except Exception as error:
            errors.append(
                f"Índice '{index_name}' | erro ao localizar candidatos: "
                f"{error.__class__.__name__}: {error}"
            )
            return
        if not candidates:
            errors.append(f"Índice '{index_name}' não encontrado.")
            return

        index = candidates[0]
        if index.document_count <= 0:
            errors.append(f"Índice '{index.name}' não possui documentos.")
            return

        document = self._get_latest_document(index.name, "date", errors)
        if document is None:
            return
        latest_date = self._get_document_date(index.name, document, "date", errors)
        if latest_date is None:
            return

        if latest_date != self._reference_date:
            errors.append(
                f"Índice '{index.name}' | documento mais recente com date "
                f"{latest_date.isoformat()}; último dia encontrado: {latest_date.isoformat()}; "
                f"esperado {self._reference_date.isoformat()}."
            )
        else:
            details.append(
                f"Índice '{index.name}' | dados de hoje presentes: "
                f"date={latest_date.isoformat()}."
            )

        latest_timestamp = self._source(document).get("date")
        if not isinstance(latest_timestamp, str):
            errors.append(
                f"Índice '{index.name}' | documento mais recente sem date válido."
            )
            return
        previous_documents = self._get_previous_day_documents(
            index.name,
            latest_timestamp,
            "date",
            latest_date,
            errors,
        )
        if previous_documents is None:
            return
        if not previous_documents:
            errors.append(
                f"Índice '{index.name}' não possui documento no dia anterior "
                f"ao mais recente ({(latest_date - timedelta(days=1)).isoformat()})."
            )
            return

        previous_document = previous_documents[0]
        previous_date = self._get_document_date(
            index.name,
            previous_document,
            "date",
            errors,
        )
        expected_previous_date = latest_date - timedelta(days=1)
        if previous_date != expected_previous_date:
            errors.append(
                f"Índice '{index.name}' | documento histórico com date "
                f"{previous_date.isoformat() if previous_date else 'não informado'}; esperado "
                f"{expected_previous_date.isoformat()}."
            )
            return
        self._validate_score_history_fields(
            index.name,
            document,
            previous_document,
            client,
            errors,
            details,
        )

    def _validate_dated_oto_dashboard_indices(
        self,
        client_id: str,
        errors: list[str],
        details: list[str],
    ) -> None:
        """Compara os documentos mais recentes dos índices diários do OTO Dashboard."""
        index_prefix = f"{client_id}_oto_dashboard"
        previous_date = self._reference_date - timedelta(days=1)
        try:
            index_names = self._repository.get_index_names_for_dates(
                index_prefix,
                (self._reference_date, previous_date),
            )
        except Exception as error:
            errors.append(
                f"Índices OTO Dashboard com prefixo '{index_prefix}' | erro ao localizar "
                f"datas: {error.__class__.__name__}: {error}"
            )
            return

        current_index_name = index_names.get(self._reference_date)
        previous_index_name = index_names.get(previous_date)
        if current_index_name is None:
            errors.append(
                f"Índice OTO Dashboard não encontrado para {self._reference_date.isoformat()}."
            )
        if previous_index_name is None:
            errors.append(
                f"Índice OTO Dashboard não encontrado para {previous_date.isoformat()}."
            )
        if current_index_name is None or previous_index_name is None:
            return

        self._validate_mapping(
            current_index_name,
            EXPECTED_OTO_DASHBOARD_MAPPING,
            errors,
            details,
        )
        self._validate_mapping(
            previous_index_name,
            EXPECTED_OTO_DASHBOARD_MAPPING,
            errors,
            details,
        )

        current_document = self._validate_dated_index_document(
            current_index_name,
            self._reference_date,
            "@timestamp",
            errors,
            details,
        )
        previous_document = self._validate_dated_index_document(
            previous_index_name,
            previous_date,
            "@timestamp",
            errors,
            details,
        )
        if current_document is not None and previous_document is not None:
            self._validate_oto_dashboard_metrics(
                current_index_name,
                current_document,
                previous_document,
                errors,
                details,
            )

    def _validate_oto_dashboard_metrics(
        self,
        index_name: str,
        latest_document: dict[str, Any],
        previous_document: dict[str, Any],
        errors: list[str],
        details: list[str],
    ) -> None:
        """Delega a comparação do `_source` ao validador específico do OTO."""
        self._oto_dashboard_document_validator.validate(
            index_name,
            self._source(latest_document),
            self._source(previous_document),
            errors,
            details,
        )

    def _validate_score_history_fields(
        self,
        index_name: str,
        latest_document: dict[str, Any],
        previous_document: dict[str, Any],
        client: dict[str, Any],
        errors: list[str],
        details: list[str],
    ) -> None:
        """Valida valores válidos e variação máxima de 50% nos scores aplicáveis."""
        latest_source = self._source(latest_document)
        previous_source = self._source(previous_document)
        for field_name, required_flag in self._SCORE_HISTORY_FIELDS:
            if required_flag is not None and not bool(client.get(required_flag)):
                details.append(
                    f"Índice '{index_name}' | score {field_name} não aplicável: "
                    f"{required_flag} desabilitado."
                )
                continue

            latest_value = latest_source.get(field_name)
            previous_value = previous_source.get(field_name)
            if not self._is_valid_score(latest_value):
                errors.append(
                    f"Índice '{index_name}' | score {field_name} inválido no documento "
                    f"mais recente: {latest_value!r}. Valores 0 e -1 não são permitidos."
                )
                continue
            if not self._is_valid_score(previous_value):
                errors.append(
                    f"Índice '{index_name}' | score {field_name} inválido no documento "
                    f"do dia anterior: {previous_value!r}."
                )
                continue

            self._validate_score_history_variation(
                index_name,
                field_name,
                float(latest_value),
                float(previous_value),
                errors,
                details,
            )

    def _validate_score_history_variation(
        self,
        index_name: str,
        field_name: str,
        latest_value: float,
        previous_value: float,
        errors: list[str],
        details: list[str],
    ) -> None:
        """Sinaliza alteração absoluta acima de 50% entre scores consecutivos."""
        variation = abs(latest_value - previous_value) / abs(previous_value)
        details.append(
            f"Índice '{index_name}' | score {field_name}: anterior={previous_value}, "
            f"mais recente={latest_value}, variação={variation:.0%}."
        )
        if variation > 0.5:
            errors.append(
                f"Índice '{index_name}' | score {field_name} variou {variation:.0%} "
                f"(anterior={previous_value}, mais recente={latest_value}); "
                "máximo permitido: 50%."
            )

    def _validate_module_indices(
        self,
        target: ClientTarget,
        expected_flag: str,
        index_definitions: Iterable[tuple[str, str]],
        validate_creation_date: bool = False,
        compare_previous_day: bool = True,
        expected_value: object = True,
        expected_mappings: dict[str, dict[str, str | dict[str, Any]]] | None = None,
    ) -> tuple[list[str], list[str]]:
        client, errors, details = self._get_applicable_client(
            target,
            expected_flag,
            expected_value,
        )
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
                expected_mappings.get(suffix) if expected_mappings else None,
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
        expected_mapping: dict[str, str | dict[str, Any]] | None = None,
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
            if expected_mapping is not None:
                self._validate_mapping(candidate_index.name, expected_mapping, errors, details)
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

    def _validate_current_asset_index(
        self,
        client_id: str,
        timestamp_field: str,
        expected_mapping: dict[str, str | dict[str, Any]],
        errors: list[str],
        details: list[str],
    ) -> None:
        index_name = f"{client_id}_asset"
        try:
            documents = self._repository.get_documents_by_date_match(
                index_name,
                self._reference_date,
                timestamp_field,
            )
        except Exception as error:
            errors.append(
                f"Índice de ativos '{index_name}' | erro ao consultar documentos de "
                f"{self._reference_date.isoformat()}: "
                f"{error.__class__.__name__}: {error}"
            )
            return

        if not documents:
            errors.append(
                f"Índice de ativos '{index_name}' não retornou documentos com "
                f"{timestamp_field} em {self._reference_date.isoformat()}."
            )
            return
        self._validate_mappings_for_documents(
            documents,
            expected_mapping,
            errors,
            details,
        )
        self._validate_current_asset_documents(
            index_name,
            documents,
            timestamp_field,
            errors,
            details,
        )

    def _validate_current_asset_documents(
        self,
        index_name: str,
        documents: list[dict[str, Any]],
        timestamp_field: str,
        errors: list[str],
        details: list[str],
    ) -> None:
        """Garante que todos os documentos do índice diário pertençam a hoje."""
        invalid_timestamps: list[str] = []
        for document in documents:
            timestamp = self._source(document).get(timestamp_field)
            document_date = self._parse_date(timestamp)
            if document_date != self._reference_date:
                document_id = str(document.get("_id", "não informado"))
                invalid_timestamps.append(
                    f"_id={document_id}, {timestamp_field}={timestamp or 'não informado'}"
                )

        if invalid_timestamps:
            errors.append(
                f"Índice '{index_name}' | {len(invalid_timestamps)} de "
                f"{len(documents)} documento(s) possuem {timestamp_field} diferente de "
                f"{self._reference_date.isoformat()}: {', '.join(invalid_timestamps)}."
            )
            return

        details.append(
            f"Índice '{index_name}' | busca por {timestamp_field} em "
            f"{self._reference_date.isoformat()} retornou {len(documents)} documento(s), "
            "todos validados."
        )

    def _validate_mappings_for_documents(
        self,
        documents: list[dict[str, Any]],
        expected_mapping: dict[str, str | dict[str, Any]],
        errors: list[str],
        details: list[str],
    ) -> None:
        """Valida o mapping do OpenSearch e o `_source` de todos os documentos."""
        indexes_from_documents: set[str] = set()
        validated_documents_by_index: dict[str, int] = {}
        mapping_validator = OpenSearchMappingValidator()
        for position, document in enumerate(documents, start=1):
            document_index = document.get("_index")
            document_id = str(document.get("_id", "não informado"))
            if not isinstance(document_index, str) or not document_index:
                errors.append(
                    f"Documento {position} (_id={document_id}) da busca de ativos não "
                    "retornou o nome do índice (_index)."
                )
                continue
            indexes_from_documents.add(document_index)

            source = self._source(document)
            document_mapping_errors = mapping_validator.validate_document(
                source,
                expected_mapping,
            )
            if document_mapping_errors:
                errors.extend(
                    f"Índice '{document_index}' | documento {position} (_id={document_id}) | "
                    f"mapping inválido: {error}"
                    for error in document_mapping_errors
                )
                continue
            validated_documents_by_index[document_index] = (
                validated_documents_by_index.get(document_index, 0) + 1
            )

        if not indexes_from_documents:
            errors.append("A busca de ativos não retornou nome de índice em nenhum documento.")
            return

        for document_index in sorted(indexes_from_documents):
            self._validate_mapping(document_index, expected_mapping, errors, details)
            details.append(
                f"Índice '{document_index}' | mapping estrutural validado em "
                f"{validated_documents_by_index.get(document_index, 0)} documento(s)."
            )

    def _validate_mapping(
        self,
        index_name: str,
        expected_mapping: dict[str, str | dict[str, Any]],
        errors: list[str],
        details: list[str],
    ) -> None:
        """Compara o mapping efetivo do índice com o contrato do respectivo produto."""
        try:
            metadata = self._repository.get_index_metadata(index_name)
        except Exception as error:
            errors.append(
                f"Índice '{index_name}' | erro ao consultar mapping: "
                f"{error.__class__.__name__}: {error}"
            )
            return

        actual_properties = metadata.mapping.get("properties")
        if not isinstance(actual_properties, dict):
            errors.append(f"Índice '{index_name}' | mapping sem propriedades configuradas.")
            return

        mapping_errors = OpenSearchMappingValidator().validate(
            actual_properties,
            expected_mapping,
        )
        if mapping_errors:
            errors.extend(
                f"Índice '{index_name}' | mapping inválido: {mapping_error}"
                for mapping_error in mapping_errors
            )
            return
        details.append(f"Índice '{index_name}' | mapping validado com sucesso.")

    def _validate_dated_index_document(
        self,
        index_name: str,
        expected_date: date,
        timestamp_field: str,
        errors: list[str],
        details: list[str],
        continue_when_outdated: bool = False,
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

        self._save_document_source(index_name, self._source(document))
        timestamp = self._source(document).get(timestamp_field)
        document_date = self._parse_date(timestamp)
        if document_date != expected_date:
            errors.append(
                f"Índice '{index_name}' | documento mais recente com {timestamp_field} "
                f"{timestamp or 'não informado'}; última data encontrada: "
                f"{document_date.isoformat() if document_date else 'não informada'}; "
                f"esperado {expected_date.isoformat()}."
            )
            if not continue_when_outdated:
                return None
        details.append(
            f"Índice '{index_name}' validado: {index.document_count} documento(s); "
            f"{timestamp_field} mais recente: {timestamp}."
        )
        return document

    @staticmethod
    def _save_document_source(index_name: str, source: dict[str, Any]) -> None:
        """Salva o `_source` retornado para inspeção local durante a execução."""
        output_directory = Path("reports/debug-documents")
        safe_index_name = re.sub(r"[^A-Za-z0-9._-]+", "_", index_name)
        output_path = output_directory / f"{safe_index_name}.json"
        try:
            output_directory.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(source, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
        except OSError:
            # O dump é somente diagnóstico e não deve alterar o resultado do teste.
            return

    def _get_applicable_client(
        self,
        target: ClientTarget,
        expected_field: str,
        expected_value: object = True,
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
        actual_value = client.get(expected_field)
        if actual_value != expected_value:
            return None, [], [
                f"Cliente '{target.client_id}' | {expected_field}={actual_value!r}; "
                f"esperado {expected_value!r}; índices não aplicáveis."
            ]
        return client, [], [
            f"Cliente '{target.client_id}' | Cognito validado: "
            f"{expected_field}={expected_value!r}."
        ]

    def _validate_index(
        self,
        index_or_name: VulnerabilityIndex | str,
        timestamp_field: str,
        errors: list[str],
        details: list[str],
        compare_previous_day: bool = True,
        continue_when_outdated: bool = False,
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
            continue_when_outdated,
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
        if document_date == self._reference_date:
            details.append(
                f"Índice '{index_name}' possui {index.document_count} documento(s); "
                "documento mais recente é de hoje."
            )
        else:
            details.append(
                f"Índice '{index_name}' possui {index.document_count} documento(s); "
                f"documento mais recente de {document_date.isoformat()} será usado nas "
                "demais validações."
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
        continue_when_outdated: bool = False,
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
            if not continue_when_outdated:
                return None
        return timestamp, document_date

    def _get_document_date(
        self,
        index_name: str,
        document: dict[str, Any],
        field_name: str,
        errors: list[str],
    ) -> date | None:
        """Extrai uma data de documento sem exigir que ela seja a data de hoje."""
        document_date = self._parse_date(self._source(document).get(field_name))
        if document_date is None:
            errors.append(
                f"Índice '{index_name}' | documento mais recente sem {field_name} válido."
            )
        return document_date

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
        errors: list[str],
        details: list[str],
    ) -> None:
        """Compara a soma diária dos indicadores dos históricos de ativos."""
        if index_name.endswith("_asset-historical-software"):
            fields = (
                "assets_total",
                "assets_missing_mandatory_softwares",
                "assets_with_unauthorized_softwares",
            )
        elif index_name.endswith("_asset-historical-observability"):
            fields = ("assets.monitored_vulns", "assets.monitored_events")
        else:
            return

        previous_date = self._reference_date - timedelta(days=1)
        current_documents = self._get_documents_for_date(
            index_name,
            self._reference_date,
            errors,
        )
        previous_documents = self._get_documents_for_date(
            index_name,
            previous_date,
            errors,
        )
        if current_documents is None or previous_documents is None:
            return
        if not current_documents or not previous_documents:
            missing_date = (
                self._reference_date if not current_documents else previous_date
            )
            errors.append(
                f"Índice '{index_name}' não retornou documentos em "
                f"{missing_date.isoformat()} para calcular a variação diária."
            )
            return

        current_totals, current_invalid_fields = self._sum_document_fields(
            index_name,
            current_documents,
            fields,
            errors,
        )
        previous_totals, previous_invalid_fields = self._sum_document_fields(
            index_name,
            previous_documents,
            fields,
            errors,
        )
        invalid_fields = current_invalid_fields | previous_invalid_fields
        valid_fields = tuple(field for field in fields if field not in invalid_fields)
        if not valid_fields:
            return

        details.append(
            f"Índice '{index_name}' | soma de {len(current_documents)} documento(s) em "
            f"{self._reference_date.isoformat()} comparada com {len(previous_documents)} "
            f"documento(s) em {previous_date.isoformat()}."
        )
        self._validate_fifty_percent_variation(
            index_name,
            tuple(
                (field, current_totals[field], previous_totals[field])
                for field in valid_fields
            ),
            errors,
            details,
        )

    def _get_documents_for_date(
        self,
        index_name: str,
        reference_date: date,
        errors: list[str],
    ) -> list[dict[str, Any]] | None:
        start = datetime.combine(reference_date, datetime.min.time())
        try:
            return self._repository.get_documents_between(
                index_name,
                start,
                start + timedelta(days=1),
                timestamp_field="date",
            )
        except Exception as error:
            errors.append(
                f"Índice '{index_name}' | erro ao consultar documentos de "
                f"{reference_date.isoformat()}: {error.__class__.__name__}: {error}"
            )
            return None

    def _sum_document_fields(
        self,
        index_name: str,
        documents: list[dict[str, Any]],
        fields: tuple[str, ...],
        errors: list[str],
    ) -> tuple[dict[str, float], set[str]]:
        totals = {field: 0.0 for field in fields}
        invalid_fields: set[str] = set()
        for position, document in enumerate(documents, start=1):
            source = self._source(document)
            document_id = str(document.get("_id", "não informado"))
            for field in fields:
                value = self._get_nested_value(source, field)
                if not self._is_number(value):
                    errors.append(
                        f"Índice '{index_name}' | documento {position} (_id={document_id}) | "
                        f"{field} deve ser numérico para compor a soma diária."
                    )
                    invalid_fields.add(field)
                    continue
                totals[field] += float(value)
        return totals, invalid_fields

    @staticmethod
    def _get_nested_value(source: dict[str, Any], field_path: str) -> object:
        value: object = source
        for field_name in field_path.split("."):
            if not isinstance(value, dict):
                return None
            value = value.get(field_name)
        return value

    def _validate_fifty_percent_variation(
        self,
        index_name: str,
        fields: tuple[tuple[str, object, object], ...],
        errors: list[str],
        details: list[str],
    ) -> None:
        """Falha quando um total diário cresce mais de 50% em relação ao dia anterior."""
        for field_name, current_value, previous_value in fields:
            if not self._is_number(current_value) or not self._is_number(previous_value):
                errors.append(
                    f"Índice '{index_name}' | total de {field_name} deve ser numérico "
                    "nos dias comparados."
                )
                continue

            current = float(current_value)
            previous = float(previous_value)
            if previous < 0 or current < 0:
                errors.append(
                    f"Índice '{index_name}' | total de {field_name} não pode possuir valor "
                    f"negativo (ontem={previous_value}, hoje={current_value})."
                )
                continue
            if previous == 0:
                if current > 0:
                    errors.append(
                        f"Índice '{index_name}' | total de {field_name} aumentou de 0 para "
                        f"{current_value}; excede o limite de 50%."
                    )
                else:
                    details.append(
                        f"Índice '{index_name}' | total de {field_name}: sem variação (0 para 0)."
                    )
                continue

            variation = (current - previous) / previous
            details.append(
                f"Índice '{index_name}' | total de {field_name}: ontem={previous_value}, "
                f"hoje={current_value}, variação={variation:.0%}."
            )
            if variation > 0.5:
                errors.append(
                f"Índice '{index_name}' | total de {field_name} aumentou {variation:.0%} "
                f"(ontem={previous_value}, hoje={current_value}); "
                    "máximo permitido: 50%."
                )

    @staticmethod
    def _source(document: dict[str, Any]) -> dict[str, Any]:
        return document.get("_source", document)

    @staticmethod
    def _is_number(value: object) -> bool:
        return isinstance(value, (int, float)) and not isinstance(value, bool)

    @classmethod
    def _is_valid_score(cls, value: object) -> bool:
        return cls._is_number(value) and value not in {0, -1}

    @staticmethod
    def _parse_date(value: object) -> date | None:
        if not isinstance(value, str):
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        except ValueError:
            return None
