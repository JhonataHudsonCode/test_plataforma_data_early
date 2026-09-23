from __future__ import annotations

from uuid import UUID

from src.config.settings import ClientTarget
from src.models.client_validation_result import ClientValidationResult
from src.queries.assets_client_queries import SELECT_ASSETS_CLIENT_ACTIVATION_KEY_IDS
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

        duplicate_names = self._duplicate_names(keys)
        if duplicate_names:
            return ClientValidationResult(
                target.client_id,
                failures=[
                    f"Cliente '{target.client_id}' possui mais de uma chave de ativação "
                    f"com o mesmo activation_key_name: {', '.join(duplicate_names)}."
                ],
            )

        invalid_ids = [
            value
            for key in keys
            if not self._is_uuid_string(value := key.get("activation_key_id"))
        ]
        if invalid_ids:
            return ClientValidationResult(
                target.client_id,
                failures=[
                    f"Cliente '{target.client_id}' possui activation_key_id inválido: "
                    f"{', '.join(repr(value) for value in invalid_ids)}."
                ],
            )
        return ClientValidationResult(
            target.client_id,
            details=[
                f"Cliente '{target.client_id}' possui {len(keys)} activation_key_id "
                "preenchido(s) no formato UUID."
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

    @staticmethod
    def _duplicate_names(keys: list[dict[str, object]]) -> list[str]:
        names: dict[str, int] = {}
        for key in keys:
            name = str(key.get("activation_key_name") or "não informado").strip()
            normalized_name = name.casefold()
            names[normalized_name] = names.get(normalized_name, 0) + 1
        return [name for name, count in names.items() if count > 1]
