from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from src.validators.after_pipeline.controllers.oto_score_variation_controller import (
    OtoScoreVariationController,
)
from src.validators.after_pipeline.oto_dashboard.section_validator import (
    OtoDashboardSectionValidator,
)


class OtoAssessmentDataValidator(OtoDashboardSectionValidator):
    """Valida os indicadores de melhoria dentro de `assessment_data`."""

    section_name = "assessment_data"
    _CONFIGURATION_PATH = Path(__file__).with_name("assessment_data_validation_controls.json")

    def __init__(
        self,
        reference_date: date,
        variation_controller: OtoScoreVariationController | None = None,
        configuration_path: Path | None = None,
    ) -> None:
        del reference_date
        self._variation_controller = variation_controller or OtoScoreVariationController()
        self._configuration_path = configuration_path or self._CONFIGURATION_PATH

    def validate(
        self,
        index_name: str,
        latest_assessment_data: object,
        previous_assessment_data: object,
        errors: list[str],
        details: list[str],
    ) -> None:
        if not isinstance(latest_assessment_data, dict):
            errors.append(
                f"Índice '{index_name}' | seção **assessment_data** ausente ou inválida "
                "no documento mais recente."
            )
            return
        if not isinstance(previous_assessment_data, dict):
            errors.append(
                f"Índice '{index_name}' | seção **assessment_data** ausente ou inválida "
                "no documento do dia anterior."
            )
            return

        try:
            object_name, fields, variation_control_prefix = self._load_controls()
        except (OSError, ValueError, json.JSONDecodeError) as error:
            errors.append(
                f"Índice '{index_name}' | erro ao carregar controles de assessment_data: "
                f"{error.__class__.__name__}: {error}"
            )
            return

        latest_improvement = latest_assessment_data.get(object_name)
        previous_improvement = previous_assessment_data.get(object_name)
        if not isinstance(latest_improvement, dict):
            errors.append(
                f"Índice '{index_name}' | seção **assessment_data.{object_name}** ausente ou "
                "inválida no documento mais recente."
            )
            return
        if not isinstance(previous_improvement, dict):
            errors.append(
                f"Índice '{index_name}' | seção **assessment_data.{object_name}** ausente ou "
                "inválida no documento do dia anterior."
            )
            return

        for field_name, expected_type in fields.items():
            attribute_path = f"assessment_data.{object_name}.{field_name}"
            latest_value = latest_improvement.get(field_name)
            previous_value = previous_improvement.get(field_name)
            if not self._is_float(latest_value):
                errors.append(
                    f"Índice '{index_name}' | atributo **{attribute_path}** deve ser "
                    f"{expected_type} no documento mais recente; recebido {latest_value!r}."
                )
                continue
            if not self._is_float(previous_value):
                errors.append(
                    f"Índice '{index_name}' | atributo **{attribute_path}** deve ser "
                    f"{expected_type} no documento do dia anterior; recebido {previous_value!r}."
                )
                continue

            self._validate_variation(
                index_name,
                attribute_path,
                latest_value,
                previous_value,
                f"{variation_control_prefix}{field_name}",
                errors,
                details,
            )

    def _validate_variation(
        self,
        index_name: str,
        attribute_path: str,
        latest_value: float,
        previous_value: float,
        variation_control: str,
        errors: list[str],
        details: list[str],
    ) -> None:
        try:
            limits = self._variation_controller.limits_for(variation_control)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            errors.append(
                f"Índice '{index_name}' | atributo **{attribute_path}** | erro ao carregar "
                f"controlador '{variation_control}': {error.__class__.__name__}: {error}"
            )
            return
        if limits is None:
            errors.append(
                f"Índice '{index_name}' | atributo **{attribute_path}** | controlador "
                f"'{variation_control}' não configurado."
            )
            return

        result = self._variation_controller.validate_percentage_variation(
            latest_value,
            previous_value,
            limits,
        )
        variation = "não calculável" if result.variation is None else f"{result.variation:.0%}"
        message = (
            f"Índice '{index_name}' | seção **assessment_data.improvement** | atributo "
            f"**{attribute_path}**: anterior={previous_value}, mais recente={latest_value}, "
            f"variação={variation}; limites: +{limits.maximum_increase:.0%}/"
            f"-{limits.maximum_decrease:.0%}."
        )
        details.append(message)
        if not result.is_valid:
            errors.append(f"{message} Erro: {result.reason}.")

    def _load_controls(self) -> tuple[str, dict[str, str], str]:
        controls: dict[str, Any] = json.loads(
            self._configuration_path.read_text(encoding="utf-8")
        )
        object_name = controls.get("object_name")
        fields = controls.get("fields")
        variation_control_prefix = controls.get("variation_control_prefix")
        if (
            not isinstance(object_name, str)
            or not isinstance(fields, dict)
            or not fields
            or not all(
                isinstance(field_name, str) and expected_type == "float"
                for field_name, expected_type in fields.items()
            )
            or not isinstance(variation_control_prefix, str)
        ):
            raise ValueError(
                "Os controles devem informar object_name, fields e variation_control_prefix válidos."
            )
        return object_name, fields, variation_control_prefix

    @staticmethod
    def _is_float(value: object) -> bool:
        return isinstance(value, float) and not isinstance(value, bool)
