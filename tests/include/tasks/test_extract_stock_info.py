import sys
from unittest.mock import MagicMock, patch
import pytest

# Mock modules that might be missing in the test environment
sys.modules['airflow'] = MagicMock()
sys.modules['airflow.sdk'] = MagicMock()
sys.modules['airflow.sdk.bases'] = MagicMock()
sys.modules['airflow.sdk.bases.hook'] = MagicMock()
sys.modules['airflow.hooks'] = MagicMock()
sys.modules['airflow.hooks.base'] = MagicMock()
sys.modules['airflow.exceptions'] = MagicMock()
sys.modules['minio'] = MagicMock()
sys.modules['requests'] = MagicMock()

# Import the module under test
# We rely on PYTHONPATH including the root directory
from include.tasks.extract_stock_info import extract_news_top3_most_active_stocks

def test_extract_news_top3_most_active_stocks():
    # Setup mocks
    mock_ti = MagicMock()
    mock_context = {'ti': mock_ti}

    # Mock return values for xcom_pull
    def xcom_side_effect(key, task_ids):
        if key == 'top3_stocks':
            return ['AAPL', 'GOOGL', 'MSFT']
        if key == 'return_value':
            return 'my-bucket/2023-10-27'
        return None

    mock_ti.xcom_pull.side_effect = xcom_side_effect

    with patch('include.tasks.extract_stock_info._connect_database') as mock_connect_db, \
         patch('include.tasks.extract_stock_info.BaseHook') as mock_base_hook, \
         patch('include.tasks.extract_stock_info.re') as mock_requests, \
         patch('include.tasks.extract_stock_info.time.sleep'):

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
        mock_response.json.return_value = {'sentiment': 'positive', 'feed': []}
        mock_response.raise_for_status.return_value = None
        mock_requests.get.return_value = mock_response

        # Run the function
        result = extract_news_top3_most_active_stocks(**mock_context)

        # Verify result
        assert result == "All news data for top 3 most active stocks stored in my-bucket/2023-10-27/news/"

        # Verify MinIO put_object calls
        assert mock_client.put_object.call_count == 3

        # Verify first call
        args, kwargs = mock_client.put_object.call_args_list[0]
        assert kwargs['bucket_name'] == 'my-bucket'
        assert kwargs['object_name'] == '2023-10-27/news/0_AAPL_stocks_news.json'

        # Verify API calls
        assert mock_requests.get.call_count == 3
        # Check params of first call
        call_args = mock_requests.get.call_args_list[0]
        assert call_args[1]['params']['function'] == 'NEWS_SENTIMENT'
        assert call_args[1]['params']['tickers'] == 'AAPL'
        assert call_args[1]['params']['apikey'] == 'dummy_key'
