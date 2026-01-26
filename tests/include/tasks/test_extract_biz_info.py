import sys
from unittest.mock import MagicMock, patch
import pytest

# Mock modules
sys.modules['airflow'] = MagicMock()
sys.modules['airflow.sdk'] = MagicMock()
sys.modules['airflow.sdk.bases'] = MagicMock()
sys.modules['airflow.sdk.bases.hook'] = MagicMock()
sys.modules['airflow.exceptions'] = MagicMock()
sys.modules['minio'] = MagicMock()
sys.modules['requests'] = MagicMock()

import os
sys.path.append(os.getcwd())

from include.tasks.extract_stock_info import extract_biz_info_top3_most_active_stocks

def test_extract_biz_info_top3_most_active_stocks():
    # Setup mocks
    mock_ti = MagicMock()
    mock_context = {'ti': mock_ti}

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
         patch('include.tasks.extract_stock_info.time.sleep') as mock_sleep:

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
        mock_response.json.return_value = {'Symbol': 'AAPL', 'Description': 'Tech'}
        mock_response.raise_for_status.return_value = None
        mock_requests.get.return_value = mock_response

        # Run the function
        result = extract_biz_info_top3_most_active_stocks(**mock_context)

        # Verify result
        assert result == "All business info data for top 3 most active stocks stored in my-bucket/2023-10-27/business_info/"

        # Verify MinIO put_object calls
        assert mock_client.put_object.call_count == 3

        # Verify call arguments
        # Since we use threading, order is not guaranteed.
        calls = mock_client.put_object.call_args_list
        object_names = sorted([call[1]['object_name'] for call in calls])

        assert object_names[0] == '2023-10-27/business_info/0_AAPL_stocks_business_info.json'
        assert object_names[1] == '2023-10-27/business_info/1_GOOGL_stocks_business_info.json'
        assert object_names[2] == '2023-10-27/business_info/2_MSFT_stocks_business_info.json'

        # Verify API calls
        assert mock_requests.get.call_count == 3
        # Check params of calls - we check that AAPL was requested
        call_params = [call[1]['params'] for call in mock_requests.get.call_args_list]
        symbols = sorted([p['symbol'] for p in call_params])
        assert symbols == ['AAPL', 'GOOGL', 'MSFT']
