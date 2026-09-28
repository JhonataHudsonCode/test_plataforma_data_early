from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from src.models.opensearch_product.asset_policy_compliance_mapping import (
    EXPECTED_ASSET_POLICY_COMPLIANCE_MAPPING,
)
from src.validators.opensearch_mapping_validator import OpenSearchMappingValidator


class AssetPolicyComplianceDocumentValidator:
    """Valida os arrays de hosts dos resultados de policy compliance."""

    _HOST_FIELDS = ("invalid", "passed", "fail")

    def __init__(self) -> None:
        self._mapping_validator = OpenSearchMappingValidator()
        self._document_definition = {
            **EXPECTED_ASSET_POLICY_COMPLIANCE_MAPPING,
        }
        for field_name in self._HOST_FIELDS:
            field_definition = EXPECTED_ASSET_POLICY_COMPLIANCE_MAPPING[field_name]
            assert isinstance(field_definition, dict)
            self._document_definition[field_name] = {
                name: definition
                for name, definition in field_definition.items()
                if name != "hosts"
            }

    def validate(self, source: Mapping[str, Any]) -> list[str]:
        errors = self._mapping_validator.validate_document(
            source,
            self._document_definition,
        )
        for field_name in self._HOST_FIELDS:
            field = source.get(field_name)
            if not isinstance(field, Mapping):
                continue
            hosts = field.get("hosts")
            if not isinstance(hosts, list):
                errors.append(f"Campo lista inválido no documento: {field_name}.hosts")
                continue
            for position, host in enumerate(hosts, start=1):
                if not isinstance(host, str):
                    errors.append(
                        "Tipo inválido no documento para "
                        f"{field_name}.hosts[{position}]. Esperado: text; "
                        f"encontrado: {type(host).__name__}"
                    )
        return errors
