# Python AutoAPI
## Automatically generate a REST API for an existing database
This containerized python app will automatically profile a database and create a fully-documented REST API, allowing you to read and modify tables over HTTP.  

## Setup & Configuration

**Important Note**: *The target database, for which an API will be dynamically created, will be profiled by autoapi when the application is run (i.e. when a container is created from the autoapi image and run, such as when running `docker-compose up -d`).  Any changes to database structure and schemas (including creation/deletion of tables or changes to column types of existing tables) will not be recognized by autoapi until the application (or container) is restarted**

### **Getting Started**
- Run `docker-compose up -d` (This will bring up the API along with a sample Postgres database.  Very basic sample SQL tables are automatically created by the SQL scripts mounted into the sample Postgres database)
- Navigate to http://localhost:8000/docs to see the automatically-generated Swagger API Documentation and test the API

### **Connecting to Another Database**
The API service expects an environment variable 'SQLALCHEMY_URIS' to be set. SQLALCHEMY_URIS should be a string of comma-separated SQLAlchemy URIs. DO NOT INCLUDE A DATABASE NAME AT THE END OF THE URI!!  By default, the SQLALCHEMY_URIS value is configured for the sample postgres database included in the docker-compose.yml.  

To generate an API for another database (see supported database types listed below): 
1. Add your database-specific sqlalchemy-compatible python dialects to the requirements.txt file so that they are `pip install`ed into the API container image when it is built).
2. Add the SQLAlchemy connection string for the database to the SQLALCHEMY_URIS environment variable in the docker-compose.yml
3. Rebuild and bring up the AutoAPI container (`docker-compose up -d --build`)
```
docker-compose build autoapi
``` 
or 
```
docker build -t autoapi .
```
)
3. Update the DB_CONNECTION_STRING environment variable with the SQLAlchemy-compatible connection-string for the database.  If you are using the provided docker-compose.yml file, you can simply update the DB_CONNECTION_STRING environment variable to use your connection string.
 

### **Adding Additional Tables to or Interacting with the Sample Postgres Database**
SQL commands can be executed using the psql command line tool that is bundled in the Postgres Docker image.  If you want to open a shell in the Postgres container, you can run
 ```
 docker-compose exec postgres psql -U autoapi
 ```  
 Alternatively, you can create a .sql script (with PostgreSQL syntax) and execute the contents of the script by running 
 ```
 docker-compose exec postgres psql -U autoapi -c "$(cat ./<YOUR_SCRIPT>.sql)"
 ```

 ## Supported Databases

The following databases are currently supported, but more will be added:
- Trino
- PostgreSQL

Adding support for a new database is simply a matter of adding the required python requirements for the given database to the requirements.txt and adding a "get_db_statement" line for the given dialect in the "get_database_names" method in the autoapi.AutoApi class.

## ROADMAP
- [x] Restore Postgres Examples
- [ ] Document "SQLALCHEMY_URIS" environment variable
- [ ] Add support for additional databases
    - [x] Add check for supported dialect
    - [ ] Add SQL statements for listing databases in autoapi.py
        - [x] PostgreSQL
- [ ] Update readme with basic usage instructions
- [ ] Implement config/model saving
- [ ] Implement authorization
- [ ] Add class and method docstring
- [ ] Add Create/Update/Delete routes
- [ ] Add pagination