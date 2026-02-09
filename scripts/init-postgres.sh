#!/bin/bash
set -e

# Connect to default 'postgres' database to check/create other databases
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "postgres" <<-EOSQL
    SELECT 'CREATE DATABASE stocks_db'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'stocks_db')\gexec
    GRANT ALL PRIVILEGES ON DATABASE stocks_db TO $POSTGRES_USER;
EOSQL
