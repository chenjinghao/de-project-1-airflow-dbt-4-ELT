from google.cloud import storage
from airflow.sdk.bases.hook import BaseHook
from google.oauth2 import service_account
import json
import os

BUCKET_NAME = f"bronze-{os.environ.get('GCP_PROJECT', 'my-de-project-485605')}"

def _connect_database():
    """
    Connect to Google Cloud Storage using the 'google_cloud_default' Airflow connection.
    Returns a google.cloud.storage.Client.
    """
    conn = BaseHook.get_connection('google_cloud_default')
    
    # If the connection has a JSON keyfile content in the extra field or keyfile_dict
    keyfile_dict = None
    if conn.extra_dejson:
        if 'keyfile_dict' in conn.extra_dejson:
            # Sometimes stored as a string, sometimes as a dict
            kf = conn.extra_dejson['keyfile_dict']
            if isinstance(kf, str):
                 keyfile_dict = json.loads(kf)
            else:
                 keyfile_dict = kf
        elif 'extra__google_cloud_platform__keyfile_dict' in conn.extra_dejson:
             kf = conn.extra_dejson['extra__google_cloud_platform__keyfile_dict']
             if isinstance(kf, str):
                 keyfile_dict = json.loads(kf)
             else:
                 keyfile_dict = kf

    # Check if we found credentials in the connection
    if keyfile_dict:
        credentials = service_account.Credentials.from_service_account_info(keyfile_dict)
        client = storage.Client(credentials=credentials)
    else:
        # Fallback to ADC or environment variables if no specific keyfile is found
        # This works if the environment is configured with GOOGLE_APPLICATION_CREDENTIALS
        client = storage.Client()

    return client
