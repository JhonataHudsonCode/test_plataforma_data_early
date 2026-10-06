from __future__ import annotations

from datetime import date

from src.config.settings import ClientTarget
from src.models.client_validation_result import ClientValidationResult
from src.models.opensearch_client.rules_mapping import (
    EXPECTED_RULES_MAPPING,
    RULES_INDEX_NAME,
)
from src.queries.cognito_client_queries import SELECT_COGNITO_CLIENT_HAS_ALERTS_BY_ID
from src.repositories.db_client_repository import DataBaseRepository
from src.repositories.opensearch_client_rsa_repository import OpenSearchClientRepository
from src.validators.opensearch_mapping_validator import OpenSearchMappingValidator


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
        cognito_validation = f"[Geral] Cliente '{target.client_id}' | tabela 'public.clients' do Cognito | coluna 'has_alerts' encontrada com valor {'habilitado' if client['has_alerts'] else 'desabilitado'}."
        if not client["has_alerts"]:
            return ClientValidationResult(
                target.client_id,
                infos=[
                    f"[Geral] Cliente '{target.client_id}' possui has_alerts desabilitado; "
                    "índice rules não aplicável."
                ],
                details=[cognito_validation],
            )

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
            if index.document_count <= 0:
                failures.append(
                    f"[Geral] Cliente '{target.client_id}' | host '{host}' | índice rules "
                    "retornou zero documentos."
                )
                return ClientValidationResult(target.client_id, failures=failures, details=details)

            details.append(
                f"[Geral] Índice rules encontrado com {index.document_count} documento(s)."
            )
            documents = self._opensearch_repository.get_documents(
                host,
                RULES_INDEX_NAME,
                size=1,
                sort_by_timestamp=True,
            )
            if not documents:
                failures.append(
                    f"[Geral] Cliente '{target.client_id}' | host '{host}' | índice rules "
                    "possui documentos na listagem, mas não retornou documento para validar o mapping."
                )
                return ClientValidationResult(
                    target.client_id,
                    failures=failures,
                    details=details,
                )

            document = documents[0]
            document_id = document.get("_id", "não informado")
            mapping_errors = OpenSearchMappingValidator().validate_document(
                document.get("_source", {}),
                EXPECTED_RULES_MAPPING,
            )
            failures.extend(
                f"[Mapping] Cliente '{target.client_id}' | índice '{RULES_INDEX_NAME}' | "
                f"host '{host}' | documento '{document_id}' | mapping inválido: {error}"
                for error in mapping_errors
            )
            if not mapping_errors:
                details.append(
                    f"[Mapping] Índice rules | documento '{document_id}' | "
                    "mapping validado com sucesso."
                )
            return ClientValidationResult(target.client_id, failures=failures, details=details)
        except Exception as error:
            return ClientValidationResult(
                target.client_id,
                failures=[
                    f"[Geral] Cliente '{target.client_id}' | host '{host}' | falha ao validar "
                    f"o índice rules: {error.__class__.__name__}: {error}"
                ],
                details=[cognito_validation],
            )
