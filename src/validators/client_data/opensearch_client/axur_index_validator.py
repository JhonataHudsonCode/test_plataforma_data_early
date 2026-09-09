from __future__ import annotations

from datetime import date

from src.config.settings import ClientTarget
from src.models.client_validation_result import ClientValidationResult
from src.models.opensearch_product.axur_mapping import AXUR_INDEX_NAME, EXPECTED_AXUR_MAPPING
from src.queries.cognito_client_queries import SELECT_COGNITO_CLIENT_HAS_AXUR_BY_ID
from src.repositories.db_client_repository import DataBaseRepository
from src.repositories.opensearch_client_rsa_repository import OpenSearchClientRepository
from src.validators.opensearch_mapping_validator import OpenSearchMappingValidator


class AxurIndexValidator:
    def __init__(self, cognito_repository: DataBaseRepository, opensearch_repository: OpenSearchClientRepository, reference_date: date) -> None:
        self._cognito_repository = cognito_repository
        self._opensearch_repository = opensearch_repository
        self._reference_date = reference_date

    def validate(self, target: ClientTarget) -> ClientValidationResult:
        client = self._cognito_repository.get_table("public", target.client_id, SELECT_COGNITO_CLIENT_HAS_AXUR_BY_ID)
        if not client:
            return ClientValidationResult(target.client_id, failures=[f"Cliente '{target.client_id}' não encontrado no Cognito; consulta de has_axur não retornou registro."])
        if not client.get("has_axur"):
            return ClientValidationResult(target.client_id, infos=[f"Cliente '{target.client_id}' possui has_axur desabilitado; índice Axur não aplicável."])
        host = target.host or client["octopus_endpoint"].replace("https://", "")
        failures: list[str] = []
        try:
            indices = self._opensearch_repository.get_indices_axur(host, AXUR_INDEX_NAME)
            index = {item.name: item for item in indices}.get(AXUR_INDEX_NAME)
            if index is None:
                failures.append(f"Cliente '{target.client_id}' | índice Axur '{AXUR_INDEX_NAME}' não encontrado no OpenSearch do cliente.")
            elif index.document_count <= 0:
                failures.append(f"Cliente '{target.client_id}' | índice Axur '{AXUR_INDEX_NAME}' não contém documentos.")
            metadata = self._opensearch_repository.get_index_metadata(host, AXUR_INDEX_NAME)
            if metadata.created_at.date() != self._reference_date:
                failures.append(f"Cliente '{target.client_id}' | índice Axur '{AXUR_INDEX_NAME}' foi criado em '{metadata.created_at:%Y-%m-%d}', esperada '{self._reference_date:%Y-%m-%d}'. Host: '{host}'.")
            if not metadata.mapping:
                failures.append(f"Cliente '{target.client_id}' | índice Axur '{AXUR_INDEX_NAME}' não possui mapping configurado. Host: '{host}'.")
            else:
                failures.extend(f"Cliente '{target.client_id}' | índice Axur '{AXUR_INDEX_NAME}' | mapping inválido: {error}" for error in OpenSearchMappingValidator().validate(metadata.mapping.get("properties", {}), EXPECTED_AXUR_MAPPING))
        except Exception as error:
            failures.append(f"Cliente '{target.client_id}' | host '{host}' | falha ao validar o índice Axur: {error.__class__.__name__}: {error}")
        return ClientValidationResult(target.client_id, failures=failures)
