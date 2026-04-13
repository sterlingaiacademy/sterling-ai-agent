import json
from agent.database import supabase

def get_memory(phone: str):
    result = supabase.table("conversations")\
        .select("role, content, tool_calls")\
        .eq("wa_phone", phone)\
        .order("created_at")\
        .execute()
    
    history = []
    for row in result.data:
        msg = {"role": row["role"], "content": row["content"]}
        if row.get("tool_calls"):
            msg["tool_calls"] = row["tool_calls"]
        history.append(msg)
    return history

def save_memory(phone: str, history: list):
    # Only save the last message (assistant reply)
    last = history[-1]
    supabase.table("conversations").insert({
        "wa_phone": phone,
        "role": last["role"],
        "content": last["content"],
    }).execute()

def save_user_message(phone: str, message: str):
    supabase.table("conversations").insert({
        "wa_phone": phone,
        "role": "user",
        "content": message,
    }).execute()