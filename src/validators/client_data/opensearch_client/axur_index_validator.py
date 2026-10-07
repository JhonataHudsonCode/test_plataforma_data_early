from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime

from src.config.settings import ClientTarget
from src.models.client_validation_result import ClientValidationResult
from src.models.opensearch_product.axur_mapping import AXUR_INDEX_NAME, EXPECTED_AXUR_MAPPING
from src.queries.cognito_client_queries import SELECT_COGNITO_CLIENT_HAS_AXUR_BY_ID
from src.repositories.db_client_repository import DataBaseRepository
from src.repositories.opensearch_client_rsa_repository import OpenSearchClientRepository
from src.validators.opensearch_mapping_validator import OpenSearchMappingValidator


class AxurIndexValidator:
    """Valida documentos recentes e o contrato do índice Axur por cliente."""

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
            "public", target.client_id, SELECT_COGNITO_CLIENT_HAS_AXUR_BY_ID
        )
        if not client:
            return ClientValidationResult(
                target.client_id,
                failures=[
                    f"[Geral] Cliente '{target.client_id}' não encontrado no Cognito; "
                    "consulta de has_axur não retornou registro."
                ],
                not_executed=self._not_executed_stages(
                    target.client_id,
                    "cliente não disponível para a validação Axur",
                    "Mapping",
                    "Timestamp",
                ),
            )
        if "has_axur" not in client:
            return ClientValidationResult(
                target.client_id,
                failures=[f"[Geral] Cliente '{target.client_id}' | tabela 'public.clients' do Cognito não retornou a coluna 'has_axur'."],
                not_executed=self._not_executed_stages(
                    target.client_id,
                    "coluna has_axur não retornada pelo Cognito",
                    "Mapping",
                    "Timestamp",
                ),
            )
        cognito_validation = f"[Geral] Cliente '{target.client_id}' | tabela 'public.clients' do Cognito | coluna 'has_axur' encontrada com valor {'habilitado' if client['has_axur'] else 'desabilitado'}."
        if not client["has_axur"]:
            return ClientValidationResult(
                target.client_id,
                infos=[
                    f"[Geral] Cliente '{target.client_id}' possui has_axur desabilitado; "
                    "índice Axur não aplicável."
                ],
                details=[cognito_validation],
                not_executed=self._not_executed_stages(
                    target.client_id,
                    "has_axur desabilitado",
                    "Mapping",
                    "Timestamp",
                ),
            )

        host = target.host or client["octopus_endpoint"].replace("https://", "")
        failures: list[str] = []
        details: list[str] = [cognito_validation]
        try:
            indices = self._opensearch_repository.get_indices_axur(host, AXUR_INDEX_NAME)
            index = {item.name: item for item in indices}.get(AXUR_INDEX_NAME)
            if index is None:
                failures.append(
                    f"[Geral] Cliente '{target.client_id}' | índice Axur "
                    f"'{AXUR_INDEX_NAME}' não encontrado no OpenSearch do cliente."
                )
                return ClientValidationResult(
                    target.client_id,
                    failures=failures,
                    details=details,
                    not_executed=self._not_executed_stages(
                        target.client_id,
                        "índice Axur não encontrado",
                        "Mapping",
                        "Timestamp",
                    ),
                )
            if index.document_count <= 0:
                failures.append(
                    f"[Geral] Cliente '{target.client_id}' | índice Axur "
                    f"'{AXUR_INDEX_NAME}' não contém documentos."
                )
                return ClientValidationResult(
                    target.client_id,
                    failures=failures,
                    details=details,
                    not_executed=self._not_executed_stages(
                        target.client_id,
                        "índice Axur sem documentos",
                        "Mapping",
                        "Timestamp",
                    ),
                )

            details.append(
                f"[Geral] Cliente '{target.client_id}' | índice Axur '{AXUR_INDEX_NAME}' "
                f"encontrado com {index.document_count} documento(s)."
            )
            start_date = self._subtract_months(self._reference_date, months=3)
            documents = self._opensearch_repository.get_documents_by_timestamp_range(
                host,
                AXUR_INDEX_NAME,
                start_date=start_date,
                end_date=self._reference_date,
                size=index.document_count,
            )
            if not documents:
                failures.append(
                    f"[Timestamp] Cliente '{target.client_id}' | índice Axur "
                    f"'{AXUR_INDEX_NAME}' | nenhum documento retornado com @timestamp "
                    f"entre {start_date.isoformat()} e {self._reference_date.isoformat()}."
                )
                return ClientValidationResult(
                    target.client_id,
                    failures=failures,
                    details=details,
                    not_executed=self._not_executed_stages(
                        target.client_id,
                        "nenhum documento disponível para validar a estrutura",
                        "Mapping",
                    ),
                )

            self._validate_first_document_mapping(
                target.client_id, host, documents, failures, details
            )
            self._validate_document_timestamps(
                target.client_id, documents, start_date, failures, details
            )
        except Exception as error:
            failures.append(
                f"[Geral] Cliente '{target.client_id}' | host '{host}' | falha ao validar "
                f"o índice Axur: {error.__class__.__name__}: {error}"
            )
        not_executed = (
            self._not_executed_stages(
                target.client_id,
                "falha inesperada durante a validação do índice Axur",
                "Mapping",
                "Timestamp",
            )
            if failures and not any(message.startswith("[Mapping]") or message.startswith("[Timestamp]") for message in failures + details)
            else []
        )
        return ClientValidationResult(
            target.client_id,
            failures=failures,
            details=details,
            not_executed=not_executed,
        )

    @staticmethod
    def _not_executed_stages(
        client_id: str,
        reason: str,
        *stages: str,
    ) -> list[str]:
        return [
            f"[{stage}] Cliente '{client_id}' | etapa não executada: {reason}."
            for stage in stages
        ]

    @staticmethod
    def _validate_first_document_mapping(
        client_id: str,
        host: str,
        documents: list[dict],
        failures: list[str],
        details: list[str],
    ) -> None:
        document = documents[0]
        document_id = document.get("_id", "não informado")
        mapping_errors = OpenSearchMappingValidator().validate_document(
            document.get("_source", {}),
            EXPECTED_AXUR_MAPPING,
        )
        failures.extend(
            f"[Mapping] Cliente '{client_id}' | índice Axur '{AXUR_INDEX_NAME}' | "
            f"host '{host}' | primeiro documento (_id={document_id}) com mapping "
            f"inválido: {error}"
            for error in mapping_errors
        )
        if not mapping_errors:
            details.append(
                f"[Mapping] Índice Axur '{AXUR_INDEX_NAME}' | mapping do primeiro "
                f"documento (_id={document_id}) validado com sucesso."
            )

    def _validate_document_timestamps(
        self,
        client_id: str,
        documents: list[dict],
        start_date: date,
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
            if not start_date <= timestamp_date <= self._reference_date:
                invalid_documents.append(
                    f"_id={document_id} (@timestamp fora do intervalo: {timestamp})"
                )

        if invalid_documents:
            failures.append(
                f"[Timestamp] Cliente '{client_id}' | índice Axur '{AXUR_INDEX_NAME}' | "
                f"{len(invalid_documents)} de {len(documents)} documento(s) com "
                f"@timestamp ausente, inválido ou fora do intervalo de "
                f"{start_date.isoformat()} a {self._reference_date.isoformat()}: "
                f"{', '.join(invalid_documents)}."
            )
            return
        details.append(
            f"[Timestamp] Índice Axur '{AXUR_INDEX_NAME}' | consulta por @timestamp "
            f"entre {start_date.isoformat()} e {self._reference_date.isoformat()} retornou "
            f"{len(documents)} documento(s), todos validados."
        )

    @staticmethod
    def _subtract_months(reference_date: date, months: int) -> date:
        month_index = reference_date.year * 12 + reference_date.month - 1 - months
        year, month_zero_based = divmod(month_index, 12)
        month = month_zero_based + 1
        return date(year, month, min(reference_date.day, monthrange(year, month)[1]))
