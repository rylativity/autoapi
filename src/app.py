import os

from autoapi import AutoApi

DB_HOST = os.environ.get("DB_HOST")
DB_USER = os.environ.get("DB_USER")
DB_PASSWORD = os.environ.get("DB_PASSWORD")
DB_PORT = os.environ.get("DB_PORT")
DB_DIALECT = os.environ.get("DB_DIALECT")

empty_vars = [var for var in [DB_HOST, DB_USER, DB_PORT, DB_DIALECT] if var is None] # Don't check password, because not always required
if empty_vars is None:
    raise EnvironmentError()

autoapi = AutoApi(host=DB_HOST, user=DB_USER, port=DB_PORT, dialect=DB_DIALECT, password=DB_PASSWORD)

app = autoapi.create_api_app(http_methods=["GET"])

