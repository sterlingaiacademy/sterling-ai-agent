from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
import bcrypt
from agent.database import get_client_by_email, create_client_account
from agent.otp_service import generate_otp, send_otp_email, store_otp_data, verify_otp, clear_otp_data

router = APIRouter()

def is_authenticated(request: Request) -> bool:
    return bool(request.session.get("client_email"))

# ── Login page (GET) ──────────────────────────────────────────────────────────
@router.get("/login")
async def login_page():
    return HTMLResponse("""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Sterling AI · Login</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700&family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet"/>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#f4f1ec;--card:#ffffff;--border:#d4cec4;--text:#1a1714;
  --muted:#6b6358;--accent:#1a3a2a;--accent3:#2d5a3d;--accent-l:#e8f0eb;
  --err:#7a1f1f;--err-l:#fdf0f0;
}
body{background:var(--bg);font-family:'Plus Jakarta Sans',sans-serif;
  min-height:100vh;display:flex;align-items:center;justify-content:center;}
.card{background:var(--card);border:1px solid var(--border);border-radius:16px;
  padding:48px 40px;width:100%;max-width:420px;
  box-shadow:0 2px 8px rgba(26,23,20,.06),0 12px 40px rgba(26,23,20,.08);}
.logo{width:44px;height:44px;background:var(--accent);border-radius:10px;
  display:flex;align-items:center;justify-content:center;
  color:white;font-size:18px;font-weight:700;margin:0 auto 20px;}
h1{font-family:'Playfair Display',serif;font-size:28px;text-align:center;
  color:var(--text);margin-bottom:6px;}
.sub{text-align:center;color:var(--muted);font-size:13.5px;margin-bottom:32px;}
.tabs{display:flex;background:#f4f1ec;border-radius:8px;padding:4px;margin-bottom:28px;}
.tab{flex:1;padding:8px;text-align:center;font-size:13px;font-weight:600;
  border-radius:6px;cursor:pointer;color:var(--muted);border:none;background:none;transition:all .2s;}
.tab.active{background:var(--card);color:var(--accent);
  box-shadow:0 1px 4px rgba(26,23,20,.1);}
.form-group{margin-bottom:16px;}
label{display:block;font-size:12px;font-weight:700;text-transform:uppercase;
  letter-spacing:1px;color:var(--accent);margin-bottom:6px;}
input{width:100%;padding:11px 14px;border:1.5px solid var(--border);border-radius:8px;
  font-family:'Plus Jakarta Sans',sans-serif;font-size:14px;color:var(--text);
  background:var(--bg);outline:none;transition:border-color .2s;}
input:focus{border-color:var(--accent);background:white;}
.btn{width:100%;padding:13px;background:var(--accent);color:white;border:none;
  border-radius:8px;font-family:'Plus Jakarta Sans',sans-serif;
  font-size:14px;font-weight:700;cursor:pointer;margin-top:8px;transition:all .2s;}
.btn:hover{background:#0f2a1c;}
.error{background:var(--err-l);border:1px solid rgba(122,31,31,.2);color:var(--err);
  padding:10px 14px;border-radius:8px;font-size:13px;margin-bottom:16px;display:none;}
.panel{display:none;} .panel.active{display:block;}
</style>
</head>
<body>
<div class="card">
  <div class="logo">S</div>
  <h1>Sterling AI</h1>
  <p class="sub">Your intelligent WhatsApp assistant</p>

  <div class="tabs">
    <button class="tab active" onclick="switchTab('login')">Sign In</button>
    <button class="tab" onclick="switchTab('register')">Create Account</button>
  </div>

  <div id="err" class="error"></div>

  <!-- Login -->
  <div class="panel active" id="panel-login">
    <form method="POST" action="/login">
      <div class="form-group">
        <label>Email</label>
        <input type="email" name="email" placeholder="you@example.com" required/>
      </div>
      <div class="form-group">
        <label>Password</label>
        <input type="password" name="password" placeholder="••••••••" required/>
      </div>
      <button class="btn" type="submit">Sign In →</button>
    </form>
  </div>

  <!-- Register -->
  <div class="panel" id="panel-register">
    <form method="POST" action="/register">
      <div class="form-group">
        <label>Email</label>
        <input type="email" name="email" placeholder="you@example.com" required/>
      </div>
      <div class="form-group">
        <label>Password</label>
        <input type="password" name="password" placeholder="Choose a strong password" required/>
      </div>
      <button class="btn" type="submit">Create Account →</button>
    </form>
  </div>
</div>
<script>
  function switchTab(t){
    document.querySelectorAll('.tab').forEach(el=>el.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(el=>el.classList.remove('active'));
    document.getElementById('panel-'+t).classList.add('active');
    event.target.classList.add('active');
  }
  const err = new URLSearchParams(window.location.search).get('error');
  if(err){ const el=document.getElementById('err'); el.textContent=err; el.style.display='block'; }
</script>
</body>
</html>
""")

# ── Login POST ────────────────────────────────────────────────────────────────
@router.post("/login")
async def login(request: Request):
    form = await request.form()
    email = form.get("email")
    password = form.get("password")

    client = get_client_by_email(email)
    if not client:
        return RedirectResponse("/login?error=Invalid+email+or+password", status_code=302)

    if not bcrypt.checkpw(password.encode(), client["password_hash"].encode()):
        return RedirectResponse("/login?error=Invalid+email+or+password", status_code=302)

    request.session["client_email"] = email
    request.session["client_id"] = client["id"]
    return RedirectResponse("/setup", status_code=302)

