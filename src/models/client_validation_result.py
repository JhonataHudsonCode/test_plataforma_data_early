from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ClientValidationResult:
    """Resultado independente da tecnologia usada na validação do cliente."""

    client_id: str
    failures: list[str] = field(default_factory=list)
    infos: list[str] = field(default_factory=list)
    details: list[str] = field(default_factory=list)
