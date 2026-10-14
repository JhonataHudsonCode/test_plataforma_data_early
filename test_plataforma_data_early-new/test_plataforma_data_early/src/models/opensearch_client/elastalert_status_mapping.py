from __future__ import annotations

from typing import Any


ELASTALERT_STATUS_INDEX_NAME = "elastalert_status"

EXPECTED_ELASTALERT_STATUS_MAPPING: dict[str, str | dict[str, Any]] = {
    "@timestamp": "date",
    "aggregate_id": "text",
    "aggregation_key": "text",
    "alert": {
        "classification": "text",
        "created": "date",
        "host_name": "text",
        "id": "text",
        "key": "text",
        "severity": "text",
        "source_country_iso_code": "text",
        "source_country_name": "text",
        "source_ip": "text",
        "status": "text",
        "technology": "text",
        "title": "text",
        "updated": "date",
        "user_name": "text",
    },
    "alert_info": {
        "http_post_webhook_url": "text",
        "recipients": "text",
        "type": "text",
    },
    "alert_sent": "boolean",
    "alert_time": "date",
    "client": {
        "name": "text",
        "organization": "text",
        "tag": "text",
    },
    "response": {
        "inTime": "boolean",
        "time": "float"
    },
    "rule": {
        "channels": "text",
        "description": "text",
        "handling": "text",
        "id": "text",
        "index": "text",
        "name": "text",
        "properties": {
            "homolog": "boolean",
            "realert": {
                "hours": "long",
                "minutes": "long",
            },
            "type": "text",
        },
        "severity": "text",
        "source": "text",
    },
    "rule_name": "text",
    "sla": {
        "end": "date",
        "response": "date",
        "start": "date",
    },
    "type": "text",
    "unique_id": "text"
}