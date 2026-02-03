import json
import requests
import logging
from airflow.sdk.bases.hook import BaseHook
from airflow.exceptions import AirflowException
from include.connection.connect_database import _connect_database
import time

def extract_most_active_stocks(folder_path, **context):
    """Extract most active stocks from Alpha Vantage API and store in GCS"""
    logging.info("Extracting most active stocks data from API.")

    bucket_name = folder_path.split('/')[0]
    folder_name = folder_path.split('/')[1]
    
    api = BaseHook.get_connection('stock_api')
    url = f'{api.host}'
    
    try:
        response = requests.get(
            url,
            params={'function': 'TOP_GAINERS_LOSERS', 
                    'apikey': api.password},
            timeout=10
        )
        response.raise_for_status()
        logging.info("Successfully retrieved most active stocks data.")
        
        most_active_stocks = response.json()
        most_active_stocks = most_active_stocks.get('most_actively_traded', [])
        context['ti'].xcom_push(key='most_active_stocks', value=most_active_stocks)
        
        
        client = _connect_database()
        data = json.dumps(most_active_stocks, ensure_ascii=False)

        object_name = f'{folder_name}/most_active_stocks.json'
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(object_name)
        blob.upload_from_string(data, content_type='application/json')

        logging.info(f"Stored most active stocks data at {bucket_name}/{object_name}")
        return f"{bucket_name}/{object_name}"

    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to extract most active stocks data: {e}")
        raise AirflowException("Most active stocks API request failed.")
    
def extract_price_top3_most_active_stocks(file_path, **context):
    """Extract price data for top 3 most active stocks and store in GCS"""
    logging.info("Extracting price data for top 3 most active stocks.")

    api = BaseHook.get_connection('stock_api')
    url = f'{api.host}'

    try:
        client = _connect_database()
        bucket_name = file_path.split('/')[0]
        folder_name = file_path.split('/')[1]
        bucket = client.bucket(bucket_name)

        # Try to get most_active_stocks from XCom with multiple possible sources
        most_active_stocks = context['ti'].xcom_pull(key='most_active_stocks', task_ids='Extraction_from_API.extract_most_active_stocks')
        if not most_active_stocks:
            # Try without the group prefix
            most_active_stocks = context['ti'].xcom_pull(key='most_active_stocks', task_ids='extract_most_active_stocks')
        if not most_active_stocks:
            raise AirflowException("most_active_stocks XCom missing from extract_most_active_stocks")

        top3_stocks = [stock['ticker'] for stock in most_active_stocks[:3]]
        context['ti'].xcom_push(key='top3_stocks', value=top3_stocks)

        for symbol in top3_stocks:
            stock_response = requests.get(
                url,
                params={'function': 'TIME_SERIES_DAILY', 
                        'symbol': symbol,
                        'apikey': api.password},
                timeout=10
            )
            stock_response.raise_for_status()
            price_data = stock_response.json()

            data = json.dumps(price_data, ensure_ascii=False)

            object_name = f'{folder_name}/price/{top3_stocks.index(symbol)}_{symbol}_stocks_price.json'
            blob = bucket.blob(object_name)
            blob.upload_from_string(data, content_type='application/json')

            logging.info(f"Stored price data for {symbol} at {bucket_name}/{object_name}")
            time.sleep(2)  # To respect API rate limits
        return f"All price data for top 3 most active stocks stored in {bucket_name}/{folder_name}/price/"

    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to extract price data: {e}")
        raise AirflowException("Price data API request failed.")
    
def extract_news_top3_most_active_stocks(**context):
    """Extract news sentiment data for top 3 most active stocks from Alpha Vantage API and store in GCS"""
    logging.info("News extraction for top 3 most active stocks.")
    
    client = _connect_database()

    api = BaseHook.get_connection('stock_api')
    url = f'{api.host}'

    # Try to get top3_stocks from XCom with multiple possible sources
    top3_stocks = context['ti'].xcom_pull(key='top3_stocks', task_ids='Extraction_from_API.price_top3_most_active_stocks')
    if not top3_stocks:
        # Try without the group prefix
        top3_stocks = context['ti'].xcom_pull(key='top3_stocks', task_ids='price_top3_most_active_stocks')
    if not top3_stocks:
        raise AirflowException("top3_stocks XCom missing from price_top3_most_active_stocks")

    folder_path = context['ti'].xcom_pull(key='return_value', task_ids='Extraction_from_API.create_today_folder')
    if not folder_path:
        folder_path = context['ti'].xcom_pull(key='return_value', task_ids='create_today_folder')
    bucket_name = folder_path.split('/')[0]
    folder_name = folder_path.split('/')[1]
    bucket = client.bucket(bucket_name)

    try:
        for symbol in top3_stocks:
            response = requests.get(
                url,
                params={'function': 'NEWS_SENTIMENT', 
                        'tickers': symbol,
                        'apikey': api.password},
                timeout=10
            )
            response.raise_for_status()
            news_data = response.json()

            data = json.dumps(news_data, ensure_ascii=False)

            object_name = f'{folder_name}/news/{top3_stocks.index(symbol)}_{symbol}_stocks_news.json'
            blob = bucket.blob(object_name)
            blob.upload_from_string(data, content_type='application/json')

            logging.info(f"Stored news data for {symbol} at {bucket_name}/{object_name}")
            time.sleep(2)
        return f"All news data for top 3 most active stocks stored in {bucket_name}/{folder_name}/news/"
    
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to extract news data: {e}")
        raise AirflowException("News data API request failed.")

def extract_biz_info_top3_most_active_stocks(**context):
    """Extract business info for top 3 most active stocks from Alpha Vantage API and store in GCS"""
    logging.info("Business info extraction for top 3 most active stocks.")
    
    client = _connect_database()

    api = BaseHook.get_connection('stock_api')
    url = f'{api.host}'

    # Try to get top3_stocks from XCom with multiple possible sources
    top3_stocks = context['ti'].xcom_pull(key='top3_stocks', task_ids='Extraction_from_API.price_top3_most_active_stocks')
    if not top3_stocks:
        # Try without the group prefix
        top3_stocks = context['ti'].xcom_pull(key='top3_stocks', task_ids='price_top3_most_active_stocks')
    if not top3_stocks:
        raise AirflowException("top3_stocks XCom missing from price_top3_most_active_stocks")

    folder_path = context['ti'].xcom_pull(key='return_value', task_ids='Extraction_from_API.create_today_folder')
    
    if not folder_path:
        folder_path = context['ti'].xcom_pull(key='return_value', task_ids='create_today_folder')
    
    bucket_name = folder_path.split('/')[0]
    folder_name = folder_path.split('/')[1]
    bucket = client.bucket(bucket_name)

    try:
        for symbol in top3_stocks:
            response = requests.get(
                url,
                params={'function': 'OVERVIEW', 
                        'symbol': symbol,
                        'apikey': api.password},
                timeout=10
            )
            response.raise_for_status()
            biz_info_data = response.json()

            data = json.dumps(biz_info_data, ensure_ascii=False)

            object_name = f'{folder_name}/business_info/{top3_stocks.index(symbol)}_{symbol}_stocks_business_info.json'
            blob = bucket.blob(object_name)
            blob.upload_from_string(data, content_type='application/json')

            logging.info(f"Stored business info data for {symbol} at {bucket_name}/{object_name}")
            time.sleep(2)  # To respect API rate limits
        return f"All business info data for top 3 most active stocks stored in {bucket_name}/{folder_name}/business_info/"
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to extract business info data: {e}")
        raise AirflowException("Business info data API request failed.")
