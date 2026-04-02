# agent/setup_routes.py
from agent.database import update_client
from fastapi import APIRouter
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
import os, re

router = APIRouter()

class WhatsAppConfig(BaseModel):
    wa_token:        str
    wa_phone_id:     str
    wa_verify_token: str
    sheet_id:        str
    alert_email:     str


@router.get("/setup", response_class=HTMLResponse)
async def setup_page():
    """Serve the onboarding UI."""
    html_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "onboarding.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()


@router.post("/setup/whatsapp")
async def save_whatsapp_config(config: WhatsAppConfig):
    """Save WhatsApp + Sheet credentials to .env file."""
    try:
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")

        # Read existing .env
        if os.path.exists(env_path):
            with open(env_path, "r") as f:
                lines = f.readlines()
        else:
            lines = []

        # Keys to update
        updates = {
            "WA_TOKEN":          config.wa_token,
            "WA_PHONE_NUMBER_ID": config.wa_phone_id,
            "WA_VERIFY_TOKEN":   config.wa_verify_token,
            "GOOGLE_SHEET_ID":   config.sheet_id,
            "ALERT_EMAIL":       config.alert_email,
        }

        updated_keys = set()
        new_lines = []

        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                new_lines.append(line)
                continue
            key = stripped.split("=")[0].strip()
            if key in updates:
                new_lines.append(f"{key}={updates[key]}\n")
                updated_keys.add(key)
            else:
                new_lines.append(line)

        # Add any keys that weren't in the file yet
        for key, val in updates.items():
            if key not in updated_keys:
                new_lines.append(f"{key}={val}\n")

        with open(env_path, "w") as f:
            f.writelines(new_lines)

        # Reload env vars in running process
        for key, val in updates.items():
            os.environ[key] = val

        return {"status": "ok", "message": "Configuration saved successfully."}

    except Exception as e:
        return {"status": "error", "detail": str(e)}, 500
    
    
@router.post("/setup/save")
async def save_setup(request: Request):
    client_id = request.session.get("client_id")
    form = await request.form()
    
    update_client(client_id, {
        "wa_phone": form.get("wa_phone"),
        "wa_token": form.get("wa_token"),
        "wa_phone_number_id": form.get("wa_phone_number_id"),
        "google_sheet_id": form.get("google_sheet_id"),
        "alert_email": form.get("alert_email"),
        "timezone": form.get("timezone", "Asia/Kolkata"),
    })
    return RedirectResponse("/setup?saved=true", status_code=302)
