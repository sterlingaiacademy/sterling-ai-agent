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
    # Confirmed by live API test: Fireflies requires 'meeting_link' (NOT 'meeting_url')
    headers = _get_headers(client_data)
    print(f"[Fireflies] Sending bot to: {meeting_url}")

    query = 'mutation { addToLiveMeeting(meeting_link: "%s") { success message } }' % meeting_url.replace('"', '\\"')

    try:
        resp = requests.post(
            FIREFLIES_API,
            json={"query": query},
            headers=headers,
            timeout=15
        )
        data = resp.json()
        print(f"[Fireflies] response ({resp.status_code}): {data}")

        result = (data.get("data") or {}).get("addToLiveMeeting") or {}
        errors  = data.get("errors") or []

        if result.get("success"):
            if client_data and client_data.get("id"):
                from agent.database import add_meeting_minutes
                add_meeting_minutes(client_data["id"], "online", 0, 1)
            import asyncio
            asyncio.create_task(poll_and_deliver_transcript(meeting_name, client_data))
            return (
                "Your Fireflies AI notetaker is joining *'" + meeting_name + "'* now.\n"
                "It may take up to 1 minute to appear. Once the meeting ends, "
                "I'll send you a full summary and transcript automatically."
            )
        else:
            if errors:
                error_msg = errors[0].get("message", "Unknown error")
            else:
                error_msg = result.get("message") or "Unknown error"
            print(f"[Fireflies] error: {error_msg}")
            return (
                "Could not join meeting: " + error_msg + "\n\n"
                "Make sure:\n"
                "- The meeting is currently live (bot can only join active meetings)\n"
                "- The link is a valid Google Meet / Zoom / Teams URL\n"
                "- Your Fireflies API key is correct (Setup Step 3)"
            )
    except Exception as e:
        print(f"[Fireflies] exception: {e}")
        return "Could not reach Fireflies API. Please try again in a moment."



async def poll_and_deliver_transcript(meeting_name: str, client_data: dict = None, max_wait_mins: int = 120):
    """
    Polls Fireflies every 5 minutes (up to max_wait_mins) after a meeting is invited.
    When the transcript appears, sends a summary back to the user via WhatsApp.
    """
    import asyncio
    from datetime import datetime, timezone

    headers = _get_headers(client_data)
    wa_phone = (client_data or {}).get("wa_phone")
    client_id = (client_data or {}).get("id")
    if not wa_phone:
        return

    query = """
    query GetTranscripts {
        transcripts(limit: 5) {
            id title date duration
            summary { overview action_items }
        }
    }
    """
    poll_interval = 5 * 60   # 5 minutes
    max_polls     = max_wait_mins // 5
    seen_ids      = set()

    # Seed seen IDs so we only alert on NEW transcripts
    try:
        seed = requests.post(FIREFLIES_API, json={"query": query}, headers=headers, timeout=10).json()
        for t in (seed.get("data") or {}).get("transcripts") or []:
            seen_ids.add(t["id"])
    except Exception:
        pass

    for _ in range(max_polls):
        await asyncio.sleep(poll_interval)
        try:
            resp = requests.post(FIREFLIES_API, json={"query": query}, headers=headers, timeout=10).json()
            transcripts = (resp.get("data") or {}).get("transcripts") or []
            for t in transcripts:
                if t["id"] in seen_ids:
                    continue
                if meeting_name.lower() not in (t.get("title") or "").lower():
                    continue
                # New transcript found for this meeting!
                seen_ids.add(t["id"])
                dur  = round(float(t.get("duration") or 0), 1)
                summ = (t.get("summary") or {})
                overview  = summ.get("overview")  or "No summary available."
                actions   = summ.get("action_items") or "None noted."
                msg = (
                    f"📋 *Meeting Transcript Ready: {t.get('title', meeting_name)}*\n"
                    f"⏱ Duration: {dur} mins\n\n"
                    f"📝 *Summary:*\n{overview}\n\n"
                    f"✅ *Action Items:*\n{actions}"
                )
                try:
                    from agent.tools.whatsapp import send_whatsapp_message
                    await send_whatsapp_message(wa_phone, msg, client_data=client_data)
                    if client_id and dur > 0:
                        from agent.database import add_meeting_minutes
                        add_meeting_minutes(client_id, "online", dur, 0)
                except Exception as we:
                    print(f"[Fireflies] Failed to send transcript to {wa_phone}: {we}")
                return  # done
        except Exception as pe:
            print(f"[Fireflies] Poll error: {pe}")



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