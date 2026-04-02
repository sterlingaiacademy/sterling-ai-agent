from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
import bcrypt
from agent.database import get_client_by_email, create_client_account

router = APIRouter()

def is_authenticated(request: Request) -> bool:
    return bool(request.session.get("client_email"))

@router.post("/login")
async def login(request: Request):
    form = await request.form()
    email = form.get("email")
    password = form.get("password")
    
    client = get_client_by_email(email)
    if not client:
        return HTMLResponse("Invalid email or password", status_code=401)
    
    if not bcrypt.checkpw(password.encode(), client["password_hash"].encode()):
        return HTMLResponse("Invalid email or password", status_code=401)
    
    request.session["client_email"] = email
    request.session["client_id"] = client["id"]
    return RedirectResponse("/setup", status_code=302)

@router.post("/register")
async def register(request: Request):
    form = await request.form()
    email = form.get("email")
    password = form.get("password")
    
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    client = create_client_account(email, hashed)
    
    request.session["client_email"] = email
    request.session["client_id"] = client["id"]
    return RedirectResponse("/setup", status_code=302)