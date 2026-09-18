from __future__ import annotations

import json
from typing import Any, Callable

from src.validators.after_pipeline.controllers.oto_score_variation_controller import (
    OtoScoreVariationController,
)


class OtoScoreDataValidator:
    """Reúne as validações dos objetos internos de `score_data`."""

    _HISTORICAL_SCORE_CONTROL = "score_data.historical.score"

    def __init__(
        self,
        reference_month: str,
        variation_controller: OtoScoreVariationController | None = None,
    ) -> None:
        self._reference_month = reference_month
        self._variation_controller = variation_controller or OtoScoreVariationController()
        self._object_validators: dict[
            str,
            Callable[[str, object, object, list[str], list[str]], None],
        ] = {
            "historical": self._validate_historical,
        }

    def validate(
        self,
        index_name: str,
        latest_score_data: object,
        previous_score_data: object,
        errors: list[str],
        details: list[str],
    ) -> None:
        """Valida os objetos de `score_data` usando os dados brutos dos documentos."""
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

        for object_name, object_validator in self._object_validators.items():
            object_validator(
                index_name,
                latest_score_data.get(object_name),
                previous_score_data.get(object_name),
                errors,
                details,
            )

    def _validate_historical(
        self,
        index_name: str,
        latest_historical: object,
        previous_historical: object,
        errors: list[str],
        details: list[str],
    ) -> None:
        """Valida o item mensal de `score_data.historical`."""
        latest_item = self._find_reference_month_item(latest_historical)
        previous_item = self._find_reference_month_item(previous_historical)
        attribute_path = f"score_data.historical[date={self._reference_month}].score"
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

        latest_value = latest_item.get("score")
        previous_value = previous_item.get("score")
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

        self._validate_historical_score(
            index_name,
            attribute_path,
            latest_value,
            previous_value,
            errors,
            details,
        )

    def _validate_historical_score(
        self,
        index_name: str,
        attribute_path: str,
        latest_value: float,
        previous_value: float,
        errors: list[str],
        details: list[str],
    ) -> None:
        """Aplica a política percentual configurada ao score mensal já validado."""
        try:
            limits = self._variation_controller.limits_for(self._HISTORICAL_SCORE_CONTROL)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            errors.append(
                f"Índice '{index_name}' | atributo **{attribute_path}** | "
                f"erro ao carregar controlador '{self._HISTORICAL_SCORE_CONTROL}': "
                f"{error.__class__.__name__}: {error}"
            )
            return
        if limits is None:
            errors.append(
                f"Índice '{index_name}' | atributo **{attribute_path}** | "
                f"controlador '{self._HISTORICAL_SCORE_CONTROL}' não configurado."
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

    def _find_reference_month_item(self, historical: object) -> dict[str, Any] | None:
        if not isinstance(historical, list):
            return None
        return next(
            (
                item
                for item in historical
                if isinstance(item, dict)
                and isinstance(item.get("date"), str)
                and item["date"].startswith(self._reference_month)
            ),
            None,
        )

    @staticmethod
    def _is_float(value: object) -> bool:
        return isinstance(value, float) and not isinstance(value, bool)
