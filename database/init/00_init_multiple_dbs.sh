#!/bin/bash
set -e

# Create single database with two schemas (NDS + DDS)
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE "SMI_DSS";
EOSQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "SMI_DSS" <<-EOSQL
    CREATE SCHEMA IF NOT EXISTS nds;
    CREATE SCHEMA IF NOT EXISTS dds;
EOSQL

echo "Database SMI_DSS created with schemas nds and dds"

# Run NDS schema creation against SMI_DSS database
if [ -f "/database/nds/01_create_nds_schema.sql" ]; then
    echo "Running NDS schema creation..."
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "SMI_DSS" -f "/database/nds/01_create_nds_schema.sql"
fi

# Run DDS schema creation against SMI_DSS database
if [ -f "/database/dds/01_create_dds_schema.sql" ]; then
    echo "Running DDS schema creation..."
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "SMI_DSS" -f "/database/dds/01_create_dds_schema.sql"
fi

# Run ETL procedures against SMI_DSS database
if [ -f "/database/dds/02_etl_procedures.sql" ]; then
    echo "Running ETL procedures..."
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "SMI_DSS" -f "/database/dds/02_etl_procedures.sql"
fi

# Run seed data against SMI_DSS database
if [ -f "/database/init/03_seed_data.sql" ]; then
    echo "Running seed data..."
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "SMI_DSS" -f "/database/init/03_seed_data.sql"
fi

echo "Database initialization completed successfully"
