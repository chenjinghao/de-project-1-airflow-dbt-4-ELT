FROM astrocrpublic.azurecr.io/runtime:3.1-12

# Enable XCom pickling for astro-sdk-python
ENV AIRFLOW__CORE__ENABLE_XCOM_PICKLING=True

# Increase UV download timeout for slow/constrained VMs
ENV UV_HTTP_TIMEOUT=300
