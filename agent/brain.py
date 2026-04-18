# agent/brain.py
from openai import OpenAI
from agent.tools.whatsapp import send_whatsapp_message
from agent.tools.gmail import send_email
from agent.tools.sheets import log_expense
from agent.tools.calendar import create_event
from dotenv import load_dotenv
from agent.memory import get_memory, save_memory, save_user_message
from agent.tools.search import search_web
import json
import os
from agent.tools.fireflies import (
    invite_bot_to_meeting,
    upload_audio_to_fireflies,
    get_meeting_transcripts,
    get_transcript_detail
)
from datetime import datetime
import pytz
load_dotenv()

# ── GPT-4o pricing (per 1K tokens) ───────────────────────────────────────────
GPT4O_INPUT_COST_PER_1K  = 0.005   # $0.005 per 1K input tokens
GPT4O_OUTPUT_COST_PER_1K = 0.015   # $0.015 per 1K output tokens

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "send_email",
            "description": "Send an email via Gmail",
            "parameters": {
                "type": "object",
                "properties": {
                    "to":      {"type": "string"},
                    "subject": {"type": "string"},
                    "body":    {"type": "string"}
                },
                "required": ["to", "subject", "body"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "log_expense",
            "description": "Log a credit or debit expense to Google Sheets",
            "parameters": {
                "type": "object",
                "properties": {
                    "credit_debit": {"type": "string", "enum": ["credit", "debit"]},
                    "purpose":      {"type": "string"},
                    "amount":       {"type": "number"},
                    "balance":      {"type": "number"}
                },
                "required": ["credit_debit", "purpose", "amount", "balance"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_calendar_event",
            "description": "Create a Google Calendar event",
            "parameters": {
                "type": "object",
                "properties": {
                    "title":       {"type": "string"},
                    "start":       {"type": "string", "description": "ISO 8601 format e.g. 2025-08-01T14:00:00"},
                    "end":         {"type": "string"},
                    "description": {"type": "string"},
                    "attendees":   {"type": "array", "items": {"type": "string"}}
                },
                "required": ["title", "start", "end"]
            }
        }
    },
    {
    "type": "function",
    "function": {
        "name": "get_calendar_events",
        "description": "View all calendar events for a specific date. Use this to check schedule and detect conflicts before creating new events.",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Date in YYYY-MM-DD format"}
            },
            "required": ["date"]
        }
    }
},
    {
    "type": "function",
    "function": {
        "name": "get_emails",
        "description": "View recent emails from Gmail inbox",
        "parameters": {
            "type": "object",
            "properties": {
                "max_results": {"type": "integer", "description": "Number of emails to fetch, default 5"}
            },
            "required": []
        }
    }
},
{
    "type": "function",
    "function": {
        "name": "get_email_body",
        "description": "Get full content of a specific email to summarize or read it",
        "parameters": {
            "type": "object",
            "properties": {
                "subject_keyword": {"type": "string", "description": "Keyword from the email subject to search"}
            },
            "required": ["subject_keyword"]
        }
    }
},{
    "type": "function",
    "function": {
        "name": "invite_bot_to_meeting",
        "description": "[ONLINE MEETINGS ONLY] Send your AI assistant to join and record a LIVE meeting when the user shares a URL (Google Meet, Zoom, Teams, Webex). Use this ONLY when the user pastes a meeting link. Do NOT use this for voice notes. Do NOT call save_meeting_recording after this.",
        "parameters": {
            "type": "object",
            "properties": {
                "meeting_url": {"type": "string", "description": "The meeting link e.g. https://meet.google.com/xxx"},
                "meeting_name": {"type": "string", "description": "Name/title for this meeting"}
            },
            "required": ["meeting_url", "meeting_name"]
        }
    }
},
{
    "type": "function",
    "function": {
        "name": "get_meeting_transcripts",
        "description": "[ONLINE MEETINGS ONLY] Get list of recent LIVE meeting transcripts (meetings the user attended via a link). Use this only when user asks about online/live meetings. Do NOT use for voice note recordings.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Number of recent meetings to fetch, default 3"}
            },
            "required": []
        }
    }
},
{
    "type": "function",
    "function": {
        "name": "get_transcript_detail",
        "description": "[ONLINE MEETINGS ONLY] Get full transcript of a specific LIVE meeting by its title. Use only for meetings the user attended via a link, not for voice note recordings.",
        "parameters": {
            "type": "object",
            "properties": {
                "meeting_title": {"type": "string", "description": "Title or keyword of the meeting to find"}
            },
            "required": ["meeting_title"]
        }
    }
},{
    "type": "function",
    "function": {
        "name": "save_meeting_recording",
        "description": "[OFFLINE MEETINGS ONLY] Transcribe and save a VOICE NOTE recording sent via WhatsApp. Use this ONLY when the system message explicitly says '[Voice note received. Media ID saved.]' AND the user has provided a name. NEVER call this for meeting links or URLs.",
        "parameters": {
            "type": "object",
            "properties": {
                "meeting_name": {"type": "string", "description": "Name to save this voice note recording as"}
            },
            "required": ["meeting_name"]
        }
    }
},
{
    "type": "function",
    "function": {
        "name": "get_meeting_summary",
        "description": "[OFFLINE MEETINGS ONLY] Get the summary and action items of a saved VOICE NOTE recording. Use this only for offline recordings the user sent as voice notes, not for live meetings.",
        "parameters": {
            "type": "object",
            "properties": {
                "meeting_name": {"type": "string", "description": "Name or keyword of the voice note recording"}
            },
            "required": ["meeting_name"]
        }
    }
},
{
    "type": "function",
    "function": {
        "name": "get_all_meetings",
        "description": "[OFFLINE MEETINGS ONLY] Get list of all saved VOICE NOTE recordings the user has sent. Use this only for offline recordings, not for live/online meetings attended via a link.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    }
},
{
    "type": "function",
    "function": {
        "name": "search_web",
        "description": "Search the internet for real-time information such as current weather, news, prices, cricket/sports scores, or any factual question that requires up-to-date knowledge. Use this whenever the user asks about something that may have changed recently.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query to look up"}
            },
            "required": ["query"]
        }
    }
},
]

