from __future__ import annotations

from typing import Any


ASSET_HISTORICAL_SOFTWARE_INDEX_NAME = "asset-historical-software"

EXPECTED_ASSET_HISTORICAL_SOFTWARE_MAPPING: dict[str, str | dict[str, Any]] = {
    "asset": {
        "external": "text",
        "importance": "text",
        "tags": "text",
        "type": "text",
    },
    "assets_missing_mandatory_softwares": "long",
    "assets_total": "long",
    "assets_with_unauthorized_softwares": "long",
    "client": "text",
    "date": "date",
}
