from __future__ import annotations

from typing import Any


EXPECTED_ASSET_POLICY_COMPLIANCE_MAPPING: dict[str, str | dict[str, Any]] = {
    "description": "text",
    "end_scan": "date",
    "fail": {"count": "long", "hosts": "text"},
    "id": "long",
    "invalid": {"count": "long", "hosts": "text"},
    "passed": {"count": "long", "hosts": "text"},
    "rationale": "text",
    "remediation": "text",
    "rules": {"rule": "text", "type": "text"},
    "target": "text",
    "title": "text",
}
