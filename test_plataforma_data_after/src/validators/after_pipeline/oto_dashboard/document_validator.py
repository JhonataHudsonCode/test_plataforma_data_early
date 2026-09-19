from __future__ import annotations

from datetime import date
from typing import Any

from src.validators.after_pipeline.oto_dashboard.score_data_validator import (
    OtoScoreDataValidator,
)
from src.validators.after_pipeline.oto_dashboard.rsa_data_validator import (
    OtoRsaDataValidator,
)


class OtoDashboardDocumentValidator:
    """Encaminha cada objeto pai do `_source` ao seu validador específico."""

    def __init__(self, reference_date: date) -> None:
        reference_month = reference_date.strftime("%Y-%m")
        self._section_validators = {
            "score_data": OtoScoreDataValidator(reference_month),
            "rsa_data": OtoRsaDataValidator(),
        }

    def validate(
        self,
        index_name: str,
        latest_source: dict[str, Any],
        previous_source: dict[str, Any],
        errors: list[str],
        details: list[str],
    ) -> None:
        """Entrega o conteúdo bruto de cada seção aos validadores registrados."""
        for section_name, section_validator in self._section_validators.items():
            section_validator.validate(
                index_name,
                latest_source.get(section_name),
                previous_source.get(section_name),
                errors,
                details,
            )
