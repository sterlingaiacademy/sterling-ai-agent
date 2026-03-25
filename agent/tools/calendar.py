from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from dotenv import load_dotenv
import os

load_dotenv()

async def create_event(title: str, start: str, end: str, description: str = "", attendees: list = []):
    calendar_id = os.getenv("GOOGLE_CALENDAR_ID", "primary")
    timezone    = os.getenv("TIMEZONE", "Asia/Kolkata")
        
    creds   = Credentials.from_authorized_user_file("token.json")
    service = build("calendar", "v3", credentials=creds)

    event = {
        "summary":     title,
        "description": description,
        "start":  {"dateTime": start, "timeZone": timezone},
        "end":    {"dateTime": end,   "timeZone": timezone},
        "attendees": [{"email": a} for a in attendees],
    }

    created = service.events().insert(
        calendarId=calendar_id, body=event
    ).execute()

    print(f"[Calendar] Event created: {title} | {start}")
    return f"Event created: {title} on {start}"