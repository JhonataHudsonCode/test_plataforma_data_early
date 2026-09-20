from __future__ import annotations

import importlib
import json
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

        validator_classes_by_section = {
            validator_class.section_name: validator_class
            for validator_class in OtoDashboardSectionValidator.__subclasses__()
        }
        validation_order = OtoDashboardDocumentValidator._load_validation_order()
        configured_classes = [
            validator_classes_by_section.pop(section_name)
            for section_name in validation_order
            if section_name in validator_classes_by_section
        ]
        validator_classes = configured_classes + sorted(
            validator_classes_by_section.values(),
            key=lambda validator_class: validator_class.section_name,
        )
        return tuple(validator_class(reference_date) for validator_class in validator_classes)

    @classmethod
    def _load_validation_order(cls) -> list[str]:
        configuration = json.loads(cls._VALIDATION_ORDER_PATH.read_text(encoding="utf-8"))
        sections = configuration.get("sections")
        if (
            not isinstance(sections, list)
            or not all(isinstance(section, str) for section in sections)
            or len(sections) != len(set(sections))
        ):
            raise ValueError(
                "validation_order.json deve possuir uma lista de seções únicas em 'sections'."
            )
        return sections
    _VALIDATION_ORDER_PATH = Path(__file__).with_name("validation_order.json")
