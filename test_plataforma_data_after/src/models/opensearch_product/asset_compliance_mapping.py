from __future__ import annotations

from typing import Any


EXPECTED_ASSET_COMPLIANCE_MAPPING: dict[str, str | dict[str, Any]] = {
    "agent_id": "text",
    "checks": {
        "items": {
            "command": "text",
            "compliance": {"key": "text", "value": "text"},
            "condition": "text",
            "description": "text",
            "directory": "text",
            "file": "text",
            "id": "long",
            "policy_id": "text",
            "rationale": "text",
            "reason": "text",
            "references": "text",
            "registry": "text",
            "remediation": "text",
            "result": "text",
            "rules": {"rule": "text", "type": "text"},
            "target": "text",
            "title": "text",
        },
        "total_affected_items": "long",
        "total_failed_items": "long",
        "totalItems": "long",
    },
    "cis_name": "text",
    "end_scan": "date",
    "fail": "long",
    "invalid": "long",
    "name": "text",
    "os": "text",
    "pct_score": "long",
    "policies": "long",
    "start_scan": "date",
    "success": "long",
    "total_checks": "long",
}
