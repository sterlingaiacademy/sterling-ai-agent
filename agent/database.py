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