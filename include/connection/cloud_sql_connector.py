import logging
from airflow.providers.postgres.hooks.postgres import PostgresHook
# Import conditionally to avoid breaking local if not installed (though we added to requirements)
try:
    from google.cloud.sql.connector import Connector, IPTypes
    from googleapiclient import discovery
except ImportError:
    Connector = None
    discovery = None

# Global connector to reuse
_connector = None

def get_gcp_cloud_sql_connection(connection_id, project_id, region):
    """
    Establishes a connection to a database.
    If the host looks like a local service, uses standard PostgresHook.
    If the host looks like an external IP, attempts to use Cloud SQL Python Connector
    by discovering the instance in the given project/region.
    """
    global _connector

    # Get Airflow Connection details
    hook = PostgresHook(postgres_conn_id=connection_id)
    try:
        conn_params = hook.get_connection(connection_id)
    except Exception:
        # If connection doesn't exist, hook might handle it or raise.
        # But hook.get_conn() handles it usually.
        logging.warning(f"Could not retrieve connection details for {connection_id}")
        return hook.get_conn()

    host = conn_params.host

    # Local/Internal check:
    # If host is 'database' (docker-compose), 'postgres', 'localhost', or None, use standard hook.
    # We also check if Connector is available.
    is_local_host = host in ['database', 'postgres', 'localhost', '127.0.0.1'] or not host or not Connector

    if is_local_host:
        logging.info(f"Connecting to database at '{host}' using standard PostgresHook.")
        return hook.get_conn()

    logging.info(f"Host '{host}' appears to be external. Attempting Cloud SQL Connector discovery.")

    # Discovery
    try:
        service = discovery.build('sqladmin', 'v1beta4', cache_discovery=False)
        req = service.instances().list(project=project_id)
        resp = req.execute()
        items = resp.get('items', [])

        target_instance = None
        for item in items:
            # We look for a RUNNABLE Postgres instance in the region
            if item.get('region') == region and item.get('databaseVersion', '').startswith('POSTGRES') and item.get('state') == 'RUNNABLE':
                target_instance = item['name']
                # If there are multiple, we pick the first one.
                # Ideally we would match against something, but we don't know the instance name.
                break

        if not target_instance:
             logging.warning(f"No RUNNABLE Postgres instance found in {project_id}/{region}. Falling back to standard hook.")
             return hook.get_conn()

        instance_connection_name = f"{project_id}:{region}:{target_instance}"
        logging.info(f"Discovered Cloud SQL Instance: {instance_connection_name}")

        # Connect using Connector
        if _connector is None:
            _connector = Connector()

        conn = _connector.connect(
            instance_connection_name,
            "psycopg2",
            user=conn_params.login,
            password=conn_params.password,
            db=conn_params.schema,
            ip_type=IPTypes.PUBLIC  # Uses ephemeral certs to allow public IP access
        )
        return conn

    except Exception as e:
        logging.error(f"Failed to use Cloud SQL Connector: {e}. Falling back to standard hook.")
        return hook.get_conn()
