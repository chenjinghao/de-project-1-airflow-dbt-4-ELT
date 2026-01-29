
import sys
import unittest
from unittest.mock import MagicMock, call
import json
import os

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
from psycopg2.extras import Json

# Configure Json to return the data passed to it
Json.side_effect = lambda x: x

from airflow.providers.postgres.hooks.postgres import PostgresHook

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

# Add project root to sys.path
sys.path.append(os.getcwd())

# Import
from include.tasks.load_2_db import load_to_db

class TestLoad2DB(unittest.TestCase):
    def test_load_to_db_populates_cols_correctly(self):
        # Setup
        files = [
            "2023-10-26/most_active_stocks.json",
            "2023-10-26/price/0_AAPL_stocks_price.json",
        ]

        mock_objects = [MagicMock(object_name=f) for f in files]
        mock_client.list_objects.return_value = mock_objects

        def side_effect_get_object(bucket, key):
            mock_resp = MagicMock()
            if "most_active_stocks.json" in key:
                 content = {"data": "active"}
            else:
                 content = {"data": "price"}
            mock_resp.read.return_value = json.dumps(content).encode("utf-8")
            return mock_resp

        mock_client.get_object.side_effect = side_effect_get_object

        # Run
        load_to_db()

        # Assert
        # Check if execute was called
        self.assertTrue(mock_cur.execute.called)

        # Get the call args
        # Find the call with INSERT
        insert_call = None
        for call_args in mock_cur.execute.call_args_list:
            args, _ = call_args
            if "INSERT INTO" in args[0]:
                insert_call = call_args
                break

        self.assertIsNotNone(insert_call)
        args, _ = insert_call
        query, params = args

        self.assertIn("raw_most_active_stocks", query)

        # Verify params are populated correctly
        # Since Json returns the input data (due to side_effect), we can check directly
        self.assertEqual(params['most_active'], {"data": "active"})
        self.assertEqual(params['price1'], {"data": "price"})
        self.assertIsNone(params['price2'])

if __name__ == '__main__':
    unittest.main()
