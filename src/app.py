import os

from autoapi import AutoApi
from logconfig import log

DB_HOST = os.environ.get("DB_HOST")
DB_USER = os.environ.get("DB_USER")
DB_PORT = os.environ.get("DB_PORT")
DB_DIALECT = os.environ.get("DB_DIALECT")

for var in [DB_HOST, DB_USER, DB_PORT]:
    if var is None:
        log.error(f"No value set for environment variable ${var}...")
        log.warn(f"Will fall back to default value for {var}")

trino_autoapi = AutoApi(host=DB_HOST, user=DB_USER, port=DB_PORT, dialect=DB_DIALECT)

app = trino_autoapi.create_api_app(http_methods=["GET"])

