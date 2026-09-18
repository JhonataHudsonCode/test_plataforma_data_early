from __future__ import annotations

import json

from src.validators.after_pipeline.controllers.oto_score_variation_controller import (
    OtoScoreVariationController,
)


class OtoScoreDataValidator:
    """Reúne as validações dos objetos internos de `score_data`."""

    _HISTORICAL_SCORE_CONTROL = "score_data.historical.score"

    def __init__(
        self,
        variation_controller: OtoScoreVariationController | None = None,
    ) -> None:
        self._variation_controller = variation_controller or OtoScoreVariationController()

    @staticmethod
    def handles(attribute_path: str) -> bool:
        """Informa se o atributo possui uma regra própria de `score_data`."""
        return attribute_path.startswith("score_data.historical[") and attribute_path.endswith(
            "].score"
        )

    def validate_attribute(
        self,
        index_name: str,
        attribute_path: str,
        latest_value: float,
        previous_value: float,
        errors: list[str],
        details: list[str],
    ) -> None:
        """Direciona atributos de `score_data` para sua regra interna apropriada."""
        if self.handles(attribute_path):
            self.validate_historical_score(
                index_name,
                attribute_path,
                latest_value,
                previous_value,
                errors,
                details,
            )

    def validate_historical_score(
        self,
        index_name: str,
        attribute_path: str,
        latest_value: float,
        previous_value: float,
        errors: list[str],
        details: list[str],
    ) -> None:
        """Valida o score mensal de `score_data.historical` pelos limites configurados."""
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
