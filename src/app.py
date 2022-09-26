import os

from trinoautoapi import TrinoAutoApi
from logconfig import log

TRINO_HOST = os.environ.get("TRINO_HOST")
TRINO_USER = os.environ.get("TRINO_USER")
TRINO_PORT = os.environ.get("TRINO_PORT")

for var in [TRINO_HOST, TRINO_USER, TRINO_PORT]:
    if var is None:
        log.warn(f"No value set for environment variable ${var}...")
        log.warn(f"Will fall back to default value for {var}")

trino_autoapi = TrinoAutoApi(host=TRINO_HOST, user=TRINO_USER, port=TRINO_PORT)

app = trino_autoapi.create_api_app(http_methods=["GET"])

