# agent/brain.py
from openai import OpenAI
from agent.memory import get_memory, save_memory
from agent.tools.whatsapp import send_whatsapp_message
from agent.tools.gmail import send_email
from agent.tools.sheets import log_expense
from agent.tools.calendar import create_event
from dotenv import load_dotenv
import json
import os

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
    }
]

SYSTEM_PROMPT = """
You are a smart personal assistant accessible via WhatsApp. You can:
- Track expenses (detect credit/debit, amount, purpose, calculate running balance)
- Send emails via Gmail
- Create Google Calendar events
- Always reply to the user after completing any action.

Expense rules:
- Debit = subtract from balance
- Credit = add to balance
- If balance drops to 5000 or below, AUTOMATICALLY send a low balance alert email.
"""

async def run_agent(user_message: str, phone: str, client_data: dict):
    history = get_memory(phone)
    history.append({"role": "user", "content": user_message})

    # First AI call
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": SYSTEM_PROMPT}] + history,
        tools=TOOLS,
        tool_choice="auto"
    )

    reply_message = response.choices[0].message

    if reply_message.tool_calls:
        tool_results = []

        for tool_call in reply_message.tool_calls:
            fn_name = tool_call.function.name
            args    = json.loads(tool_call.function.arguments)
            result = await execute_tool(fn_name, args, client_data)
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
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + history,
        )
        final_text = final_response.choices[0].message.content
    else:
        final_text = reply_message.content

    # Send WhatsApp reply
    await send_whatsapp_message(phone, final_text)

    # Save memory (only serializable dicts)
    history.append({"role": "assistant", "content": final_text})
    save_memory(phone, history)


async def execute_tool(name: str, args: dict, client_data: dict):
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