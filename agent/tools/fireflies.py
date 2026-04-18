import os
import requests

FIREFLIES_API = "https://api.fireflies.ai/graphql"

def _get_headers(client_data: dict = None) -> dict:
    """Get auth headers using per-user Fireflies API key with fallback to env."""
    key = None
    if client_data:
        key = client_data.get("fireflies_api_key")
    if not key:
        key = os.getenv("FIREFLIES_API_KEY", "")
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }

async def invite_bot_to_meeting(meeting_url: str, meeting_name: str = "Meeting", client_data: dict = None):
    """Send Fireflies bot to join a Google Meet / Zoom / Teams meeting."""
    query = """
    mutation AddToLiveMeeting($url: String!, $title: String!) {
        addToLiveMeeting(meeting_link: $url, title: $title) {
            success
            message
        }
    }
    """
    response = requests.post(
        FIREFLIES_API,
        json={
            "query": query,
            "variables": {
                "url": meeting_url,
                "title": meeting_name
            }
        },
        headers=_get_headers(client_data),
        timeout=15
    )
    data = response.json()
    result = (data.get("data") or {}).get("addToLiveMeeting") or {}

    if result.get("success"):
        # Track online meeting — we don't know duration yet, count the invite
        if client_data and client_data.get("id"):
            from agent.database import add_meeting_minutes
            add_meeting_minutes(client_data["id"], "online", 0, 1)
        return f"✅ Your assistant is joining your meeting: '{meeting_name}'. It will record and transcribe automatically."
    else:
        errors = data.get("errors", [])
        if isinstance(errors, list) and len(errors) > 0:
            error_msg = errors[0].get("message", "Unknown error")
        else:
            error_msg = result.get("message") or "Unknown error"
        return f"❌ Could not join meeting: {error_msg}"


async def upload_audio_to_fireflies(audio_url: str, meeting_name: str, client_data: dict = None):
    """Upload a recorded audio file to Fireflies for transcription."""

    print(f"[Fireflies] Uploading: {meeting_name} | URL: {audio_url}")

    query = """
    mutation UploadAudio($input: AudioUploadInput!) {
        uploadAudio(input: $input) {
            success
            title
            message
        }
    }
    """
    response = requests.post(
        FIREFLIES_API,
        json={
            "query": query,
            "variables": {
                "input": {
                    "url": audio_url,
                    "title": meeting_name
                }
            }
        },
        headers=_get_headers(client_data),
        timeout=15
    )

    print(f"[Fireflies] Response status: {response.status_code}")
    print(f"[Fireflies] Response body: {response.text}")

    data = response.json()
    result = (data.get("data") or {}).get("uploadAudio") or {}

    if result.get("success"):
        return f"✅ Recording '{meeting_name}' has been saved and is being transcribed by your assistant."
    else:
        errors = data.get("errors", [])
        if isinstance(errors, list) and len(errors) > 0:
            error_msg = errors[0].get("message", "Unknown error")
        else:
            error_msg = result.get("message") or str(data.get("errors", "Unknown error"))

        print(f"[Fireflies] Upload failed: {error_msg}")
        return f"❌ Upload failed: {error_msg}"


async def get_meeting_transcripts(limit: int = 3, client_data: dict = None):
    """Get recent meeting transcripts from Fireflies."""
    query = """
    query GetTranscripts($limit: Int!) {
        transcripts(limit: $limit) {
            id
            title
            date
            duration
            summary {
                overview
                action_items
                keywords
            }
        }
    }
    """
    response = requests.post(
        FIREFLIES_API,
        json={
            "query": query,
            "variables": {"limit": limit}
        },
        headers=_get_headers(client_data),
        timeout=15
    )
    data = response.json()
    transcripts = data.get("data", {}).get("transcripts", [])

    if not transcripts:
        return "No meeting transcripts found."

    # Track total online meeting minutes from fetched transcripts
    if client_data and client_data.get("id"):
        from agent.database import add_meeting_minutes
        total_mins = sum(float(t.get("duration") or 0) for t in transcripts)
        if total_mins > 0:
            add_meeting_minutes(client_data["id"], "online", total_mins, 0)

    result = ""
    for t in transcripts:
        result += f"📋 *{t['title']}*\n"
        result += f"📅 Date: {t.get('date', 'N/A')}\n"
        result += f"⏱ Duration: {t.get('duration', 'N/A')} mins\n"
        if t.get("summary"):
            s = t["summary"]
            if s.get("overview"):
                result += f"📝 Summary: {s['overview']}\n"
            if s.get("action_items"):
                result += f"✅ Action Items: {s['action_items']}\n"
        result += "\n"

    return result


async def get_transcript_detail(meeting_title: str, client_data: dict = None):
    """Get full transcript of a specific meeting by title keyword."""
    query = """
    query GetTranscripts {
        transcripts(limit: 20) {
            id
            title
            date
            duration
            sentences {
                text
                speaker_name
            }
            summary {
                overview
                action_items
                keywords
            }
        }
    }
    """
    response = requests.post(
        FIREFLIES_API,
        json={"query": query},
        headers=_get_headers(client_data),
        timeout=15
    )
    data = response.json()
    transcripts = data.get("data", {}).get("transcripts", [])

    # Find matching transcript
    match = None
    for t in transcripts:
        if meeting_title.lower() in t["title"].lower():
            match = t
            break

    if not match:
        return f"No meeting found with title containing '{meeting_title}'"

    result = f"📋 *{match['title']}*\n"
    result += f"📅 {match.get('date', '')}\n\n"

    if match.get("summary"):
        s = match["summary"]
        if s.get("overview"):
            result += f"📝 *Overview:*\n{s['overview']}\n\n"
        if s.get("action_items"):
            result += f"✅ *Action Items:*\n{s['action_items']}\n\n"

    # Add some transcript lines
    sentences = match.get("sentences", [])[:20]
    if sentences:
        result += "💬 *Transcript snippet:*\n"
        for s in sentences:
            result += f"{s.get('speaker_name', 'Speaker')}: {s.get('text', '')}\n"

    return result


async def get_fireflies_usage(client_data: dict = None) -> dict:
    """Fetch Fireflies account usage/subscription info."""
    query = """
    query GetUser {
        user {
            user_id
            email
            name
            minutes_consumed
            is_admin
        }
    }
    """
    try:
        response = requests.post(
            FIREFLIES_API,
            json={"query": query},
            headers=_get_headers(client_data),
            timeout=10
        )
        data = response.json()
        user = (data.get("data") or {}).get("user") or {}
        return {
            "email": user.get("email", ""),
            "name": user.get("name", ""),
            "minutes_consumed": user.get("minutes_consumed", 0),
        }
    except Exception as e:
        print(f"[Fireflies] Usage fetch error: {e}")
        return {}