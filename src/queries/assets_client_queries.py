
SELECT_ASSETS_CLIENT_ACTIVATION_KEYS = """
SELECT * FROM assets.{schema_name}.activation_keys
WHERE client_id = %s;
"""

SELECT_ASSETS_CLIENT_ACTIVATION_KEY_IDS = """
SELECT activation_key_id FROM assets.{schema_name}.activation_keys
WHERE client_id = %s;
"""
