from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path
from typing import Any

from src.validators.after_pipeline.controllers.oto_score_variation_controller import (
    OtoScoreVariationController,
)
from src.validators.after_pipeline.oto_dashboard.section_validator import (
    OtoDashboardSectionValidator,
)


class OtoScoreDataValidator(OtoDashboardSectionValidator):
    """Reúne as validações dos objetos internos de `score_data`."""

    _CONFIGURATION_PATH = Path(__file__).with_name("score_data_validation_controls.json")
    section_name = "score_data"
    _VALIDATION_METHODS: dict[str, str] = {
        "historical": "_validate_historical",
        "score_values": "_validate_score_values",
        "variation_data": "_validate_variation_data",
        "estimate_new_score": "_validate_estimate_new_score",
        "impact": "_validate_impact",
    }

    def __init__(
        self,
        reference_date: date,
        variation_controller: OtoScoreVariationController | None = None,
        configuration_path: Path | None = None,
    ) -> None:
        self._reference_month = reference_date.strftime("%Y-%m")
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
        control: dict[str, Any],
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

    def _validate_score_values(
        self,
        index_name: str,
        latest_values: object,
        previous_values: object,
        control: dict[str, Any],
        errors: list[str],
        details: list[str],
    ) -> None:
        """Valida os campos numéricos de um objeto de score contra o dia anterior."""
        object_name: str = control["object_name"]
        if not isinstance(latest_values, dict):
            errors.append(
                f"Índice '{index_name}' | seção **score_data.{object_name}** ausente ou "
                "inválida no documento mais recente."
            )
            return
        if not isinstance(previous_values, dict):
            errors.append(
                f"Índice '{index_name}' | seção **score_data.{object_name}** ausente ou "
                "inválida no documento do dia anterior."
            )
            return

        value_fields: list[str] = control["value_fields"]
        variation_control_prefix: str = control["variation_control_prefix"]
        for field_name in value_fields:
            attribute_path = f"score_data.{object_name}.{field_name}"
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

            self._validate_controlled_score(
                index_name,
                attribute_path,
                latest_value,
                previous_value,
                f"{variation_control_prefix}{field_name}",
                errors,
                details,
            )

    def _validate_estimate_new_score(
        self,
        index_name: str,
        latest_estimate_new_score: object,
        previous_estimate_new_score: object,
        control: dict[str, Any],
        errors: list[str],
        details: list[str],
    ) -> None:
        """Valida os atributos configurados de `score_data.estimate_new_score`."""
        self._validate_score_values(
            index_name,
            latest_estimate_new_score,
            previous_estimate_new_score,
            control,
            errors,
            details,
        )

    def _validate_impact(
        self,
        index_name: str,
        latest_impact: object,
        previous_impact: object,
        control: dict[str, Any],
        errors: list[str],
        details: list[str],
    ) -> None:
        """Valida os atributos configurados de `score_data.impact`."""
        self._validate_score_values(
            index_name,
            latest_impact,
            previous_impact,
            control,
            errors,
            details,
        )

    def _validate_variation_data(
        self,
        index_name: str,
        latest_variation_data: object,
        previous_variation_data: object,
        control: dict[str, Any],
        errors: list[str],
        details: list[str],
    ) -> None:
        """Valida os valores e a coerência das variações calculadas por módulo."""
        value_fields: list[str] = control["value_fields"]
        nested_value_fields: list[str] = control["nested_value_fields"]
        self._validate_variation_document(
            index_name,
            "mais recente",
            latest_variation_data,
            value_fields,
            nested_value_fields,
            errors,
            details,
        )
        self._validate_variation_document(
            index_name,
            "do dia anterior",
            previous_variation_data,
            value_fields,
            nested_value_fields,
            errors,
            details,
        )

    def _validate_variation_document(
        self,
        index_name: str,
        document_label: str,
        variation_data: object,
        value_fields: list[str],
        nested_value_fields: list[str],
        errors: list[str],
        details: list[str],
    ) -> None:
        if not isinstance(variation_data, dict):
            errors.append(
                f"Índice '{index_name}' | seção **score_data.variation_data** ausente ou "
                f"inválida no documento {document_label}."
            )
            return

        for field_name in value_fields:
            attribute_path = f"score_data.variation_data.{field_name}"
            values = variation_data.get(field_name)
            if not isinstance(values, dict):
                errors.append(
                    f"Índice '{index_name}' | atributo **{attribute_path}** ausente ou "
                    f"inválido no documento {document_label}."
                )
                continue

            invalid_fields = [
                nested_field
                for nested_field in nested_value_fields
                if not self._is_float(values.get(nested_field))
            ]
            if invalid_fields:
                errors.append(
                    f"Índice '{index_name}' | atributo **{attribute_path}** no documento "
                    f"{document_label} deve conter float em {', '.join(invalid_fields)}."
                )
                continue

            current = values["current"]
            past = values["past"]
            variation = values["variation"]
            expected_variation = self._calculate_variation(current, past)
            if expected_variation is None:
                errors.append(
                    f"Índice '{index_name}' | atributo **{attribute_path}** no documento "
                    f"{document_label} possui past=0.0 e a variação não pode ser conferida."
                )
                continue
            if not math.isclose(variation, expected_variation, abs_tol=0.01):
                errors.append(
                    f"Índice '{index_name}' | atributo **{attribute_path}.variation** "
                    f"incoerente no documento {document_label}: recebido={variation}, "
                    f"esperado≈{expected_variation:.2f}."
                )
                continue

            details.append(
                f"Índice '{index_name}' | seção **score_data.variation_data** | atributo "
                f"**{attribute_path}** no documento {document_label}: current={current}, "
                f"past={past}, variation={variation:.2f}; valores e cálculo válidos."
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

    def _load_object_controls(self) -> dict[str, dict[str, Any]]:
        configuration = json.loads(self._configuration_path.read_text(encoding="utf-8"))
        object_controls = configuration.get("objects")
        if not isinstance(object_controls, dict):
            raise ValueError("A chave 'objects' deve ser um objeto JSON.")
        if not all(isinstance(name, str) and isinstance(value, dict) for name, value in object_controls.items()):
            raise ValueError("Cada objeto de score_data deve possuir uma configuração JSON.")
        for object_name, control in object_controls.items():
            validation = control.get("validation")
            if not isinstance(validation, str):
                raise ValueError(f"O controle '{object_name}' deve informar 'validation'.")
            if validation == "historical":
                required_fields = {"date_field", "value_field", "variation_control"}
                if not required_fields.issubset(control) or not all(
                    isinstance(control[field], str) for field in required_fields
                ):
                    raise ValueError(
                        f"O controle '{object_name}' deve possuir date_field, value_field "
                        "e variation_control como texto."
                    )
            elif validation in {"score_values", "estimate_new_score", "impact"}:
                value_fields = control.get("value_fields")
                variation_control_prefix = control.get("variation_control_prefix")
                if (
                    not isinstance(control.get("object_name"), str)
                    or not isinstance(value_fields, list)
                    or not value_fields
                    or not all(isinstance(field, str) for field in value_fields)
                    or not isinstance(variation_control_prefix, str)
                ):
                    raise ValueError(
                        f"O controle '{object_name}' deve possuir value_fields e "
                        "variation_control_prefix válidos."
                    )
            elif validation == "variation_data":
                value_fields = control.get("value_fields")
                nested_value_fields = control.get("nested_value_fields")
                if (
                    not isinstance(value_fields, list)
                    or not value_fields
                    or not all(isinstance(field, str) for field in value_fields)
                    or not isinstance(nested_value_fields, list)
                    or set(nested_value_fields) != {"current", "past", "variation"}
                ):
                    raise ValueError(
                        f"O controle '{object_name}' deve possuir campos de variação válidos."
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

    @staticmethod
    def _calculate_variation(current: float, past: float) -> float | None:
        if past == 0.0:
            return None
        return (current - past) / abs(past)
