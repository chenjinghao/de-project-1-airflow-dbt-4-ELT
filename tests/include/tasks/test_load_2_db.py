
import sys
import unittest.mock
from unittest.mock import MagicMock, patch
import pytest

# Mock modules
sys.modules['airflow'] = MagicMock()
sys.modules['airflow.sdk'] = MagicMock()
sys.modules['airflow.sdk.bases'] = MagicMock()
sys.modules['airflow.sdk.bases.hook'] = MagicMock()
sys.modules['airflow.providers.postgres.hooks.postgres'] = MagicMock()
sys.modules['airflow.exceptions'] = MagicMock()
sys.modules['google.cloud'] = MagicMock()
sys.modules['google.cloud.storage'] = MagicMock()
sys.modules['google.oauth2'] = MagicMock()
sys.modules['psycopg2'] = MagicMock()
sys.modules['psycopg2.extras'] = MagicMock()
sys.modules['psycopg2.sql'] = MagicMock()
sys.modules['pandas'] = MagicMock()
sys.modules['pandas'].Timestamp.now.return_value.strftime.return_value = "2023-10-27"

# Import the module under test
# ensure include.connection.connect_database is mocked before import
sys.modules['include.connection.connect_database'] = MagicMock()

from include.tasks.load_2_db import load_to_db

@patch('include.tasks.load_2_db.PostgresHook')
@patch('include.tasks.load_2_db.Json')
def test_load_to_db_parallel(mock_json, mock_pg_hook):
    # Setup Mocks
    mock_connect_db = sys.modules['include.connection.connect_database']._connect_database
    mock_client = MagicMock()
    mock_connect_db.return_value = mock_client

    # Mock list_blobs
    file_list = [
        MagicMock(name=f"most_active_stocks.json"),
        MagicMock(name=f"path/price/0_AAPL_stocks_price.json"),
    ]
    file_list[0].name = "most_active_stocks.json"
    file_list[1].name = "path/price/0_AAPL_stocks_price.json"

    mock_client.list_blobs.return_value = file_list

    # Mock bucket/blob
    mock_bucket = MagicMock()
    mock_client.bucket.return_value = mock_bucket
    mock_blob = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_blob.download_as_text.return_value = '{"data": "value"}'

    # Mock DB
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_pg_hook.return_value.get_conn.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cur

    # Mock Json side effect to verify data
    mock_json.side_effect = lambda x: f"JSON({x})"

    # Run
    load_to_db()

    # Assertions
    # Verify both files were downloaded
    assert mock_blob.download_as_text.call_count == 2

    # Verify execute was called (once for CREATE TABLE, once for INSERT)
    assert mock_cur.execute.call_count == 2

    # Get the last call (INSERT)
    args, kwargs = mock_cur.execute.call_args
    # Check that cols were populated
    assert 'most_active' in args[1]
    # Python dict repr uses single quotes
    assert args[1]['most_active'] == "JSON({'data': 'value'})"
    assert 'price1' in args[1]
    assert args[1]['price1'] == "JSON({'data': 'value'})"
