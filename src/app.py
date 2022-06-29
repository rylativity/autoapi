import os

from autoapi import AutoAPI
from logconfig import log

DB_CONNECTION_STRING = os.environ.get("DB_CONNECTION_STRING")

if DB_CONNECTION_STRING is None:
    DB_CONNECTION_STRING = "sqlite:///sqlite.db"
    log.warn(f"No value set for environment variable $DB_CONNECTION_STRING...")
try:
    log.info(f"Using connection with dialect {DB_CONNECTION_STRING.split('://')[0]}")
except IndexError:
    raise ValueError(
        f"Could not parse sqlalchemy dialect from connection string {DB_CONNECTION_STRING}"
    )

autoapi = AutoAPI(DB_CONNECTION_STRING)

app = autoapi.create_api_app(http_methods=["GET","POST"])

# Alternative Instantiation and Usage
# app = FastAPI(debug=DEBUG)
# path_functions = autoapi.generate_api_path_functions(app)

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=3000)
