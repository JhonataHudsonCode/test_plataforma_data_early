
SELECT_CLIENT_BY_ID = """
SELECT "createdAt", "updatedAt" FROM {schema_name}.clients AS c
WHERE "name" = %s;
"""

SELECT_ALERT_CLIENT_BY_ID = """
SELECT "createdAt", "updatedAt" FROM {schema_name}.alertClients AS c
WHERE "id" = %s;
"""
