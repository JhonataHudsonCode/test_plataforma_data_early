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


class OtoRsaDataValidator(OtoDashboardSectionValidator):
    """Valida os scores expostos pelo objeto pai `rsa_data` do OTO Dashboard."""

    _CONFIGURATION_PATH = Path(__file__).with_name("rsa_data_validation_controls.json")
    section_name = "rsa_data"

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
        latest_rsa_data: object,
        previous_rsa_data: object,
        errors: list[str],
        details: list[str],
    ) -> None:
        if not isinstance(latest_rsa_data, dict):
            errors.append(
                f"Índice '{index_name}' | seção **rsa_data** ausente ou inválida "
                "no documento mais recente."
            )
            return
        if not isinstance(previous_rsa_data, dict):
            errors.append(
                f"Índice '{index_name}' | seção **rsa_data** ausente ou inválida "
                "no documento do dia anterior."
            )
            return

        try:
            value_fields, variation_control_prefix = self._load_controls()
        except (OSError, ValueError, json.JSONDecodeError) as error:
            errors.append(
                f"Índice '{index_name}' | erro ao carregar controles de rsa_data: "
                f"{error.__class__.__name__}: {error}"
            )
            return

        for field_name in value_fields:
            attribute_path = f"rsa_data.{field_name}"
            latest_value = latest_rsa_data.get(field_name)
            previous_value = previous_rsa_data.get(field_name)
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
            f"Índice '{index_name}' | seção **rsa_data** | atributo **{attribute_path}**: "
            f"anterior={previous_value}, mais recente={latest_value}, variação={variation}; "
            f"limites: +{limits.maximum_increase:.0%}/-{limits.maximum_decrease:.0%}."
        )
        details.append(message)
        if not result.is_valid:
            errors.append(f"{message} Erro: {result.reason}.")

    def _load_controls(self) -> tuple[list[str], str]:
        controls: dict[str, Any] = json.loads(
            self._configuration_path.read_text(encoding="utf-8")
        )
        value_fields = controls.get("value_fields")
        variation_control_prefix = controls.get("variation_control_prefix")
        if (
            not isinstance(value_fields, list)
            or not value_fields
            or not all(isinstance(field, str) for field in value_fields)
            or not isinstance(variation_control_prefix, str)
        ):
            raise ValueError(
                "Os controles devem informar value_fields e variation_control_prefix válidos."
            )
        return value_fields, variation_control_prefix

    @staticmethod
    def _is_float(value: object) -> bool:
        return isinstance(value, float) and not isinstance(value, bool)
