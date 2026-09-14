from __future__ import annotations

from typing import Any

from src.connections.opensearch_dashboards import OpenSearchDashboardsConnection


class OpenSearchDashboardsRepository:
    """Consulta dashboards salvos na aplicação OpenSearch Dashboards."""

    def __init__(self, connection: OpenSearchDashboardsConnection) -> None:
        self._connection = connection

    def list_dashboards(self) -> list[str]:
        response = self._connection.get(
            "/api/saved_objects/_find",
            params={"type": "dashboard", "per_page": 10_000},
        )
        response.raise_for_status()
        payload: dict[str, Any] = response.json()

        return sorted(
            item["attributes"]["title"]
            for item in payload.get("saved_objects", [])
            if item.get("attributes", {}).get("title")
        )