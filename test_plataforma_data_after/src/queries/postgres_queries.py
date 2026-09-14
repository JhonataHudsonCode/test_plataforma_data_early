CHECK_CONNECTION = """
SELECT 1 AS health;
"""

SELECT_TABLE_FROM_PG_TABLES = """
SELECT
    *
FROM pg_catalog.pg_tables
WHERE schemaname = %s
  AND tablename = %s;
"""