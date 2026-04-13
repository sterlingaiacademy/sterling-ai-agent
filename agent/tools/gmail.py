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
async def get_emails(max_results: int = 5, client_data: dict = None):
    """Fetch recent emails."""
    if client_data:
        token_json = client_data.get("google_token_json")
        creds = Credentials.from_authorized_user_info(json.loads(token_json))
    else:
        creds = Credentials.from_authorized_user_file("token.json")

    service = build("gmail", "v1", credentials=creds)
    
    results = service.users().messages().list(
        userId="me", maxResults=max_results
    ).execute()
    
    messages = results.get("messages", [])
    if not messages:
        return "No emails found"

    email_list = []
    for msg in messages:
        detail = service.users().messages().get(
            userId="me", id=msg["id"], format="metadata",
            metadataHeaders=["From", "Subject", "Date"]
        ).execute()
        
        headers = {h["name"]: h["value"] for h in detail["payload"]["headers"]}
        email_list.append(
            f"From: {headers.get('From','?')}\n"
            f"Subject: {headers.get('Subject','?')}\n"
            f"Date: {headers.get('Date','?')}"
        )
    
    return "\n\n".join(email_list)


async def get_email_body(subject_keyword: str, client_data: dict = None):
    """Get full body of an email by searching subject keyword."""
    if client_data:
        token_json = client_data.get("google_token_json")
        creds = Credentials.from_authorized_user_info(json.loads(token_json))
    else:
        creds = Credentials.from_authorized_user_file("token.json")

    service = build("gmail", "v1", credentials=creds)
    import base64

    results = service.users().messages().list(
        userId="me", q=f"subject:{subject_keyword}", maxResults=1
    ).execute()

    messages = results.get("messages", [])
    if not messages:
        return f"No email found with subject: {subject_keyword}"

    msg = service.users().messages().get(
        userId="me", id=messages[0]["id"], format="full"
    ).execute()

    # Extract body
    parts = msg["payload"].get("parts", [])
    body = ""
    for part in parts:
        if part["mimeType"] == "text/plain":
            data = part["body"].get("data", "")
            body = base64.urlsafe_b64decode(data).decode("utf-8")
            break
    
    if not body:
        data = msg["payload"]["body"].get("data", "")
        if data:
            body = base64.urlsafe_b64decode(data).decode("utf-8")

    return body[:3000]  # limit to 3000 chars