SYSTEM_PROMPT = """
You are a smart personal assistant accessible via WhatsApp. You remember everything the user has told you — all past conversations are stored and loaded every time they message.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MEMORY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- You have FULL memory of all past conversations
- NEVER say you don't remember something — always check the conversation history
- When asked "what do you know about me", summarize from history

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MEETINGS — TWO COMPLETELY SEPARATE TYPES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔵 ONLINE MEETINGS (user shares a URL link)
  Trigger : User sends a meeting URL (meet.google.com, zoom.us, teams.microsoft.com, webex, etc.)
  Step 1  : Detect the URL in the message
  Step 2  : Ask "What name should I give this meeting?" (if name not already provided)
  Step 3  : Call invite_bot_to_meeting(meeting_url, meeting_name)
  Step 4  : Reply "Your assistant will join and record the meeting"
  Tools   : invite_bot_to_meeting | get_meeting_transcripts | get_transcript_detail
  ❌ NEVER ask the user to send a voice note for online meetings
  ❌ NEVER call save_meeting_recording for a URL

🟢 OFFLINE MEETINGS (user sends a voice note)
  Trigger : System message says "[Voice note received. Media ID saved.]"
  Step 1  : Ask "What name would you like to give this recording?"
  Step 2  : When user gives name → call save_meeting_recording(meeting_name)
  Step 3  : Reply with the transcription summary
  Tools   : save_meeting_recording | get_meeting_summary | get_all_meetings
  ❌ NEVER call save_meeting_recording unless the system said [Voice note received]
  ❌ NEVER use this flow when the user sends a URL

📋 WHEN USER ASKS ABOUT MEETINGS (transcripts, summaries, count, details):
  Step 1  : Ask "Are you asking about your online meetings (live meetings via link) or offline recordings (voice notes you sent)?"
  Step 2  : For online  → use get_meeting_transcripts or get_transcript_detail
  Step 3  : For offline → use get_all_meetings or get_meeting_summary

⚠️  CRITICAL: These two meeting flows are COMPLETELY SEPARATE. Never mix them.
    URL → online flow. Voice note → offline flow. No exceptions.
    NEVER use the word "Fireflies" — always say "your assistant".

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WEB SEARCH
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- You have FULL internet access via the search_web tool
- For ANY question about: news, weather, prices, cricket/sports scores, stock market,
  current events, BBC, CNN, or anything time-sensitive — ALWAYS call search_web FIRST
- NEVER say "I can't access the internet" or "check the website yourself"
- NEVER answer time-sensitive questions from memory — always search first
- search_web can get BBC headlines, live weather, stock prices, sports scores — use it

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXPENSES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Debit = subtract from balance | Credit = add to balance
- If balance drops to 5000 or below, AUTOMATICALLY send a low balance alert email
"""

