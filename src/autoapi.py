from copy import deepcopy
import logging
import os
from typing import List, Optional, Container, Type

from pydantic import BaseConfig, BaseModel, create_model

from sqlalchemy import create_engine
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.inspection import inspect
from sqlalchemy.orm.properties import ColumnProperty
from sqlalchemy.orm import sessionmaker

class SQLAlchemyDriver:

    def __init__(self, connection_string:str):
        self.engine = create_engine(connection_string)
        with self.engine.connect(): # test the connection
            pass
        self.sessionmaker = sessionmaker(self.engine)
    
    def query(self, query_string: str):
        with self.engine.connect() as conn:
            result = conn.execute(query_string)
        return [dict(row) for row in result]
    

class EndpointConfig:
    """ Simple Python object representing an endpoint configuration (url route, pydantic model, and sqlalchemy model) dynamically generated from a SQL table
    """

    def __repr__(self) -> str:
        return f"<{self.__class__}>{self.to_dict()}"

    def __init__(self, route:str, pydantic_model: BaseModel, sqlalchemy_model = None) -> None:
        self.route=route
        self.pydantic_model=pydantic_model
        self.sqlalchemy_model=sqlalchemy_model

    def to_dict(self):
        return {
            "route":self.route,
            "pydantic_model":self.pydantic_model,
            "sqlalchemy_model":self.sqlalchemy_model
        }

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

class ModelEndpointFactory:

    log = logging.getLogger(__name__)
    log.setLevel("INFO")

    def __init__(self, db_connection_string: str) -> None:
        self.driver = SQLAlchemyDriver(db_connection_string)
        self.base = automap_base()
        self.base.prepare(autoload_with=self.driver.engine)
        self.base.metadata.reflect(bind=self.driver.engine)

    def generate_endpoint_configs(self) -> List[EndpointConfig]:

        endpoint_configs = []
        for name in list(self.base.metadata.tables.keys()):
            table = self.base.metadata.tables.get(name)
            schema = table.schema
            if schema is not None:
                route = f"/{schema}/{table}"
            else:
                route = f"/{table}"
            sqlalchemy_model = self.base.classes.get(name)
            pydantic_model = sqlalchemy_to_pydantic(sqlalchemy_model)
            config = EndpointConfig(route = route, pydantic_model = deepcopy(pydantic_model), sqlalchemy_model=deepcopy(sqlalchemy_model))
            endpoint_configs.append(config)
        return endpoint_configs

if __name__ == "__main__":
    endpoint_factory = ModelEndpointFactory(db_connection_string="postgresql+psycopg2://autoapi:autoapi@localhost:5432/autoapi")
    configs = endpoint_factory.generate_endpoint_configs()
    print(configs)