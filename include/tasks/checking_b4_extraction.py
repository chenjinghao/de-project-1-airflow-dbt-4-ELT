import logging
import pendulum
from include.connection.connect_database import _connect_database
import pandas_market_calendars
import numpy as np

BUCKET_NAME = "bronze-my-de-project-485605"

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


def is_today_folder_exists(client, bucket_name=BUCKET_NAME, folder_name=None):
    '''Check if today's folder exists in the specified GCS bucket.
    Args:
        client (google.cloud.storage.Client): Google Cloud Storage client.
        bucket_name (str): Name of the GCS bucket.
        folder_name (str, optional): Specific folder name to check. Defaults to today's date in 'America/New_York' timezone.
        Returns:
        bool: True if the folder exists, False otherwise.
    '''

    folder = folder_name or f"{pendulum.today('America/New_York').to_date_string()}/"
    
    try:
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(folder)
        if blob.exists():
            return True
        else:
            # Check if there are any objects with this prefix, acting as a folder
            blobs = list(client.list_blobs(bucket_name, prefix=folder, max_results=1))
            if blobs:
                return True
            logging.info("Folder does not exist: %s/%s", bucket_name, folder)
            return False
    except Exception as exc:
        logging.exception("Failed to check folder existence for bucket=%s, prefix=%s", bucket_name, folder)
        raise

def create_today_folder():
    """
    Create today's folder in the specified GCS bucket if it doesn't exist.
    Returns:
        str: The path of the created folder in the format 'bucket_name/folder_name/'
    """
    client = _connect_database()
    bucket_name = BUCKET_NAME
    folder = f"{pendulum.today('America/New_York').to_date_string()}/"

    try:
        bucket = client.bucket(bucket_name)
        if not bucket.exists():
            client.create_bucket(bucket_name)
            logging.info("Created bucket %s", bucket_name)

        # Create a "folder" by uploading an empty object with a trailing slash
        blob = bucket.blob(folder)
        blob.upload_from_string("")
        logging.info("Created folder %s/%s", bucket_name, folder)

        return f"{bucket_name}/{folder}"
    except Exception as exc:
        logging.exception("Failed to ensure folder %s/%s", bucket_name, folder)
        raise

def check_files_exist_in_folder():
    """
    Check which files exist in today's folder and determine which task to start from.
    
    Returns:
        str: Task ID to branch to based on existing files
            - "extract_most_active_stocks" if most_active_stocks.json doesn't exist
            - "price_top3_most_active_stocks" if only most_active_stocks.json exists
            - "news_top3_most_active_stocks" if most_active + all price files exist
            - "biz_info_top3_most_active_stocks" if most_active + price + all news files exist
            - "skip_extraction" if all files exist
    """
    client = _connect_database()
    prefix_name = pendulum.today('America/New_York').to_date_string()
    prefix = f"{prefix_name}/"

    try:
        blobs = client.list_blobs(BUCKET_NAME, prefix=prefix)
        json_keys = [blob.name for blob in blobs if blob.name.endswith(".json")]
        logging.info(f"Found {len(json_keys)} JSON files in {prefix}: {json_keys}")
    except Exception as exc:
        logging.exception("Failed to list objects for bucket=%s, prefix=%s", BUCKET_NAME, prefix)
        return "extract_most_active_stocks"

    # Check for most_active_stocks.json
    most_active_file = f"{prefix_name}/most_active_stocks.json"
    has_most_active = most_active_file in json_keys
    
    if not has_most_active:
        logging.info("most_active_stocks.json does not exist. Starting from extract_most_active_stocks.")
        return "extract_most_active_stocks"
    
    # Check for price files (expecting 3 files with pattern *_stocks_price.json)
    price_files = [f for f in json_keys if '/price/' in f and f.endswith('_stocks_price.json')]
    has_all_price = len(price_files) >= 3
    
    if not has_all_price:
        logging.info(f"Found {len(price_files)} price files. Starting from price_top3_most_active_stocks.")
        return "price_top3_most_active_stocks"
    
    # Check for news files (expecting 3 files with pattern *_stocks_news.json)
    news_files = [f for f in json_keys if '/news/' in f and f.endswith('_stocks_news.json')]
    has_all_news = len(news_files) >= 3
    
    if not has_all_news:
        logging.info(f"Found {len(news_files)} news files. Starting from news_top3_most_active_stocks.")
        return "news_top3_most_active_stocks"
    
    # Check for business_info files (expecting 3 files with pattern *_stocks_business_info.json)
    biz_files = [f for f in json_keys if '/business_info/' in f and f.endswith('_stocks_business_info.json')]
    has_all_biz = len(biz_files) >= 3
    
    if not has_all_biz:
        logging.info(f"Found {len(biz_files)} business_info files. Starting from biz_info_top3_most_active_stocks.")
        return "biz_info_top3_most_active_stocks"
    
    # All files exist, skip extraction
    logging.info("All extraction files exist. Skipping extraction group.")
    return "skip_extraction"
