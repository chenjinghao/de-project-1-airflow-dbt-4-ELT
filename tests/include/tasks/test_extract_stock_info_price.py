import sys
from unittest.mock import MagicMock, patch
import pytest

# Mock modules that might be missing in the test environment
sys.modules['airflow'] = MagicMock()
sys.modules['airflow.sdk'] = MagicMock()
sys.modules['airflow.sdk.bases'] = MagicMock()
sys.modules['airflow.sdk.bases.hook'] = MagicMock()
sys.modules['airflow.exceptions'] = MagicMock()
sys.modules['minio'] = MagicMock()
# sys.modules['requests'] = MagicMock() # requests is installed, no need to mock module level if not needed, but code does imports

# Import the module under test
# We rely on PYTHONPATH including the root directory
from include.tasks.extract_stock_info import extract_price_top3_most_active_stocks

def test_extract_price_top3_most_active_stocks():
    # Setup mocks
    mock_ti = MagicMock()
    mock_context = {'ti': mock_ti}

    # Mock return values for xcom_pull
    def xcom_side_effect(key, task_ids):
        if key == 'most_active_stocks':
            return [{'ticker': 'AAPL'}, {'ticker': 'GOOGL'}, {'ticker': 'MSFT'}]
        return None

    mock_ti.xcom_pull.side_effect = xcom_side_effect

    with patch('include.tasks.extract_stock_info._connect_database') as mock_connect_db, \
         patch('include.tasks.extract_stock_info.BaseHook') as mock_base_hook, \
         patch('include.tasks.extract_stock_info.re') as mock_requests:
         # Note: we don't mock time.sleep anymore because we removed it or it's not used in parallel path

        # Setup MinIO client mock
        mock_client = MagicMock()
        mock_connect_db.return_value = mock_client

        # Setup API connection mock
        mock_api_conn = MagicMock()
        mock_api_conn.host = 'http://api.example.com'
        mock_api_conn.password = 'dummy_key'
        mock_base_hook.get_connection.return_value = mock_api_conn

        # Setup Requests mock
        mock_response = MagicMock()
        mock_response.json.return_value = {'Time Series (Daily)': {}}
        mock_response.raise_for_status.return_value = None
        mock_requests.get.return_value = mock_response

        file_path = "my-bucket/2023-10-27"

        # Run the function
        result = extract_price_top3_most_active_stocks(file_path, **mock_context)

        # Verify result
        assert result == "All price data for top 3 most active stocks stored in my-bucket/2023-10-27/price/"

        # Verify MinIO put_object calls
        assert mock_client.put_object.call_count == 3

        # Verify calls - since it is concurrent, order is not guaranteed, so we check existence
        # Collect all object names uploaded
        uploaded_objects = [c[1]['object_name'] for c in mock_client.put_object.call_args_list]
        expected_objects = [
            '2023-10-27/price/0_AAPL_stocks_price.json',
            '2023-10-27/price/1_GOOGL_stocks_price.json',
            '2023-10-27/price/2_MSFT_stocks_price.json'
        ]

        assert sorted(uploaded_objects) == sorted(expected_objects)

        # Verify API calls
        assert mock_requests.get.call_count == 3

        # Verify params
        symbols_requested = []
        for call in mock_requests.get.call_args_list:
            symbols_requested.append(call[1]['params']['symbol'])
            assert call[1]['params']['function'] == 'TIME_SERIES_DAILY'
            assert call[1]['params']['apikey'] == 'dummy_key'

        assert sorted(symbols_requested) == sorted(['AAPL', 'GOOGL', 'MSFT'])
