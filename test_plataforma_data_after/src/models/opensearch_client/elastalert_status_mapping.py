from __future__ import annotations

from typing import Any


ELASTALERT_STATUS_INDEX_NAME = "elastalert_status"

EXPECTED_ELASTALERT_STATUS_MAPPING: dict[str, str | dict[str, Any]] = {
    "@timestamp": "date",
    "@version": "text",
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
        "tecnology": "text",
        "title": "text",
        "updated": "date",
        "user_name": "text",
    },
    "alert_info": {
        "ActorIpAddress": "text",
        "ClientIP": "text",
        "UserId": "text",
        "UserKey": "text",
        "recipients": "text",
        "severity_level": "text",
        "source": "text",
        "type": "text",
    },
    "alert_sent": "boolean",
    "alert_time": "date",
    "alertas_id": "text",
    "asset": "text",
    "client": {
        "name": "text",
        "organization": "text",
        "tag": "text",
    },
    "cloud": {
        "account": {"id": "text"},
        "availability_zone": "text",
        "image": {"id": "text"},
        "instance": {"id": "text"},
        "machine": {"type": "text"},
        "provider": "text",
        "region": "text",
        "service": {"name": "text"},
    },
    "event": {"description": "text"},
    "host": {
        "id": "text",
        "name": "text",
    },
    "id": "long",
    "input": {"type": "text"},
    "key": "text",
    "log": {
        "file": {"path": "text"},
        "offset": "long",
    },
    "match_body": "object",
    "match_time": "date",
    "message": "text",
    "port": "text",
    "response": {
        "inTime": "boolean",
        "time": "float",
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
    "rule_description": "text",
    "rule_id": "text",
    "rule_name": "text",
    "severity": "text",
    "sla": {
        "end": "date",
        "response": "date",
        "start": "date",
    },
    "source": {"ip": "text"},
    "status": "text",
    "tags": "text",
    "technology": "text",
    "type": "text",
    "unique_id": "text",
    "user":{
        "name": "text"
    } 
        
}