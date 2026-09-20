from __future__ import annotations

from src.repositories.opensearch_vulnerability_repository import (
    OpenSearchVulnerabilityRepository,
)


class OpenSearchAliasesValidator:
    """Valida se cada alias aponta para um índice do seu próprio prefixo."""

    def __init__(self, repository: OpenSearchVulnerabilityRepository) -> None:
        self._repository = repository

    def validate(self) -> tuple[list[str], list[str]]:
        try:
            aliases = self._repository.get_aliases()
        except RuntimeError as error:
            return [str(error)], []

        if not aliases:
            return ["Ambiente OpenSearch | Nenhum alias foi encontrado."], []

        errors: list[str] = []
        valid_aliases = 0
        for alias_data in aliases:
            alias = alias_data["alias"].strip()
            index_name = alias_data["index"].strip()

            if self._has_matching_prefix(alias, index_name):
                valid_aliases += 1
                continue

            errors.append(
                "Ambiente OpenSearch | "
                f"Alias '{alias}' aponta para o índice '{index_name}', "
                "mas o prefixo do índice não corresponde ao alias."
            )

        details = [
            "Ambiente OpenSearch | "
            f"{valid_aliases} alias(es) apontam para índices com o prefixo esperado."
        ]
        return errors, details

    @staticmethod
    def _has_matching_prefix(alias: str, index_name: str) -> bool:
        return bool(alias) and index_name.startswith(alias)
