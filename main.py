# main.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from agent.brain import run_agent
from agent.google_auth_flow import router as auth_router
from agent.setup_routes import router as setup_router
from agent.auth_middleware import router as login_router, is_authenticated
from agent.database import get_client_by_phone
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv
import traceback, os, uuid
import requests as req

load_dotenv()

app = FastAPI(title="Sterling AI Assistant")

# ── Message deduplication to prevent WhatsApp webhook retries from firing twice ─
_processed_message_ids: set = set()

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET", "sterling-secret-change-this")
)

# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(login_router)
app.include_router(auth_router)
app.include_router(setup_router)


# ── Root → redirect to login ───────────────────────────────────────────────────
@app.get("/")
async def root(request: Request):
    if is_authenticated(request):
        return RedirectResponse(url="/setup")
    return RedirectResponse(url="/login")


# ── Protect routes ─────────────────────────────────────────────────────────────
@app.middleware("http")
async def auth_guard(request: Request, call_next):
    protected = ["/setup", "/auth/google", "/auth/status"]
    path = request.url.path

    public = ["/login", "/register", "/verify-otp", "/logout", "/webhook", "/auth/callback", "/docs", "/openapi"]
    if any(path.startswith(p) for p in public):
        return await call_next(request)

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


# ── Receive WhatsApp messages ──────────────────────────────────────────────────
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
        message_id = message.get("id", "")

        # Deduplicate: WhatsApp sometimes delivers the same webhook event twice
        if message_id and message_id in _processed_message_ids:
            print(f"[Webhook] Duplicate message_id {message_id}, skipping.")
            return {"status": "duplicate"}
        if message_id:
            _processed_message_ids.add(message_id)
            # Keep the set from growing unbounded — trim oldest if too large
            if len(_processed_message_ids) > 500:
                _processed_message_ids.pop()

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
            token = client.get("wa_token")

            # Store media_id in database — ask for name first
            from agent.database import save_pending_audio
            save_pending_audio(sender_phone, media_id)

            user_message = (
                f"[Voice note received. Media ID saved.] "
                f"Ask the user what name to give this meeting recording."
            )
            await run_agent(user_message, sender_phone, client)

        else:
            return {"status": "ignored"}

    except Exception as e:
        print(f"[Webhook ERROR]\n{traceback.format_exc()}")
        return {"status": "error", "detail": str(e)}

    return {"status": "ok"}


# ── Helper: Get WhatsApp media URL ─────────────────────────────────────────────
async def get_whatsapp_media_url(media_id: str, token: str) -> str:
    response = req.get(
        f"https://graph.facebook.com/v18.0/{media_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10
    )
    return response.json().get("url", "")


# ── Helper: Download audio and store ───────────────────────────────────────────
async def download_and_store_audio(media_id: str, token: str) -> str:
    from agent.database import supabase
    import tempfile

    meta_response = req.get(
        f"https://graph.facebook.com/v18.0/{media_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10
    )
    if meta_response.status_code != 200:
        raise Exception(f"Failed to get media info from Meta: {meta_response.text}")

    media_url = meta_response.json().get("url", "")
    if not media_url:
        raise Exception(f"Could not get media URL from Meta response: {meta_response.json()}")

    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "Mozilla/5.0"
    }
    audio_response = req.get(media_url, headers=headers, timeout=30)

    if audio_response.status_code != 200:
        raise Exception(f"Failed to download audio: {audio_response.text}")

    filename = f"recording_{uuid.uuid4().hex}.ogg"

    with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as tmp_file:
        tmp_file.write(audio_response.content)
        tmp_file_path = tmp_file.name

    try:
        supabase.storage.from_("recordings").upload(
            filename,
            tmp_file_path,
            {"content-type": "audio/ogg"}
        )
    finally:
        if os.path.exists(tmp_file_path):
            os.remove(tmp_file_path)

    public_url = supabase.storage.from_("recordings").get_public_url(filename)
    print(f"[Audio] Uploaded: {public_url}")

    return public_url