# agent/tools/whatsapp.py
import requests
import os


async def send_whatsapp_message(phone: str, message: str):
    """Send a WhatsApp text message back to the user."""
    token    = os.getenv("WA_TOKEN")
    phone_id = os.getenv("WA_PHONE_NUMBER_ID")

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
