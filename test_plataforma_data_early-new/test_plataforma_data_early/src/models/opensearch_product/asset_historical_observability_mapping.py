from __future__ import annotations

from typing import Any

ASSET_HISTORICAL_OBSERVABILITY_INDEX_NAME = "asset-historical-observability"

EXPECTED_ASSET_HISTORICAL_OBSERVABILITY_MAPPING: dict[str, str | dict[str, Any]] = {
    "asset": {
        "monitored_events": "long",
        "monitored_vulns": "long",
        "total": "long"
    },
    "date": "date",
    "external": "text",
    "importance": "text",
    "was": {
        "monitored_vulns": "long",
        "total": "long"
    }
}