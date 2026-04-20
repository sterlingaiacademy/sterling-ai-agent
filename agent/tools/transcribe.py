import os
import requests
from openai import OpenAI
from agent.database import supabase
import uuid

async def download_whatsapp_audio(media_id: str, token: str) -> bytes:
    """Download audio file from WhatsApp."""
    meta_response = requests.get(
        f"https://graph.facebook.com/v18.0/{media_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10
    )
    media_url = meta_response.json().get("url", "")
    if not media_url:
        raise Exception("Could not get media URL from Meta")

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
    wa_phone: str,
    client_data: dict = None
) -> str:
    """Full pipeline: download → transcribe → summarize → save to DB."""

    # ── Per-user OpenAI client ────────────────────────────────────────────────
    openai_key = None
    if client_data:
        openai_key = client_data.get("openai_api_key")
    if not openai_key:
        openai_key = os.getenv("OPENAI_API_KEY")
    ai_client = OpenAI(api_key=openai_key)
    client_id = (client_data or {}).get("id")

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

    # Step 3: Transcribe with Whisper (verbose_json gives real duration)
    print(f"[Transcribe] Transcribing with Whisper...")
    import tempfile, os as _os
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    with open(tmp_path, "rb") as audio_file:
        transcript_response = ai_client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="verbose_json"
        )
    _os.unlink(tmp_path)
    transcript_text = transcript_response.text
    print(f"[Transcribe] Transcript: {transcript_text[:100]}...")

    # Step 4: Get actual audio duration from Whisper response (in seconds → minutes)
    try:
        duration_seconds = float(transcript_response.duration)
        estimated_minutes = round(duration_seconds / 60, 2)
    except Exception:
        # Fallback: estimate from word count (~150 words/min)
        word_count = len(transcript_text.split())
        estimated_minutes = round(word_count / 150, 2)
    # Safety floor: at least 0.5 min if any audio was processed
    if estimated_minutes == 0.0 and len(audio_bytes) > 0:
        estimated_minutes = 0.5
    print(f"[Transcribe] Duration: {estimated_minutes} minutes")

    # Step 5: Summarize and extract action items with GPT
    print(f"[Transcribe] Summarizing...")
    summary_response = ai_client.chat.completions.create(
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

    # Step 6: Track token usage + offline meeting minutes
    if client_id:
        from agent.database import increment_openai_usage, add_meeting_minutes
        try:
            usage = summary_response.usage
            input_t  = usage.prompt_tokens or 0
            output_t = usage.completion_tokens or 0
            total_t  = input_t + output_t
            cost     = round(input_t / 1000 * 0.005 + output_t / 1000 * 0.015, 6)
            increment_openai_usage(client_id, total_t, cost)
        except Exception as e:
            print(f"[Transcribe] Usage tracking error: {e}")

        add_meeting_minutes(client_id, "offline", estimated_minutes, 1)

    # Step 7: Save everything to Supabase
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