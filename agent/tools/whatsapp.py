# agent/tools/whatsapp.py
import requests
import os


async def send_whatsapp_message(phone: str, message: str, client_data: dict = None):
    """Send a WhatsApp text message back to the user.
    Uses per-user credentials from client_data (Supabase), falls back to env vars.
    """
    # Use per-user credentials stored in Supabase, fall back to env vars
    token    = (client_data or {}).get("wa_token") or os.getenv("WA_TOKEN")
    phone_id = (client_data or {}).get("wa_phone_number_id") or os.getenv("WA_PHONE_NUMBER_ID")

    if not token:
        print(f"[WhatsApp] ERROR: No WA_TOKEN found for {phone}")
        return {"error": "missing_token"}

    if not phone_id:
        print(f"[WhatsApp] ERROR: No WA_PHONE_NUMBER_ID found for {phone}")
        return {"error": "missing_phone_id"}

    url = f"https://graph.facebook.com/v18.0/{phone_id}/messages"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
    }

    payload = {
        "messaging_product": "whatsapp",
        "to":   phone,
        "type": "text",
        "text": {"body": message},
    }

    response = requests.post(url, json=payload, headers=headers)
    result   = response.json()

    print(f"[WhatsApp] Reply to {phone}: {message[:60]}...")
    print(f"[WhatsApp] API response: {result}")

    return result
