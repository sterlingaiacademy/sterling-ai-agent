import os
import requests

FIREFLIES_API = "https://api.fireflies.ai/graphql"

def get_headers():
    return {
        "Authorization": f"Bearer {os.getenv('FIREFLIES_API_KEY')}",
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
        headers=get_headers(),
        timeout=15
    )
    data = response.json()
    result = data.get("data", {}).get("addToLiveMeeting", {})
    
    if result.get("success"):
        return f"✅ Fireflies bot is joining your meeting: '{meeting_name}'. It will record and transcribe automatically."
    else:
        return f"❌ Could not join meeting: {result.get('message', 'Unknown error')}"


async def upload_audio_to_fireflies(audio_url: str, meeting_name: str, client_data: dict = None):
    """Upload a recorded audio file to Fireflies for transcription."""
    
    print(f"[Fireflies] Uploading: {meeting_name} | URL: {audio_url}")
    print(f"[Fireflies] API Key exists: {bool(os.getenv('FIREFLIES_API_KEY'))}")
    
    query = """
    mutation UploadAudio($url: String!, $title: String!) {
        uploadAudio(url: $url, title: $title) {
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
                "url": audio_url,
                "title": meeting_name
            }
        },
        headers=get_headers(),
        timeout=15
    )
    
    print(f"[Fireflies] Response status: {response.status_code}")
    print(f"[Fireflies] Response body: {response.text}")
    
    data = response.json()
    result = data.get("data", {}).get("uploadAudio", {})

    if result.get("success"):
        return f"✅ Recording '{meeting_name}' uploaded to Fireflies successfully."
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
        headers=get_headers(),
        timeout=15
    )
    data = response.json()
    transcripts = data.get("data", {}).get("transcripts", [])

    if not transcripts:
        return "No meeting transcripts found in Fireflies."

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
        headers=get_headers(),
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