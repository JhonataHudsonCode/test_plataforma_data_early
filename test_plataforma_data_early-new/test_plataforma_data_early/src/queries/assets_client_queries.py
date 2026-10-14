
SELECT_ASSETS_CLIENT_ACTIVATION_KEYS = """
SELECT * FROM assets.{schema_name}.activation_keys
WHERE client_id = %s;
"""

SELECT_ASSETS_CLIENT_ACTIVATION_KEY_IDS = """
SELECT activation_key_id, activation_key_name FROM assets.{schema_name}.activation_keys
WHERE client_id = %s;
"""

SELECT_ASSETS_CLIENT_WAZUH_KEYS = """
SELECT activation_password FROM assets.{schema_name}.wazuh_keys
WHERE client_id = %s;
"""