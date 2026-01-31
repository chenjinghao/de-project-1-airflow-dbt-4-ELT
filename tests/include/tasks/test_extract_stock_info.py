import sys
from unittest.mock import MagicMock, patch
import pytest

# Mock modules that might be missing in the test environment or need to be mocked
sys.modules['airflow'] = MagicMock()
sys.modules['airflow.sdk'] = MagicMock()
sys.modules['airflow.sdk.bases'] = MagicMock()
sys.modules['airflow.sdk.bases.hook'] = MagicMock()
sys.modules['airflow.exceptions'] = MagicMock()

# Mock Google modules structure
mock_google = MagicMock()
sys.modules['google'] = mock_google
sys.modules['google.cloud'] = MagicMock()
sys.modules['google.cloud.storage'] = MagicMock()
sys.modules['google.oauth2'] = MagicMock()
sys.modules['google.oauth2.service_account'] = MagicMock()

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

        # Setup GCS client mock
        mock_client = MagicMock()
        mock_connect_db.return_value = mock_client

        mock_bucket = MagicMock()
        mock_client.bucket.return_value = mock_bucket

        mock_blob = MagicMock()
        mock_bucket.blob.return_value = mock_blob

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

        # Verify GCS calls
        assert mock_client.bucket.call_count == 1
        mock_client.bucket.assert_called_with('my-bucket')

        assert mock_bucket.blob.call_count == 3

        # Check first blob call
        mock_bucket.blob.assert_any_call('2023-10-27/news/0_AAPL_stocks_news.json')

        assert mock_blob.upload_from_string.call_count == 3

        # Verify API calls
        assert mock_requests.get.call_count == 3
