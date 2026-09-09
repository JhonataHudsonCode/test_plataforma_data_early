from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class OpenSearchIndexMetadata:
    """Metadados necessários para validar um índice do OpenSearch."""

    name: str
    created_at: datetime
    mapping: dict[str, Any]