# Deduplication: track recently sent replies per phone to prevent duplicate messages
_last_reply: dict = {}


def _calculate_cost(usage) -> tuple[int, float]:
    """Return (total_tokens, cost_usd) from an OpenAI usage object."""
    try:
        input_tokens  = usage.prompt_tokens or 0
        output_tokens = usage.completion_tokens or 0
        total_tokens  = input_tokens + output_tokens
        cost = (input_tokens  / 1000 * GPT4O_INPUT_COST_PER_1K +
                output_tokens / 1000 * GPT4O_OUTPUT_COST_PER_1K)
        return total_tokens, round(cost, 6)
    except Exception:
        return 0, 0.0


async def run_agent(user_message: str, phone: str, client_data: dict):
    # Get current date and time in client's timezone
    timezone = client_data.get("timezone") or "Asia/Kolkata"
    tz = pytz.timezone(timezone)
    now = datetime.now(tz)
    current_datetime = now.strftime("%A, %d %B %Y %I:%M %p")

    # Inject date into system prompt
    dated_system_prompt = (
        SYSTEM_PROMPT
        + f"\n\nCURRENT DATE AND TIME: {current_datetime}"
        + f"\nTimezone: {timezone}"
        + "\n\nAlways use this date as 'today' when user says today/tomorrow/yesterday/next week etc. Never assume any other date."
    )

    # Save user message to Supabase immediately (before AI call)
    save_user_message(phone, user_message)

    # Load full conversation history from Supabase
    history = get_memory(phone)

    # ── Per-user OpenAI client ────────────────────────────────────────────────
    openai_key = client_data.get("openai_api_key") or os.getenv("OPENAI_API_KEY")
    ai_client  = OpenAI(api_key=openai_key)
    client_id  = client_data.get("id")

    total_tokens_used = 0
    total_cost_usd    = 0.0

    # First AI call
    response = ai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": dated_system_prompt}] + history,
        tools=TOOLS,
        tool_choice="auto"
    )

    # Track usage from first call
    tokens, cost = _calculate_cost(response.usage)
    total_tokens_used += tokens
    total_cost_usd    += cost

    reply_message = response.choices[0].message

    if reply_message.tool_calls:
        tool_results = []

        for tool_call in reply_message.tool_calls:
            fn_name = tool_call.function.name
            args    = json.loads(tool_call.function.arguments)
            result  = await execute_tool(fn_name, args, client_data, phone)
            tool_results.append({
                "tool_call_id": tool_call.id,
                "role":         "tool",
                "content":      str(result)
            })

        # Serialize the assistant message properly (not the raw OpenAI object)
        history.append({
            "role": "assistant",
            "content": reply_message.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                } for tc in reply_message.tool_calls
            ]
        })
        history.extend(tool_results)

        # Second AI call with tool results
        final_response = ai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": dated_system_prompt}] + history,
        )

        # Track usage from second call
        tokens2, cost2 = _calculate_cost(final_response.usage)
        total_tokens_used += tokens2
        total_cost_usd    += cost2

        final_text = final_response.choices[0].message.content
    else:
        final_text = reply_message.content

    # ── Persist usage stats ───────────────────────────────────────────────────
    if client_id and total_tokens_used > 0:
        from agent.database import increment_openai_usage
        increment_openai_usage(client_id, total_tokens_used, total_cost_usd)

    # ── Deduplication guard: skip if this exact reply was just sent ──
    last = _last_reply.get(phone)
    if last and last["text"] == final_text and (now.timestamp() - last["ts"]) < 10:
        print(f"[Dedup] Skipping duplicate reply to {phone}")
        return
    _last_reply[phone] = {"text": final_text, "ts": now.timestamp()}

    # Send WhatsApp reply using per-user credentials from Supabase
    await send_whatsapp_message(phone, final_text, client_data=client_data)

    # Save assistant reply to Supabase
    from agent.database import supabase as _supa
    try:
        _supa.table("conversations").insert({
            "wa_phone": phone,
            "role": "assistant",
            "content": final_text,
        }).execute()
        print(f"[Memory] Saved assistant reply for {phone}")
    except Exception as _me:
        print(f"[Memory] Failed to save assistant reply: {_me}")


