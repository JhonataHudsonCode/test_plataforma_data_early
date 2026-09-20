from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class OpenSearchMappingValidator:
    """Compara um mapping retornado pelo OpenSearch com um contrato esperado."""

    def validate(
        self,
        actual_properties: Mapping[str, Any],
        expected_properties: Mapping[str, str | dict[str, Any]],
    ) -> list[str]:
        return self._validate_properties(
            actual_properties=actual_properties,
            expected_properties=expected_properties,
        )

    def _validate_properties(
        self,
        actual_properties: Mapping[str, Any],
        expected_properties: Mapping[str, str | dict[str, Any]],
        path: str = "",
    ) -> list[str]:
        errors: list[str] = []

        for field_name, expected_definition in expected_properties.items():
            field_path = f"{path}.{field_name}" if path else field_name
            actual_definition = actual_properties.get(field_name)

            if actual_definition is None:
                errors.append(f"Campo ausente no mapping: {field_path}")
                continue

            if isinstance(expected_definition, dict):
                nested_properties = actual_definition.get("properties", {})
                if not nested_properties:
                    errors.append(
                        f"Campo objeto sem propriedades no mapping: {field_path}"
                    )
                    continue

                errors.extend(
                    self._validate_properties(
                        actual_properties=nested_properties,
                        expected_properties=expected_definition,
                        path=field_path,
                    )
                )
                continue

            actual_type = actual_definition.get("type")
            if actual_type != expected_definition:
                errors.append(
                    f"Tipo incorreto para {field_path}. "
                    f"Esperado: {expected_definition}; encontrado: {actual_type}"
                )

        return errors
