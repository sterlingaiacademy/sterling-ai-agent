from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import base64, os
from email.mime.text import MIMEText


async def send_email(to: str, subject: str, body: str):
    # Guard against empty/invalid email
    if not to or "@" not in str(to):
        print(f"[Gmail] Skipped — invalid 'to' address: {to}")
        return "Email skipped: invalid address"

    creds   = Credentials.from_authorized_user_file("token.json")
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