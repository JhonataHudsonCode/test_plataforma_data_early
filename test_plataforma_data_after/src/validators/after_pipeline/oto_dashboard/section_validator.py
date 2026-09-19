from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import ClassVar


class OtoDashboardSectionValidator(ABC):
    """Contrato para validar um objeto pai do `_source` do OTO Dashboard."""

    section_name: ClassVar[str]

    @abstractmethod
    def __init__(self, reference_date: date) -> None:
        """Recebe a data de referência compartilhada pela execução."""

    @abstractmethod
    def validate(
        self,
        index_name: str,
        latest_section: object,
        previous_section: object,
        errors: list[str],
        details: list[str],
    ) -> None:
        """Compara a seção atual com a seção do documento anterior."""
