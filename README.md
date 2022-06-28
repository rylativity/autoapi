# Python AutoAPI
## Automatically generate a REST API for an existing database
Built on top of FastAPI and SQLAlchemy

## Setup
- Run `docker-compose up -d` (This will bring up the API along with a sample database)

## Configuration
The API service expects an environment variable 'DB_CONNECTION_STRING' to be set.  By default, this value is configured for the sample postgres database included in the docker-compose.yml.  Simply replace this value with your own sqlalchemy-compatible connection string (Note: you will also need to add your database-specific sqlalchemy-compatible python library to the requirements.txt file).

## ROADMAP
- [x] Update util.py classes to use SQLAlchemy automap_base to map databases
- [ ] Update readme with basic usage instructions