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

    def validate_document(
        self,
        source: Mapping[str, Any],
        expected_properties: Mapping[str, str | dict[str, Any]],
    ) -> list[str]:
        """Valida os campos e tipos do `_source` de um documento retornado."""
        return self._validate_document_properties(source, expected_properties)

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

    def _validate_document_properties(
        self,
        source: Mapping[str, Any],
        expected_properties: Mapping[str, str | dict[str, Any]],
        path: str = "",
    ) -> list[str]:
        errors: list[str] = []
        for field_name, expected_definition in expected_properties.items():
            field_path = f"{path}.{field_name}" if path else field_name
            if field_name not in source:
                errors.append(f"Campo ausente no documento: {field_path}")
                continue

            value = source[field_name]
            if isinstance(expected_definition, dict):
                if not isinstance(value, Mapping):
                    errors.append(f"Campo objeto inválido no documento: {field_path}")
                    continue
                errors.extend(
                    self._validate_document_properties(
                        value,
                        expected_definition,
                        field_path,
                    )
                )
                continue

            if not self._matches_document_type(value, expected_definition):
                errors.append(
                    f"Tipo inválido no documento para {field_path}. "
                    f"Esperado: {expected_definition}; encontrado: {type(value).__name__}"
                )
        return errors

    @staticmethod
    def _matches_document_type(value: Any, expected_type: str) -> bool:
        if expected_type in {"text", "keyword", "date"}:
            return isinstance(value, str)
        if expected_type == "boolean":
            return isinstance(value, bool)
        if expected_type in {"long", "integer", "short", "byte"}:
            return isinstance(value, int) and not isinstance(value, bool)
        if expected_type in {"float", "double", "half_float", "scaled_float"}:
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        return value is not None
