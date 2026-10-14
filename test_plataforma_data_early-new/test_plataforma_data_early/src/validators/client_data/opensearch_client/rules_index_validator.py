from __future__ import annotations

from datetime import date, datetime

from src.config.settings import ClientTarget
from src.models.client_validation_result import ClientValidationResult
from src.models.opensearch_client.rules_mapping import (
    EXPECTED_RULES_MAPPING,
    RULES_INDEX_NAME,
)
from src.queries.cognito_client_queries import SELECT_COGNITO_CLIENT_HAS_ALERTS_BY_ID
from src.repositories.db_client_repository import DataBaseRepository
from src.repositories.opensearch_client_rsa_repository import OpenSearchClientRepository
from src.validators.client_data.opensearch_client.helpers import (
    OpenSearchClientValidationHelper,
)


class RulesIndexValidator:
    """Valida existência, documentos e mapping do índice rules por cliente."""

    def __init__(
        self,
        cognito_repository: DataBaseRepository,
        opensearch_repository: OpenSearchClientRepository,
        reference_date: date,
    ) -> None:
        self._cognito_repository = cognito_repository
        self._opensearch_repository = opensearch_repository
        self._reference_date = reference_date

    def validate(self, target: ClientTarget) -> ClientValidationResult:
        client = self._cognito_repository.get_table(
            "public", target.client_id, SELECT_COGNITO_CLIENT_HAS_ALERTS_BY_ID
        )
        if not client:
            return ClientValidationResult(
                target.client_id,
                failures=[
                    f"[Geral] Cliente '{target.client_id}' não encontrado no Cognito; "
                    "consulta de has_alerts não retornou registro."
                ],
            )
        if "has_alerts" not in client:
            return ClientValidationResult(target.client_id, failures=[f"[Geral] Cliente '{target.client_id}' | tabela 'public.clients' do Cognito não retornou a coluna 'has_alerts'."])

        if not client["has_alerts"]:
            return ClientValidationResult(
                target.client_id,
                infos=[
                    f"[Geral] Cliente '{target.client_id}' possui has_alerts desabilitado; "
                    "índice rules não aplicável."
                ]
            )
        else:
            cognito_validation = f"[Geral] Cliente '{target.client_id}' | tabela 'public.clients' do Cognito | coluna 'has_alerts' encontrada com valor habilitado."

        host = target.host or client["octopus_endpoint"].replace("https://", "")
        try:
            failures: list[str] = []
            details: list[str] = [cognito_validation]
            indices = self._opensearch_repository.get_indices_rsa(host, RULES_INDEX_NAME)
            index = {item.name: item for item in indices}.get(RULES_INDEX_NAME)
            if index is None:
                failures.append(
                    f"[Geral] Cliente '{target.client_id}' | host '{host}' | índice rules não encontrado."
                )
                return ClientValidationResult(target.client_id, failures=failures, details=details)

            details.append(
                f"[Geral] Índice rules encontrado com sucesso."
            )
            mapping_available, mapping_errors = (
                OpenSearchClientValidationHelper.validate_mapping(
                    self._opensearch_repository,
                    host,
                    RULES_INDEX_NAME,
                    EXPECTED_RULES_MAPPING,
                )
            )
            if not mapping_available:
                failures.append(
                    f"[Mapping] Cliente '{target.client_id}' | índice '{RULES_INDEX_NAME}' | "
                    f"consulta GET /{RULES_INDEX_NAME}/_mapping não retornou propriedades "
                    "para validação."
                )
            else:
                failures.extend(
                    f"[Mapping] Cliente '{target.client_id}' | índice '{RULES_INDEX_NAME}' | "
                    f"host '{host}' | mapping inválido: {error}"
                    for error in mapping_errors
                )
                if not mapping_errors:
                    details.append(
                        f"[Mapping] Índice rules | propriedades retornadas por GET "
                        f"/{RULES_INDEX_NAME}/_mapping validadas com sucesso."
                    )

            if index.document_count <= 0:
                failures.append(
                    f"[Geral] Cliente '{target.client_id}' | host '{host}' | índice rules "
                    "retornou zero documentos."
                )
                return ClientValidationResult(target.client_id, failures=failures, details=details)

            documents = self._opensearch_repository.get_documents(
                host,
                RULES_INDEX_NAME,
                sort_by_timestamp=True,
            )

            details.append(
                f"[Geral] Índice rules encontrado com {index.document_count} documento(s)."
            )

            if not documents:
                failures.append(
                    f"[Timestamp] Cliente '{target.client_id}' | host '{host}' | índice rules "
                    "possui documentos na listagem, mas não retornou documento para validar "
                    "@timestamp."
                )
                return ClientValidationResult(
                    target.client_id, failures=failures, details=details
                )

            self._validate_document_timestamps(
                target.client_id,
                documents,
                failures,
                details,
            )
            return ClientValidationResult(target.client_id, failures=failures, details=details)
        except Exception as error:
            return ClientValidationResult(
                target.client_id,
                failures=[
                    f"[Geral] Cliente '{target.client_id}' | host '{host}' | falha ao validar "
                    f"o índice rules: {error.__class__.__name__}: {error}"
                ]
            )

    def _validate_document_timestamps(
        self,
        client_id: str,
        documents: list[dict],
        failures: list[str],
        details: list[str],
    ) -> None:
        invalid_documents: list[str] = []
        for document in documents:
            document_id = document.get("_id", "não informado")
            timestamp = document.get("_source", {}).get("@timestamp")
            if not isinstance(timestamp, str):
                invalid_documents.append(f"_id={document_id} (@timestamp não informado)")
                continue
            try:
                timestamp_date = datetime.fromisoformat(
                    timestamp.replace("Z", "+00:00")
                ).date()
            except ValueError:
                invalid_documents.append(
                    f"_id={document_id} (@timestamp inválido: {timestamp})"
                )
                continue
            if timestamp_date != self._reference_date:
                invalid_documents.append(
                    f"_id={document_id} (@timestamp fora da data atual: {timestamp})"
                )

        if invalid_documents:
            failures.append(
                f"[Timestamp] Cliente '{client_id}' | índice '{RULES_INDEX_NAME}' | "
                f"{len(invalid_documents)} de {len(documents)} documento(s) com "
                f"@timestamp ausente, inválido ou diferente de "
                f"{self._reference_date.isoformat()}: {', '.join(invalid_documents)}."
            )
            return

        details.append(
            f"[Timestamp] Índice '{RULES_INDEX_NAME}' | os {len(documents)} "
            f"documento(s) retornado(s) possuem @timestamp em "
            f"{self._reference_date.isoformat()}."
        )
