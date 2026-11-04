"""Metadados opcionais associados às mensagens de validação."""
from __future__ import annotations

import math
from functools import wraps
from datetime import timedelta


class StructuredMessage(str):
    def __new__(cls, text, metadata):
        instance = super().__new__(cls, text)
        instance.metadata = metadata
        return instance

    def with_prefix(self, prefix):
        return StructuredMessage(prefix + self, self.metadata)


def percentage_message(text, *, index_name, attribute_name, previous, current,
                       reference_date, direction=None, max_increase=50, max_decrease=None,
                       reason_code=None):
    previous, current = float(previous), float(current)
    if not math.isfinite(previous) or not math.isfinite(current):
        return text
    actual_direction = "increase" if current > previous else "decrease" if current < previous else "unchanged"
    return StructuredMessage(text, {
        "index_name": index_name,
        "attribute_name": attribute_name,
        "previous_value": previous,
        "current_value": current,
        "variation_percent": (current - previous) / abs(previous) * 100 if previous else None,
        "comparison_direction": direction or actual_direction,
        "comparison_limit_percent": max_increase if actual_direction == "increase" else max_decrease if actual_direction == "decrease" else None,
        "max_increase_percent": max_increase,
        "max_decrease_percent": max_decrease,
        "previous_date": (reference_date - timedelta(days=1)).isoformat() if reference_date else None,
        "current_date": reference_date.isoformat() if reference_date else None,
        "reason_code": reason_code,
    })


def structured_field_comparisons(method):
    """Preserva valores originais das comparações geradas pelos validadores de totais."""
    @wraps(method)
    def wrapped(self, index_name, fields, errors, details):
        failures, successes = [], []
        method(self, index_name, fields, failures, successes)
        for target, messages, failed in ((errors, failures, True), (details, successes, False)):
            for message in messages:
                matched = next((item for item in fields if f"| total de {item[0]} " in message or f"| total de {item[0]}:" in message), None)
                if matched is not None:
                    field, current, previous, *rule = matched
                    if isinstance(current, (int, float)) and isinstance(previous, (int, float)):
                        message = percentage_message(
                            message, index_name=index_name, attribute_name=field,
                            previous=previous, current=current, reference_date=self._reference_date,
                            max_decrease=50 if (rule and rule[0] == "decrease") or method.__name__ == "_validate_absolute_fifty_percent_variation" else None,
                            max_increase=None if rule and rule[0] == "decrease" else 50,
                            reason_code="PERCENTAGE_LIMIT_EXCEEDED" if failed and ("limite" in message or "máximo" in message) else None,
                        )
                target.append(message)
    return wrapped
