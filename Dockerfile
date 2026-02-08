FROM quay.io/astronomer/astro-runtime:3.1-12

# Enable XCom pickling for astro-sdk-python
ENV AIRFLOW__CORE__ENABLE_XCOM_PICKLING=True
