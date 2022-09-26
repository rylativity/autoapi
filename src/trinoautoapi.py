from enum import Enum
from typing import List, Optional, Union

from fastapi import APIRouter, FastAPI, Response
from trino.dbapi import connect
from trino.exceptions import TrinoExternalError
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
            log.info(f"Using default username '{username}")
        if port is None:
            port = 8080
            log.info(f"Using default port '{port}")
        
        conn_info = {
            "host":host,
            "user":user,
            "port":str(port)
        }
        log.info(f"Connecting to Trino. Connection info: {conn_info}")
        if password is not None:
            conn_info["password"] = password
            log.info(f"Password set - {''.join(['x' for letter in password])}")
        else:
            log.info("No password set...")
        
        self.conn_info = conn_info
        self.trino_conn = connect(**conn_info)
        
        cur = self.trino_conn.cursor()
        # Query runtime nodes to test connection
        cur.execute("SELECT * FROM system.runtime.nodes")
        rows = cur.fetchall()
        field_names = [d[0] for d in cur.description]

        self.node_info = [dict(zip(field_names, row)) for row in rows]
        log.info(f"Nodes Discovered: {self.node_info}")
    
    def get_catalog_names(self, exclude = ['jmx', 'memory', 'system', 'tpcds', 'tpch']):

        cur = self.trino_conn.cursor()
        cur.execute("SHOW CATALOGS")
        rows = cur.fetchall()
        catalogs = [row[0] for row in rows if row[0] not in exclude]
        
        return catalogs
    
    def get_schema_names(self, catalog, exclude=['default','information_schema']):
    
        cur = self.trino_conn.cursor()
        cur.execute(f"SHOW SCHEMAS IN {catalog}")
        rows = cur.fetchall()
        schemas = [row[0] for row in rows if row[0] not in exclude]
        return schemas
    
    def get_tables(self, catalog, schema, exclude=[]):
        cur = self.trino_conn.cursor()
        cur.execute(f"SHOW TABLES IN {catalog}.{schema}")
        rows = cur.fetchall()
        tables = [row[0] for row in rows if row[0] not in exclude]
        return tables
    
    def describe_table(self, catalog, schema, table):
        cur = self.trino_conn.cursor()
        cur.execute(f"DESCRIBE {catalog}.{schema}.{table}")
        rows = cur.fetchall()
        table_desc = dict(zip([row[0] for row in rows], [row[1] for row in rows]))
        return table_desc
    
    def pydantic_from_table(self, catalog, schema, table):
        
        table_desc = self.describe_table(catalog,schema, table)
        
        model_dict = {}
        
        for col_name, trino_type in table_desc.items():
            
            if trino_type == 'varchar':
                model_dict[col_name] = (Optional[str],...)
            elif trino_type == 'double':
                model_dict[col_name] = (Optional[float],...)
            elif trino_type == 'integer':
                model_dict[col_name] = (Optional[int],...)
            else:
                raise Exception(f"No handler for column {col_name} with type {trino_type}")
        
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
                    except TrinoExternalError as e:
                        if e.error_name == "UNSUPPORTED_TABLE_TYPE":
                            log.error(f"Cannot create pydantic model for table {catalog}.{schema}.{table}.")
        
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
            def auto_api_function(limit: Optional[int] = None):

                if limit is None:
                    limit = 10
                sql_table_name = endpoint_config.route.strip("/").replace("/",".")
                cur = self.trino_conn.cursor()
                rows = cur.execute(f"SELECT * FROM {sql_table_name} LIMIT {limit}")
                col_names = [d[0] for d in cur.description]
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
        @app.get("/health/")
        def healthcheck():
            return Response(status_code=200)

        return app