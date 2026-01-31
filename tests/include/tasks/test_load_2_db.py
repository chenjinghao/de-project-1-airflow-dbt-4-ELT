import sys
from unittest.mock import MagicMock, patch
import pytest

# Mock modules that might be missing or need mocking
sys.modules['airflow'] = MagicMock()
sys.modules['airflow.providers.postgres.hooks.postgres'] = MagicMock()
sys.modules['include.connection.connect_database'] = MagicMock()

# Mock psycopg2
mock_psycopg2 = MagicMock()
sys.modules['psycopg2'] = mock_psycopg2
sys.modules['psycopg2.extras'] = MagicMock()
sys.modules['psycopg2.sql'] = MagicMock()

# Mock Google Cloud
sys.modules['google.cloud'] = MagicMock()

# Mock pandas
mock_pd = MagicMock()
sys.modules['pandas'] = mock_pd

# Import the module under test
# We rely on PYTHONPATH including the root directory
from include.tasks.load_2_db import load_to_db, load_2_db_biz_lookup

@pytest.fixture
def mock_dependencies():
    with patch('include.tasks.load_2_db._connect_database') as mock_connect_db, \
         patch('include.tasks.load_2_db.PostgresHook') as mock_pg_hook, \
         patch('include.tasks.load_2_db.Json') as mock_json, \
         patch('include.tasks.load_2_db.execute_values') as mock_execute_values:

        # Setup GCS client mock
        mock_client = MagicMock()
        mock_connect_db.return_value = mock_client

        # Setup Postgres mock
        mock_conn = MagicMock()
        # Ensure encoding is present for execute_values/sql.as_string
        mock_conn.encoding = 'UTF8'

        mock_cur = MagicMock()
        mock_pg_hook.return_value.get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur

        # Setup Json wrapper to just return the data
        mock_json.side_effect = lambda x: x

        yield {
            'client': mock_client,
            'cur': mock_cur,
            'conn': mock_conn,
            'json': mock_json,
            'execute_values': mock_execute_values
        }

def test_load_to_db(mock_dependencies):
    mocks = mock_dependencies
    client = mocks['client']
    cur = mocks['cur']

    # Setup GCS blobs
    blob1 = MagicMock()
    blob1.name = "2023-10-27/most_active_stocks.json"
    blob1.download_as_text.return_value = '[{"ticker": "AAPL"}]'

    blob2 = MagicMock()
    blob2.name = "2023-10-27/price/0_AAPL_stocks_price.json"
    blob2.download_as_text.return_value = '{"price": 150}'

    client.list_blobs.return_value = [blob1, blob2]

    # Map blob names to mocks for client.bucket().blob()
    blobs_map = {
        blob1.name: blob1,
        blob2.name: blob2
    }

    def blob_side_effect(blob_name):
        return blobs_map.get(blob_name, MagicMock())

    client.bucket.return_value.blob.side_effect = blob_side_effect

    # Run function
    load_to_db()

    # Verify GCS calls
    assert blob1.download_as_text.call_count == 1
    assert blob2.download_as_text.call_count == 1

    # Verify DB calls
    # Check that execute was called with an INSERT statement
    assert cur.execute.call_count >= 2 # One for _ensure_table, one for INSERT

    # Get the last call to execute (the INSERT)
    args, kwargs = cur.execute.call_args
    sql_query = args[0]
    params = args[1]

    assert "INSERT INTO raw_most_active_stocks" in sql_query
    assert params['most_active'] == [{"ticker": "AAPL"}]
    assert params['price1'] == {"price": 150}

def test_load_2_db_biz_lookup(mock_dependencies):
    mocks = mock_dependencies
    client = mocks['client']
    cur = mocks['cur']
    execute_values = mocks['execute_values']

    # Setup GCS blobs
    blob1 = MagicMock()
    blob1.name = "2023-10-27/business_info/0_AAPL_stocks_business_info.json"
    blob1.download_as_text.return_value = '{"Symbol": "AAPL", "Name": "Apple Inc."}'

    client.list_blobs.return_value = [blob1]

    # Map blob names to mocks
    blobs_map = {
        blob1.name: blob1
    }

    def blob_side_effect(blob_name):
        return blobs_map.get(blob_name, MagicMock())

    client.bucket.return_value.blob.side_effect = blob_side_effect

    # Run function
    load_2_db_biz_lookup()

    # Verify execute_values called
    assert execute_values.call_count == 1
    call_args = execute_values.call_args

    # Args: (cur, sql, argslist)
    # Check that argslist (generator) produces the expected record
    generator = call_args[0][2]
    records = list(generator)

    assert len(records) == 1
    # Check first column (Symbol) and third (Name) based on BIZ_LOOKUP_COLUMNS order
    # "Symbol" is index 0, "Name" is index 2
    assert records[0][0] == "AAPL"
    assert records[0][2] == "Apple Inc."
