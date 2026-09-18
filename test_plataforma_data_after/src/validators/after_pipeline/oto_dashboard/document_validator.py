from __future__ import annotations

from datetime import date
from typing import Any

from src.validators.after_pipeline.oto_dashboard.score_data_validator import (
    OtoScoreDataValidator,
)


class OtoDashboardDocumentValidator:
    """Orquestra os validadores dos objetos pai do `_source` do OTO Dashboard."""

    _NON_NUMERIC_SCORE_KEYS = frozenset({"domain_score"})

    def __init__(self, reference_date: date) -> None:
        self._reference_month = reference_date.strftime("%Y-%m")
        self._section_validators = {
            "score_data": OtoScoreDataValidator(),
        }

    def validate(
        self,
        index_name: str,
        latest_document: dict[str, Any],
        previous_document: dict[str, Any],
        errors: list[str],
        details: list[str],
    ) -> None:
        latest_scores = self._collect_score_attributes(latest_document)
        previous_scores = self._collect_score_attributes(previous_document)
        if not latest_scores:
            errors.append(
                f"Índice '{index_name}' | nenhum atributo de score foi encontrado "
                "no documento mais recente."
            )
            return

        for attribute_path, latest_value in latest_scores.items():
            section = attribute_path.split(".", 1)[0].split("[", 1)[0]
            previous_value = previous_scores.get(attribute_path)
            if not self._is_float_score(latest_value):
                errors.append(
                    f"Índice '{index_name}' | seção **{section}** | atributo "
                    f"**{attribute_path}** deve ser float no documento mais recente; "
                    f"recebido {latest_value!r}."
                )
                continue
            if attribute_path not in previous_scores:
                errors.append(
                    f"Índice '{index_name}' | seção **{section}** | atributo "
                    f"**{attribute_path}** ausente no documento do dia anterior."
                )
                continue
            if not self._is_float_score(previous_value):
                errors.append(
                    f"Índice '{index_name}' | seção **{section}** | atributo "
                    f"**{attribute_path}** deve ser float no documento do dia anterior; "
                    f"recebido {previous_value!r}."
                )
                continue

            section_validator = self._section_validators.get(section)
            if section_validator and section_validator.handles(attribute_path):
                section_validator.validate_attribute(
                    index_name,
                    attribute_path,
                    latest_value,
                    previous_value,
                    errors,
                    details,
                )
                continue
            self._validate_default_score_variation(
                index_name,
                section,
                attribute_path,
                latest_value,
                previous_value,
                errors,
                details,
            )

        for attribute_path in previous_scores.keys() - latest_scores.keys():
            section = attribute_path.split(".", 1)[0].split("[", 1)[0]
            errors.append(
                f"Índice '{index_name}' | seção **{section}** | atributo "
                f"**{attribute_path}** ausente no documento mais recente."
            )

    def _collect_score_attributes(
        self,
        value: object,
        path: str = "",
        score_container: bool = False,
    ) -> dict[str, object]:
        attributes: dict[str, object] = {}
        if isinstance(value, dict):
            for key, nested_value in value.items():
                attribute_path = f"{path}.{key}" if path else key
                key_has_score = "score" in key.casefold()
                if key.casefold() in self._NON_NUMERIC_SCORE_KEYS:
                    continue
                if isinstance(nested_value, (dict, list)):
                    attributes.update(
                        self._collect_score_attributes(
                            nested_value,
                            attribute_path,
                            key_has_score and key.casefold() != "score_data",
                        )
                    )
                elif key_has_score or score_container:
                    attributes[attribute_path] = nested_value
        elif isinstance(value, list):
            for position, nested_value in enumerate(value):
                if path == "score_data.historical":
                    if not isinstance(nested_value, dict):
                        continue
                    historical_date = nested_value.get("date")
                    if not isinstance(historical_date, str) or not historical_date.startswith(
                        self._reference_month
                    ):
                        continue
                    attribute_path = f"{path}[date={historical_date}]"
                else:
                    attribute_path = f"{path}[{position}]"
                attributes.update(
                    self._collect_score_attributes(
                        nested_value,
                        attribute_path,
                        score_container,
                    )
                )
        return attributes

    @staticmethod
    def _is_float_score(value: object) -> bool:
        return isinstance(value, float) and not isinstance(value, bool)

    @staticmethod
    def _validate_default_score_variation(
        index_name: str,
        section: str,
        attribute_path: str,
        latest_value: float,
        previous_value: float,
        errors: list[str],
        details: list[str],
    ) -> None:
        if previous_value == 0.0:
            if latest_value == 0.0:
                details.append(
                    f"Índice '{index_name}' | seção **{section}** | atributo "
                    f"**{attribute_path}**: sem variação (0.0 para 0.0)."
                )
            else:
                errors.append(
                    f"Índice '{index_name}' | seção **{section}** | atributo "
                    f"**{attribute_path}** mudou de 0.0 para {latest_value}; "
                    "não atende ao limite de 50%."
                )
            return

        variation = abs(latest_value - previous_value) / abs(previous_value)
        message = (
            f"Índice '{index_name}' | seção **{section}** | atributo "
            f"**{attribute_path}**: anterior={previous_value}, "
            f"mais recente={latest_value}, variação={variation:.0%}."
        )
        details.append(message)
        if variation > 0.5:
            errors.append(f"{message} Máximo permitido: 50%.")
