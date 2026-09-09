from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class AssetsTableMetadata:
    created_at: datetime | None
    updated_at: datetime | None