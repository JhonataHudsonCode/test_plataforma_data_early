from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.validators.after_pipeline.controllers.oto_score_variation_controller import (
    OtoScoreVariationController,
)


class OtoScoreDataValidator:
    """Reúne as validações dos objetos internos de `score_data`."""

    _CONFIGURATION_PATH = Path(__file__).with_name("score_data_validation_controls.json")
    _VALIDATION_METHODS: dict[str, str] = {
        "historical": "_validate_historical",
    }

    def __init__(
        self,
        reference_month: str,
        variation_controller: OtoScoreVariationController | None = None,
        configuration_path: Path | None = None,
    ) -> None:
        self._reference_month = reference_month
        self._variation_controller = variation_controller or OtoScoreVariationController()
        self._configuration_path = configuration_path or self._CONFIGURATION_PATH

    def validate(
        self,
        index_name: str,
        latest_score_data: object,
        previous_score_data: object,
        errors: list[str],
        details: list[str],
    ) -> None:
        """Valida os objetos definidos no JSON usando os dados brutos recebidos."""
        if not isinstance(latest_score_data, dict):
            errors.append(
                f"Índice '{index_name}' | seção **score_data** ausente ou inválida "
                "no documento mais recente."
            )
            return
        if not isinstance(previous_score_data, dict):
            errors.append(
                f"Índice '{index_name}' | seção **score_data** ausente ou inválida "
                "no documento do dia anterior."
            )
            return

        try:
            object_controls = self._load_object_controls()
        except (OSError, ValueError, json.JSONDecodeError) as error:
            errors.append(
                f"Índice '{index_name}' | erro ao carregar controles de score_data: "
                f"{error.__class__.__name__}: {error}"
            )
            return

        for object_name, control in object_controls.items():
            validation_name = control.get("validation")
            method_name = self._VALIDATION_METHODS.get(validation_name)
            object_validator = getattr(self, method_name, None) if method_name else None
            if not callable(object_validator):
                errors.append(
                    f"Índice '{index_name}' | score_data.{object_name} possui validação "
                    f"não suportada: {validation_name!r}."
                )
                continue
            object_validator(
                index_name,
                latest_score_data.get(object_name),
                previous_score_data.get(object_name),
                control,
                errors,
                details,
            )

    def _validate_historical(
        self,
        index_name: str,
        latest_historical: object,
        previous_historical: object,
        control: dict[str, str],
        errors: list[str],
        details: list[str],
    ) -> None:
        """Valida o item mensal de `score_data.historical` configurado no JSON."""
        date_field = control["date_field"]
        value_field = control["value_field"]
        variation_control = control["variation_control"]
        latest_item = self._find_reference_month_item(latest_historical, date_field)
        previous_item = self._find_reference_month_item(previous_historical, date_field)
        attribute_path = (
            f"score_data.historical[{date_field}={self._reference_month}].{value_field}"
        )
        if latest_item is None:
            errors.append(
                f"Índice '{index_name}' | atributo **{attribute_path}** ausente "
                "no documento mais recente."
            )
            return
        if previous_item is None:
            errors.append(
                f"Índice '{index_name}' | atributo **{attribute_path}** ausente "
                "no documento do dia anterior."
            )
            return

        latest_value = latest_item.get(value_field)
        previous_value = previous_item.get(value_field)
        if not self._is_float(latest_value):
            errors.append(
                f"Índice '{index_name}' | atributo **{attribute_path}** deve ser float "
                f"no documento mais recente; recebido {latest_value!r}."
            )
            return
        if not self._is_float(previous_value):
            errors.append(
                f"Índice '{index_name}' | atributo **{attribute_path}** deve ser float "
                f"no documento do dia anterior; recebido {previous_value!r}."
            )
            return

        self._validate_controlled_score(
            index_name,
            attribute_path,
            latest_value,
            previous_value,
            variation_control,
            errors,
            details,
        )

    def _validate_controlled_score(
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
                f"Índice '{index_name}' | atributo **{attribute_path}** | "
                f"erro ao carregar controlador '{variation_control}': "
                f"{error.__class__.__name__}: {error}"
            )
            return
        if limits is None:
            errors.append(
                f"Índice '{index_name}' | atributo **{attribute_path}** | "
                f"controlador '{variation_control}' não configurado."
            )
            return

        result = self._variation_controller.validate_percentage_variation(
            latest_value,
            previous_value,
            limits,
        )
        variation = "não calculável" if result.variation is None else f"{result.variation:.0%}"
        message = (
            f"Índice '{index_name}' | seção **score_data** | atributo "
            f"**{attribute_path}**: anterior={previous_value}, "
            f"mais recente={latest_value}, variação={variation}; "
            f"limites: +{limits.maximum_increase:.0%}/-{limits.maximum_decrease:.0%}."
        )
        details.append(message)
        if not result.is_valid:
            errors.append(f"{message} Erro: {result.reason}.")

    def _load_object_controls(self) -> dict[str, dict[str, str]]:
        configuration = json.loads(self._configuration_path.read_text(encoding="utf-8"))
        object_controls = configuration.get("objects")
        if not isinstance(object_controls, dict):
            raise ValueError("A chave 'objects' deve ser um objeto JSON.")
        if not all(isinstance(name, str) and isinstance(value, dict) for name, value in object_controls.items()):
            raise ValueError("Cada objeto de score_data deve possuir uma configuração JSON.")
        required_fields = {"validation", "date_field", "value_field", "variation_control"}
        if any(
            not required_fields.issubset(control)
            or not all(isinstance(control[field], str) for field in required_fields)
            for control in object_controls.values()
        ):
            raise ValueError(
                "Cada controle deve possuir validation, date_field, value_field e variation_control."
            )
        return object_controls

    def _find_reference_month_item(
        self,
        historical: object,
        date_field: str,
    ) -> dict[str, Any] | None:
        if not isinstance(historical, list):
            return None
        return next(
            (
                item
                for item in historical
                if isinstance(item, dict)
                and isinstance(item.get(date_field), str)
                and item[date_field].startswith(self._reference_month)
            ),
            None,
        )

    @staticmethod
    def _is_float(value: object) -> bool:
        return isinstance(value, float) and not isinstance(value, bool)
