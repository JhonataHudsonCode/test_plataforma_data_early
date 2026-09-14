from __future__ import annotations

from typing import Any

EPSS_INDEX_NAME = "epss"

EXPECTED_EPSS_MAPPING: dict[str, str | dict[str, Any]] = {
    "cve": "text",
    "epss": "float",
    "percentile": "float"
}