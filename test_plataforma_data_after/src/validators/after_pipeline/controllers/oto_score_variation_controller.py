from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class PercentageVariationResult:
    """Resultado reutilizável da comparação percentual entre dois valores."""

    variation: float | None
    is_valid: bool
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class PercentageVariationLimits:
    """Limites percentuais permitidos para um atributo."""

    maximum_increase: float
    maximum_decrease: float


class OtoScoreVariationController:
    """Obtém controles de score do JSON e aplica a regra percentual genérica."""

    _CONFIGURATION_PATH = Path(__file__).with_name("oto_score_variation_controls.json")

    def __init__(self, configuration_path: Path | None = None) -> None:
        self._configuration_path = configuration_path or self._CONFIGURATION_PATH

    def limits_for(self, attribute_name: str) -> PercentageVariationLimits | None:
        configuration = json.loads(self._configuration_path.read_text(encoding="utf-8"))
        values = configuration.get("attributes", {}).get(attribute_name)
        if not isinstance(values, dict):
            return None

        increase = values.get("maximum_increase_percentage")
        decrease = values.get("maximum_decrease_percentage")
        if not self._is_valid_limit(increase) or not self._is_valid_limit(decrease):
            raise ValueError(
                f"Limites inválidos para '{attribute_name}' em {self._configuration_path.name}."
            )
        return PercentageVariationLimits(
            maximum_increase=float(increase) / 100,
            maximum_decrease=float(decrease) / 100,
        )

    @staticmethod
    def validate_percentage_variation(
        latest_value: float,
        previous_value: float,
        limits: PercentageVariationLimits,
    ) -> PercentageVariationResult:
        """Valida aumento e redução percentuais com limites independentes."""
        if previous_value == 0.0:
            if latest_value == 0.0:
                return PercentageVariationResult(variation=0.0, is_valid=True)
            return PercentageVariationResult(
                variation=None,
                is_valid=False,
                reason="valor anterior é 0.0 e não permite calcular a diferença percentual",
            )

        variation = (latest_value - previous_value) / abs(previous_value)
        if variation > limits.maximum_increase:
            return PercentageVariationResult(
                variation=variation,
                is_valid=False,
                reason=f"aumento máximo permitido: {limits.maximum_increase:.0%}",
            )
        if variation < -limits.maximum_decrease:
            return PercentageVariationResult(
                variation=variation,
                is_valid=False,
                reason=f"redução máxima permitida: {limits.maximum_decrease:.0%}",
            )
        return PercentageVariationResult(variation=variation, is_valid=True)

    @staticmethod
    def _is_valid_limit(value: object) -> bool:
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and value >= 0
        )
