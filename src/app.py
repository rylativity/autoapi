import logging
import os

from typing import List, Optional, Union
from fastapi import FastAPI, APIRouter, Response
from time import sleep

from autoapi import EndpointConfig, ModelEndpointFactory, SQLAlchemyDriver


app = FastAPI(debug=True)

DEBUG = os.environ.get("DEBUG")

log = logging.getLogger('uvicorn')
if DEBUG:
    log.setLevel(logging.DEBUG)
else:
    log.setLevel(logging.INFO)

DB_CONNECTION_STRING = os.environ.get("DB_CONNECTION_STRING")
if DB_CONNECTION_STRING is None:
    DB_CONNECTION_STRING = "sqlite:///sqlite.db"
    log.warn(f"No value set for environment variable $DB_CONNECTION_STRING...")
try:
    log.info(f"Using connection with dialect {DB_CONNECTION_STRING.split('://')[0]}")
except IndexError:
    raise ValueError(f"Could not parse sqlalchemy dialect from connection string {DB_CONNECTION_STRING}")

routers: List[APIRouter] = []
endpoint_factory = ModelEndpointFactory(DB_CONNECTION_STRING)
configs = endpoint_factory.generate_endpoint_configs()
session = endpoint_factory.driver.sessionmaker()

def make_fastapi_route_function(endpoint_config: EndpointConfig, fastapi_route_or_app):
    
    @fastapi_route_or_app.get(endpoint_config.route, 
                response_model=Union[List[endpoint_config.pydantic_model], endpoint_config.pydantic_model]
                )
    def func(limit: Optional[int] = 10):
        print(endpoint_config.sqlalchemy_model.__dict__)
        res = session.query(endpoint_config.sqlalchemy_model)
        response = [row.__dict__ for row in res.limit(limit).all()]
        return response
    return func

for config in configs:

    route_function = make_fastapi_route_function(endpoint_config=config, fastapi_route_or_app=app)
    
@app.get("/health")
@app.get("/health/")
def healthcheck():
    return Response(status_code=200)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3000)
