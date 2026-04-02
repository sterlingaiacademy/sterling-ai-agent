import os, json
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, JSONResponse
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from agent.database import save_google_token, get_client_by_email

router = APIRouter()

SCOPES = [
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/calendar',
]

def build_flow():
    client_config = json.loads(os.getenv("GOOGLE_CREDENTIALS_JSON"))
    return Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=os.getenv("GOOGLE_REDIRECT_URI")
    )

@router.get("/auth/google")
async def start_google_auth(request: Request):
    # Must be logged in
    client_email = request.session.get("client_email")
    if not client_email:
        return RedirectResponse("/login")
    
    flow = build_flow()
    auth_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'   # forces refresh_token to always be returned
    )
    request.session["oauth_state"] = state
    return RedirectResponse(auth_url)

@router.get("/auth/callback")
async def google_callback(request: Request):
    client_email = request.session.get("client_email")
    if not client_email:
        return RedirectResponse("/login")
    
    flow = build_flow()
    flow.fetch_token(authorization_response=str(request.url))
    
    creds = flow.credentials
    token_json = creds.to_json()
    
    # Save to database against this client
    client = get_client_by_email(client_email)
    save_google_token(client["id"], token_json)
    
    return RedirectResponse("/setup?google=connected")

@router.get("/auth/status")
async def auth_status(request: Request):
    client_email = request.session.get("client_email")
    if not client_email:
        return JSONResponse({"authenticated": False})
    
    from agent.database import get_client_by_email
    client = get_client_by_email(client_email)
    return JSONResponse({
        "authenticated": True,
        "google_connected": bool(client.get("google_token_json")),
        "wa_connected": bool(client.get("wa_phone")),
    })

def get_google_credentials_for_client(client: dict):
    """Load and auto-refresh Google credentials for a given client dict."""
    token_json = client.get("google_token_json")
    if not token_json:
        raise Exception(f"No Google token for client {client['email']}")
    
    creds = Credentials.from_authorized_user_info(
        json.loads(token_json),
        scopes=SCOPES
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(GoogleRequest())
        # Save refreshed token back to DB
        save_google_token(client["id"], creds.to_json())
    
    return creds