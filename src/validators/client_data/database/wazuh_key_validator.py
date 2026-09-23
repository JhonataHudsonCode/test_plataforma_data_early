from __future__ import annotations

from uuid import UUID

from src.config.settings import ClientTarget
from src.models.client_validation_result import ClientValidationResult
from src.queries.assets_client_queries import SELECT_ASSETS_CLIENT_ACTIVATION_KEY_IDS
from src.queries.cognito_client_queries import SELECT_COGNITO_CLIENT_HAS_WAZUH_BY_ID
from src.repositories.db_client_repository import DataBaseRepository


class WazuhKeyValidator:
    def __init__(self, cognito_repository: DataBaseRepository, assets_repository: DataBaseRepository) -> None:
        self._cognito_repository = cognito_repository
        self._assets_repository = assets_repository

    def validate(self, target: ClientTarget) -> ClientValidationResult:
        client = self._cognito_repository.get_table("public", target.client_id, SELECT_COGNITO_CLIENT_HAS_WAZUH_BY_ID)
        if not client:
            return ClientValidationResult(target.client_id, failures=[f"Cliente '{target.client_id}' não encontrado no Cognito; consulta de has_wazuh não retornou registro."])
        if not client.get("has_wazuh"):
            return ClientValidationResult(target.client_id, infos=[f"Cliente '{target.client_id}' possui has_wazuh desabilitado; chave de ativação não aplicável."])
        keys = self._assets_repository.get_activation_keys(
            "public",
            target.client_id,
            SELECT_ASSETS_CLIENT_ACTIVATION_KEY_IDS,
        )
        if not keys:
            return ClientValidationResult(
                target.client_id,
                failures=[f"Cliente '{target.client_id}' não possui chave de ativação cadastrada."],
            )
        if len(keys) > 1:
            return ClientValidationResult(
                target.client_id,
                failures=[
                    f"Cliente '{target.client_id}' possui "
                    f"{len(keys)} registros cadastrados; era esperado apenas 1."
                ],
            )

        activation_key_id = keys[0].get("activation_key_id")
        if not self._is_uuid_string(activation_key_id):
            return ClientValidationResult(
                target.client_id,
                failures=[
                    f"Chave do Wazuh do cliente '{target.client_id}' possui "
                    f"activation_key_id inválido: {activation_key_id!r}."
                ],
            )
        return ClientValidationResult(
            target.client_id,
            details=[
                f"Chave do Wazuh do cliente '{target.client_id}' possui "
                "activation_key_id preenchido no formato UUID."
            ],
        )

    @staticmethod
    def _is_uuid_string(value: object) -> bool:
        if not isinstance(value, str):
            return False
        try:
            return str(UUID(value)) == value.lower()
        except (AttributeError, TypeError, ValueError):
            return False
