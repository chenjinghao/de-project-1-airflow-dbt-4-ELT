import pytest
from unittest.mock import MagicMock, patch
import sys

# Mock imports that might be missing in sandbox
sys.modules['google.cloud.sql.connector'] = MagicMock()
sys.modules['googleapiclient'] = MagicMock()
sys.modules['googleapiclient.discovery'] = MagicMock()

# Mock Airflow
mock_airflow = MagicMock()
sys.modules['airflow'] = mock_airflow
sys.modules['airflow.providers'] = MagicMock()
sys.modules['airflow.providers.postgres'] = MagicMock()
sys.modules['airflow.providers.postgres.hooks'] = MagicMock()
sys.modules['airflow.providers.postgres.hooks.postgres'] = MagicMock()

from include.connection import cloud_sql_connector

@patch('include.connection.cloud_sql_connector.PostgresHook')
def test_local_connection(mock_hook):
    # Setup
    mock_hook_instance = mock_hook.return_value
    mock_conn = MagicMock()
    mock_conn.host = 'localhost'
    mock_hook_instance.get_connection.return_value = mock_conn

    # Run
    cloud_sql_connector.get_gcp_cloud_sql_connection('my_conn', 'proj', 'region')

    # Assert
    mock_hook_instance.get_conn.assert_called_once()

@patch('include.connection.cloud_sql_connector.PostgresHook')
def test_cloud_sql_connection_flow(mock_hook):
    # Setup
    mock_hook_instance = mock_hook.return_value
    mock_conn = MagicMock()
    mock_conn.host = '34.1.1.1'
    mock_conn.login = 'user'
    mock_conn.password = 'pass'
    mock_conn.schema = 'db'
    mock_hook_instance.get_connection.return_value = mock_conn

    # Mock Connector and Discovery manually on the module
    mock_discovery = MagicMock()
    mock_Connector = MagicMock()
    mock_IPTypes = MagicMock()
    mock_IPTypes.PUBLIC = "PUBLIC"

    # Apply mocks to module
    original_discovery = cloud_sql_connector.discovery
    original_Connector = cloud_sql_connector.Connector
    original_IPTypes = getattr(cloud_sql_connector, 'IPTypes', None)

    cloud_sql_connector.discovery = mock_discovery
    cloud_sql_connector.Connector = mock_Connector
    cloud_sql_connector.IPTypes = mock_IPTypes

    try:
        # Mock Discovery Response
        mock_service = MagicMock()
        mock_discovery.build.return_value = mock_service
        mock_req = MagicMock()
        mock_service.instances().list.return_value = mock_req
        mock_req.execute.return_value = {
            'items': [
                {'name': 'wrong-instance', 'region': 'us-east1', 'databaseVersion': 'POSTGRES_13', 'state': 'RUNNABLE'},
                {'name': 'target-instance', 'region': 'us-west1', 'databaseVersion': 'POSTGRES_13', 'state': 'RUNNABLE'}
            ]
        }

        # Mock Connector Instance
        mock_connector_instance = MagicMock()
        mock_Connector.return_value = mock_connector_instance
        mock_db_conn = MagicMock()
        mock_connector_instance.connect.return_value = mock_db_conn

        # Run
        result = cloud_sql_connector.get_gcp_cloud_sql_connection('my_conn', 'my-proj', 'us-west1')

        # Assert
        assert result == mock_db_conn
        mock_connector_instance.connect.assert_called_with(
            "my-proj:us-west1:target-instance",
            "psycopg2",
            user='user',
            password='pass',
            db='db',
            ip_type="PUBLIC"
        )

    finally:
        # Restore
        cloud_sql_connector.discovery = original_discovery
        cloud_sql_connector.Connector = original_Connector
        if original_IPTypes:
             cloud_sql_connector.IPTypes = original_IPTypes

@patch('include.connection.cloud_sql_connector.PostgresHook')
def test_cloud_sql_fallback_on_discovery_fail(mock_hook):
    # Setup
    mock_hook_instance = mock_hook.return_value
    mock_conn = MagicMock()
    mock_conn.host = '34.1.1.1'
    mock_hook_instance.get_connection.return_value = mock_conn

    # Mock Discovery to return no items
    mock_discovery = MagicMock()
    mock_Connector = MagicMock()

    cloud_sql_connector.discovery = mock_discovery
    cloud_sql_connector.Connector = mock_Connector

    try:
        mock_service = MagicMock()
        mock_discovery.build.return_value = mock_service
        mock_service.instances().list.return_value.execute.return_value = {'items': []}

        # Run
        result = cloud_sql_connector.get_gcp_cloud_sql_connection('my_conn', 'proj', 'us-west1')

        # Assert: Should fall back to standard hook
        mock_hook_instance.get_conn.assert_called_once()

    finally:
        cloud_sql_connector.discovery = None
        cloud_sql_connector.Connector = None
