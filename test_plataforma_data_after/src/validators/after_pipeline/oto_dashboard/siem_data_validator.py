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


class OtoSiemDataValidator(OtoDashboardSectionValidator):
    """Valida os indicadores de melhoria dentro de `siem_data`."""

    section_name = "siem_data"
    _CONFIGURATION_PATH = Path(__file__).with_name("siem_data_validation_controls.json")

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
        latest_siem_data: object,
        previous_siem_data: object,
        errors: list[str],
        details: list[str],
    ) -> None:
        if not isinstance(latest_siem_data, dict):
            errors.append(
                f"Índice '{index_name}' | seção **siem_data** ausente ou inválida "
                "no documento mais recente."
            )
            return
        if not isinstance(previous_siem_data, dict):
            errors.append(
                f"Índice '{index_name}' | seção **siem_data** ausente ou inválida "
                "no documento do dia anterior."
            )
            return

        try:
            value_fields, object_name, improvement_fields, variation_control_prefix = (
                self._load_controls()
            )
        except (OSError, ValueError, json.JSONDecodeError) as error:
            errors.append(
                f"Índice '{index_name}' | erro ao carregar controles de siem_data: "
                f"{error.__class__.__name__}: {error}"
            )
            return

        self._validate_fields(
            index_name,
            latest_siem_data,
            previous_siem_data,
            value_fields,
            "siem_data.",
            "siem_data.",
            errors,
            details,
        )

        latest_improvement = latest_siem_data.get(object_name)
        previous_improvement = previous_siem_data.get(object_name)
        if not isinstance(latest_improvement, dict):
            errors.append(
                f"Índice '{index_name}' | seção **siem_data.{object_name}** ausente ou "
                "inválida no documento mais recente."
            )
            return
        if not isinstance(previous_improvement, dict):
            errors.append(
                f"Índice '{index_name}' | seção **siem_data.{object_name}** ausente ou "
                "inválida no documento do dia anterior."
            )
            return

        self._validate_fields(
            index_name,
            latest_improvement,
            previous_improvement,
            improvement_fields,
            f"siem_data.{object_name}.",
            variation_control_prefix,
            errors,
            details,
        )

    def _validate_fields(
        self,
        index_name: str,
        latest_values: dict[str, Any],
        previous_values: dict[str, Any],
        fields: dict[str, str],
        attribute_prefix: str,
        variation_control_prefix: str,
        errors: list[str],
        details: list[str],
    ) -> None:
        for field_name, expected_type in fields.items():
            attribute_path = f"{attribute_prefix}{field_name}"
            latest_value = latest_values.get(field_name)
            previous_value = previous_values.get(field_name)
            if not self._matches_type(latest_value, expected_type):
                errors.append(
                    f"Índice '{index_name}' | atributo **{attribute_path}** deve ser "
                    f"{expected_type} no documento mais recente; recebido {latest_value!r}."
                )
                continue
            if not self._matches_type(previous_value, expected_type):
                errors.append(
                    f"Índice '{index_name}' | atributo **{attribute_path}** deve ser "
                    f"{expected_type} no documento do dia anterior; recebido {previous_value!r}."
                )
                continue

            self._validate_variation(
                index_name,
                attribute_prefix.rstrip("."),
                attribute_path,
                float(latest_value),
                float(previous_value),
                f"{variation_control_prefix}{field_name}",
                errors,
                details,
            )

    def _validate_variation(
        self,
        index_name: str,
        section_path: str,
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
            f"Índice '{index_name}' | seção **{section_path}** | atributo "
            f"**{attribute_path}**: anterior={previous_value}, mais recente={latest_value}, "
            f"variação={variation}; limites: +{limits.maximum_increase:.0%}/"
            f"-{limits.maximum_decrease:.0%}."
        )
        details.append(message)
        if not result.is_valid:
            errors.append(f"{message} Erro: {result.reason}.")

    def _load_controls(self) -> tuple[dict[str, str], str, dict[str, str], str]:
        controls: dict[str, Any] = json.loads(
            self._configuration_path.read_text(encoding="utf-8")
        )
        value_fields = controls.get("value_fields")
        object_name = controls.get("object_name")
        improvement_fields = controls.get("fields")
        variation_control_prefix = controls.get("variation_control_prefix")
        if (
            not isinstance(value_fields, dict)
            or not value_fields
            or not isinstance(object_name, str)
            or not isinstance(improvement_fields, dict)
            or not improvement_fields
            or not all(
                isinstance(field_name, str) and expected_type in {"float", "int"}
                for field_name, expected_type in value_fields.items()
            )
            or not all(
                isinstance(field_name, str) and expected_type in {"float", "int"}
                for field_name, expected_type in improvement_fields.items()
            )
            or not isinstance(variation_control_prefix, str)
        ):
            raise ValueError(
                "Os controles devem informar object_name, fields e variation_control_prefix válidos."
            )
        return value_fields, object_name, improvement_fields, variation_control_prefix

    @staticmethod
    def _matches_type(value: object, expected_type: str) -> bool:
        if isinstance(value, bool):
            return False
        return isinstance(value, float) if expected_type == "float" else isinstance(value, int)
