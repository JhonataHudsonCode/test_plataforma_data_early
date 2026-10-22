from __future__ import annotations

import os
import logging
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from typing import TypeVar


Target = TypeVar("Target")
Result = TypeVar("Result")

_DEFAULT_MAX_REQUESTS_PER_OPENSEARCH = 5
logger = logging.getLogger(__name__)


def _max_requests_per_opensearch() -> int:
    """Obtém o limite de validações simultâneas, nunca superior a cinco."""
    value = os.getenv(
        "OPENSEARCH_MAX_CONCURRENT_CLIENTS",
        os.getenv(
            "OPENSEARCH_MAX_CONCURRENT_REQUESTS",
            str(_DEFAULT_MAX_REQUESTS_PER_OPENSEARCH),
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

    return min(configured_limit, _DEFAULT_MAX_REQUESTS_PER_OPENSEARCH)


def validate_targets_by_opensearch(
    targets: Iterable[Target],
    validate: Callable[[Target], Result],
    opensearch_key: Callable[[Target], str | None],
) -> list[Result]:
    """Executa validações concorrentes sem exceder cinco por OpenSearch.

    A chave identifica o endpoint que receberá as chamadas. Cada validação faz
    suas próprias requisições de forma sequencial; portanto, limitar as
    validações simultâneas limita as requisições simultâneas por endpoint.
    A ordem retornada acompanha a ordem dos alvos recebidos.
    """
    items = list(targets)
    if not items:
        return []

    limit = _max_requests_per_opensearch()
    keys = {opensearch_key(target) or "__default__" for target in items}
    max_workers = min(len(items), limit * len(keys))

    from threading import BoundedSemaphore, Lock

    semaphores: dict[str, BoundedSemaphore] = {}
    semaphore_lock = Lock()

    def run(target: Target) -> Result:
        key = opensearch_key(target) or "__default__"
        with semaphore_lock:
            semaphore = semaphores.setdefault(key, BoundedSemaphore(limit))
        with semaphore:
            return validate(target)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        return list(executor.map(run, items))


def validate_targets_on_product_opensearch(
    targets: Iterable[Target],
    validate: Callable[[Target], Result],
) -> list[Result]:
    """Executa no máximo cinco validações no OpenSearch de produto compartilhado."""
    items = list(targets)
    if not items:
        return []

    limit = min(len(items), _max_requests_per_opensearch())
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
        results.extend(
            validate_targets_by_opensearch(batch, validate_with_log, lambda _target: "product")
        )

    return results
