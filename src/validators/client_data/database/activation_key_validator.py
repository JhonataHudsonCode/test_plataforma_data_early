from __future__ import annotations

from src.config.settings import ClientTarget
from src.models.client_validation_result import ClientValidationResult
from src.queries.assets_client_queries import SELECT_ASSETS_CLIENT_ACTIVATION_KEYS
from src.queries.cognito_client_queries import SELECT_COGNITO_CLIENT_HAS_BART_BY_ID
from src.repositories.db_client_repository import DataBaseRepository


class ActivationKeyValidator:
    def __init__(self, cognito_repository: DataBaseRepository, assets_repository: DataBaseRepository) -> None:
        self._cognito_repository = cognito_repository
        self._assets_repository = assets_repository

    def validate(self, target: ClientTarget) -> ClientValidationResult:
        client = self._cognito_repository.get_table("public", target.client_id, SELECT_COGNITO_CLIENT_HAS_BART_BY_ID)
        if not client:
            return ClientValidationResult(target.client_id, failures=[f"Cliente '{target.client_id}' não encontrado no Cognito; consulta de has_bart não retornou registro."])
        if not client.get("has_bart"):
            return ClientValidationResult(target.client_id, infos=[f"Cliente '{target.client_id}' possui has_bart desabilitado; chave de ativação não aplicável."])
        found = self._assets_repository.has_activation_key("public", target.client_id, target.activation_key_name or "", SELECT_ASSETS_CLIENT_ACTIVATION_KEYS)
        return ClientValidationResult(target.client_id, failures=[] if found else [f"Chave de ativação '{target.activation_key_name}' não encontrada."])
