from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ClientMetadata:
    client_id: str
    has_rsa: bool
    octopus_endpoint: str
    has_alerts: bool
    has_bart: bool
    has_asset: bool
