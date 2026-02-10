# Licensed under the Apache License, Version 2.0
"""
Fix for FAB auth manager login form in Airflow 3.x with Astronomer Runtime.

Problem: The FAB login form at /auth/login/ goes through Starlette's WSGIMiddleware
which strips HTTP response headers (Set-Cookie, Location) and converts 302 to 200.
This means the Flask login view authenticates the user but can't set session cookies
or redirect the browser.

Solution: Monkey-patch FabAuthManager.get_fastapi_app() to add a native FastAPI
POST /login/ route. This route handles the form submission, creates a JWT via the
existing token service, sets it as the '_token' cookie, and redirects to the
dashboard. Since FastAPI routes take priority over WSGIMiddleware mounts, this
route handles the POST instead of the broken Flask path.

This file is named airflow_local_settings.py so Airflow auto-imports it during
early initialization (in airflow/settings.py), before create_app() is called.
"""
from __future__ import annotations

from airflow.providers.fab.auth_manager.fab_auth_manager import FabAuthManager

_original_get_fastapi_app = FabAuthManager.get_fastapi_app


def _patched_get_fastapi_app(self):
    """Patched version that adds a working POST /login/ route."""
    app = _original_get_fastapi_app(self)
    if app is None:
        return None

    from urllib.parse import urlparse

    from fastapi import Form, Request
    from fastapi.responses import RedirectResponse

    from airflow.api_fastapi.auth.managers.base_auth_manager import COOKIE_NAME_JWT_TOKEN
    from airflow.configuration import conf
    from airflow.providers.fab.auth_manager.api_fastapi.services.login import (
        FABAuthManagerLogin,
    )
    from airflow.providers.fab.auth_manager.cli_commands.utils import (
        get_application_builder,
    )

    @app.post("/login/")
    def handle_login_form(
        request: Request,
        username: str = Form(...),
        password: str = Form(...),
    ):
        next_url = request.query_params.get("next", "/")

        # Sanitize next_url — only allow relative paths
        parsed = urlparse(next_url)
        if parsed.netloc:
            next_url = parsed.path or "/"
        if not next_url.startswith("/"):
            next_url = "/"

        try:
            with get_application_builder():
                token_response = FABAuthManagerLogin.create_token(
                    headers=dict(request.headers),
                    body={"username": username, "password": password},
                )
        except Exception:
            return RedirectResponse(url="/auth/login/", status_code=302)

        secure = request.base_url.scheme == "https" or bool(
            conf.get("api", "ssl_cert", fallback="")
        )
        response = RedirectResponse(url=next_url, status_code=302)
        response.set_cookie(
            key=COOKIE_NAME_JWT_TOKEN,
            value=token_response.access_token,
            httponly=True,
            secure=secure,
            path="/",
            samesite="lax",
        )
        return response

    return app


FabAuthManager.get_fastapi_app = _patched_get_fastapi_app
