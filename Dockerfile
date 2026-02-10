FROM astrocrpublic.azurecr.io/runtime:3.1-12

# Enable XCom pickling for astro-sdk-python
ENV AIRFLOW__CORE__ENABLE_XCOM_PICKLING=True

# Increase UV download timeout for slow/constrained VMs
ENV UV_HTTP_TIMEOUT=300

# Fix FAB login: add native FastAPI POST /login/ route
# The Flask login form goes through WSGIMiddleware which strips response headers.
# This appends a proper FastAPI route to handle the form submission directly.
USER root
COPY include/fab_login_patch.py /tmp/fab_login_patch.py
RUN cat /tmp/fab_login_patch.py >> /usr/local/lib/python3.12/site-packages/airflow/providers/fab/auth_manager/api_fastapi/routes/login.py \
    && rm /tmp/fab_login_patch.py
USER astro
