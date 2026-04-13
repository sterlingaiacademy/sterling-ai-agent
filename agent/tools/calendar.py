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
async def get_events(date: str, client_data: dict = None):
    """Get all calendar events for a specific date."""
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
    
    # Get start and end of the day
    from datetime import datetime, timedelta
    import pytz
    
    tz = pytz.timezone(timezone)
    day_start = tz.localize(datetime.strptime(date, "%Y-%m-%d"))
    day_end   = day_start + timedelta(days=1)

    events = service.events().list(
        calendarId=calendar_id,
        timeMin=day_start.isoformat(),
        timeMax=day_end.isoformat(),
        singleEvents=True,
        orderBy="startTime"
    ).execute()

    items = events.get("items", [])
    if not items:
        return f"No events on {date}"
    
    result = f"Events on {date}:\n"
    for e in items:
        start = e["start"].get("dateTime", e["start"].get("date"))
        result += f"- {e['summary']} at {start}\n"
    return result