# ── Register POST ─────────────────────────────────────────────────────────────
@router.post("/register")
async def register(request: Request):
    form = await request.form()
    email    = form.get("email")
    password = form.get("password")

    existing = get_client_by_email(email)
    if existing:
        return RedirectResponse("/login?error=Account+already+exists,+please+sign+in", status_code=302)

    # Generate OTP and email it
    otp = generate_otp()
    sent = send_otp_email(email, otp)

    if not sent:
        return RedirectResponse("/login?error=Failed+to+send+verification+email.+Please+try+again.", status_code=302)

    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    store_otp_data(email, otp, hashed)

    request.session["pending_email"] = email
    return RedirectResponse("/verify-otp", status_code=302)

# ── OTP Verification page (GET) ───────────────────────────────────────────────
@router.get("/verify-otp")
async def verify_otp_page(request: Request):
    pending_email = request.session.get("pending_email", "")
    if not pending_email:
        return RedirectResponse("/login", status_code=302)

    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
    <meta charset="UTF-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
    <title>Verify Email · Sterling AI</title>
    <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700&family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet"/>
    <style>
    *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
    :root{{
      --bg:#f4f1ec;--card:#ffffff;--border:#d4cec4;--text:#1a1714;
      --muted:#6b6358;--accent:#1a3a2a;--err:#7a1f1f;--err-l:#fdf0f0;
    }}
    body{{background:var(--bg);font-family:'Plus Jakarta Sans',sans-serif;
      min-height:100vh;display:flex;align-items:center;justify-content:center;}}
    .card{{background:var(--card);border:1px solid var(--border);border-radius:16px;
      padding:48px 40px;width:100%;max-width:420px;
      box-shadow:0 2px 8px rgba(26,23,20,.06),0 12px 40px rgba(26,23,20,.08);text-align:center;}}
    .logo{{width:44px;height:44px;background:var(--accent);border-radius:10px;
      display:inline-flex;align-items:center;justify-content:center;
      color:white;font-size:18px;font-weight:700;margin-bottom:20px;}}
    h1{{font-family:'Playfair Display',serif;font-size:24px;color:var(--text);margin-bottom:8px;}}
    p.sub{{color:var(--muted);font-size:14px;margin-bottom:24px;line-height:1.5;}}
    strong{{color:var(--text);}}
    .form-group{{margin-bottom:16px;text-align:left;}}
    label{{display:block;font-size:12px;font-weight:700;text-transform:uppercase;
      letter-spacing:1px;color:var(--accent);margin-bottom:6px;}}
    input{{width:100%;padding:11px 14px;border:1.5px solid var(--border);border-radius:8px;
      font-family:'Plus Jakarta Sans',sans-serif;font-size:24px;text-align:center;
      color:var(--text);background:var(--bg);outline:none;transition:border-color .2s;letter-spacing:8px;}}
    input:focus{{border-color:var(--accent);background:white;}}
    .btn{{width:100%;padding:13px;background:var(--accent);color:white;border:none;
      border-radius:8px;font-family:'Plus Jakarta Sans',sans-serif;
      font-size:14px;font-weight:700;cursor:pointer;margin-top:8px;transition:all .2s;}}
    .btn:hover{{background:#0f2a1c;}}
    .error{{background:var(--err-l);border:1px solid rgba(122,31,31,.2);color:var(--err);
      padding:10px 14px;border-radius:8px;font-size:13px;margin-bottom:16px;display:none;text-align:left;}}
    </style>
    </head>
    <body>
    <div class="card">
      <div class="logo">S</div>
      <h1>Check your email</h1>
      <p class="sub">We sent a 6-digit code to <strong>{pending_email}</strong>.<br/>Enter it below to complete registration.</p>

      <div id="err" class="error"></div>

      <form method="POST" action="/verify-otp">
        <div class="form-group">
          <label>Verification Code</label>
          <input type="text" name="otp" placeholder="······" maxlength="6" required autocomplete="one-time-code"/>
        </div>
        <button class="btn" type="submit">Verify & Continue →</button>
      </form>
    </div>
    <script>
      const err = new URLSearchParams(window.location.search).get('error');
      if(err){{ const el=document.getElementById('err'); el.textContent=err; el.style.display='block'; }}
    </script>
    </body>
    </html>
    """)

# ── OTP Verification POST ─────────────────────────────────────────────────────
@router.post("/verify-otp")
async def verify_otp_post(request: Request):
    form        = await request.form()
    otp_attempt = form.get("otp", "").strip()
    pending_email = request.session.get("pending_email")

    if not pending_email:
        return RedirectResponse("/login?error=Session+expired.+Please+register+again.", status_code=302)

    record = verify_otp(pending_email, otp_attempt)
    if not record:
        return RedirectResponse("/verify-otp?error=Invalid+or+expired+code", status_code=302)

    # Create the account
    client = create_client_account(pending_email, record["password_hash"])
    clear_otp_data(pending_email)

    request.session.pop("pending_email", None)
    request.session["client_email"] = pending_email
    request.session["client_id"]    = client["id"]

    return RedirectResponse("/setup", status_code=302)

# ── Logout ────────────────────────────────────────────────────────────────────
@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=302)