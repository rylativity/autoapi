import logging
import os

from typing import List, Optional, Union
from fastapi import FastAPI, APIRouter, Request, Response
from fastapi.logger import logger
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError
from time import sleep

from util import ModelEndpointFactory, SQLAlchemyDriver

DB_CONNECTION_STRING = os.environ.get("DB_CONNECTION_STRING")

app = FastAPI(debug=True)

uvicorn_logger = logging.getLogger('uvicorn.error')
if __name__ != "main":
    logger.setLevel(uvicorn_logger.level)
else:
    logger.setLevel(logging.DEBUG)

success = False
while not success:
    try:
        driver = SQLAlchemyDriver(DB_CONNECTION_STRING)
        success = True
        logger.info("Successfully connected to database... Preparing to initialize API...")
        sleep(3)
    except OperationalError:
        logger.error("Could not connect to database... Reattempting connection...")
        sleep(2)

session: Session = driver.sessionmaker()

routers = []
for config in ModelEndpointFactory(DB_CONNECTION_STRING).generate_endpoint_configs():
    
    route = config.route
    pydantic_model = config.pydantic_model
    sqlalchemy_model = config.sqlalchemy_model

    router = APIRouter(prefix=route)
    
    @router.get("", 
                response_model=Union[List[pydantic_model], pydantic_model]
                )
    def func(limit: Optional[int] = 10):
        res = session.query(sqlalchemy_model)
        response = [row.__dict__ for row in res.limit(limit).all()]
        return response
    
    routers.append(router)
    
@app.get("/health")
@app.get("/health/")
def healthcheck():
    return Response(status_code=200)

for router in routers:
    app.include_router(router)
