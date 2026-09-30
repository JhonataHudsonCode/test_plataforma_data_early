from __future__ import annotations

from datetime import date

from src.config.settings import ClientTarget
from src.models.client_validation_result import ClientValidationResult
from src.models.opensearch_client.rsa_mapping import (
    EXPECTED_RSA_MAPPING,
    RSA_INDEX_NAME,
)
from src.queries.cognito_client_queries import SELECT_COGNITO_CLIENT_HAS_RSA_BY_ID
from src.repositories.db_client_repository import DataBaseRepository
from src.repositories.opensearch_client_rsa_repository import OpenSearchClientRepository
from src.validators.opensearch_mapping_validator import OpenSearchMappingValidator


CLIENT_SCHEMA = "public"


class RsaIndexValidator:
    """Valida a disponibilidade, atualidade e contrato do índice RSA por cliente."""

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
            schema_name=CLIENT_SCHEMA,
            client_id=target.client_id,
            query=SELECT_COGNITO_CLIENT_HAS_RSA_BY_ID,
        )
        if not client:
            return ClientValidationResult(
                target.client_id,
                failures=[
                    f"[Geral] Cliente '{target.client_id}' não encontrado no Cognito; "
                    "consulta de has_rsa não retornou registro."
                ],
            )
        if not client.get("has_rsa"):
            return ClientValidationResult(
                target.client_id,
                infos=[
                    f"[Geral] Cliente '{target.client_id}' possui has_rsa desabilitado; "
                    "índice RSA não aplicável."
                ],
            )

        host = target.host or client["octopus_endpoint"].replace("https://", "")
        try:
            indices = self._opensearch_repository.get_indices_rsa(host, RSA_INDEX_NAME)
            index = {item.name: item for item in indices}.get(RSA_INDEX_NAME)
            if index is None:
                return ClientValidationResult(
                    target.client_id,
                    failures=[
                        f"[Geral] Cliente '{target.client_id}' | host '{host}' | índice RSA "
                        f"'{RSA_INDEX_NAME}' não encontrado. Índices encontrados: "
                        f"{', '.join(item.name for item in indices) or 'nenhum'}."
                    ],
                )

            failures: list[str] = []
            details: list[str] = [
                f"[Geral] Cliente '{target.client_id}' | índice RSA '{RSA_INDEX_NAME}' "
                f"encontrado no host '{host}'."
            ]
            documents = self._opensearch_repository.get_documents_by_timestamp_match(
                host,
                RSA_INDEX_NAME,
                self._reference_date,
            )
            if not documents:
                failures.append(
                    f"[Timestamp] Cliente '{target.client_id}' | índice RSA '{RSA_INDEX_NAME}' | "
                    f"host '{host}' | nenhum documento retornado com @timestamp em "
                    f"{self._reference_date.isoformat()}."
                )
                return ClientValidationResult(
                    target.client_id,
                    failures=failures,
                    details=details,
                )

            first_source = documents[0].get("_source", {})
            mapping_errors = OpenSearchMappingValidator().validate_document(
                first_source,
                EXPECTED_RSA_MAPPING,
            )
            failures.extend(
                f"[Mapping] Cliente '{target.client_id}' | índice RSA '{RSA_INDEX_NAME}' | "
                f"host '{host}' | primeiro documento (_id={documents[0].get('_id', 'não informado')}) "
                f"com mapping inválido: {error}"
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
                    f"[Timestamp] Cliente '{target.client_id}' | índice RSA '{RSA_INDEX_NAME}' | "
                    f"{len(invalid_timestamps)} de {len(documents)} documento(s) com "
                    f"@timestamp diferente de {self._reference_date.isoformat()}: "
                    f"{', '.join(invalid_timestamps)}."
                )
            else:
                details.append(
                    f"[Timestamp] Índice RSA '{RSA_INDEX_NAME}' | consulta por @timestamp em "
                    f"{self._reference_date.isoformat()} retornou {len(documents)} "
                    "documento(s), todos validados."
                )
            if not mapping_errors:
                details.append(
                    f"[Mapping] Índice RSA '{RSA_INDEX_NAME}' | mapping do primeiro documento "
                    f"(_id={documents[0].get('_id', 'não informado')}) validado com sucesso."
                )
            return ClientValidationResult(target.client_id, failures=failures, details=details)
        except Exception as error:
            return ClientValidationResult(
                target.client_id,
                failures=[
                    f"[Geral] Cliente '{target.client_id}' | falha ao validar o índice RSA "
                    f"'{RSA_INDEX_NAME}': {error.__class__.__name__}: {error}"
                ],
            )
