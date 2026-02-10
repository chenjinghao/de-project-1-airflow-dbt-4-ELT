
# --- FAB Login Form Fix ---
# Adds a native FastAPI POST /login/ route to handle the HTML login form.
# The Flask login at /auth/login/ goes through WSGIMiddleware which strips
# response headers (Set-Cookie, Location) and converts 302 to 200.
# This route bypasses WSGIMiddleware entirely.
from urllib.parse import urlparse
from fastapi import Form
from airflow.api_fastapi.auth.managers.base_auth_manager import COOKIE_NAME_JWT_TOKEN


@login_router.post("/login/")
def handle_login_form(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    """Handle the FAB login form submission natively in FastAPI."""
    next_url = request.query_params.get("next", "/")
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
