from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from dotenv import load_dotenv
import os

load_dotenv()

async def log_expense(credit_debit, purpose, amount, balance):
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    creds    = Credentials.from_authorized_user_file("token.json")
    service  = build("sheets", "v4", credentials=creds)

    values = [[credit_debit, purpose, amount, balance]]
    service.spreadsheets().values().append(
        spreadsheetId=sheet_id,
        range="Sheet1",
        valueInputOption="RAW",
        body={"values": values}
    ).execute()
    return "Expense logged"