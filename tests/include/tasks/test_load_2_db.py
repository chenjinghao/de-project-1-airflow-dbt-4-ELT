import sys
from unittest.mock import MagicMock, patch, ANY

# Mock dependencies before import
sys.modules['airflow'] = MagicMock()
sys.modules['airflow.providers'] = MagicMock()
sys.modules['airflow.providers.postgres'] = MagicMock()
sys.modules['airflow.providers.postgres.hooks'] = MagicMock()
sys.modules['airflow.providers.postgres.hooks.postgres'] = MagicMock()
sys.modules['psycopg2'] = MagicMock()
sys.modules['psycopg2.extras'] = MagicMock()
sys.modules['psycopg2.sql'] = MagicMock()
sys.modules['include.connection.connect_database'] = MagicMock()
sys.modules['pandas'] = MagicMock()

# Setup mocks for specific attributes
mock_postgres_hook = MagicMock()
sys.modules['airflow.providers.postgres.hooks.postgres'].PostgresHook = mock_postgres_hook

mock_connect_db = MagicMock()
sys.modules['include.connection.connect_database']._connect_database = mock_connect_db
sys.modules['include.connection.connect_database'].BUCKET_NAME = "bronze-test-bucket"

# Mock psycopg2.extras.Json
# Memory says: "Unit tests involving psycopg2.extras.Json should mock the class with a side effect... to pass through data"
mock_json = MagicMock(side_effect=lambda x: x)
sys.modules['psycopg2.extras'].Json = mock_json

# Now import the module under test
from include.tasks.load_2_db import load_to_db

def test_load_to_db_uses_correct_bucket():
    # Setup
    mock_client = MagicMock()
    mock_connect_db.return_value = mock_client

    # Mock list_blobs to return empty list so the loop doesn't run and crash on other things
    mock_client.list_blobs.return_value = []

    mock_conn = MagicMock()
    mock_postgres_hook.return_value.get_conn.return_value = mock_conn

    # Run
    load_to_db()

    # Assert
    # We expect it to call client.list_blobs(BUCKET_NAME, ...)
    # Now BUCKET_NAME is "bronze-test-bucket"
    mock_client.list_blobs.assert_called_with("bronze-test-bucket", prefix=ANY)
