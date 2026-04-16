# agent/brain.py
from openai import OpenAI
from agent.tools.whatsapp import send_whatsapp_message
from agent.tools.gmail import send_email
from agent.tools.sheets import log_expense
from agent.tools.calendar import create_event
from dotenv import load_dotenv
from agent.memory import get_memory, save_memory, save_user_message
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

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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
        "description": "Send Fireflies AI bot to join and record a Google Meet, Zoom or Teams meeting link",
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
        "description": "Get list of recent meeting transcripts and summaries from Fireflies",
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
        "description": "Get full details and transcript of a specific meeting by its title",
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
        "description": "Transcribe and save a voice note meeting recording. Use when user provides a name for their voice recording.",
        "parameters": {
            "type": "object",
            "properties": {
                "meeting_name": {"type": "string", "description": "Name to save this meeting as"}
            },
            "required": ["meeting_name"]
        }
    }
},
{
    "type": "function",
    "function": {
        "name": "get_meeting_summary",
        "description": "Get summary and action items of a saved meeting",
        "parameters": {
            "type": "object",
            "properties": {
                "meeting_name": {"type": "string", "description": "Name or keyword of the meeting"}
            },
            "required": ["meeting_name"]
        }
    }
},
{
    "type": "function",
    "function": {
        "name": "get_all_meetings",
        "description": "Get list of all saved meeting recordings",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    }
},
]

SYSTEM_PROMPT = """
You are a smart personal assistant accessible via WhatsApp. You can:
- Track expenses (detect credit/debit, amount, purpose, calculate running balance)
- Send emails via Gmail
- Read and summarize Gmail emails
- Create Google Calendar events
- View calendar events and detect conflicts
- Join meetings via Fireflies bot (when user shares a meeting link)
- Upload voice recordings to Fireflies for transcription
- Retrieve and summarize meeting notes from Fireflies

Meeting rules:
- When user shares a Google Meet/Zoom/Teams link, ask for meeting name then invite the bot
- When user sends a voice note, ask for the meeting name before uploading to Fireflies
- When asked about a meeting, fetch from Fireflies and summarize clearly

Meeting recording rules:
- When user sends a voice note, ask what name to give the meeting
- When user provides the name, call save_meeting_recording
- The recording will be transcribed and summarized automatically
- When user asks about a meeting, use get_meeting_summary
- When user asks to list meetings, use get_all_meetings


Expense rules:
- Debit = subtract from balance
- Credit = add to balance  
- If balance drops to 5000 or below, AUTOMATICALLY send a low balance alert email

"""
async def run_agent(user_message: str, phone: str, client_data: dict):
    # Get current date and time in client's timezone
    timezone = client_data.get("timezone") or "Asia/Kolkata"
    tz = pytz.timezone(timezone)
    now = datetime.now(tz)
    current_datetime = now.strftime("%A, %d %B %Y %I:%M %p")  
    # Example: "Monday, 14 April 2026 10:42 AM"

    # Inject date into system prompt
    dated_system_prompt = SYSTEM_PROMPT + f"\n\nCURRENT DATE AND TIME: {current_datetime}\nTimezone: {timezone}\n\nAlways use this date as 'today' when user says today/tomorrow/yesterday/next week etc. Never assume any other date."

    history = get_memory(phone)
    history.append({"role": "user", "content": user_message})

    # First AI call
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": dated_system_prompt}] + history,
        tools=TOOLS,
        tool_choice="auto"
    )


    reply_message = response.choices[0].message

    if reply_message.tool_calls:
        tool_results = []

        for tool_call in reply_message.tool_calls:
            fn_name = tool_call.function.name
            args    = json.loads(tool_call.function.arguments)
            result = await execute_tool(fn_name, args, client_data, phone)
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
        final_response = client.chat.completions.create(
            model="gpt-4o",
             messages=[{"role": "system", "content": dated_system_prompt}] + history,
        )
        final_text = final_response.choices[0].message.content
    else:
        final_text = reply_message.content

    # Send WhatsApp reply using per-user credentials from Supabase
    await send_whatsapp_message(phone, final_text, client_data=client_data)

    # Save memory (only serializable dicts)
    history.append({"role": "assistant", "content": final_text})
    save_memory(phone, history)



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
            wa_phone=phone
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