from __future__ import annotations

from datetime import date

from src.config.settings import ClientTarget
from src.models.client_validation_result import ClientValidationResult
from src.models.opensearch_client.elastalert_status_mapping import (
    ELASTALERT_STATUS_INDEX_NAME,
    EXPECTED_ELASTALERT_STATUS_MAPPING,
)
from src.queries.cognito_client_queries import SELECT_COGNITO_CLIENT_HAS_ALERTS_BY_ID
from src.repositories.db_client_repository import DataBaseRepository
from src.repositories.opensearch_client_rsa_repository import OpenSearchClientRepository
from src.validators.opensearch_mapping_validator import OpenSearchMappingValidator


class AlertsIndexValidator:
    """Valida o índice de status de alertas nos OpenSearch dos clientes."""

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
                failures=[f"[Geral] Cliente '{target.client_id}' não encontrado no Cognito."],
            )
        if "has_alerts" not in client:
            return ClientValidationResult(target.client_id, failures=[f"[Geral] Cliente '{target.client_id}' | tabela 'public.clients' do Cognito não retornou a coluna 'has_alerts'."])
        cognito_validation = f"[Geral] Cliente '{target.client_id}' | tabela 'public.clients' do Cognito | coluna 'has_alerts' encontrada com valor {'habilitado' if client['has_alerts'] else 'desabilitado'}."
        if not client["has_alerts"]:
            return ClientValidationResult(
                target.client_id,
                infos=[
                    f"[Geral] Cliente '{target.client_id}' possui has_alerts desabilitado; "
                    "validação do OpenSearch não aplicável."
                ],
                details=[cognito_validation],
            )

        host = target.host or client["octopus_endpoint"].replace("https://", "")
        try:
            indices = self._opensearch_repository.get_indices_elastalerts_status_today(
                host, ELASTALERT_STATUS_INDEX_NAME
            )
            failures: list[str] = []
            details: list[str] = [cognito_validation]
            index = next(
                (item for item in indices if item.name == ELASTALERT_STATUS_INDEX_NAME),
                None,
            )
            if index is None:
                return ClientValidationResult(
                    target.client_id,
                    failures=[
                        f"[Geral] Cliente '{target.client_id}' | índice '{ELASTALERT_STATUS_INDEX_NAME}' "
                        f"não encontrado no host '{host}'. Índices encontrados: "
                        f"{', '.join(item.name for item in indices) or 'nenhum'}."
                    ],
                    details=[cognito_validation],
                )
            details.append(
                f"[Geral] Cliente '{target.client_id}' | índice "
                f"'{ELASTALERT_STATUS_INDEX_NAME}' encontrado no host '{host}'."
            )
            documents = self._opensearch_repository.get_documents_by_timestamp_match(
                host,
                ELASTALERT_STATUS_INDEX_NAME,
                self._reference_date,
            )
            if not documents:
                failures.append(
                    f"[Timestamp] Cliente '{target.client_id}' | índice "
                    f"'{ELASTALERT_STATUS_INDEX_NAME}' | nenhum documento retornado com "
                    f"@timestamp em {self._reference_date.isoformat()}."
                )
                return ClientValidationResult(
                    target.client_id, failures=failures, details=details
                )

            first_source = documents[0].get("_source", {})
            mapping_errors = OpenSearchMappingValidator().validate_document(
                first_source,
                EXPECTED_ELASTALERT_STATUS_MAPPING,
            )
            failures.extend(
                f"[Mapping] Cliente '{target.client_id}' | índice "
                f"'{ELASTALERT_STATUS_INDEX_NAME}' | primeiro documento "
                f"(_id={documents[0].get('_id', 'não informado')}) com mapping inválido: {error}"
                for error in mapping_errors
            )

            invalid_timestamps: list[str] = []
            for document in documents:
                timestamp = document.get("_source", {}).get("@timestamp")
                if not isinstance(timestamp, str) or not timestamp.startswith(
                    self._reference_date.isoformat()
                ):
                    invalid_timestamps.append(
                        f"_id={document.get('_id', 'não informado')}, "
                        f"@timestamp={timestamp or 'não informado'}"
                    )
            if invalid_timestamps:
                failures.append(
                    f"[Timestamp] Cliente '{target.client_id}' | índice "
                    f"'{ELASTALERT_STATUS_INDEX_NAME}' | {len(invalid_timestamps)} de "
                    f"{len(documents)} documento(s) com @timestamp diferente de "
                    f"{self._reference_date.isoformat()}: {', '.join(invalid_timestamps)}."
                )
            else:
                details.append(
                    f"[Timestamp] Índice '{ELASTALERT_STATUS_INDEX_NAME}' | consulta por "
                    f"@timestamp em {self._reference_date.isoformat()} retornou "
                    f"{len(documents)} documento(s), todos validados."
                )
            if not mapping_errors:
                details.append(
                    f"[Mapping] Índice '{ELASTALERT_STATUS_INDEX_NAME}' | mapping do "
                    f"primeiro documento (_id={documents[0].get('_id', 'não informado')}) "
                    "validado com sucesso."
                )
            return ClientValidationResult(
                target.client_id,
                failures=failures,
                details=details,
            )
        except Exception as error:
            return ClientValidationResult(
                target.client_id,
                failures=[
                    f"[Geral] Cliente '{target.client_id}' | endpoint '{host}' | falha inesperada durante "
                    f"a validação de '{ELASTALERT_STATUS_INDEX_NAME}': "
                    f"{error.__class__.__name__}: {error}"
                ],
                details=[cognito_validation],
            )
