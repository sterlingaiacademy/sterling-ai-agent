import json, os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

async def create_event(title: str, start: str, end: str,
                       description: str = "", attendees: list = [],
                       client_data: dict = None):

    if client_data:
        token_json  = client_data.get("google_token_json")
        calendar_id = client_data.get("google_calendar_id") or "primary"
        timezone    = client_data.get("timezone") or "Asia/Kolkata"
        creds = Credentials.from_authorized_user_info(json.loads(token_json))
    else:
        calendar_id = os.getenv("GOOGLE_CALENDAR_ID", "primary")
        timezone    = os.getenv("TIMEZONE", "Asia/Kolkata")
        creds = Credentials.from_authorized_user_file("token.json")

    service = build("calendar", "v3", credentials=creds)

    event = {
        "summary":     title,
        "description": description,
        "start":  {"dateTime": start, "timeZone": timezone},
        "end":    {"dateTime": end,   "timeZone": timezone},
        "attendees": [{"email": a} for a in attendees],
    }

    service.events().insert(calendarId=calendar_id, body=event).execute()
    print(f"[Calendar] Event created: {title} | {start}")
    return f"Event created: {title} on {start}"