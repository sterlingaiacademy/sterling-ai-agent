# agent/setup_routes.py
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from pydantic import BaseModel
from agent.database import update_client, get_client_by_email
import os
import re
import requests as http_requests

router = APIRouter()

class WhatsAppConfig(BaseModel):
    wa_token:        str
    wa_phone_id:     str
    wa_verify_token: str
    sheet_id:        str
    alert_email:     str
    wa_phone:        str


# ── Serve setup page ──────────────────────────────────────────────────────────
@router.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request):
    client_email = request.session.get("client_email")
    if not client_email:
        return RedirectResponse("/login")

    html_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "onboarding.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()


# ── Verify credentials ────────────────────────────────────────────────────────
@router.post("/setup/verify")
async def verify_credentials(config: WhatsAppConfig, request: Request):
    results = {}

    # 1. Verify WhatsApp token + Phone ID
    try:
        res = http_requests.get(
            f"https://graph.facebook.com/v18.0/{config.wa_phone_id}",
            headers={"Authorization": f"Bearer {config.wa_token}"},
            timeout=10
        )
        if res.status_code == 200:
            results["whatsapp"] = {"ok": True, "msg": "WhatsApp API connected successfully"}
        else:
            data = res.json()
            err = data.get("error", {}).get("message", "Invalid token or Phone ID")
            results["whatsapp"] = {"ok": False, "msg": err}
    except Exception as e:
        results["whatsapp"] = {"ok": False, "msg": str(e)}

    # 2. Verify Google Sheets access
    try:
        from agent.google_auth_flow import get_google_credentials_for_client
        from googleapiclient.discovery import build

        client_email = request.session.get("client_email")
        client = get_client_by_email(client_email)
        creds = get_google_credentials_for_client(client)
        service = build("sheets", "v4", credentials=creds)
        service.spreadsheets().get(spreadsheetId=config.sheet_id).execute()
        results["sheets"] = {"ok": True, "msg": "Google Sheet found and accessible"}
    except Exception as e:
        results["sheets"] = {"ok": False, "msg": f"Could not access sheet: {str(e)[:80]}"}

    # 3. Verify alert email format
    if re.match(r"[^@]+@[^@]+\.[^@]+", config.alert_email):
        results["email"] = {"ok": True, "msg": f"Alert email set to {config.alert_email}"}
    else:
        results["email"] = {"ok": False, "msg": "Invalid email address format"}

    return JSONResponse({"results": results})


# ── Save WhatsApp + service config to database ────────────────────────────────
@router.post("/setup/whatsapp")
async def save_whatsapp_config(config: WhatsAppConfig, request: Request):
    try:
        client_id = request.session.get("client_id")
        if not client_id:
            return JSONResponse(
                {"status": "error", "detail": "Not logged in"},
                status_code=401
            )

        update_client(client_id, {
            "wa_token":           config.wa_token,
            "wa_phone_number_id": config.wa_phone_id,
            "wa_verify_token":    config.wa_verify_token,
            "google_sheet_id":    config.sheet_id,
            "alert_email":        config.alert_email,
            "wa_phone":           config.wa_phone,
        })

        return JSONResponse({"status": "ok", "message": "Configuration saved successfully."})

    except Exception as e:
        return JSONResponse(
            {"status": "error", "detail": str(e)},
            status_code=500
        )
        
    