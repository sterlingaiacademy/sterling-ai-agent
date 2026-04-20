import os
from supabase import create_client

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

def get_client_by_phone(wa_phone: str):
    result = supabase.table("clients").select("*").eq("wa_phone", wa_phone).execute()
    return result.data[0] if result.data else None

def get_client_by_email(email: str):
    result = supabase.table("clients").select("*").eq("email", email).execute()
    return result.data[0] if result.data else None

def save_google_token(client_id: str, token_json: str):
    supabase.table("clients").update({
        "google_token_json": token_json
    }).eq("id", client_id).execute()

def update_client(client_id: str, data: dict):
    supabase.table("clients").update(data).eq("id", client_id).execute()

def get_client_by_mobile(mobile_number: str):
    result = supabase.table("clients").select("*").eq("mobile_number", mobile_number).execute()
    return result.data[0] if result.data else None

def create_client_account(email: str, password_hash: str, mobile_number: str = None):
    data = {
        "email": email,
        "password_hash": password_hash
    }
    if mobile_number:
        data["mobile_number"] = mobile_number
    result = supabase.table("clients").insert(data).execute()
    return result.data[0]

def save_pending_audio(wa_phone: str, audio_url: str):
    supabase.table("clients").update({
        "pending_audio_url": audio_url
    }).eq("wa_phone", wa_phone).execute()

def get_pending_audio(wa_phone: str):
    result = supabase.table("clients").select("pending_audio_url")\
        .eq("wa_phone", wa_phone).execute()
    return result.data[0].get("pending_audio_url") if result.data else None

def clear_pending_audio(wa_phone: str):
    supabase.table("clients").update({
        "pending_audio_url": None
    }).eq("wa_phone", wa_phone).execute()

# ── Usage Tracking ─────────────────────────────────────────────────────────────

# Human-readable labels for each tool name
EVENT_LABELS = {
    "send_email":              "📧 Send Email",
    "log_expense":             "💰 Log Expense",
    "create_calendar_event":   "📅 Create Calendar Event",
    "get_calendar_events":     "📅 View Calendar",
    "get_emails":              "📬 Read Emails",
    "get_email_body":          "📖 Read Email Body",
    "invite_bot_to_meeting":   "🎥 Join Meeting (Online)",
    "save_meeting_recording":  "🎙️ Transcribe Voice Note",
    "get_meeting_summary":     "📋 Get Meeting Summary",
    "get_all_meetings":        "📋 List All Meetings",
    "get_meeting_transcripts": "🔥 Get Online Transcripts",
    "get_transcript_detail":   "🔥 Get Transcript Detail",
    "search_web":              "🔍 Web Search",
}

def increment_openai_usage(client_id: str, tokens: int, cost_usd: float):
    """Add to the cumulative OpenAI token + cost counters for a client."""
    try:
        result = supabase.table("clients")\
            .select("openai_tokens_used, openai_cost_usd")\
            .eq("id", client_id).execute()
        if not result.data:
            return
        row = result.data[0]
        new_tokens = (row.get("openai_tokens_used") or 0) + tokens
        new_cost   = (row.get("openai_cost_usd") or 0.0) + cost_usd
        supabase.table("clients").update({
            "openai_tokens_used": new_tokens,
            "openai_cost_usd": round(new_cost, 6)
        }).eq("id", client_id).execute()
    except Exception as e:
        print(f"[Usage] Failed to increment OpenAI usage: {e}")

def add_meeting_minutes(client_id: str, meeting_type: str, minutes: float, count: int = 1):
    """Add meeting minutes and count for online or offline meetings."""
    try:
        col_mins  = "online_meeting_minutes"  if meeting_type == "online"  else "offline_meeting_minutes"
        col_count = "online_meetings_count"   if meeting_type == "online"  else "offline_meetings_count"

        result = supabase.table("clients")\
            .select(f"{col_mins}, {col_count}")\
            .eq("id", client_id).execute()
        if not result.data:
            return
        row = result.data[0]
        new_mins  = (row.get(col_mins)  or 0.0) + minutes
        new_count = (row.get(col_count) or 0)   + count
        supabase.table("clients").update({
            col_mins:  round(new_mins, 2),
            col_count: new_count
        }).eq("id", client_id).execute()
    except Exception as e:
        print(f"[Usage] Failed to add meeting minutes: {e}")

def get_usage_stats(client_id: str) -> dict:
    """Return all usage stats for a client."""
    try:
        result = supabase.table("clients").select(
            "openai_tokens_used, openai_cost_usd, "
            "online_meeting_minutes, offline_meeting_minutes, "
            "online_meetings_count, offline_meetings_count"
        ).eq("id", client_id).execute()
        return result.data[0] if result.data else {}
    except Exception as e:
        print(f"[Usage] Failed to get usage stats: {e}")
        return {}

def log_usage_event(client_id: str, tool_name: str, tokens: int, cost_usd: float):
    """Log a single tool-level usage event to the usage_events table."""
    try:
        label = EVENT_LABELS.get(tool_name, f"⚡ {tool_name.replace('_', ' ').title()}")
        supabase.table("usage_events").insert({
            "client_id":   client_id,
            "tool_name":   tool_name,
            "event_label": label,
            "tokens":      tokens,
            "cost_usd":    cost_usd,
        }).execute()
    except Exception as e:
        print(f"[Usage] Failed to log event: {e}")

def get_usage_events(client_id: str, limit: int = 30) -> list:
    """Get recent usage events (most recent first) for a client."""
    try:
        result = supabase.table("usage_events")\
            .select("tool_name, event_label, tokens, cost_usd, created_at")\
            .eq("client_id", client_id)\
            .order("created_at", desc=True)\
            .limit(limit)\
            .execute()
        return result.data or []
    except Exception as e:
        print(f"[Usage] Failed to get events: {e}")
        return []

def get_usage_events_summary(client_id: str) -> list:
    """Get token usage aggregated by event type, sorted by total tokens desc."""
    try:
        result = supabase.table("usage_events")\
            .select("event_label, tokens, cost_usd")\
            .eq("client_id", client_id)\
            .execute()
        agg: dict = {}
        for row in (result.data or []):
            lbl = row["event_label"]
            if lbl not in agg:
                agg[lbl] = {"event_label": lbl, "total_tokens": 0, "total_cost": 0.0, "count": 0}
            agg[lbl]["total_tokens"] += row.get("tokens", 0)
            agg[lbl]["total_cost"]   += row.get("cost_usd", 0.0)
            agg[lbl]["count"]        += 1
        return sorted(agg.values(), key=lambda x: x["total_tokens"], reverse=True)
    except Exception as e:
        print(f"[Usage] Failed to get events summary: {e}")
        return []

def get_meetings_list(wa_phone: str, limit: int = 20) -> list:
    """Get offline voice-note meeting recordings for a user."""
    try:
        result = supabase.table("meeting_transcripts")\
            .select("meeting_name, created_at, summary")\
            .eq("wa_phone", wa_phone)\
            .order("created_at", desc=True)\
            .limit(limit)\
            .execute()
        return result.data or []
    except Exception as e:
        print(f"[Usage] Failed to get meetings list: {e}")
        return []