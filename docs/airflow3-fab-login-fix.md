# Airflow 3.x FAB Login Redirect Loop — Root Cause & Fix

## The Problem

When using **Airflow 3.x** (specifically Astronomer Runtime 3.1-12, which ships Airflow 3.1.7) with the **FAB (Flask-AppBuilder) auth manager**, the login form at `/auth/login/` appears to authenticate successfully but **never sets cookies or redirects the browser**. The user sees a blank page or gets stuck in a redirect loop.

### Symptoms

- `POST /auth/login/` returns **200 OK** instead of **302 Found**
- No `Set-Cookie` header in the response (confirmed via `curl -c cookies.txt`)
- The response body contains `<h1>Redirecting...</h1>` HTML (Flask's `redirect()` output), but the actual HTTP status is 200
- API server logs show `Updated user Admin User last_login` (authentication succeeds server-side)
- The browser never reaches the dashboard

---

## Root Cause: WSGIMiddleware Strips HTTP Headers

### Airflow 3 Architecture

Airflow 3 uses a **split architecture**:

- **FastAPI** — main application, API server, React UI
- **Flask/FAB** — authentication sub-app, mounted at `/auth`

The FAB auth manager's `get_fastapi_app()` method (in `airflow/providers/fab/auth_manager/fab_auth_manager.py`) creates a FastAPI sub-app structured like this:

```python
def get_fastapi_app(self):
    app = FastAPI(...)
    app.include_router(login_router)        # FastAPI-native routes
    app.mount("/", WSGIMiddleware(flask_app))  # Flask catch-all
    return app
```

### What `login_router` provides (FastAPI-native)

| Route | Method | Purpose | Works? |
|-------|--------|---------|--------|
| `/token` | POST | Create JWT token (API clients) | Yes |
| `/token/cli` | POST | Create CLI token | Yes |
| `/logout` | GET | Delete cookies, redirect | Yes |

### What's missing

There is **no** `POST /login/` route in `login_router`. The HTML login form submission falls through to the **WSGIMiddleware catch-all**, which routes it to Flask's `AuthDBView.login()`.

### The WSGIMiddleware Bug

Starlette's `WSGIMiddleware` has a known limitation: it **strips HTTP response headers** (including `Set-Cookie` and `Location`) and **converts 302 responses to 200**. This means:

1. Flask's login view authenticates the user successfully
2. Flask calls `redirect("/")` which sets `Location: /` and status `302`
3. Flask calls `response.set_cookie(...)` to set the session cookie
4. **WSGIMiddleware strips all of this** and returns status `200` with the redirect HTML body but no headers

The browser receives a 200 response with no cookies and no redirect, so login appears broken.

---

## The Fix: Native FastAPI POST /login/ Route

Bypass WSGIMiddleware entirely by adding a **native FastAPI route** that handles the login form submission. Since FastAPI routes take priority over WSGIMiddleware mounts, this route intercepts `POST /login/` before it reaches Flask.

### Implementation (Dockerfile-based)

This approach patches the FAB provider's source code during Docker build. It works because the route is defined on `login_router` (the same router used by `/token` and `/logout`), so it's automatically included when `get_fastapi_app()` runs.

#### File: `include/fab_login_patch.py`

```python

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
```

**Why this works:** This code is appended to the end of `airflow/providers/fab/auth_manager/api_fastapi/routes/login.py`, which already has `login_router`, `Request`, `RedirectResponse`, `conf`, `get_application_builder`, and `FABAuthManagerLogin` in scope. The new route uses `FABAuthManagerLogin.create_token()` (the same service behind `POST /auth/token`) to create a JWT, sets it as the `_token` cookie, and redirects to the dashboard.

#### Dockerfile Changes

```dockerfile
# Fix FAB login: add native FastAPI POST /login/ route
# The Flask login form goes through WSGIMiddleware which strips response headers.
# This appends a proper FastAPI route to handle the form submission directly.
USER root
COPY include/fab_login_patch.py /tmp/fab_login_patch.py
RUN cat /tmp/fab_login_patch.py >> /usr/local/lib/python3.12/site-packages/airflow/providers/fab/auth_manager/api_fastapi/routes/login.py \
    && rm /tmp/fab_login_patch.py
USER astro
```

**Important:** `USER root` is required because Astronomer Runtime runs as the non-root `astro` user, which cannot write to `site-packages`. Switch back to `USER astro` afterward.

---

## Other Issues Encountered & Fixes

### 1. JWT Secret Key Too Short

**Symptom:** `InsecureKeyLengthWarning: The HMAC key is 24 bytes long` in apiserver logs. JWTs may fail to validate across restarts.

**Fix:** Generate a 64-byte hex key and add to `.env`:

```bash
openssl rand -hex 64
```

Add to `.env`:
```
AIRFLOW_SECRET_KEY=<the-generated-key>
```

Both `AIRFLOW__API__SECRET_KEY` and `AIRFLOW__WEBSERVER__SECRET_KEY` must use this value (configured in `docker-compose.prod.yml`):

```yaml
AIRFLOW__API__SECRET_KEY: ${AIRFLOW_SECRET_KEY}
AIRFLOW__WEBSERVER__SECRET_KEY: ${AIRFLOW_SECRET_KEY}
```

And in `webserver_config.py` (for Flask/FAB):
```python
import os
SECRET_KEY = os.environ.get("AIRFLOW__WEBSERVER__SECRET_KEY",
    os.environ.get("AIRFLOW__API__SECRET_KEY", "temporary-insecure-key"))
WTF_CSRF_ENABLED = False
```

### 2. airflow_local_settings.py Monkey-Patch Does NOT Work

**What was tried:** A `plugins/airflow_local_settings.py` file that monkey-patches `FabAuthManager.get_fastapi_app` to inject the login route at runtime.

**Why it fails:** Airflow imports `airflow_local_settings.py` **after** `create_app()` has already called `get_fastapi_app()`. The monkey-patch applies successfully (verified via manual import), but by the time it runs, the FastAPI sub-app has already been created without the patched route.

**Conclusion:** The Dockerfile-based source patching approach is the only reliable method. The `airflow_local_settings.py` file is harmless but ineffective and can be removed.

### 3. FAB Auth Manager Must Be Explicitly Configured

Airflow 3.x defaults to a different auth manager. You must explicitly set:

```yaml
AIRFLOW__CORE__AUTH_MANAGER: airflow.providers.fab.auth_manager.fab_auth_manager.FabAuthManager
```

And add to `requirements.txt`:
```
apache-airflow-providers-fab
```

### 4. CSRF Must Be Disabled for the Login Form

The native FastAPI login route doesn't generate CSRF tokens (it's not a Flask/WTF form). Disable CSRF in `webserver_config.py`:

