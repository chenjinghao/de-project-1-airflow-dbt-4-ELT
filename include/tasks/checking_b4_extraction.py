import logging
from io import BytesIO
import pendulum
from include.connection.connect_database import _connect_database
import logging
import pandas_market_calendars
import numpy as np
import pandas as pd

def is_holiday(
    timezone: str = "America/New_York",
    calendar: str = "NYSE",
) -> str:
    """
    Returns the task_id to follow based on whether 'today' is a market holiday.
    Args:
        timezone (str): Timezone to consider for 'today'. Default is "America/New_York".
        calendar (str): Market calendar to use. Default is "NYSE".
    Returns:
        bool: True if today is a holiday, False otherwise.
    """ 
    today = pendulum.today(timezone).to_date_string()
    today = np.datetime64(today)

    cal = pandas_market_calendars.get_calendar(calendar)
    holidays = cal.holidays().holidays
    is_holiday = today in holidays

    if is_holiday:
        logging.info("%s is a holiday. Skipping stock data processing.", today)
        return True

    logging.info("%s is not a holiday. Proceeding with stock data processing.", today)
    return False


def is_today_folder_exists(client, bucket_name="bronze", folder_name=None):
    folder = folder_name or f"{pendulum.today('America/New_York').to_date_string()}/"
    try:
        objects = client.list_objects(bucket_name, prefix=folder, recursive=False)
        for obj in objects:
            if obj.object_name == folder:
                return True
            else:
                logging.info("Folder already exists: %s/%s", bucket_name, folder)
                return False
    except Exception as exc:
        logging.exception("Failed to list objects for bucket=%s, prefix=%s", bucket_name, folder)
        raise

def create_today_folder():
    client = _connect_database()
    bucket_name = "bronze"
    folder = f"{pendulum.today('America/New_York').to_date_string()}/"

    try:
        if client.bucket_exists(bucket_name):

            client.put_object(bucket_name, folder, BytesIO(b""), 0)
            logging.info("Created folder %s/%s", bucket_name, folder)
        else:
            client.make_bucket(bucket_name)
            logging.info("Created bucket %s", bucket_name)

            client.put_object(bucket_name, folder, BytesIO(b""), 0)
            logging.info("Created folder %s/%s", bucket_name, folder)

        return f"{bucket_name}/{folder}"
    except Exception as exc:
        logging.exception("Failed to ensure folder %s/%s", bucket_name, folder)
        raise

def check_files_exist_in_folder():
    """
    Check which files exist in today's folder and determine which tasks to run.
    
    Returns:
        list[str]: List of task IDs to branch to.
    """
    client = _connect_database()
    BUCKET_NAME = "bronze"
    prefix_name = pendulum.today('America/New_York').to_date_string()
    prefix = f"{prefix_name}/"

    try:
        objects = client.list_objects(bucket_name=BUCKET_NAME, prefix=prefix, recursive=True)
        json_keys = [obj.object_name for obj in objects if obj.object_name.endswith(".json")]
        logging.info(f"Found {len(json_keys)} JSON files in {prefix}: {json_keys}")
    except Exception as exc:
        logging.exception("Failed to list objects for bucket=%s, prefix=%s", BUCKET_NAME, prefix)
        return ["extract_most_active_stocks"]

    # Check for most_active_stocks.json
    most_active_file = f"{prefix_name}/most_active_stocks.json"
    has_most_active = most_active_file in json_keys
    
    if not has_most_active:
        logging.info("most_active_stocks.json does not exist. Starting from extract_most_active_stocks.")
        return ["extract_most_active_stocks"]

    tasks_to_run = []
    
    # Check for price files (expecting 3 files with pattern *_stocks_price.json)
    price_files = [f for f in json_keys if '/price/' in f and f.endswith('_stocks_price.json')]
    has_all_price = len(price_files) >= 3
    
    if not has_all_price:
        logging.info(f"Found {len(price_files)} price files. Adding price_top3_most_active_stocks to run list.")
        tasks_to_run.append("price_top3_most_active_stocks")
    
    # Check for news files (expecting 3 files with pattern *_stocks_news.json)
    news_files = [f for f in json_keys if '/news/' in f and f.endswith('_stocks_news.json')]
    has_all_news = len(news_files) >= 3
    
    if not has_all_news:
        logging.info(f"Found {len(news_files)} news files. Adding news_top3_most_active_stocks to run list.")
        tasks_to_run.append("news_top3_most_active_stocks")
    
    # Check for business_info files (expecting 3 files with pattern *_stocks_business_info.json)
    biz_files = [f for f in json_keys if '/business_info/' in f and f.endswith('_stocks_business_info.json')]
    has_all_biz = len(biz_files) >= 3
    
    if not has_all_biz:
        logging.info(f"Found {len(biz_files)} business_info files. Adding biz_info_top3_most_active_stocks to run list.")
        tasks_to_run.append("biz_info_top3_most_active_stocks")

    if not tasks_to_run:
        # All files exist, skip extraction
        logging.info("All extraction files exist. Skipping extraction group.")
        return ["skip_extraction"]
    
    return tasks_to_run
