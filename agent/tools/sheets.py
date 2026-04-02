import json, os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

async def log_expense(credit_debit, purpose, amount, balance, client_data: dict = None):
    if client_data:
        sheet_id   = client_data.get("google_sheet_id") or os.getenv("GOOGLE_SHEET_ID")
        token_json = client_data.get("google_token_json")
        creds = Credentials.from_authorized_user_info(json.loads(token_json))
    else:
        sheet_id = os.getenv("GOOGLE_SHEET_ID")
        creds = Credentials.from_authorized_user_file("token.json")

    service = build("sheets", "v4", credentials=creds)
    values = [[credit_debit, purpose, amount, balance]]
    service.spreadsheets().values().append(
        spreadsheetId=sheet_id,
        range="Sheet1",
        valueInputOption="RAW",
        body={"values": values}
    ).execute()

    print(f"[Sheets] Logged: {credit_debit} | {purpose} | {amount} | bal:{balance}")
    return "Expense logged"