from enum import Enum
from time import sleep
from typing import List, Optional, Union
from venv import create

from fastapi import APIRouter, FastAPI, Response
from sqlalchemy import create_engine, inspect, types
from sqlalchemy.schema import Table, MetaData
from sqlalchemy.sql.expression import select
from pydantic import create_model, BaseModel

from logconfig import log, DEBUG

### Helper Classes and Functions ###
class EndpointConfig:
    """Simple Python container object representing an endpoint configuration.
    Holds an API path string, a Pydantic Model, and a SQLAlchemy Model
    """

    def __repr__(self) -> str:
        return f"<{self.__class__}>{self.to_dict()}"

    def __init__(
        self, route: str, pydantic_model: BaseModel = None
    ) -> None:
        self.route = route
        self.pydantic_model = pydantic_model

    def to_dict(self):
        return {
            "route": self.route,
            "pydantic_model": self.pydantic_model,
        }

class HTTPMethod(Enum):
    GET = "GET"
    # PUT = "PUT"
    # POST = "POST"
    # PATCH = "PATCH"
    # DELETE = "DELETE"
    # OPTIONS = "OPTIONS"

    @staticmethod
    def get_values():
        return [m.value for m in HTTPMethod]
### END Helper Classes and Functions ###

class TrinoAutoApi:

    def __init__(self, host=None, user=None, password=None, port=None):

        if host is None:
            host = "trino"
            log.info(f"Using default hostname '{host}")
        if user is None:
            user = "trino"
            log.info(f"Using default username '{user}")
        if port is None:
            port = 8080
            log.info(f"Using default port '{port}")
        
        conn_info = {
            "host":host,
            "user":user,
            "port":str(port)
        }
        log.info(f"Attempting to connect to Trino. Connection info: {conn_info}")
        if password is not None:
            conn_info["password"] = password
            log.info(f"Password set - {''.join(['x' for letter in password])}")
        else:
            log.info("No password set...")
        
        self.conn_info = conn_info

        if password is None:
            self.base_connection_string = f"trino://{user}@{host}:{port}"
        else:
            self.base_connection_string = f"trino://{user}:{password}@{host}:{port}" 

        self.engines = {} # Initialize empty dict to hold SQLAlchemy Engines. Will have one per connection  
    
    def get_catalog_names(self, exclude = ['jmx', 'memory', 'system', 'tpcds', 'tpch']):

        engine = create_engine(self.base_connection_string)
        self.engines["base"] = engine
        
        conn = engine.connect()
        cur = conn.execute("SHOW CATALOGS")
        rows = cur.fetchall()
        catalogs = [row[0] for row in rows if row[0] not in exclude]
        conn.close()
        
        return catalogs
    
    def get_schema_names(self, catalog, exclude=['default','information_schema']):
        
        engine = self.engines.get(catalog)
        if engine is None:
            engine = create_engine(self.base_connection_string + f"/{catalog}")
        insp = inspect(engine)
        schemas = insp.get_schema_names()
        schemas = [schema for schema in schemas if schema not in exclude]
        return schemas
    
    def get_tables(self, catalog, schema, exclude=[]):
        
        engine = self.engines.get(catalog)
        if engine is None:
            engine = create_engine(self.base_connection_string + f"/{catalog}")
        insp = inspect(engine)
        tables = insp.get_table_names(schema)
        tables = [table for table in tables if table not in exclude]
        return tables
    
    def get_columns(self, catalog, schema, table):
        
        engine = self.engines.get(catalog)
        if engine is None:
            engine = create_engine(self.base_connection_string + f"/{catalog}")
        insp = inspect(engine)
        columns = insp.get_columns(schema=schema, table_name=table)
        return columns
    
    def pydantic_from_table(self, catalog, schema, table):
        
        columns = self.get_columns(catalog,schema, table)
        
        model_dict = {}
        
        for col in columns:

            col_name = col["name"]
            col_type = col["type"]
            
            
            if isinstance(col_type, types.String):
                model_dict[col_name] = (Optional[str],...)
            elif isinstance(col_type, types.Float):
                model_dict[col_name] = (Optional[float],...)
            elif isinstance(col_type, types.Integer):
                model_dict[col_name] = (Optional[int],...)
            elif isinstance(col_type, types.Boolean):
                model_dict[col_name] = (Optional[bool],...)
            else:
                raise Exception(f"No handler for column {col_name} with type {col_type}")
        
        model_name = f"{schema}_{table}"
        
        model = create_model(model_name, **model_dict)
        
        return model

    def __generate_endpoint_configs(self):

        endpoint_configs = []

        catalogs = self.get_catalog_names()

        for catalog in catalogs:
            schemas = self.get_schema_names(catalog)

            for schema in schemas:
                tables = self.get_tables(catalog, schema)

                for table in tables:
                    try:
                        pydantic_model = self.pydantic_from_table(catalog, schema, table)
                        endpoint_config = EndpointConfig(
                            route = f"/{catalog}/{schema}/{table}",
                            pydantic_model = pydantic_model
                        )
                        endpoint_configs.append(endpoint_config)
                    except Exception as e:
                        log.error(f"Cannot create pydantic model for table {catalog}.{schema}.{table}.")
                        log.error(e)
        
        return endpoint_configs
    
    def generate_api_path_function(
        self,
        endpoint_config: EndpointConfig,
        router_or_app: Union[FastAPI, APIRouter],
        http_method: HTTPMethod = "GET",
    ) -> list:

        if http_method.upper() == HTTPMethod.GET.value:

            @router_or_app.get(
                endpoint_config.route,
                response_model=Union[
                    List[endpoint_config.pydantic_model], endpoint_config.pydantic_model
                ],
            )
            @router_or_app.get(
                endpoint_config.route + "/",
                response_model=Union[
                    List[endpoint_config.pydantic_model], endpoint_config.pydantic_model
                ],
                include_in_schema=False
            )
            def auto_api_function(limit: Optional[int] = 10):

                catalog, schema, table = endpoint_config.route.strip("/").split("/")
                
                engine = self.engines.get(catalog)
                if engine is None:
                    engine = create_engine(self.base_connection_string + f"/{catalog}")
                if limit is None:
                    limit = 10
                
                table = Table(
                    table,
                    MetaData(schema=schema),
                    autoload=True,
                    autoload_with=engine
                )

                conn = engine.connect()
                cursor = conn.execute(select(table))
                rows = cursor.fetchmany(limit)
                col_names = list(cursor.keys())
                response = [dict(zip(col_names, row)) for row in rows]
                conn.close()
                return response

            return auto_api_function
                    
    def generate_api_path_functions(
        self, router_or_app: Union[FastAPI, APIRouter], http_methods=["GET"]
    ) -> list:
        endpoint_configs = self.__generate_endpoint_configs()

        api_path_functions = []
        for cfg in endpoint_configs:
            route = cfg.route
            pydantic_model = cfg.pydantic_model
            for method in http_methods:
                if method not in HTTPMethod.get_values():
                    log.error(f"HTTP Method {method} not supported. Skipping path function creation")
                    continue
                log.info(
                    f"Creating {method} API route {route} with Pydantic Model {pydantic_model}"
                )
                path_function = self.generate_api_path_function(
                    endpoint_config=cfg, router_or_app=router_or_app, http_method=method
                )
                api_path_functions.append(path_function)
                log.info(f"Created {method} {cfg.route}")

        return api_path_functions

    def create_api_app(self, http_methods = ["GET"]):
        
        app = FastAPI(debug=DEBUG)
        self.generate_api_path_functions(router_or_app=app, http_methods=http_methods)

        @app.get("/health")
        @app.get("/health/", include_in_schema=False)
        def healthcheck():
            return Response(status_code=200)

        return app