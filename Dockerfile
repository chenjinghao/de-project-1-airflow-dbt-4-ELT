FROM quay.io/astronomer/astro-runtime:12.6.0

# Enable XCom pickling for astro-sdk-python
ENV AIRFLOW__CORE__ENABLE_XCOM_PICKLING=True
