import sys
from unittest.mock import MagicMock, patch
import pytest
import time

# Mock modules that might be missing in the test environment
sys.modules['airflow'] = MagicMock()
sys.modules['airflow.sdk'] = MagicMock()
sys.modules['airflow.sdk.bases'] = MagicMock()
sys.modules['airflow.sdk.bases.hook'] = MagicMock()
sys.modules['airflow.providers'] = MagicMock()
sys.modules['airflow.providers.postgres'] = MagicMock()
sys.modules['airflow.providers.postgres.hooks'] = MagicMock()
sys.modules['airflow.providers.postgres.hooks.postgres'] = MagicMock()
sys.modules['psycopg2'] = MagicMock()
sys.modules['psycopg2.extras'] = MagicMock()
sys.modules['psycopg2.sql'] = MagicMock()
sys.modules['minio'] = MagicMock()
sys.modules['pandas'] = MagicMock()

# Import the module under test
# We rely on PYTHONPATH including the root directory
from include.tasks.load_2_db import load_to_db, load_2_db_biz_lookup

def test_load_to_db_performance():
    # Setup mocks
    with patch('include.tasks.load_2_db._connect_database') as mock_connect_db, \
         patch('include.tasks.load_2_db.PostgresHook') as mock_pg_hook, \
         patch('include.tasks.load_2_db.pd') as mock_pd, \
         patch('include.tasks.load_2_db.execute_values') as mock_execute_values:

        # Mock MinIO client
        mock_client = MagicMock()
        mock_connect_db.return_value = mock_client

        # Mock listing objects (7 files)
        file_list = [
            MagicMock(object_name='2023-10-27/most_active_stocks.json'),
            MagicMock(object_name='2023-10-27/price/0_AAPL.json'),
            MagicMock(object_name='2023-10-27/price/1_GOOGL.json'),
            MagicMock(object_name='2023-10-27/price/2_MSFT.json'),
            MagicMock(object_name='2023-10-27/news/0_AAPL.json'),
            MagicMock(object_name='2023-10-27/news/1_GOOGL.json'),
            MagicMock(object_name='2023-10-27/news/2_MSFT.json'),
        ]
        mock_client.list_objects.return_value = file_list

        # Mock get_object with delay
        def side_effect_get_object(bucket, key):
            time.sleep(0.1) # Simulate network latency
            mock_resp = MagicMock()
            mock_resp.read.return_value = b'{"some": "data"}'
            return mock_resp

        mock_client.get_object.side_effect = side_effect_get_object

        # Mock Postgres connection
        mock_conn = MagicMock()
        mock_pg_hook.return_value.get_conn.return_value = mock_conn
        mock_cur = mock_conn.cursor.return_value

        # Mock pandas timestamp
        mock_pd.Timestamp.now.return_value.strftime.return_value = '2023-10-27'

        # Measure time
        start_time = time.time()
        load_to_db()
        end_time = time.time()

        duration = end_time - start_time
        print(f"load_to_db execution time: {duration:.4f}s")

        # Verify calls
        assert mock_client.get_object.call_count == 7
        assert mock_cur.execute.call_count >= 2 # create table + insert

def test_load_2_db_biz_lookup_performance():
    # Setup mocks
    with patch('include.tasks.load_2_db._connect_database') as mock_connect_db, \
         patch('include.tasks.load_2_db.PostgresHook') as mock_pg_hook, \
         patch('include.tasks.load_2_db.pd') as mock_pd, \
         patch('include.tasks.load_2_db.execute_values') as mock_execute_values:

        # Mock MinIO client
        mock_client = MagicMock()
        mock_connect_db.return_value = mock_client

        # Mock listing objects (3 files)
        file_list = [
            MagicMock(object_name='2023-10-27/business_info/0_AAPL.json'),
            MagicMock(object_name='2023-10-27/business_info/1_GOOGL.json'),
            MagicMock(object_name='2023-10-27/business_info/2_MSFT.json'),
        ]
        mock_client.list_objects.return_value = file_list

        # Mock get_object with delay
        def side_effect_get_object(bucket, key):
            time.sleep(0.1) # Simulate network latency
            mock_resp = MagicMock()
            # Return valid structure for biz info
            mock_resp.read.return_value = b'{"Symbol": "AAPL", "Name": "Apple Inc."}'
            return mock_resp

        mock_client.get_object.side_effect = side_effect_get_object

        # Mock Postgres connection
        mock_conn = MagicMock()
        mock_pg_hook.return_value.get_conn.return_value = mock_conn
        mock_cur = mock_conn.cursor.return_value

        # Mock execute_values to consume generator
        def side_effect_execute_values(cur, sql, argslist):
            # argslist is a generator, consume it to trigger downloads
            list(argslist)
        mock_execute_values.side_effect = side_effect_execute_values

        # Mock pandas timestamp
        mock_pd.Timestamp.now.return_value.strftime.return_value = '2023-10-27'

        # Measure time
        start_time = time.time()
        load_2_db_biz_lookup()
        end_time = time.time()

        duration = end_time - start_time
        print(f"load_2_db_biz_lookup execution time: {duration:.4f}s")

        # Verify calls
        assert mock_client.get_object.call_count == 3
