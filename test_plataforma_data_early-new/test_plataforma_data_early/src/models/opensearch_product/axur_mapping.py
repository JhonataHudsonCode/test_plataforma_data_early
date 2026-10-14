from __future__ import annotations

from typing import Any

AXUR_INDEX_NAME = "axur"

EXPECTED_AXUR_MAPPING: dict[str, str | dict[str, Any]] = {
	"alert": {
		"status": "text",
	},
	"event": {
		"category": "text",
		"type": "text",
	},
}