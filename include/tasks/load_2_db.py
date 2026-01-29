import pandas as pd
import logging
import json
import concurrent.futures
from psycopg2.extras import Json, execute_values
from psycopg2 import sql
from airflow.providers.postgres.hooks.postgres import PostgresHook
from include.connection.connect_database import _connect_database

TABLE_NAME = "raw_most_active_stocks"
BIZ_LOOKUP_TABLE_NAME = "biz_info_lookup"

def _ensure_table(cur, table_name):
    cur.execute(
        sql.SQL("""
            CREATE TABLE IF NOT EXISTS {} (
                date DATE PRIMARY KEY,
                most_active JSONB,
                price1 JSONB,
                price2 JSONB,
                price3 JSONB,
                new1 JSONB,
                new2 JSONB,
                new3 JSONB
            );
        """).format(
            sql.Identifier(table_name)
        )
    )

def _load_json(client, bucket, key):
    resp = client.get_object(bucket, key)
    data = resp.read()
    resp.close()
    resp.release_conn()
    return json.loads(data.decode("utf-8"))

def load_to_db():
    client = _connect_database()
    postgres_hook = PostgresHook(postgres_conn_id="postgres_stock")
    conn = postgres_hook.get_conn()
    cur = conn.cursor()

    BUCKET_NAME = "bronze"
    today_ts = pd.Timestamp.now()
    prefix_name = today_ts.strftime("%Y-%m-%d")

    objects = client.list_objects(bucket_name=BUCKET_NAME, prefix=prefix_name, recursive=True)
    json_keys = [obj.object_name for obj in objects if obj.object_name.endswith(".json")]

    logging.info(f"JSON files in {BUCKET_NAME}/{prefix_name}: {json_keys}")

    _ensure_table(cur, table_name=TABLE_NAME)

    cols = {
        "date": prefix_name,
        "most_active": None,
        "price1": None,
        "price2": None,
        "price3": None,
        "new1": None,
        "new2": None,
        "new3": None,
    }

    # Map files to columns by filename patterns
    # Fetch data in parallel to speed up I/O
    def load_file(key):
        return key, _load_json(client, BUCKET_NAME, key)

    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_to_key = {executor.submit(load_file, key): key for key in json_keys}
        for future in concurrent.futures.as_completed(future_to_key):
            key, data = future.result()
            if key.endswith("most_active_stocks.json"):
                cols["most_active"] = Json(data)
            elif "/price/0_" in key:
                cols["price1"] = Json(data)
            elif "/price/1_" in key:
                cols["price2"] = Json(data)
            elif "/price/2_" in key:
                cols["price3"] = Json(data)
            elif "/news/0_" in key:
                cols["new1"] = Json(data)
            elif "/news/1_" in key:
                cols["new2"] = Json(data)
            elif "/news/2_" in key:
                cols["new3"] = Json(data)

    cur.execute(
        f"""
        INSERT INTO {TABLE_NAME} (
            date, most_active,
            price1, price2, price3,
            new1, new2, new3
        )
        VALUES (%(date)s, %(most_active)s,
                %(price1)s, %(price2)s, %(price3)s,
                %(new1)s, %(new2)s, %(new3)s)
        ON CONFLICT (date) DO NOTHING;
        """,
        cols,
    )
    conn.commit()
    cur.close()
    conn.close()
    logging.info("Data loaded into the database successfully.")

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
    if isinstance(v, (dict, list)):
        return json.dumps(v)
    return v

def load_2_db_biz_lookup():
    client = _connect_database()
    postgres_hook = PostgresHook(postgres_conn_id="postgres_stock")
    conn = postgres_hook.get_conn()
    cur = conn.cursor()

    BUCKET_NAME = "bronze"
    today_ts = pd.Timestamp.now()
    prefix_name = today_ts.strftime("%Y-%m-%d")
    prefix = f"{prefix_name}/business_info"

    objects = client.list_objects(bucket_name=BUCKET_NAME, prefix=prefix, recursive=True)
    json_keys = [obj.object_name for obj in objects if obj.object_name.endswith(".json")]

    logging.info(f"JSON files in {BUCKET_NAME}/{prefix}: {json_keys}")

    _ensure_lookup_table(cur, table_name=BIZ_LOOKUP_TABLE_NAME)

    cols = BIZ_LOOKUP_COLUMNS

    # Use batch insert with execute_values
    insert_query = sql.SQL("""
        INSERT INTO {} ({})
        VALUES %s
        ON CONFLICT ({}) DO NOTHING
    """).format(
        sql.Identifier(BIZ_LOOKUP_TABLE_NAME),
        sql.SQL(", ").join(map(sql.Identifier, cols)),
        sql.Identifier("Symbol"),
    )

    # Convert to string as required by execute_values when using Composed objects
    insert_query_str = insert_query.as_string(conn)

    def generate_records():
        for key in json_keys:
            data = _load_json(client, BUCKET_NAME, key)

            records = data if isinstance(data, list) else [data]
            for record in records:
                if not isinstance(record, dict) or "Symbol" not in record:
                    logging.warning(f"Skipping invalid record in {key}: {record}")
                    continue

                yield [_normalize_value(record.get(c)) for c in cols]

    execute_values(cur, insert_query_str, generate_records())
    logging.info(f"Inserted records into {BIZ_LOOKUP_TABLE_NAME}.")

    conn.commit()
    cur.close()
    conn.close()
    logging.info("Business lookup data loaded into the database successfully.")