```python
WTF_CSRF_ENABLED = False
```

---

## Emergency Workaround: Browser Console Login

If the Dockerfile fix isn't deployed yet, you can log in via the browser console. **Navigate to `http://<IP>:8080/` first** (not `/auth/login/`), then run:

```javascript
fetch('/auth/token', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({username: 'admin', password: 'YOUR_PASSWORD'})
})
.then(r => {
  if (!r.ok) throw new Error('Login failed: ' + r.status);
  return r.json();
})
.then(d => {
  document.cookie = '_token=' + d.access_token + '; path=/; SameSite=Lax';
  window.location.href = '/';
})
.catch(e => alert(e.message));
```

**Important notes:**
- Run this from `http://<IP>:8080/` (React app), NOT from `/auth/login/` (Flask page has jQuery conflicts)
- Replace `YOUR_PASSWORD` with the actual admin password
- Use `window.location.href='/'`, not `location.reload()` (which would reload the current page)

---

## Quick Fix Checklist

For future deployments, ensure all of these are in place:

- [ ] `include/fab_login_patch.py` exists with the FastAPI login route
- [ ] `Dockerfile` has the `USER root` / patch / `USER astro` block
- [ ] `requirements.txt` includes `apache-airflow-providers-fab`
- [ ] `docker-compose.prod.yml` sets `AIRFLOW__CORE__AUTH_MANAGER` to FAB
- [ ] `docker-compose.prod.yml` sets both `AIRFLOW__API__SECRET_KEY` and `AIRFLOW__WEBSERVER__SECRET_KEY`
- [ ] `.env` has `AIRFLOW_SECRET_KEY` with a 64-byte hex value (`openssl rand -hex 64`)
- [ ] `webserver_config.py` has `WTF_CSRF_ENABLED = False` and reads `SECRET_KEY` from env
- [ ] Build with `docker compose -f docker-compose.prod.yml build --no-cache` after any Dockerfile changes

---

## Files Modified (Summary)

| File | Change |
|------|--------|
| `Dockerfile` | Added `USER root`, COPY+RUN to append login patch, `USER astro` |
| `include/fab_login_patch.py` | New file: FastAPI POST /login/ route |
| `docker-compose.prod.yml` | Added `AIRFLOW__WEBSERVER__SECRET_KEY`, FAB auth manager config |
| `webserver_config.py` | Added `SECRET_KEY` from env, disabled CSRF, cookie settings |
| `requirements.txt` | Added `apache-airflow-providers-fab` |
| `plugins/airflow_local_settings.py` | Created but ineffective (can be removed) |

---

## How the Login Flow Works After the Fix

```
Browser                    FastAPI (Airflow 3)              Flask/FAB
  |                              |                              |
  |-- GET /auth/login/ --------->|                              |
  |                              |-- WSGIMiddleware ----------->|
  |                              |                              |-- renders login form
  |<-------- 200 HTML form ------|<-----------------------------|
  |                              |                              |
  |-- POST /auth/login/ -------->|                              |
  |                              |-- login_router.post match ---|  (BYPASSES WSGIMiddleware)
  |                              |-- FABAuthManagerLogin.create_token()
  |                              |-- Set-Cookie: _token=<JWT>
  |<-------- 302 Redirect / -----|
  |                              |
  |-- GET / ------------------->|
  |<-------- 200 React Dashboard |
```

The key difference: `POST /login/` is now handled by a **native FastAPI route** on `login_router`, so it never passes through WSGIMiddleware. The JWT cookie and redirect headers are preserved correctly.
