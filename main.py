# main.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from agent.brain import run_agent
from agent.google_auth_flow import router as auth_router
from agent.setup_routes import router as setup_router
from agent.auth_middleware import router as login_router, is_authenticated
from dotenv import load_dotenv
import traceback, os
from agent.database import get_client_by_phone
from starlette.middleware.sessions import SessionMiddleware

load_dotenv()

app = FastAPI(title="Sterling AI Assistant")
from starlette.middleware.sessions import SessionMiddleware

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET", "sterling-secret-change-this")
)

# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(login_router)   # /login  /logout
app.include_router(auth_router)    # /auth/google  /auth/callback  /auth/status
app.include_router(setup_router)   # /setup  /setup/verify  /setup/whatsapp


# ── Root → redirect to login ───────────────────────────────────────────────────
@app.get("/")
async def root(request: Request):
    if is_authenticated(request):
        return RedirectResponse(url="/setup")
    return RedirectResponse(url="/login")


# ── Protect /setup and /auth routes ───────────────────────────────────────────
@app.middleware("http")
async def auth_guard(request: Request, call_next):
    protected = ["/setup", "/auth/google", "/auth/status"]
    path = request.url.path

    # Allow: login page, logout, webhook, static
    public = ["/login", "/logout", "/webhook", "/auth/callback", "/docs", "/openapi"]
    if any(path.startswith(p) for p in public):
        return await call_next(request)

    # Protect setup and auth routes
    if any(path.startswith(p) for p in protected):
        if not is_authenticated(request):
            return RedirectResponse(url="/login", status_code=302)

    return await call_next(request)


# ── WhatsApp webhook verification ─────────────────────────────────────────────
@app.get("/webhook/whatsapp")
async def verify_webhook(request: Request):
    params = dict(request.query_params)
    if params.get("hub.verify_token") == os.getenv("WA_VERIFY_TOKEN", "my_verify_token"):
        return int(params["hub.challenge"])
    return JSONResponse({"error": "Invalid token"}, status_code=403)


# # ── Receive WhatsApp messages ──────────────────────────────────────────────────
# @app.post("/webhook/whatsapp")
# async def whatsapp_webhook(request: Request):
#     data = await request.json()
#     print(f"[Webhook] Received: {data}")

#     try:
#         entry = data["entry"][0]["changes"][0]["value"]
#         if "messages" not in entry:
#             return {"status": "no_message"}

#         message = entry["messages"][0]
#         if message.get("type") != "text":
#             return {"status": "ignored"}

#         user_message = message["text"]["body"]
#         sender_phone = message["from"]

#         print(f"[Webhook] Message from {sender_phone}: {user_message}")
#         client = get_client_by_phone(sender_phone)
#         if not client:                           # ✅ 8 spaces
#             print(f"[Webhook] Unknown phone: {sender_phone}")  # ✅ 12 spaces
#             return {"status": "unknown_client"}  # ✅ 12 spaces
#         await run_agent(user_message, sender_phone, client)    # ✅ 8 spaces
#         print(f"[Webhook] Agent finished for {sender_phone}")

#     except Exception as e:
#         print(f"[Webhook ERROR]\n{traceback.format_exc()}")
#         return {"status": "error", "detail": str(e)}

#     return {"status": "ok"}

# app.add_middleware(
#     SessionMiddleware,
#     secret_key=os.getenv("SESSION_SECRET", "change-this-secret")
# )
@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    data = await request.json()
    print(f"[Webhook] Received: {data}")

    try:
        entry = data["entry"][0]["changes"][0]["value"]
        if "messages" not in entry:
            return {"status": "no_message"}

        message = entry["messages"][0]
        sender_phone = message["from"]

        client = get_client_by_phone(sender_phone)
        if not client:
            print(f"[Webhook] Unknown phone: {sender_phone}")
            return {"status": "unknown_client"}

        msg_type = message.get("type")

        # ── Text message ──
        if msg_type == "text":
            user_message = message["text"]["body"]
            print(f"[Webhook] Message from {sender_phone}: {user_message}")
            await run_agent(user_message, sender_phone, client)

        # ── Audio/Voice note ──
        elif msg_type == "audio":
            media_id = message["audio"]["id"]
            # Get audio URL from Meta
            token = client.get("wa_token")
            media_url = await get_whatsapp_media_url(media_id, token)
            # Tell agent about it
            user_message = f"[Voice note received. Audio URL: {media_url}] Please ask the user what name to give this recording before uploading to Fireflies."
            await run_agent(user_message, sender_phone, client)

        else:
            return {"status": "ignored"}

    except Exception as e:
        print(f"[Webhook ERROR]\n{traceback.format_exc()}")
        return {"status": "error", "detail": str(e)}

    return {"status": "ok"}


async def get_whatsapp_media_url(media_id: str, token: str) -> str:
    """Get the download URL for a WhatsApp media file."""
    import requests as req
    response = req.get(
        f"https://graph.facebook.com/v18.0/{media_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10
    )
    return response.json().get("url", "")