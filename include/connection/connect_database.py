from airflow.providers.google.cloud.hooks.gcs import GCSHook

def _connect_database():
    """
    Connect to Google Cloud Storage using the 'google_cloud_default' Airflow connection.
    Returns a google.cloud.storage.Client.
    """
    return GCSHook(gcp_conn_id='google_cloud_default').get_conn()
