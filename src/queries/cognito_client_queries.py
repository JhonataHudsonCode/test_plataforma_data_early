SELECT_COGNITO_CLIENT_IDENTITY_BY_ID = """
SELECT
    client_id,
    octopus_endpoint
FROM {schema_name}.clients
WHERE client_id = %s;
"""

SELECT_COGNITO_CLIENT_HAS_RSA_BY_ID = """
SELECT has_rsa,octopus_endpoint FROM {schema_name}.clients WHERE client_id = %s;
"""

SELECT_COGNITO_CLIENT_HAS_ALERTS_BY_ID = """
SELECT has_alerts,octopus_endpoint FROM {schema_name}.clients WHERE client_id = %s;
"""

SELECT_COGNITO_CLIENT_HAS_BART_BY_ID = """
SELECT has_bart,octopus_endpoint FROM {schema_name}.clients WHERE client_id = %s;
"""

SELECT_COGNITO_CLIENT_HAS_ASSET_BY_ID = """
SELECT has_asset,octopus_endpoint FROM {schema_name}.clients WHERE client_id = %s;
"""

SELECT_COGNITO_CLIENT_HAS_AXUR_BY_ID = """
SELECT has_axur,octopus_endpoint FROM {schema_name}.clients WHERE client_id = %s;
"""

SELECT_COGNITO_CLIENT_HAS_WAZUH_BY_ID = """
SELECT has_wazuh,octopus_endpoint FROM {schema_name}.clients WHERE client_id = %s;
"""

SELECT_ALL_CLIENT_IDENTITIES = """
SELECT
    client_id,
    octopus_endpoint
FROM public.clients
ORDER BY client_id;
"""

SELECT_ALL_CLIENTS = """
SELECT *
FROM {schema_name}.clients
ORDER BY client_id;
"""

SELECT_ID_CLIENTS = """
SELECT id, name FROM {schema_name}.clients AS c
WHERE "name" = %s;
"""

SELECT_ALL_CLIENTS_HAS_RSA = """
SELECT client_id, has_rsa
FROM public.clients
ORDER BY client_id;
"""