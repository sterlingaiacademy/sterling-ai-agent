# agent/setup_routes.py
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from pydantic import BaseModel
from agent.database import update_client, get_client_by_email, get_usage_stats
import os
import re
import requests as http_requests

router = APIRouter()

class WhatsAppConfig(BaseModel):
    wa_token:          str
    wa_phone_id:       str
    wa_verify_token:   str
    sheet_id:          str
    alert_email:       str
    wa_phone:          str
    openai_api_key:    str = ""
    fireflies_api_key: str = ""


# ── Serve setup page ──────────────────────────────────────────────────────────
@router.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request):
    client_email = request.session.get("client_email")
    if not client_email:
        return RedirectResponse("/login")

    html_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "onboarding.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()


# ── Usage stats API ───────────────────────────────────────────────────────────
@router.get("/usage")
async def usage_stats(request: Request):
    client_id = request.session.get("client_id")
    if not client_id:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    stats = get_usage_stats(client_id)

    # Also fetch Fireflies live usage
    fireflies_data = {}
    try:
        client_email = request.session.get("client_email")
        from agent.database import get_client_by_email as _gce
        client = _gce(client_email)
        if client and client.get("fireflies_api_key"):
            from agent.tools.fireflies import get_fireflies_usage
            import asyncio
            fireflies_data = await get_fireflies_usage(client_data=client)
    except Exception as e:
        print(f"[Usage] Fireflies fetch error: {e}")

    return JSONResponse({
        "openai_tokens_used":       stats.get("openai_tokens_used", 0),
        "openai_cost_usd":          stats.get("openai_cost_usd", 0.0),
        "online_meeting_minutes":   stats.get("online_meeting_minutes", 0.0),
        "offline_meeting_minutes":  stats.get("offline_meeting_minutes", 0.0),
        "online_meetings_count":    stats.get("online_meetings_count", 0),
        "offline_meetings_count":   stats.get("offline_meetings_count", 0),
        "fireflies": fireflies_data,
    })


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

    # 4. Verify OpenAI API key (optional but useful)
    if config.openai_api_key:
        try:
            from openai import OpenAI
            test_client = OpenAI(api_key=config.openai_api_key)
            test_client.models.list()
            results["openai"] = {"ok": True, "msg": "OpenAI key verified successfully"}
        except Exception as e:
            results["openai"] = {"ok": False, "msg": f"OpenAI key error: {str(e)[:80]}"}

    # 5. Verify Fireflies API key (optional)
    if config.fireflies_api_key:
        try:
            res = http_requests.post(
                "https://api.fireflies.ai/graphql",
                json={"query": "query { user { email } }"},
                headers={
                    "Authorization": f"Bearer {config.fireflies_api_key}",
                    "Content-Type": "application/json"
                },
                timeout=10
            )
            data = res.json()
            if data.get("data", {}).get("user"):
                results["fireflies"] = {"ok": True, "msg": f"Fireflies connected: {data['data']['user'].get('email', '')}"}
            else:
                results["fireflies"] = {"ok": False, "msg": "Invalid Fireflies API key"}
        except Exception as e:
            results["fireflies"] = {"ok": False, "msg": str(e)}

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

        data = {
            "wa_token":           config.wa_token,
            "wa_phone_number_id": config.wa_phone_id,
            "wa_verify_token":    config.wa_verify_token,
            "google_sheet_id":    config.sheet_id,
            "alert_email":        config.alert_email,
            "wa_phone":           config.wa_phone,
        }
        if config.openai_api_key:
            data["openai_api_key"] = config.openai_api_key
        if config.fireflies_api_key:
            data["fireflies_api_key"] = config.fireflies_api_key

        update_client(client_id, data)

        return JSONResponse({"status": "ok", "message": "Configuration saved successfully."})

    except Exception as e:
        return JSONResponse(
            {"status": "error", "detail": str(e)},
            status_code=500
        )