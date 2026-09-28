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
        compliance_definition = items_definition["compliance"]
        assert isinstance(compliance_definition, dict)
        rules_definition = items_definition["rules"]
        assert isinstance(rules_definition, dict)

        self._compliance_definition = compliance_definition
        self._rules_definition = rules_definition
        self._items_definition = {
            name: definition
            for name, definition in items_definition.items()
            if name not in {"compliance", "rules"}
        }
        self._document_definition = {
            name: definition
            for name, definition in EXPECTED_ASSET_COMPLIANCE_MAPPING.items()
            if name != "policies"
        }
        self._document_definition["checks"] = {
            name: definition
            for name, definition in checks_definition.items()
            if name != "items"
        }
        self._mapping_validator = OpenSearchMappingValidator()

    def validate(self, source: Mapping[str, Any]) -> list[str]:
        """Valida os campos do documento e todos os objetos presentes no array."""
        errors = self._mapping_validator.validate_document(
            source,
            self._document_definition,
        )
        errors.extend(self._validate_policies(source))
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
            errors.extend(self._validate_compliance_items(item, item_path))
            errors.extend(self._validate_rule_items(item, item_path))
        return errors

    @staticmethod
    def _validate_policies(source: Mapping[str, Any]) -> list[str]:
        """Valida todos os valores long presentes na lista raiz policies."""
        policies = source.get("policies")
        if not isinstance(policies, list):
            return ["Campo lista inválido no documento: policies"]

        errors: list[str] = []
        for position, policy in enumerate(policies, start=1):
            if not isinstance(policy, int) or isinstance(policy, bool):
                errors.append(
                    "Tipo inválido no documento para "
                    f"policies[{position}]. Esperado: long; "
                    f"encontrado: {type(policy).__name__}"
                )
        return errors

    def _validate_compliance_items(
        self,
        item: Mapping[str, Any],
        item_path: str,
    ) -> list[str]:
        """Valida todos os objetos de compliance presentes em um item do check."""
        compliance = item.get("compliance")
        if isinstance(compliance, Mapping):
            compliance_items = [compliance]
        elif isinstance(compliance, list):
            compliance_items = compliance
        else:
            return [f"Campo lista inválido no documento: {item_path}.compliance"]

        errors: list[str] = []
        for position, compliance_item in enumerate(compliance_items, start=1):
            compliance_path = f"{item_path}.compliance[{position}]"
            if not isinstance(compliance_item, Mapping):
                errors.append(f"Item inválido no documento: {compliance_path}")
                continue
            errors.extend(
                f"{compliance_path} | {error}"
                for error in self._mapping_validator.validate_document(
                    compliance_item,
                    self._compliance_definition,
                )
            )
        return errors

    def _validate_rule_items(
        self,
        item: Mapping[str, Any],
        item_path: str,
    ) -> list[str]:
        """Valida todos os objetos de rules presentes em um item do check."""
        rules = item.get("rules")
        if isinstance(rules, Mapping):
            rule_items = [rules]
        elif isinstance(rules, list):
            rule_items = rules
        else:
            return [f"Campo lista inválido no documento: {item_path}.rules"]

        errors: list[str] = []
        for position, rule_item in enumerate(rule_items, start=1):
            rule_path = f"{item_path}.rules[{position}]"
            if not isinstance(rule_item, Mapping):
                errors.append(f"Item inválido no documento: {rule_path}")
                continue
            errors.extend(
                f"{rule_path} | {error}"
                for error in self._mapping_validator.validate_document(
                    rule_item,
                    self._rules_definition,
                )
            )
        return errors
