import logging
import json
import os
import psycopg2
from psycopg2.extras import Json, execute_values
from psycopg2 import sql
from airflow.providers.postgres.hooks.postgres import PostgresHook
# from airflow.providers.google.cloud.hooks.gcs import GCSHook # Uncomment if using GCS instead of MinIO
from include.connection.connect_database import _connect_database


# Constants
TABLE_NAME = "raw_most_active_stocks"
BIZ_LOOKUP_TABLE_NAME = "biz_info_lookup"
BUCKET_NAME = "bronze"

def _ensure_table(cur, table_name):
    """Ensure the main table exists in Postgres."""
    cur.execute(
        sql.SQL("""
            CREATE TABLE IF NOT EXISTS {} (
                date DATE PRIMARY KEY,
                most_active JSONB,
                price1 JSONB, price2 JSONB, price3 JSONB,
                new1 JSONB, new2 JSONB, new3 JSONB
            );
        """).format(sql.Identifier(table_name))
    )

def _load_json(client, bucket_name, blob_name):
    """Load JSON from GCS."""
    if hasattr(client, "get_object"):
        try:
            response = client.get_object(bucket_name, blob_name)
            data = response.read()
            response.close()
            response.release_conn()
            return json.loads(data)
        except Exception as e:
            logging.warning(f"File {blob_name} not found or error: {e}")
            return None

    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    
    # Validate if file exists to prevent crash
    if not blob.exists():
        logging.warning(f"File {blob_name} not found.")
        return None
    
    data = blob.download_as_text()
    return json.loads(data)

def _get_postgres_connection():
    """Get Postgres connection from Airflow Hook or fallback to env vars."""
    try:
        hook = PostgresHook(postgres_conn_id="postgres_stock")
        return hook.get_conn()
    except Exception as e:
        logging.warning(f"Connection 'postgres_stock' not found: {e}. Falling back to direct connection.")
        return psycopg2.connect(
            host="database",
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", "postgres"),
            dbname=os.getenv("POSTGRES_DB", "stocks_db")
        )

def load_to_db(**kwargs):
    """
    Accepts **kwargs to get the Airflow execution date (ds).
    """
    logging.info("Starting load_to_db task execution")
    # 1. Use Airflow's date (YYYY-MM-DD)
    try:
        prefix_name = kwargs['ds']
        logging.info(f"Processing date: {prefix_name}")
    except KeyError:
        logging.error("KeyError: 'ds' not found in kwargs. Ensure **context is passed from the DAG.")
        raise
    
    # 2. Connect to GCS (or MinIO) using Airflow's connection
    # client = GCSHook(gcp_conn_id='google_cloud_default').get_conn()
    # logging.info("Connected to GCS")
    client = _connect_database()
    logging.info("Connected to MinIO")

    logging.info("Connecting to Postgres...")
    # 2. Use Context Manager for auto-commit and safe closing
    with _get_postgres_connection() as conn:
        logging.info("Postgres connection established")
        with conn.cursor() as cur:
            
            # List files
            if hasattr(client, "list_objects"):
                objs = client.list_objects(BUCKET_NAME, prefix=prefix_name, recursive=True)
                json_keys = [obj.object_name for obj in objs if obj.object_name.endswith(".json")]
            else:
                blobs = client.list_blobs(BUCKET_NAME, prefix=prefix_name)
                json_keys = [blob.name for blob in blobs if blob.name.endswith(".json")]
            logging.info(f"Found {len(json_keys)} files for date {prefix_name}")

            _ensure_table(cur, TABLE_NAME)

            cols = {
                "date": prefix_name,
                "most_active": None,
                "price1": None, "price2": None, "price3": None,
                "new1": None, "new2": None, "new3": None,
            }

            # Map files (Logic looks good)
            for key in json_keys:
                data = _load_json(client, BUCKET_NAME, key)
                if not data: continue
                
                if "most_active_stocks.json" in key:
                    cols["most_active"] = Json(data)
                elif "/price/0_" in key: cols["price1"] = Json(data)
                elif "/price/1_" in key: cols["price2"] = Json(data)
                elif "/price/2_" in key: cols["price3"] = Json(data)
                elif "/news/0_" in key: cols["new1"] = Json(data)
                elif "/news/1_" in key: cols["new2"] = Json(data)
                elif "/news/2_" in key: cols["new3"] = Json(data)

            # 3. FIXED: SQL Injection safety + UPSERT logic
            # Use DO UPDATE so re-runs fill in missing data
            insert_stmt = sql.SQL("""
                INSERT INTO {} (
                    date, most_active,
                    price1, price2, price3,
                    new1, new2, new3
                )
                VALUES (
                    %(date)s, %(most_active)s,
                    %(price1)s, %(price2)s, %(price3)s,
                    %(new1)s, %(new2)s, %(new3)s
                )
                ON CONFLICT (date) DO UPDATE SET
                    most_active = EXCLUDED.most_active,
                    price1 = EXCLUDED.price1,
                    price2 = EXCLUDED.price2,
                    price3 = EXCLUDED.price3,
                    new1 = EXCLUDED.new1,
                    new2 = EXCLUDED.new2,
                    new3 = EXCLUDED.new3;
            """).format(sql.Identifier(TABLE_NAME))

            cur.execute(insert_stmt, cols)
            logging.info(f"Upserted data for {prefix_name}")

