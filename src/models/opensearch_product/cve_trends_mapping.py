from __future__ import annotations

from typing import Any

CVE_TRENDS_INDEX_NAME = "cve_trends"

EXPECTED_CVE_TRENDS_MAPPING: dict[str, str | dict[str, Any]] = {
	"affectedProduct": "text",
	"annotations": "text",
	"cve": "text",
	"cvss": "float",
	"provider": "text",
	"publicationDate": "date",
	"status": "text",
	"trendDate": "date",
}