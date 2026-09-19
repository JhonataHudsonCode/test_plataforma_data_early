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


class OtoCisDataValidator(OtoDashboardSectionValidator):
    """Valida scores e indicadores de melhoria expostos por `cis_data`."""

    section_name = "cis_data"
    _CONFIGURATION_PATH = Path(__file__).with_name("cis_data_validation_controls.json")

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
        latest_cis_data: object,
        previous_cis_data: object,
        errors: list[str],
        details: list[str],
    ) -> None:
        if not isinstance(latest_cis_data, dict):
            errors.append(
                f"Índice '{index_name}' | seção **cis_data** ausente ou inválida "
                "no documento mais recente."
            )
            return
        if not isinstance(previous_cis_data, dict):
            errors.append(
                f"Índice '{index_name}' | seção **cis_data** ausente ou inválida "
                "no documento do dia anterior."
            )
            return

        try:
            value_fields, nested_objects, variation_control_prefix = self._load_controls()
        except (OSError, ValueError, json.JSONDecodeError) as error:
            errors.append(
                f"Índice '{index_name}' | erro ao carregar controles de cis_data: "
                f"{error.__class__.__name__}: {error}"
            )
            return

        self._validate_values(
            index_name,
            latest_cis_data,
            previous_cis_data,
            value_fields,
            "",
            variation_control_prefix,
            errors,
            details,
        )
        for object_name, fields in nested_objects.items():
            latest_object = latest_cis_data.get(object_name)
            previous_object = previous_cis_data.get(object_name)
            object_path = f"cis_data.{object_name}"
            if not isinstance(latest_object, dict) or not isinstance(previous_object, dict):
                errors.append(
                    f"Índice '{index_name}' | seção **{object_path}** ausente ou inválida "
                    "em um dos documentos comparados."
                )
                continue
            self._validate_values(
                index_name,
                latest_object,
                previous_object,
                fields,
                f"{object_name}.",
                variation_control_prefix,
                errors,
                details,
            )

    def _validate_values(
        self,
        index_name: str,
        latest_values: dict[str, Any],
        previous_values: dict[str, Any],
        fields: list[str],
        path_prefix: str,
        variation_control_prefix: str,
        errors: list[str],
        details: list[str],
    ) -> None:
        for field_name in fields:
            attribute_path = f"cis_data.{path_prefix}{field_name}"
            latest_value = latest_values.get(field_name)
            previous_value = previous_values.get(field_name)
            if not self._is_float(latest_value):
                errors.append(
                    f"Índice '{index_name}' | atributo **{attribute_path}** deve ser float "
                    f"no documento mais recente; recebido {latest_value!r}."
                )
                continue
            if not self._is_float(previous_value):
                errors.append(
                    f"Índice '{index_name}' | atributo **{attribute_path}** deve ser float "
                    f"no documento do dia anterior; recebido {previous_value!r}."
                )
                continue
            self._validate_variation(
                index_name,
                attribute_path,
                latest_value,
                previous_value,
                f"{variation_control_prefix}{path_prefix}{field_name}",
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
            f"Índice '{index_name}' | seção **cis_data** | atributo **{attribute_path}**: "
            f"anterior={previous_value}, mais recente={latest_value}, variação={variation}; "
            f"limites: +{limits.maximum_increase:.0%}/-{limits.maximum_decrease:.0%}."
        )
        details.append(message)
        if not result.is_valid:
            errors.append(f"{message} Erro: {result.reason}.")

    def _load_controls(self) -> tuple[list[str], dict[str, list[str]], str]:
        controls: dict[str, Any] = json.loads(
            self._configuration_path.read_text(encoding="utf-8")
        )
        value_fields = controls.get("value_fields")
        nested_objects = controls.get("nested_objects")
        variation_control_prefix = controls.get("variation_control_prefix")
        if (
            not isinstance(value_fields, list)
            or not value_fields
            or not all(isinstance(field, str) for field in value_fields)
            or not isinstance(nested_objects, dict)
            or not all(
                isinstance(object_name, str)
                and isinstance(fields, list)
                and fields
                and all(isinstance(field, str) for field in fields)
                for object_name, fields in nested_objects.items()
            )
            or not isinstance(variation_control_prefix, str)
        ):
            raise ValueError(
                "Os controles devem informar campos e objetos aninhados válidos."
            )
        return value_fields, nested_objects, variation_control_prefix

    @staticmethod
    def _is_float(value: object) -> bool:
        return isinstance(value, float) and not isinstance(value, bool)
