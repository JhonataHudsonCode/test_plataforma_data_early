
SELECT_ASSETS_CLIENT_ACTIVATION_KEYS = """
SELECT * FROM assets.{schema_name}.activation_keys
WHERE (client_id = %s) AND (activation_key_name = %s);
"""