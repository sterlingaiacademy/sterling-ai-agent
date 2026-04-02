import json, os, base64
from email.mime.text import MIMEText
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

async def send_email(to: str, subject: str, body: str, client_data: dict = None):
    if not to or "@" not in str(to):
        print(f"[Gmail] Skipped — invalid 'to' address: {to}")
        return "Email skipped: invalid address"

    if client_data:
        token_json = client_data.get("google_token_json")
        creds = Credentials.from_authorized_user_info(json.loads(token_json))
    else:
        creds = Credentials.from_authorized_user_file("token.json")

    service = build("gmail", "v1", credentials=creds)

    msg = MIMEText(body)
    msg["to"]      = to
    msg["subject"] = subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    service.users().messages().send(
        userId="me", body={"raw": raw}
    ).execute()

    print(f"[Gmail] Email sent to {to} | Subject: {subject}")
    return "Email sent"