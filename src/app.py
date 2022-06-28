import logging
import os

from typing import List, Optional, Union
from fastapi import FastAPI, APIRouter, Request, Response
from fastapi.logger import logger
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError
from time import sleep

from util import EndpointConfig, ModelEndpointFactory, SQLAlchemyDriver

DB_CONNECTION_STRING = os.environ.get("DB_CONNECTION_STRING")

app = FastAPI(debug=True)

uvicorn_logger = logging.getLogger('uvicorn.error')
if __name__ != "main":
    logger.setLevel(uvicorn_logger.level)
else:
    logger.setLevel(logging.DEBUG)

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

# if __name__ == "__main__":
#     import uvicorn
#     os.environ["DB_CONNECTION_STRING"] = "postgresql+psycopg2://autoapi:autoapi@localhost:5432/autoapi"
#     uvicorn.run(app, host="0.0.0.0", port=3000)
