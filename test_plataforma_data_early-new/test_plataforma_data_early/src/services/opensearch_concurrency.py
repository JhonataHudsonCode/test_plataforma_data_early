from __future__ import annotations

import os
import logging
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from typing import TypeVar


Target = TypeVar("Target")
Result = TypeVar("Result")

_DEFAULT_MAX_CONCURRENT_CLIENTS = 5
logger = logging.getLogger(__name__)


def _max_concurrent_client_validations() -> int:
    """Obtém o limite global de clientes validados simultaneamente."""
    value = os.getenv(
        "OPENSEARCH_MAX_CONCURRENT_CLIENTS",
        # Mantém compatibilidade com a configuração introduzida anteriormente.
        os.getenv(
            "OPENSEARCH_MAX_CONCURRENT_REQUESTS",
            str(_DEFAULT_MAX_CONCURRENT_CLIENTS),
        ),
    )
    try:
        configured_limit = int(value)
    except ValueError as error:
        raise ValueError(
            "OPENSEARCH_MAX_CONCURRENT_CLIENTS deve ser um número inteiro entre 1 e 5."
        ) from error

    if configured_limit < 1:
        raise ValueError(
            "OPENSEARCH_MAX_CONCURRENT_CLIENTS deve ser um número inteiro entre 1 e 5."
        )

    return min(configured_limit, _DEFAULT_MAX_CONCURRENT_CLIENTS)


def validate_client_targets(
    targets: Iterable[Target],
    validate: Callable[[Target], Result],
) -> list[Result]:
    """Valida no máximo cinco clientes simultaneamente em um cenário.

    O limite é por cenário de teste, não por host. Portanto, com 246 clientes
    e limite cinco, somente cinco clientes terão consultas em seus respectivos
    endpoints Octopus em andamento por vez. A ordem retornada acompanha a dos
    alvos recebidos.
    """
    items = list(targets)
    if not items:
        return []

    max_workers = min(len(items), _max_concurrent_client_validations())
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        return list(executor.map(validate, items))


def validate_targets_on_product_opensearch(
    targets: Iterable[Target],
    validate: Callable[[Target], Result],
) -> list[Result]:
    """Executa no máximo cinco validações no OpenSearch de produto compartilhado."""
    items = list(targets)
    if not items:
        return []

    limit = min(len(items), _max_concurrent_client_validations())
    logger.info(
        "OpenSearch de produto | %s cliente(s) encontrado(s); lotes de até %s cliente(s).",
        len(items),
        limit,
    )

    def validate_with_log(target: Target) -> Result:
        client_id = str(getattr(target, "client_id", target))
        logger.info("OpenSearch de produto | iniciando validação do cliente %s.", client_id)
        try:
            result = validate(target)
        except Exception:
            logger.exception("OpenSearch de produto | falha no cliente %s.", client_id)
            raise
        logger.info("OpenSearch de produto | validação concluída para o cliente %s.", client_id)
        return result

    results: list[Result] = []
    for start in range(0, len(items), limit):
        batch = items[start : start + limit]
        batch_number = start // limit + 1
        client_ids = ", ".join(
            str(getattr(target, "client_id", target)) for target in batch
        )
        logger.info(
            "OpenSearch de produto | lote %s | clientes: %s.",
            batch_number,
            client_ids,
        )
        results.extend(validate_client_targets(batch, validate_with_log))

    return results
