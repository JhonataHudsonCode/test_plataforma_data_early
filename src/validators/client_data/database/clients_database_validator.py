from __future__ import annotations

from src.config.settings import ClientTarget
from src.models.client_validation_result import ClientValidationResult
from src.models.opensearch_client.alert_clients_mapping import ALERT_CLIENTS_INDEX_NAME
from src.models.opensearch_client.clients_mapping import CLIENTS_INDEX_NAME
from src.queries.clients_queries import SELECT_ALERT_CLIENT_BY_ID, SELECT_CLIENT_BY_ID
from src.queries.cognito_client_queries import SELECT_COGNITO_CLIENT_HAS_BART_BY_ID, SELECT_ID_CLIENTS
from src.repositories.db_client_repository import DataBaseRepository


class ClientsDatabaseValidator:
    def __init__(self, cognito_repository: DataBaseRepository, clients_repository: DataBaseRepository) -> None:
        self._cognito_repository = cognito_repository
        self._clients_repository = clients_repository

    def validate(self, target: ClientTarget) -> ClientValidationResult:
        client = self._cognito_repository.get_table("public", target.client_id, SELECT_COGNITO_CLIENT_HAS_BART_BY_ID)
        if not client:
            return ClientValidationResult(target.client_id, failures=[f"Cliente '{target.client_id}' não encontrado no Cognito; consulta de has_bart não retornou registro."])
        if not client.get("has_bart"):
            return ClientValidationResult(target.client_id, infos=[f"Cliente '{target.client_id}' possui has_bart desabilitado; tabelas clients e alertClients não aplicáveis."])

        id_row = self._clients_repository.get_table("public", target.client_id, SELECT_ID_CLIENTS)
        if not id_row or id_row.get("id") is None:
            return ClientValidationResult(target.client_id, failures=[f"Cliente '{target.client_id}' | tabela 'clients' | não foi possível obter o id para consultar alertClients."])
        return ClientValidationResult(target.client_id, failures=self._validate_tables(target.client_id, id_row["id"]))

    def _validate_tables(self, client_id: str, id_client: object) -> list[str]:
        failures: list[str] = []
        for table_name, lookup_value, query in (
            (CLIENTS_INDEX_NAME, client_id, SELECT_CLIENT_BY_ID),
            (ALERT_CLIENTS_INDEX_NAME, id_client, SELECT_ALERT_CLIENT_BY_ID),
        ):
            row = self._clients_repository.get_table("public", lookup_value, query)
            if not row:
                failures.append(f"Cliente '{client_id}' | tabela '{table_name}' | nenhum registro encontrado no database clients.")
                continue
            for field_name in ("createdAt", "updatedAt"):
                if row.get(field_name) is None:
                    failures.append(f"Cliente '{client_id}' | tabela '{table_name}' | coluna '{field_name}' sem dados.")
        return failures
