from __future__ import annotations

from typing import Any

ASSET_INDEX_NAME = "asset"

EXPECTED_ASSET_MAPPING: dict[str, str | dict[str, Any]] = {
    "@timestamp": "date",
    "asset": {
        "@timestamp": "date",
        "agent_id": "text",
        "client": "text",
        "external": "text",
        "host_tag": "text",
        "id": "text",
        "importance": "text",
        "importance_code": "long",
        "in_inventory": "boolean",
        "ip": "text",
        "last_scan_date": "date",
        "last_scan_status": "text",
        "name": "text",
        "os": "text",
        "owner": "text",
        "private_ip": "text",
        "rsa_score": "long",
        "score": "long",
        "status": "text",
        "tags": "text",
        "type": "text",
    "asset_events": {
        "compliance": {
            "fail": "long",
            "invalid": "long",
            "pass": "long",
            "score": "float",
            "total_checks": "long",
        },
        "end_scan": "date",
        "id": "text",
        "last_scan_status": "text",
        "lastcheckedin": "date",
        "method": "text",
        "start_scan": "date",
        "technology": "text",
    },
    "asset_vuln": {
        "created": "date",
        "installed_software": {
            "quantity": "long",
            "software": {
                "name": "text",
                "version": "text",
            },
        },
        "key": "text",
        "last_scan_status": "text",
        "lastcheckedin": {
            "date": "date",
            "days_since": "long",
        },
        "mandatory_missing": {
            "quantity": "long",
            "software": {"name": "text"},
        },
        "method": "text",
        "technical_specs": {
            "bios_description": "text",
            "last_loggedon_user": "text",
            "last_system_boot": "date",
            "processor": {
                "name": "text",
                "speed": "text",
            },
            "total_memory": "text",
            "technology": "text",
        },
        "unauthorized_installed": {
            "quantity": "long",
            "software": {
                "name": "text",
                "version": "text",
            },
        },
        "users": "text",
        "client": "text",
    },
    },
}