from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from src.models.opensearch_product.asset_compliance_mapping import (
    EXPECTED_ASSET_COMPLIANCE_MAPPING,
)
from src.validators.opensearch_mapping_validator import OpenSearchMappingValidator


class AssetComplianceDocumentValidator:
    """Valida documentos de asset-compliance, incluindo cada item de checks.items."""

    def __init__(self) -> None:
        checks_definition = EXPECTED_ASSET_COMPLIANCE_MAPPING["checks"]
        assert isinstance(checks_definition, dict)
        items_definition = checks_definition["items"]
        assert isinstance(items_definition, dict)

        self._items_definition = items_definition
        self._document_definition = {
            **EXPECTED_ASSET_COMPLIANCE_MAPPING,
            "checks": {
                name: definition
                for name, definition in checks_definition.items()
                if name != "items"
            },
        }
        self._mapping_validator = OpenSearchMappingValidator()

    def validate(self, source: Mapping[str, Any]) -> list[str]:
        """Valida os campos do documento e todos os objetos presentes no array."""
        errors = self._mapping_validator.validate_document(
            source,
            self._document_definition,
        )
        checks = source.get("checks")
        if not isinstance(checks, Mapping):
            return errors

        items = checks.get("items")
        if not isinstance(items, list):
            errors.append("Campo lista inválido no documento: checks.items")
            return errors

        for position, item in enumerate(items, start=1):
            item_path = f"checks.items[{position}]"
            if not isinstance(item, Mapping):
                errors.append(f"Item inválido no documento: {item_path}")
                continue
            errors.extend(
                f"{item_path} | {error}"
                for error in self._mapping_validator.validate_document(
                    item,
                    self._items_definition,
                )
            )
        return errors
