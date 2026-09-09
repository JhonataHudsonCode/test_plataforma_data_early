from __future__ import annotations

from typing import Any

RULES_INDEX_NAME = "rules"

EXPECTED_RULES_MAPPING: dict[str, str | dict[str, Any]] = {
    "@timestamp": "date",
    "cardinality": "long",
    "file": "text",
    "frequency": "long",
    "interval": "long",
    "query": "text",
    "query_key": "text",
    "rule": {
        "channels": "text",
        "description": "text",
        "handling": "text",
        "id": "text",
        "index": "text",
        "name": "text",
        "properties": {
            "homolog": "boolean",
        },
        "severity": "text",
        "source": "text",
        "type": "text",
    },
    "term": "text",
}