from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TableMetadata:
    schema_name: str
    table_name: str
    owner: str
    tablespace: str | None
    has_indexes: bool
    has_rules: bool
    has_triggers: bool
    row_security: bool