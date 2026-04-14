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

    public = ["/login", "/logout", "/webhook", "/auth/callback", "/docs", "/openapi"]
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

            try:
                public_audio_url = await download_and_store_audio(media_id, token)

                # ✅ Save URL to database so next message can use it
                from agent.database import save_pending_audio
                save_pending_audio(sender_phone, public_audio_url)

                user_message = (
                    f"[Voice recording received and stored at: {public_audio_url}] "
                    f"Ask the user what name to save this recording as in Fireflies."
                )

            except Exception as e:
                import traceback
                print(f"[Webhook ERROR in Audio Download]\n{traceback.format_exc()}")
                user_message = (
                    f"[Voice recording failed: {str(e)}] "
                    f"Tell the user there was an issue."
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


# ── Helper: Download audio and store in Supabase ───────────────────────────────
async def download_and_store_audio(media_id: str, token: str) -> str:
    from agent.database import supabase
    import tempfile

    # Step 1: Get media URL from Meta
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

    # Step 2: Download the actual audio file
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    audio_response = req.get(media_url, headers=headers, timeout=30)
    
    if audio_response.status_code != 200:
        raise Exception(f"Failed to download audio. Status: {audio_response.status_code}, Response: {audio_response.text}")

    # Step 3: Save to a temporary file locally before upload
    # Supabase python client robustly handles local file paths via string.
    filename = f"recording_{uuid.uuid4().hex}.ogg"
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as tmp_file:
        tmp_file.write(audio_response.content)
        tmp_file_path = tmp_file.name

    try:
        # Step 4: Upload to Supabase Storage
        supabase.storage.from_("recordings").upload(
            filename,
            tmp_file_path,
            {"content-type": "audio/ogg"}
        )
    finally:
        # Step 5: Clean up temporary file
        if os.path.exists(tmp_file_path):
            os.remove(tmp_file_path)

    # Step 6: Get public URL
    public_url = supabase.storage.from_("recordings").get_public_url(filename)
    return public_url