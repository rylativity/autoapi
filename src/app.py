import os

from autoapi import AutoApi

SQLALCHEMY_URIS = os.environ.get("SQLALCHEMY_URIS")

# The values below will not be used if SQLALCHEMY_URIS is set
DB_HOST = os.environ.get("DB_HOST")
DB_USER = os.environ.get("DB_USER")
DB_PASSWORD = os.environ.get("DB_PASSWORD")
DB_PORT = os.environ.get("DB_PORT")
DB_DIALECT = os.environ.get("DB_DIALECT")

autoapi = AutoApi(sqlalchemy_uris = SQLALCHEMY_URIS, host=DB_HOST, user=DB_USER, port=DB_PORT, dialect=DB_DIALECT, password=DB_PASSWORD)

app = autoapi.create_api_app(http_methods=["GET"])

