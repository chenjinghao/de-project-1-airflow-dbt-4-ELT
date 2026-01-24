import unittest
from unittest.mock import MagicMock, patch
import sys
import types

# Mocking modules that might not be present in the test environment
module_names = [
    'airflow',
    'airflow.sdk',
    'airflow.sdk.bases',
    'airflow.sdk.bases.hook',
    'airflow.exceptions',
    'minio'
]

for module_name in module_names:
    sys.modules[module_name] = MagicMock()

# Setup specific mocks for imported classes
# Mock BaseHook
mock_base_hook_class = MagicMock()
sys.modules['airflow.sdk.bases.hook'].BaseHook = mock_base_hook_class

# Mock AirflowException
class MockAirflowException(Exception):
    pass
sys.modules['airflow.exceptions'].AirflowException = MockAirflowException

# Mock Minio
mock_minio_class = MagicMock()
sys.modules['minio'].Minio = mock_minio_class

import json
from io import BytesIO

# Import the function to be tested
# Assuming the file is at include/tasks/extract_stock_info.py and include is a python package
from include.tasks.extract_stock_info import extract_biz_info_top3_most_active_stocks

class TestExtractBizInfo(unittest.TestCase):

    @patch('include.tasks.extract_stock_info._connect_database')
    @patch('include.tasks.extract_stock_info.BaseHook')
    @patch('include.tasks.extract_stock_info.re')
    @patch('include.tasks.extract_stock_info.time')
    def test_extract_biz_info(self, mock_time, mock_re, mock_base_hook, mock_connect_db):
        # Setup Mocks

        # Mock BaseHook
        mock_connection = MagicMock()
        mock_connection.host = "http://api.example.com"
        mock_connection.password = "fake_api_key"
        mock_base_hook.get_connection.return_value = mock_connection

        # Mock _connect_database
        mock_client = MagicMock()
        mock_objw = MagicMock()
        mock_objw.bucket_name = "test-bucket"
        mock_client.put_object.return_value = mock_objw
        mock_connect_db.return_value = mock_client

        # Mock re (which is requests aliased)
        mock_response = MagicMock()
        mock_response.json.return_value = {"Symbol": "AAPL", "Name": "Apple Inc."}
        mock_re.get.return_value = mock_response

        # Mock Context
        mock_ti = MagicMock()

        # Setup side_effect for xcom_pull to handle different keys
        def xcom_pull_side_effect(key, task_ids):
            if key == 'top3_stocks':
                return ['AAPL', 'GOOGL', 'MSFT']
            if key == 'return_value':
                return 'test-bucket/today-folder'
            return None

        mock_ti.xcom_pull.side_effect = xcom_pull_side_effect

        context = {'ti': mock_ti}

        # Execute the function
        result = extract_biz_info_top3_most_active_stocks(**context)

        # Assertions

        # Check connection to stock_api
        mock_base_hook.get_connection.assert_called_with('stock_api')

        # Check DB connection
        mock_connect_db.assert_called_once()

        # Check API calls
        # Should be called 3 times (for 3 stocks)
        self.assertEqual(mock_re.get.call_count, 3)

        # Check put_object calls
        self.assertEqual(mock_client.put_object.call_count, 3)

        # Verify the arguments for the first call
        call_args = mock_client.put_object.call_args_list[0]
        kwargs = call_args[1]
        self.assertEqual(kwargs['bucket_name'], 'test-bucket')
        self.assertEqual(kwargs['object_name'], 'today-folder/business_info/0_AAPL_stocks_business_info.json')

        # Verify return value
        self.assertEqual(result, "All business info data for top 3 most active stocks stored in test-bucket/today-folder/business_info/")

if __name__ == '__main__':
    unittest.main()