BIZ_LOOKUP_COLUMNS = [
    "Symbol",
    "AssetType",
    "Name",
    "Description",
    "CIK",
    "Exchange",
    "Currency",
    "Country",
    "Sector",
    "Industry",
    "Address",
    "OfficialSite",
    "FiscalYearEnd",
    "LatestQuarter",
    "MarketCapitalization",
    "EBITDA",
    "PERatio",
    "PEGRatio",
    "BookValue",
    "DividendPerShare",
    "DividendYield",
    "EPS",
    "RevenuePerShareTTM",
    "ProfitMargin",
    "OperatingMarginTTM",
    "ReturnOnAssetsTTM",
    "ReturnOnEquityTTM",
    "RevenueTTM",
    "GrossProfitTTM",
    "DilutedEPSTTM",
    "QuarterlyEarningsGrowthYOY",
    "QuarterlyRevenueGrowthYOY",
    "AnalystTargetPrice",
    "AnalystRatingStrongBuy",
    "AnalystRatingBuy",
    "AnalystRatingHold",
    "AnalystRatingSell",
    "AnalystRatingStrongSell",
    "TrailingPE",
    "ForwardPE",
    "PriceToSalesRatioTTM",
    "PriceToBookRatio",
    "EVToRevenue",
    "EVToEBITDA",
    "Beta",
    "52WeekHigh",
    "52WeekLow",
    "50DayMovingAverage",
    "200DayMovingAverage",
    "SharesOutstanding",
    "SharesFloat",
    "PercentInsiders",
    "PercentInstitutions",
    "DividendDate",
    "ExDividendDate",
]


def _ensure_lookup_table(cur, table_name):
    """Ensure the lookup table exists in Postgres."""
    cols_sql = [
        sql.SQL("{} TEXT").format(sql.Identifier(c)) for c in BIZ_LOOKUP_COLUMNS
    ]
    cur.execute(
        sql.SQL("CREATE TABLE IF NOT EXISTS {} ({} , PRIMARY KEY ({}));").format(
            sql.Identifier(table_name),
            sql.SQL(", ").join(cols_sql),
            sql.Identifier("Symbol"),
        )
    )

def _normalize_value(v):
    """Normalize value for insertion."""
    if isinstance(v, (dict, list)):
        return json.dumps(v)
    return v

def load_2_db_biz_lookup(**kwargs):
    """Load business info data into Postgres lookup table."""
    logging.info("Starting load_2_db_biz_lookup task execution")
    
    # 1. Use Airflow date
    try:
        prefix_name = kwargs['ds']
        logging.info(f"Processing date: {prefix_name}")
    except KeyError:
        logging.error("KeyError: 'ds' missing.")
        raise

    prefix = f"{prefix_name}/business_info"

    # client = GCSHook(gcp_conn_id='google_cloud_default').get_conn()
    # logging.info("Connected to GCS")
    client = _connect_database()
    logging.info("Connected to MinIO")

    logging.info("Connecting to Postgres...")
    with _get_postgres_connection() as conn:
        logging.info("Postgres connection established")
        with conn.cursor() as cur:

            if hasattr(client, "list_objects"):
                objs = client.list_objects(BUCKET_NAME, prefix=prefix, recursive=True)
                json_keys = [obj.object_name for obj in objs if obj.object_name.endswith(".json")]
            else:
                blobs = client.list_blobs(BUCKET_NAME, prefix=prefix)
                json_keys = [blob.name for blob in blobs if blob.name.endswith(".json")]

            _ensure_lookup_table(cur, BIZ_LOOKUP_TABLE_NAME)

            # 2. Prepare Query
            insert_query = sql.SQL("""
                INSERT INTO {} ({})
                VALUES %s
                ON CONFLICT ({}) DO UPDATE SET
                -- Generate 'col = EXCLUDED.col' for all columns except Symbol
                {}
            """).format(
                sql.Identifier(BIZ_LOOKUP_TABLE_NAME),
                sql.SQL(", ").join(map(sql.Identifier, BIZ_LOOKUP_COLUMNS)),
                sql.Identifier("Symbol"),
                sql.SQL(", ").join([
                    sql.SQL("{} = EXCLUDED.{}").format(sql.Identifier(c), sql.Identifier(c))
                    for c in BIZ_LOOKUP_COLUMNS if c != "Symbol"
                ])
            )

            def generate_records():
                for key in json_keys:
                    data = _load_json(client, BUCKET_NAME, key)
                    if not data: continue

                    records = data if isinstance(data, list) else [data]
                    for record in records:
                        if not isinstance(record, dict) or "Symbol" not in record:
                            continue
                        # _normalize_value function needs to be in scope or imported
                        yield [_normalize_value(record.get(c)) for c in BIZ_LOOKUP_COLUMNS]

            # 3. Execute Values
            # execute_values handles the VALUES %s expansion automatically
            execute_values(cur, insert_query, generate_records())
            logging.info(f"Inserted records into {BIZ_LOOKUP_TABLE_NAME}.")
