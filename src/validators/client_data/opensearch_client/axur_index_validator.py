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
            )
        if not client.get("has_axur"):
            return ClientValidationResult(
                target.client_id,
                infos=[
                    f"[Geral] Cliente '{target.client_id}' possui has_axur desabilitado; "
                    "índice Axur não aplicável."
                ],
            )

        host = target.host or client["octopus_endpoint"].replace("https://", "")
        failures: list[str] = []
        details: list[str] = []
        try:
            indices = self._opensearch_repository.get_indices_axur(host, AXUR_INDEX_NAME)
            index = {item.name: item for item in indices}.get(AXUR_INDEX_NAME)
            if index is None:
                failures.append(
                    f"[Geral] Cliente '{target.client_id}' | índice Axur "
                    f"'{AXUR_INDEX_NAME}' não encontrado no OpenSearch do cliente."
                )
                return ClientValidationResult(target.client_id, failures=failures)
            if index.document_count <= 0:
                failures.append(
                    f"[Geral] Cliente '{target.client_id}' | índice Axur "
                    f"'{AXUR_INDEX_NAME}' não contém documentos."
                )
                return ClientValidationResult(target.client_id, failures=failures)

            details.append(
                f"[Geral] Cliente '{target.client_id}' | índice Axur '{AXUR_INDEX_NAME}' "
                f"encontrado com {index.document_count} documento(s)."
            )
            documents = self._opensearch_repository.get_documents(
                host,
                AXUR_INDEX_NAME,
                size=index.document_count,
                sort_by_timestamp=True,
            )
            if not documents:
                failures.append(
                    f"[Geral] Cliente '{target.client_id}' | índice Axur "
                    f"'{AXUR_INDEX_NAME}' possui documentos na listagem, mas a consulta "
                    "não retornou documentos para validação."
                )
                return ClientValidationResult(
                    target.client_id,
                    failures=failures,
                    details=details,
                )

            self._validate_first_document_mapping(
                target.client_id, host, documents, failures, details
            )
            self._validate_document_timestamps(
                target.client_id, documents, failures, details
            )
        except Exception as error:
            failures.append(
                f"[Geral] Cliente '{target.client_id}' | host '{host}' | falha ao validar "
                f"o índice Axur: {error.__class__.__name__}: {error}"
            )
        return ClientValidationResult(target.client_id, failures=failures, details=details)

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
        failures: list[str],
        details: list[str],
    ) -> None:
        cutoff_date = self._subtract_months(self._reference_date, months=3)
        invalid_documents: list[str] = []
        historical_document: tuple[str, str] | None = None
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
            if timestamp_date > self._reference_date:
                invalid_documents.append(
                    f"_id={document_id} (@timestamp futuro: {timestamp})"
                )
                continue
            if timestamp_date <= cutoff_date and historical_document is None:
                historical_document = (document_id, timestamp)

        if invalid_documents:
            failures.append(
                f"[Timestamp] Cliente '{client_id}' | índice Axur '{AXUR_INDEX_NAME}' | "
                f"{len(invalid_documents)} de {len(documents)} documento(s) com "
                f"@timestamp ausente, inválido ou futuro: {', '.join(invalid_documents)}."
            )
        if historical_document is None:
            failures.append(
                f"[Timestamp] Cliente '{client_id}' | índice Axur '{AXUR_INDEX_NAME}' | "
                f"nenhum documento com @timestamp em {cutoff_date.isoformat()} ou antes; "
                "é esperado ao menos um documento de três meses atrás."
            )
            return
        if not invalid_documents:
            details.append(
                f"[Timestamp] Índice Axur '{AXUR_INDEX_NAME}' | @timestamp válido em "
                f"todos os {len(documents)} documento(s); histórico de três meses confirmado "
                f"no documento (_id={historical_document[0]}, @timestamp={historical_document[1]})."
            )

    @staticmethod
    def _subtract_months(reference_date: date, months: int) -> date:
        month_index = reference_date.year * 12 + reference_date.month - 1 - months
        year, month_zero_based = divmod(month_index, 12)
        month = month_zero_based + 1
        return date(year, month, min(reference_date.day, monthrange(year, month)[1]))
