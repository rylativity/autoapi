from copy import deepcopy
from enum import Enum
from logconfig import log, DEBUG
from typing import List, Optional, Container, Type, Union
from fastapi import APIRouter, FastAPI, Response

from pydantic import BaseConfig, BaseModel, create_model

from sqlalchemy import create_engine
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.exc import IntegrityError
from sqlalchemy.inspection import inspect
from sqlalchemy.orm.properties import ColumnProperty
from sqlalchemy.orm import sessionmaker


class SQLAlchemyDriver:
    def __init__(self, connection_string: str):
        self.engine = create_engine(connection_string)
        with self.engine.connect():  # test the connection
            pass
        self.sessionmaker = sessionmaker(self.engine)

    def query(self, query_string: str):
        with self.engine.connect() as conn:
            result = conn.execute(query_string)
        return [dict(row) for row in result]


class OrmConfig(BaseConfig):
    orm_mode = True


def sqlalchemy_to_pydantic(
    db_model: Type, *, config: Type = OrmConfig, exclude: Container[str] = []
) -> Type[BaseModel]:
    mapper = inspect(db_model)
    fields = {}
    for attr in mapper.attrs:
        if isinstance(attr, ColumnProperty):
            if attr.columns:
                name = attr.key
                if name in exclude:
                    continue
                column = attr.columns[0]
                python_type: Optional[type] = None
                if hasattr(column.type, "impl"):
                    if hasattr(column.type.impl, "python_type"):
                        python_type = column.type.impl.python_type
                elif hasattr(column.type, "python_type"):
                    python_type = column.type.python_type
                assert python_type, f"Could not infer python_type for {column}"
                default = None
                if column.default is None and not column.nullable:
                    default = ...
                fields[name] = (python_type, default)
    pydantic_model = create_model(
        db_model.__name__, __config__=config, **fields  # type: ignore
    )
    return pydantic_model


### Helper Classes ###
class EndpointConfig:
    """Simple Python container object representing an endpoint configuration.
    Holds an API path string, a Pydantic Model, and a SQLAlchemy Model
    """

    def __repr__(self) -> str:
        return f"<{self.__class__}>{self.to_dict()}"

    def __init__(
        self, route: str, pydantic_model: BaseModel = None, sqlalchemy_model=None
    ) -> None:
        self.route = route
        self.pydantic_model = pydantic_model
        self.sqlalchemy_model = sqlalchemy_model

    def to_dict(self):
        return {
            "route": self.route,
            "pydantic_model": self.pydantic_model,
            "sqlalchemy_model": self.sqlalchemy_model,
        }


class HTTPMethod(Enum):
    GET = "GET"
    PUT = "PUT"
    POST = "POST"
    PATCH = "PATCH"
    DELETE = "DELETE"
    OPTIONS = "OPTIONS"

    @staticmethod
    def get_values():
        return [m.value for m in HTTPMethod]


### End Helper Classes ###


class AutoAPI:
    def __init__(self, db_connection_string: str) -> None:
        self.driver = SQLAlchemyDriver(db_connection_string)
        self.base = automap_base()
        self.base.prepare(autoload_with=self.driver.engine)
        self.base.metadata.reflect(bind=self.driver.engine)

    def __generate_endpoint_configs(self) -> List[EndpointConfig]:
        """Dynamically generate an EndpointConfig object for each table in the database

        Returns:
            List[EndpointConfig]: Returns a list of EndpointConfig objects.  Each object holds necessary atributes to generate a decorated API path function.
        """

        endpoint_configs = []
        for name in list(self.base.metadata.tables.keys()):
            table = self.base.metadata.tables.get(name)
            schema = table.schema
            if schema is not None:
                route = f"/{schema}/{table}"
            else:
                route = f"/{table}"
            sqlalchemy_model = self.base.classes.get(name)
            if not sqlalchemy_model:
                log.warn(f"Could not create model for table {table} with no primary key")
            pydantic_model = sqlalchemy_to_pydantic(sqlalchemy_model)
            config = EndpointConfig(
                route=route,
                pydantic_model=deepcopy(pydantic_model),
                sqlalchemy_model=deepcopy(sqlalchemy_model),
            )
            endpoint_configs.append(config)
        return endpoint_configs

    def generate_api_path_function(
        self,
        endpoint_config: EndpointConfig,
        router_or_app: Union[FastAPI, APIRouter],
        http_method: HTTPMethod = "GET",
    ) -> list:

        session = self.driver.sessionmaker()
        if http_method not in HTTPMethod.get_values():
            raise ValueError(f"Param {http_method} is invalid. Must be one of {HTTPMethod.get_values()}")

        elif http_method.upper() == HTTPMethod.GET.value:

            @router_or_app.get(
                endpoint_config.route,
                response_model=Union[
                    List[endpoint_config.pydantic_model], endpoint_config.pydantic_model
                ],
            )
            def auto_api_function(limit: Optional[int] = 10):
                res = session.query(endpoint_config.sqlalchemy_model)
                response = [row.__dict__ for row in res.limit(limit).all()]
                return response

            return auto_api_function

        elif http_method.upper() == HTTPMethod.POST.value:

            @router_or_app.post(
                endpoint_config.route,
                response_model=endpoint_config.pydantic_model
            )
            def auto_api_function(obj:endpoint_config.pydantic_model):
                sqlalchemy_obj = endpoint_config.sqlalchemy_model(**obj.__dict__)
                try:
                    session.add(sqlalchemy_obj)
                    session.commit()
                    return obj
                except IntegrityError as e:
                    session.rollback()
                    info = e.orig.args
                    try:
                        msg = info[1]
                    except IndexError:
                        msg = info[0]
                    log.error(msg)
                    return Response(content=msg, status_code=400)

        else:
            raise Exception(f"Handler for HTTP method {http_method} not created yet")

    def generate_api_path_functions(
        self, router_or_app: Union[FastAPI, APIRouter], http_methods=["GET"]
    ) -> list:
        endpoint_configs = self.__generate_endpoint_configs()

        api_path_functions = []
        for cfg in endpoint_configs:
            for method in http_methods:
                log.info(
                    f"Creating {method} API route {cfg.route} with Pydantic Model {cfg.pydantic_model} and SQLAlchemy Model {cfg.sqlalchemy_model}"
                )
                path_function = self.generate_api_path_function(
                    endpoint_config=cfg, router_or_app=router_or_app, http_method=method
                )
                api_path_functions.append(path_function)
                log.info(f"Created {method} {cfg.route}")

        return api_path_functions

    def create_api_app(self, http_methods=["GET"]):

        app = FastAPI(debug=DEBUG)
        self.generate_api_path_functions(router_or_app=app, http_methods=http_methods)

        @app.get("/health")
        @app.get("/health/")
        def healthcheck():
            return Response(status_code=200)

        return app


if __name__ == "__main__":
    connection_string = "postgresql+psycopg2://autoapi:autoapi@localhost:5432/autoapi"
    autoapi = AutoAPI(db_connection_string=connection_string)
    app = autoapi.create_api_app()
