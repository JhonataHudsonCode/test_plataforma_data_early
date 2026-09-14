SELECT_COGNITO_CLIENT_BY_ID_HAS_RSA = """
SELECT
    client_id,
    has_rsa,
    octopus_endpoint
FROM cognito.public.clients
WHERE client_id = %s;
"""

SELECT_COGNITO_CLIENT_BY_ID = """
SELECT
    client_id,
    has_alerts,
    has_rsa,
    has_bart,
    has_asset,
    octopus_endpoint
FROM cognito.public.clients
WHERE client_id = %s;
"""

SELECT_ALL_CLIENTS = """
SELECT *
FROM {schema_name}.clients
ORDER BY client_id;
"""
