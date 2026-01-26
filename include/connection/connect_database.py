from minio import Minio
from airflow.sdk.bases.hook import BaseHook

def _connect_database():
    minio_conn = BaseHook.get_connection('minio')
    endpoint_url = minio_conn.extra_dejson.get('endpoint_url', '')

    secure = False
    if endpoint_url.startswith('https://'):
        secure = True
        endpoint = endpoint_url.replace('https://', '')
    elif endpoint_url.startswith('http://'):
        secure = False
        endpoint = endpoint_url.replace('http://', '')
    else:
        endpoint = endpoint_url

    access_key = minio_conn.login
    secret_key = minio_conn.password

    client = Minio(
        endpoint=endpoint,
        access_key=access_key,
        secret_key=secret_key,
        secure=secure
    )
    return client