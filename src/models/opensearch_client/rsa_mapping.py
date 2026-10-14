from __future__ import annotations

from typing import Any


EXPECTED_RSA_MAPPING: dict[str, str | dict[str, Any]] = {
    "@timestamp": "date",
    "@version": "text",
    "cpes": "text",
    "first_scan": "date",
    "ip": "text",
    "ip_port": "text",
    "key": "text",
    "last_time_vulnerable": "date",
    "main_domain": "text",
    "os": {
        "cpes": "text",
        "name": "text",
        "port": "long",
    },
    "port": "long",
    "port_severity": "text",
    "port_severity_level": "long",
    "port_severity_reason": "text",
    "port_severity_recommendation": "text",
    "protocol": "text",
    "scan_date": "date",
    "score": "long",
    "service": "text",
    "status": "text",
    "status_code": "text",
    "subdomain": "text",
    "tags": "text",
    "technology": "text",
    "times_vulnerable": "long",
    "unresolved_subdomains": "text",
    "vulnerable": "boolean",
    "vulns": "text",

}