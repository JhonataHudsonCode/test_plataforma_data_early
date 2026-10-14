from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AssetsClientMetadata:
    id: int
    client_id: str
    activation_key_id: str
    activation_key_name: str