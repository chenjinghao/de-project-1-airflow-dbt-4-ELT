
import sys
import time
import unittest
from unittest.mock import MagicMock
import json

# Mock dependencies
sys.modules['airflow'] = MagicMock()
sys.modules['airflow.providers.postgres.hooks.postgres'] = MagicMock()
sys.modules['airflow.sdk.bases.hook'] = MagicMock()
sys.modules['psycopg2'] = MagicMock()
sys.modules['psycopg2.extras'] = MagicMock()
sys.modules['psycopg2.sql'] = MagicMock()
sys.modules['minio'] = MagicMock()
sys.modules['pandas'] = MagicMock()

# Setup mocks before importing the module
from airflow.providers.postgres.hooks.postgres import PostgresHook
from psycopg2.extras import Json

# Mock PostgresHook
mock_postgres_hook = MagicMock()
PostgresHook.return_value = mock_postgres_hook
mock_conn = MagicMock()
mock_postgres_hook.get_conn.return_value = mock_conn
mock_cur = MagicMock()
mock_conn.cursor.return_value = mock_cur

# Mock Minio client
mock_client = MagicMock()

# Mock _connect_database
sys.modules['include.connection.connect_database'] = MagicMock()
from include.connection.connect_database import _connect_database
_connect_database.return_value = mock_client

# Add project root to sys.path to import include
import os
sys.path.append(os.getcwd())

# Import the module to test
from include.tasks.load_2_db import load_to_db

class BenchmarkLoad2DB:
    def setup(self):
        # Simulate list_objects return values
        self.files = [
            "2023-10-26/most_active_stocks.json",
            "2023-10-26/price/0_AAPL_stocks_price.json",
            "2023-10-26/price/1_MSFT_stocks_price.json",
            "2023-10-26/price/2_GOOG_stocks_price.json",
            "2023-10-26/news/0_AAPL_stocks_news.json",
            "2023-10-26/news/1_MSFT_stocks_news.json",
            "2023-10-26/news/2_GOOG_stocks_news.json",
        ]

        mock_objects = [MagicMock(object_name=f) for f in self.files]
        mock_client.list_objects.return_value = mock_objects

        # Simulate get_object delay
        def side_effect_get_object(bucket, key):
            time.sleep(0.1) # Simulate 100ms latency
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps({"test": "data"}).encode("utf-8")
            return mock_resp

        mock_client.get_object.side_effect = side_effect_get_object

    def run(self):
        self.setup()
        start_time = time.time()
        load_to_db()
        end_time = time.time()
        print(f"Execution time: {end_time - start_time:.4f} seconds")

if __name__ == "__main__":
    benchmark = BenchmarkLoad2DB()
    benchmark.run()
