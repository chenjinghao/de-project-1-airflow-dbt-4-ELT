from minio import Minio
from airflow.sdk.bases.hook import BaseHook

def _connect_database():
    minio_conn = BaseHook.get_connection('minio')
    endpoint_url = minio_conn.extra_dejson['endpoint_url']
    endpoint = endpoint_url.split('//')[1]
    secure = endpoint_url.startswith('https')
    
    access_key = minio_conn.login
    secret_key = minio_conn.password

    client = Minio(
        endpoint=endpoint,
        access_key=access_key,
        secret_key=secret_key,
        secure=secure
    )
    return client