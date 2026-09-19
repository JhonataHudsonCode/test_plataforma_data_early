from __future__ import annotations

import importlib
import pkgutil
from datetime import date
from pathlib import Path
from typing import Any

from src.validators.after_pipeline.oto_dashboard.section_validator import (
    OtoDashboardSectionValidator,
)


class OtoDashboardDocumentValidator:
    """Encaminha cada objeto pai do `_source` ao seu validador específico."""

    def __init__(self, reference_date: date) -> None:
        self._section_validators = self._discover_section_validators(reference_date)

    def validate(
        self,
        index_name: str,
        latest_source: dict[str, Any],
        previous_source: dict[str, Any],
        errors: list[str],
        details: list[str],
    ) -> None:
        """Entrega o conteúdo bruto de cada seção aos validadores registrados."""
        for section_validator in self._section_validators:
            section_name = section_validator.section_name
            section_validator.validate(
                index_name,
                latest_source.get(section_name),
                previous_source.get(section_name),
                errors,
                details,
            )

    @staticmethod
    def _discover_section_validators(
        reference_date: date,
    ) -> tuple[OtoDashboardSectionValidator, ...]:
        package_name = __package__
        if package_name is None:
            raise RuntimeError("Não foi possível identificar o pacote dos validadores OTO.")

        package_path = Path(__file__).parent
        for module in pkgutil.iter_modules([str(package_path)]):
            if module.name.endswith("_validator") and module.name != "document_validator":
                importlib.import_module(f"{package_name}.{module.name}")

        validator_classes = sorted(
            OtoDashboardSectionValidator.__subclasses__(),
            key=lambda validator_class: validator_class.section_name,
        )
        return tuple(validator_class(reference_date) for validator_class in validator_classes)
