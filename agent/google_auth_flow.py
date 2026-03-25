# agent/google_auth_flow.py
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from google_auth_oauthlib.flow import Flow
import os, traceback, json, tempfile

router = APIRouter()

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/calendar",
]

_flow_store = {}


def get_redirect_uri():
    return os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/callback")


def get_flow(state=None):
    """
    Load credentials from env variable (production/Render)
    or from credentials.json file (local development).
    """
    creds_env = os.getenv("GOOGLE_CREDENTIALS_JSON")

    if creds_env:
        # Production — credentials stored as env variable
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False
        ) as f:
            f.write(creds_env)
            temp_path = f.name

        kwargs = dict(scopes=SCOPES, redirect_uri=get_redirect_uri())
        if state:
            kwargs["state"] = state
        return Flow.from_client_secrets_file(temp_path, **kwargs)

    else:
        # Local development — use credentials.json file
        kwargs = dict(scopes=SCOPES, redirect_uri=get_redirect_uri())
        if state:
            kwargs["state"] = state
        return Flow.from_client_secrets_file("credentials.json", **kwargs)


@router.get("/auth/google")
async def google_login():
    """Redirect client to Google login page."""
    flow = get_flow()

    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )

    _flow_store[state] = flow
    return RedirectResponse(auth_url)


@router.get("/auth/callback")
async def google_callback(request: Request):
    """Google redirects here after client approves."""
    try:
        state = request.query_params.get("state")
        code  = request.query_params.get("code")

        if not code:
            return HTMLResponse(
                "<h2>Error: No authorization code returned from Google.</h2>",
                status_code=400
            )

        flow = _flow_store.pop(state, None)
        if flow is None:
            flow = get_flow(state=state)

        os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
        flow.fetch_token(authorization_response=str(request.url))

        creds = flow.credentials

        token_path = os.getenv("GOOGLE_TOKEN_PATH", "token.json")
        with open(token_path, "w") as f:
            f.write(creds.to_json())

        return HTMLResponse("""
        <html>
        <head>
            <style>
                body{font-family:Arial,sans-serif;display:flex;justify-content:center;
                     align-items:center;height:100vh;margin:0;background:#f0fdf4;}
                .card{background:white;border-radius:16px;padding:48px 56px;
                      text-align:center;box-shadow:0 4px 24px rgba(0,0,0,.08);max-width:420px;}
                .icon{font-size:56px;margin-bottom:16px;}
                h1{color:#16a34a;font-size:24px;margin:0 0 12px;}
                p{color:#6b7280;font-size:15px;line-height:1.6;margin:0;}
            </style>
        </head>
        <body>
            <div class="card">
                <div class="icon">&#x2705;</div>
                <h1>Google Account Connected!</h1>
                <p>Gmail, Google Sheets and Calendar are now linked
                   to your personal agent.<br><br>You can close this tab.</p>
            </div>
        </body>
        </html>
        """)

    except Exception as e:
        error_detail = traceback.format_exc()
        print(f"[Auth Callback Error]\n{error_detail}")
        return HTMLResponse(f"""
        <html><body style="font-family:Arial;padding:40px;background:#fef2f2;">
            <h2 style="color:#dc2626;">Authentication Error</h2>
            <pre style="background:#fff;padding:20px;border-radius:8px;
                        font-size:13px;overflow:auto;">{error_detail}</pre>
            <p><a href="/auth/google">Try again</a></p>
        </body></html>
        """, status_code=500)


@router.get("/auth/status")
async def auth_status():
    """Check if token.json exists."""
    token_path = os.getenv("GOOGLE_TOKEN_PATH", "token.json")
    if os.path.exists(token_path):
        return {"status": "connected", "message": "Google account is linked."}
    return {"status": "not_connected", "message": "Visit /auth/google to connect."}