async def execute_tool(name: str, args: dict, client_data: dict, phone: str):

    if name == "send_email":
        return await send_email(client_data=client_data, **args)

    elif name == "log_expense":
        result = await log_expense(client_data=client_data, **args)
        if args["balance"] <= 5000:
            alert_email = client_data.get("alert_email", os.getenv("ALERT_EMAIL", "you@gmail.com"))
            await send_email(
                to=alert_email,
                subject="Low Balance Alert",
                body=f"Your balance has dropped to Rs.{args['balance']}. Please add funds.",
                client_data=client_data
            )
        return result

    elif name == "create_calendar_event":
        return await create_event(client_data=client_data, **args)

    elif name == "get_calendar_events":
        from agent.tools.calendar import get_events
        return await get_events(client_data=client_data, **args)

    elif name == "get_emails":
        from agent.tools.gmail import get_emails
        return await get_emails(client_data=client_data, **args)

    elif name == "get_email_body":
        from agent.tools.gmail import get_email_body
        return await get_email_body(client_data=client_data, **args)

    elif name == "invite_bot_to_meeting":
        return await invite_bot_to_meeting(client_data=client_data, **args)

    elif name == "save_meeting_recording":
        from agent.tools.transcribe import transcribe_and_save
        from agent.database import get_pending_audio, clear_pending_audio

        media_id = get_pending_audio(phone)
        if not media_id:
            return "No voice recording found. Please send the voice note again."

        token = client_data.get("wa_token")
        meeting_name = args.get("meeting_name", "Meeting")

        result = await transcribe_and_save(
            media_id=media_id,
            token=token,
            meeting_name=meeting_name,
            wa_phone=phone,
            client_data=client_data
        )

        clear_pending_audio(phone)
        return result

    elif name == "get_meeting_summary":
        from agent.tools.transcribe import get_meeting_summary
        return await get_meeting_summary(wa_phone=phone, **args)

    elif name == "get_all_meetings":
        from agent.tools.transcribe import get_all_meetings
        return await get_all_meetings(wa_phone=phone)

    elif name == "get_meeting_transcripts":
        return await get_meeting_transcripts(client_data=client_data, **args)

    elif name == "get_transcript_detail":
        return await get_transcript_detail(client_data=client_data, **args)

    elif name == "search_web":
        return await search_web(**args)