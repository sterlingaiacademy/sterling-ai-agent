import os
import requests
from openai import OpenAI
from agent.database import supabase
import uuid

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def download_whatsapp_audio(media_id: str, token: str) -> bytes:
    """Download audio file from WhatsApp."""
    # Step 1: Get media URL
    meta_response = requests.get(
        f"https://graph.facebook.com/v18.0/{media_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10
    )
    media_url = meta_response.json().get("url", "")
    if not media_url:
        raise Exception("Could not get media URL from Meta")

    # Step 2: Download audio bytes
    audio_response = requests.get(
        media_url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30
    )
    return audio_response.content


async def transcribe_and_save(
    media_id: str,
    token: str,
    meeting_name: str,
    wa_phone: str
) -> str:
    """Full pipeline: download → transcribe → summarize → save to DB."""

    # Step 1: Download audio
    print(f"[Transcribe] Downloading audio for {meeting_name}...")
    audio_bytes = await download_whatsapp_audio(media_id, token)

    # Step 2: Upload to Supabase Storage
    filename = f"audio_{uuid.uuid4().hex}.ogg"
    supabase.storage.from_("recordings").upload(
        filename,
        audio_bytes,
        {"content-type": "audio/ogg", "x-upsert": "true"}
    )
    audio_url = supabase.storage.from_("recordings").get_public_url(filename)
    print(f"[Transcribe] Audio stored: {audio_url}")

    # Step 3: Transcribe with Whisper
    print(f"[Transcribe] Transcribing with Whisper...")
    import tempfile, os as _os
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    with open(tmp_path, "rb") as audio_file:
        transcript_response = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
    _os.unlink(tmp_path)
    transcript_text = transcript_response.text
    print(f"[Transcribe] Transcript: {transcript_text[:100]}...")

    # Step 4: Summarize and extract action items with GPT
    print(f"[Transcribe] Summarizing...")
    summary_response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": "You are a meeting assistant. Given a transcript, provide a concise summary and list of action items."
            },
            {
                "role": "user",
                "content": f"Meeting: {meeting_name}\n\nTranscript:\n{transcript_text}\n\nProvide:\n1. Summary (2-3 sentences)\n2. Action items (bullet points)"
            }
        ]
    )
    summary_text = summary_response.choices[0].message.content

    # Step 5: Save everything to Supabase
    supabase.table("meeting_transcripts").insert({
        "wa_phone": wa_phone,
        "meeting_name": meeting_name,
        "transcript": transcript_text,
        "summary": summary_text,
        "audio_url": audio_url
    }).execute()
    print(f"[Transcribe] Saved to database!")

    return f"✅ Meeting '{meeting_name}' transcribed and saved!\n\n{summary_text}"


async def get_meeting_summary(meeting_name: str, wa_phone: str) -> str:
    """Get summary of a saved meeting by name."""
    result = supabase.table("meeting_transcripts")\
        .select("meeting_name, summary, transcript, created_at")\
        .eq("wa_phone", wa_phone)\
        .ilike("meeting_name", f"%{meeting_name}%")\
        .order("created_at", desc=True)\
        .limit(1)\
        .execute()

    if not result.data:
        return f"No meeting found with name '{meeting_name}'"

    meeting = result.data[0]
    return f"📋 *{meeting['meeting_name']}*\n\n{meeting['summary']}"


async def get_all_meetings(wa_phone: str) -> str:
    """Get list of all saved meetings."""
    result = supabase.table("meeting_transcripts")\
        .select("meeting_name, created_at")\
        .eq("wa_phone", wa_phone)\
        .order("created_at", desc=True)\
        .limit(10)\
        .execute()

    if not result.data:
        return "No meetings saved yet."

    meetings = ""
    for m in result.data:
        date = m["created_at"][:10]
        meetings += f"📋 {m['meeting_name']} — {date}\n"

    return f"Your saved meetings:\n\n{meetings}"