import requests, os

async def send_whatsapp_message(phone: str, message: str, client_data: dict = None):
    if client_data:
        token    = client_data.get("wa_token") or os.getenv("WA_TOKEN")
        phone_id = client_data.get("wa_phone_number_id") or os.getenv("WA_PHONE_NUMBER_ID")
    else:
        token    = os.getenv("WA_TOKEN")
        phone_id = os.getenv("WA_PHONE_NUMBER_ID")

    if not token or not phone_id:
        print("[WhatsApp] ERROR: No token or phone_id found!")
        return {"error": "missing credentials"}

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