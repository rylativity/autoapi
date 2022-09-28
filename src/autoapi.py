from enum import Enum
from typing import List, Optional, Union

from fastapi import APIRouter, FastAPI, Response
from sqlalchemy import create_engine, inspect, types
from sqlalchemy.engine import make_url, URL
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
        self, route: str, pydantic_model: BaseModel, sqlalchemy_uri: Union[str, URL]
    ) -> None:
        self.pydantic_model = pydantic_model
        self.route = route
        self.sqlalchemy_uri: URL = make_url(sqlalchemy_uri)
        
    def to_dict(self):
        return {
            "route": self.route,
            "pydantic_model": self.pydantic_model,
            "sqlalchemy_uri": self.sqlalchemy_uri
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

class AutoApi:

    def __init__(self, sqlalchemy_uris:str=None, host:str=None, user:str=None, port:Union[str,int]=None, dialect:str=None, password:str=None):

        if sqlalchemy_uris:
            if type(sqlalchemy_uris) != str:
                raise ValueError("sqlalchemy_uris must be string of comma-separated SQLAlchemy URIs")
            uris = sqlalchemy_uris.split(",")
        else:
            if None in [host,user,port,dialect]:
                raise ValueError("If sqlalchemy_uris is None, host, user, port, and dialect must not be None")

            conn_info = {
                "host":host,
                "user":user,
                "port":str(port),
                "dialect":dialect
            }
            log.info(f"Attempting to connect to database. Connection info: {conn_info}")
            if password is not None:
                conn_info["password"] = password
                log.info(f"Password set - {''.join(['x' for letter in password])}")
            else:
                log.info("No password set...")
            
            self.conn_info = conn_info

            if password is None:
                uris = [f"{dialect}://{user}@{host}:{port}"]
            else:
                uris = [f"{dialect}://{user}:{password}@{host}:{port}"]

        self.sqlalchemy_uris: list[URL] = []
        for uri in uris:
            self.sqlalchemy_uris.append(make_url(uri))

    
    def get_database_names(self, uri, exclude = ['jmx', 'memory', 'system', 
                                                'tpcds', 'tpch', 'template0', 'template1']): # database is referred to as "catalog" in trino

        engine = create_engine(uri)

        dialect = engine.dialect.name.lower()
        
        if dialect in ["trino"]:
            get_db_statement = "SHOW CATALOGS"
        elif dialect in ["postgresql"]:
            get_db_statement = "SELECT datname FROM pg_database;"
        else:
            raise Exception(f"Dialect {dialect} not yet supported. A SQL statement to fetch available databases must be added")
        
        conn = engine.connect()
        cur = conn.execute(get_db_statement)
        rows = cur.fetchall()
        catalogs = [row[0] for row in rows if row[0] not in exclude]
        conn.close()
        
        return catalogs
    
    def get_schema_names(self, uri, database, exclude=['default','information_schema']):
        
        engine = create_engine(f"{uri}/{database}")
        insp = inspect(engine)
        schemas = insp.get_schema_names()
        schemas = [schema for schema in schemas if schema not in exclude]
        return schemas
    
    def get_tables(self, uri, database, schema, exclude=[]):
        
        engine = create_engine(f"{uri}/{database}")
        insp = inspect(engine)
        tables = insp.get_table_names(schema)
        tables = [table for table in tables if table not in exclude]
        return tables
    
    def get_columns(self, uri, catalog, schema, table):
        
        engine = create_engine(f"{uri}/{catalog}")
        insp = inspect(engine)
        columns = insp.get_columns(schema=schema, table_name=table)
        return columns
    
    def pydantic_from_table(self, uri:Union[str, URL], database:str, schema:str, table:str):
        
        columns = self.get_columns(uri, database, schema, table)
        
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

        for uri in self.sqlalchemy_uris:

            databases = self.get_database_names(uri=uri)

            for database in databases:
                schemas = self.get_schema_names(uri=uri, database=database)

                for schema in schemas:
                    tables = self.get_tables(uri=uri, database=database, schema=schema)

                    for table in tables:
                        try:
                            pydantic_model = self.pydantic_from_table(uri=uri, database=database, schema=schema, table=table)
                            endpoint_config = EndpointConfig(
                                route = f"/{uri.host}/{database}/{schema}/{table}",
                                pydantic_model = pydantic_model,
                                sqlalchemy_uri=uri
                            )
                            endpoint_configs.append(endpoint_config)
                        except Exception as e:
                            log.error(f"Cannot create pydantic model for table {database}.{schema}.{table} (SQLAlchemy connection URI = {uri}).")
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

                _, database, schema, table_name = endpoint_config.route.strip("/").split("/")
                
                engine = create_engine(str(endpoint_config.sqlalchemy_uri) + f"/{database}")
                if limit is None:
                    limit = 10
                
                table = Table(
                    table_name,
                    MetaData(schema=schema),
                    autoload=True,
                    autoload_with=engine
                )

                with engine.connect() as conn:
                    cursor = conn.execute(select(table))
                    rows = cursor.fetchmany(limit)
                    col_names = list(cursor.keys())
                    response = [dict(zip(col_names, row)) for row in rows]
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