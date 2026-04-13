import os, json
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, JSONResponse
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from requests_oauthlib import OAuth2Session
from agent.database import save_google_token, get_client_by_email

router = APIRouter()

SCOPES = [
    'https://www.googleapis.com/auth/gmail.send',        # send emails
    'https://www.googleapis.com/auth/gmail.readonly',    # read/list emails
    'https://www.googleapis.com/auth/spreadsheets',      # read & write sheets
    'https://www.googleapis.com/auth/calendar',          # create events
    'https://www.googleapis.com/auth/calendar.readonly', # view/list events
    'https://www.googleapis.com/auth/drive.readonly',    # drive access
]


AUTHORIZATION_BASE_URL = "https://accounts.google.com/o/oauth2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"

def get_client_secrets():
    config = json.loads(os.getenv("GOOGLE_CREDENTIALS_JSON"))
    web = config.get("web", config)
    return web["client_id"], web["client_secret"]

def get_redirect_uri():
    return os.getenv("GOOGLE_REDIRECT_URI")

@router.get("/auth/google")
async def start_google_auth(request: Request):
    client_email = request.session.get("client_email")
    if not client_email:
        return RedirectResponse("/login")

    client_id, _ = get_client_secrets()
    oauth = OAuth2Session(
        client_id=client_id,
        redirect_uri=get_redirect_uri(),
        scope=SCOPES
    )
    auth_url, state = oauth.authorization_url(
        AUTHORIZATION_BASE_URL,
        access_type="offline",
        prompt="consent"
    )
    request.session["oauth_state"] = state
    return RedirectResponse(auth_url)

@router.get("/auth/callback")
async def google_callback(request: Request):
    client_email = request.session.get("client_email")
    if not client_email:
        return RedirectResponse("/login")

    client_id, client_secret = get_client_secrets()
    state = request.session.get("oauth_state", "")

    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

    oauth = OAuth2Session(
        client_id=client_id,
        redirect_uri=get_redirect_uri(),
        state=state,
        scope=SCOPES
    )

    # Force https in the callback URL since Render uses https
    callback_url = str(request.url).replace("http://", "https://")

    token = oauth.fetch_token(
        TOKEN_URL,
        authorization_response=callback_url,
        client_secret=client_secret
    )

    # Build credentials object and save to DB
    creds = Credentials(
        token=token["access_token"],
        refresh_token=token.get("refresh_token"),
        token_uri=TOKEN_URL,
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES
    )

    client = get_client_by_email(client_email)
    save_google_token(client["id"], creds.to_json())

    return RedirectResponse("/setup?google=connected")

@router.get("/auth/status")
async def auth_status(request: Request):
    client_email = request.session.get("client_email")
    if not client_email:
        return JSONResponse({"authenticated": False, "status": "disconnected"})

    client = get_client_by_email(client_email)
    if not client:
        return JSONResponse({"authenticated": False, "status": "disconnected"})

    google_connected = bool(client.get("google_token_json"))
    return JSONResponse({
        "authenticated": True,
        "status": "connected" if google_connected else "disconnected",
        "google_connected": google_connected,
        "wa_connected": bool(client.get("wa_phone")),
    })

def get_google_credentials_for_client(client: dict):
    token_json = client.get("google_token_json")
    if not token_json:
        raise Exception(f"No Google token for client {client['email']}")

    creds = Credentials.from_authorized_user_info(
        json.loads(token_json),
        scopes=SCOPES
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(GoogleRequest())
        save_google_token(client["id"], creds.to_json())

    return creds