# agent/memory.py
"""
Conversation memory backed by Supabase.

Schema expected (conversations table):
  id          bigint (auto)
  wa_phone    text
  role        text  ('user' | 'assistant')
  content     text
  tool_calls  jsonb  (nullable)
  created_at  timestamptz (default now())

Fixes applied:
  - save_memory() now saves BOTH the user message AND assistant reply
    (previously only the assistant reply was saved, so the agent had
     no user-side context in future turns)
  - get_memory() now limits to the last 500 messages (250 turns) so the
    agent remembers a long and detailed conversation history
  - save_user_message() is still available for explicit pre-saves
"""

import json
from agent.database import supabase

# How many recent messages to load into context (keep last N rows)
MAX_HISTORY = 500


def get_memory(phone: str) -> list:
    """Load the last MAX_HISTORY messages for this phone from Supabase."""
    try:
        result = (
            supabase.table("conversations")
            .select("role, content, tool_calls")
            .eq("wa_phone", phone)
            .order("created_at", desc=True)   # newest first so we can slice
            .limit(MAX_HISTORY)
            .execute()
        )

        # Reverse so oldest→newest for the model
        rows = list(reversed(result.data))

        history = []
        for row in rows:
            msg = {"role": row["role"], "content": row["content"] or ""}
            if row.get("tool_calls"):
                # tool_calls may be stored as a JSON string or already a list
                tc = row["tool_calls"]
                if isinstance(tc, str):
                    try:
                        tc = json.loads(tc)
                    except Exception:
                        tc = None
                if tc:
                    msg["tool_calls"] = tc
            history.append(msg)

        return history

    except Exception as e:
        print(f"[Memory] get_memory error: {e}")
        return []


def save_memory(phone: str, history: list):
    """
    Save the last user message + last assistant reply to Supabase.
    We find them by scanning from the end of the history list.
    """
    try:
        rows_to_insert = []

        # Walk history in reverse to find the last user msg and last assistant reply
        found_assistant = False
        found_user = False

        for msg in reversed(history):
            role = msg.get("role")

            if role == "assistant" and not found_assistant:
                rows_to_insert.append({
                    "wa_phone": phone,
                    "role": "assistant",
                    "content": msg.get("content") or "",
                })
                found_assistant = True

            elif role == "user" and not found_user:
                rows_to_insert.append({
                    "wa_phone": phone,
                    "role": "user",
                    "content": msg.get("content") or "",
                })
                found_user = True

            if found_assistant and found_user:
                break

        if rows_to_insert:
            supabase.table("conversations").insert(rows_to_insert).execute()
            print(f"[Memory] Saved {len(rows_to_insert)} row(s) for {phone}")

    except Exception as e:
        print(f"[Memory] save_memory error: {e}")


def save_user_message(phone: str, message: str):
    """Explicitly save a user message (used for voice-note pre-saves)."""
    try:
        supabase.table("conversations").insert({
            "wa_phone": phone,
            "role": "user",
            "content": message,
        }).execute()
    except Exception as e:
        print(f"[Memory] save_user_message error: {e}")