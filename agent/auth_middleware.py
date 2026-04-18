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
<title>Sterling AI · The Ultimate AI Assistant</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600;700&family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet"/>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#0a0a0a;
  --surface:rgba(20,20,20,0.7);
  --border:rgba(212,175,55,0.2);
  --border-glow:rgba(212,175,55,0.5);
  --text:#ffffff;
  --text-muted:#a0a0a0;
  --gold:#d4af37;
  --gold-light:#f3e5ab;
  --gold-dark:#aa8c2c;
  --err:#ff4d4d;
  --err-bg:rgba(255,77,77,0.1);
}
body{
  background-color:var(--bg);
  background-image: 
    radial-gradient(circle at 15% 50%, rgba(212,175,55,0.08), transparent 25%),
    radial-gradient(circle at 85% 30%, rgba(212,175,55,0.06), transparent 25%);
  color:var(--text);
  font-family:'Plus Jakarta Sans',sans-serif;
  min-height:100vh;
  overflow-x:hidden;
}
.glass {
  background: var(--surface);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid var(--border);
  box-shadow: 0 8px 32px 0 rgba(0,0,0,0.3);
}

/* Navbar */
nav {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 24px 5%;
  position: fixed;
  top: 0;
  width: 100%;
  z-index: 100;
  background: rgba(10,10,10,0.8);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border);
}
.brand {
  font-family: 'Playfair Display', serif;
  font-size: 24px;
  font-weight: 700;
  color: var(--gold);
  display: flex;
  align-items: center;
  gap: 12px;
}
.logo-icon {
  width: 32px;
  height: 32px;
  background: linear-gradient(135deg, var(--gold), var(--gold-dark));
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #000;
  font-size: 18px;
}
.nav-links {
  display: flex;
  gap: 32px;
}
.nav-links a {
  color: var(--text-muted);
  text-decoration: none;
  font-size: 14px;
  font-weight: 500;
  transition: color 0.3s;
}
.nav-links a:hover {
  color: var(--gold-light);
}
.nav-btn {
  padding: 10px 24px;
  border-radius: 30px;
  background: transparent;
  color: var(--gold);
  border: 1px solid var(--gold);
  cursor: pointer;
  font-weight: 600;
  transition: all 0.3s;
}
.nav-btn:hover {
  background: var(--gold);
  color: #000;
  box-shadow: 0 0 15px var(--border-glow);
}

/* Main Layout */
.container {
  display: flex;
  flex-direction: column;
  padding: 120px 5% 60px;
  max-width: 1400px;
  margin: 0 auto;
}

/* Hero Section */
.hero {
  text-align: center;
  margin-bottom: 80px;
  animation: fadeIn 1s ease-out;
}
.hero h1 {
  font-family: 'Playfair Display', serif;
  font-size: 56px;
  margin-bottom: 24px;
  background: linear-gradient(to right, var(--gold-light), var(--gold), var(--gold-dark));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
.hero p {
  font-size: 18px;
  color: var(--text-muted);
  max-width: 600px;
  margin: 0 auto 40px;
  line-height: 1.6;
}

/* Split Content */
.split {
  display: flex;
  gap: 60px;
  align-items: flex-start;
}
@media (max-width: 900px) {
  .split {
    flex-direction: column;
  }
}

/* Features Info */
.info-section {
  flex: 1;
}
.section-title {
  font-family: 'Playfair Display', serif;
  font-size: 32px;
  color: var(--gold);
  margin-bottom: 32px;
}
.features-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 24px;
}
.feature-card {
  padding: 24px;
  border-radius: 16px;
  transition: transform 0.3s, box-shadow 0.3s;
}
.feature-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 10px 30px rgba(212,175,55,0.1);
  border-color: var(--gold);
}
.feature-icon {
  font-size: 24px;
  margin-bottom: 16px;
  color: var(--gold);
}
.feature-card h3 {
  font-size: 16px;
  margin-bottom: 8px;
  color: var(--text);
}
.feature-card p {
  font-size: 13px;
  color: var(--text-muted);
  line-height: 1.5;
}

/* Auth Panel */
.auth-section {
  width: 100%;
  max-width: 440px;
  border-radius: 24px;
  padding: 40px;
  position: relative;
  overflow: hidden;
  margin: 0 auto;
}
.auth-section::before {
  content: '';
  position: absolute;
  top: -50%;
  left: -50%;
  width: 200%;
  height: 200%;
  background: conic-gradient(transparent, transparent, transparent, var(--gold));
  animation: rotate 4s linear infinite;
  opacity: 0.1;
}
.auth-content {
  position: relative;
  z-index: 1;
}

.tabs {
  display: flex;
  background: rgba(0,0,0,0.3);
  border-radius: 12px;
  padding: 6px;
  margin-bottom: 32px;
  border: 1px solid rgba(255,255,255,0.05);
}
.tab {
  flex: 1;
  padding: 12px;
  text-align: center;
  font-size: 14px;
  font-weight: 600;
  border-radius: 8px;
  cursor: pointer;
  color: var(--text-muted);
  border: none;
  background: none;
  transition: all 0.3s;
}
.tab.active {
  background: var(--surface);
  color: var(--gold);
  box-shadow: 0 4px 12px rgba(0,0,0,0.2);
  border: 1px solid var(--border);
}

.form-group {
  margin-bottom: 20px;
}
label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: var(--text-muted);
  margin-bottom: 8px;
}
input {
  width: 100%;
  padding: 14px 16px;
  border: 1px solid var(--border);
  border-radius: 10px;
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-size: 14px;
  color: var(--text);
  background: rgba(0,0,0,0.2);
  outline: none;
  transition: all 0.3s;
}
input:focus {
  border-color: var(--gold);
  box-shadow: 0 0 0 2px rgba(212,175,55,0.2);
  background: rgba(0,0,0,0.4);
}
.btn-submit {
  width: 100%;
  padding: 16px;
  background: linear-gradient(135deg, var(--gold), var(--gold-dark));
  color: #000;
  border: none;
  border-radius: 10px;
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
  margin-top: 12px;
  transition: all 0.3s;
  text-transform: uppercase;
  letter-spacing: 1px;
}
.btn-submit:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(212,175,55,0.3);
}

.error {
  background: var(--err-bg);
  border: 1px solid rgba(255,77,77,0.3);
  color: var(--err);
  padding: 12px 16px;
  border-radius: 10px;
  font-size: 13px;
  margin-bottom: 24px;
  display: none;
}
.panel { display: none; animation: fadeIn 0.4s; }
.panel.active { display: block; }

@keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
@keyframes rotate { 100% { transform: rotate(360deg); } }

/* Decor elements */
.orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  z-index: -1;
}
.orb-1 { width: 300px; height: 300px; background: rgba(212,175,55,0.15); top: -100px; right: -100px; }
.orb-2 { width: 400px; height: 400px; background: rgba(212,175,55,0.1); bottom: -150px; left: -100px; }
</style>
</head>
<body>
<div class="orb orb-1"></div>
<div class="orb orb-2"></div>

<nav>
  <div class="brand">
    <div class="logo-icon">S</div>
    Sterling AI
  </div>
  <div class="nav-links">
    <a href="#features">Features</a>
  </div>
  <button class="nav-btn" onclick="document.getElementById('auth-card').scrollIntoView({behavior:'smooth'})">Get Started</button>
</nav>

<div class="container">
  <div class="hero">
    <h1>Your Ultimate Personal Assistant</h1>
    <p>Experience the epitome of AI orchestration. Connect your WhatsApp, Gmail, Calendar, and Sheets into a single, luxurious intelligence hub.</p>
  </div>

  <div class="split">
    <div class="info-section" id="features">
      <h2 class="section-title">A Symphony of Features</h2>
      <div class="features-grid">
        <div class="feature-card glass">
          <div class="feature-icon">💬</div>
          <h3>WhatsApp Control</h3>
          <p>Interact entirely via WhatsApp voice or text, anytime, anywhere.</p>
        </div>
        <div class="feature-card glass">
          <div class="feature-icon">📅</div>
          <h3>Smart Calendar</h3>
          <p>Seamlessly schedule and modify your Google Calendar events.</p>
        </div>
        <div class="feature-card glass">
          <div class="feature-icon">✉️</div>
          <h3>Email Management</h3>
          <p>Read, summarize, and draft Gmail responses intelligently.</p>
        </div>
        <div class="feature-card glass">
          <div class="feature-icon">📊</div>
          <h3>Sheets Automation</h3>
          <p>Log expenses, update records, and read directly from Google Sheets.</p>
        </div>
        <div class="feature-card glass">
          <div class="feature-icon">🎙️</div>
          <h3>Voice Intelligence</h3>
          <p>Transcribe and extract insights from your voice notes with ease.</p>
        </div>
        <div class="feature-card glass">
          <div class="feature-icon">🌐</div>
          <h3>Web Search</h3>
          <p>Access real-time information from the web instantly.</p>
        </div>
      </div>
    </div>

    <div class="auth-section glass" id="auth-card">
      <div class="auth-content">
        <div class="tabs">
          <button class="tab active" onclick="switchTab('login')">Sign In</button>
          <button class="tab" onclick="switchTab('register')">Create Account</button>
        </div>

        <div id="err" class="error"></div>

        <!-- Login -->
        <div class="panel active" id="panel-login">
          <form method="POST" action="/login">
            <div class="form-group">
              <label>Email Address</label>
              <input type="email" name="email" placeholder="you@example.com" required/>
            </div>
            <div class="form-group">
              <label>Password</label>
              <input type="password" name="password" placeholder="••••••••" required/>
            </div>
            <button class="btn-submit" type="submit">Access Dashboard</button>
          </form>
        </div>

        <!-- Register -->
        <div class="panel" id="panel-register">
          <form method="POST" action="/register">
            <div class="form-group">
              <label>Email Address</label>
              <input type="email" name="email" placeholder="you@example.com" required/>
            </div>
            <div class="form-group">
              <label>Create Password</label>
              <input type="password" name="password" placeholder="Choose a strong password" required/>
            </div>
            <button class="btn-submit" type="submit">Begin Your Journey</button>
          </form>
        </div>
      </div>
    </div>
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
    <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600;700&family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet"/>
    <style>
    *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
    :root{{
      --bg:#0a0a0a;
      --surface:rgba(20,20,20,0.7);
      --border:rgba(212,175,55,0.2);
      --text:#ffffff;
      --text-muted:#a0a0a0;
      --gold:#d4af37;
      --gold-dark:#aa8c2c;
      --err:#ff4d4d;
      --err-bg:rgba(255,77,77,0.1);
    }}
    body{{
      background-color:var(--bg);
      background-image: radial-gradient(circle at 50% 50%, rgba(212,175,55,0.05), transparent 50%);
      color:var(--text);
      font-family:'Plus Jakarta Sans',sans-serif;
      min-height:100vh;
      display:flex;align-items:center;justify-content:center;
    }}
    .glass {{
      background: var(--surface);
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      border: 1px solid var(--border);
      box-shadow: 0 8px 32px 0 rgba(0,0,0,0.3);
    }}
    .card {{
      border-radius: 24px;
      padding: 48px 40px;
      width: 100%;
      max-width: 440px;
      text-align: center;
      position: relative;
      overflow: hidden;
    }}
    .card::before {{
      content: '';
      position: absolute;
      top: -50%; left: -50%;
      width: 200%; height: 200%;
      background: conic-gradient(transparent, transparent, transparent, var(--gold));
      animation: rotate 4s linear infinite;
      opacity: 0.1;
      z-index: -1;
    }}
    @keyframes rotate {{ 100% {{ transform: rotate(360deg); }} }}
    .logo-icon {{
      width: 44px; height: 44px;
      background: linear-gradient(135deg, var(--gold), var(--gold-dark));
      border-radius: 12px;
      display: inline-flex; align-items: center; justify-content: center;
      color: #000; font-size: 20px; font-weight: 700;
      margin-bottom: 24px;
    }}
    h1 {{ font-family: 'Playfair Display', serif; font-size: 28px; color: var(--gold); margin-bottom: 12px; }}
    p.sub {{ color: var(--text-muted); font-size: 14px; margin-bottom: 32px; line-height: 1.6; }}
    strong {{ color: #fff; }}
    .form-group {{ margin-bottom: 24px; text-align: left; }}
    label {{ display: block; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; color: var(--text-muted); margin-bottom: 8px; }}
    input {{
      width: 100%; padding: 16px;
      border: 1px solid var(--border); border-radius: 10px;
      font-family: 'Plus Jakarta Sans', sans-serif; font-size: 24px; text-align: center;
      color: var(--text); background: rgba(0,0,0,0.2); outline: none; transition: all 0.3s; letter-spacing: 8px;
    }}
    input:focus {{ border-color: var(--gold); box-shadow: 0 0 0 2px rgba(212,175,55,0.2); background: rgba(0,0,0,0.4); }}
    .btn-submit {{
      width: 100%; padding: 16px;
      background: linear-gradient(135deg, var(--gold), var(--gold-dark));
      color: #000; border: none; border-radius: 10px;
      font-family: 'Plus Jakarta Sans', sans-serif; font-size: 15px; font-weight: 700;
      cursor: pointer; transition: all 0.3s; text-transform: uppercase; letter-spacing: 1px;
    }}
    .btn-submit:hover {{ transform: translateY(-2px); box-shadow: 0 8px 24px rgba(212,175,55,0.3); }}
    .error {{ background: var(--err-bg); border: 1px solid rgba(255,77,77,0.3); color: var(--err); padding: 12px 16px; border-radius: 10px; font-size: 13px; margin-bottom: 24px; display: none; text-align: left; }}
    </style>
    </head>
    <body>
    <div class="card glass">
      <div class="logo-icon">S</div>
      <h1>Verify Email</h1>
      <p class="sub">We sent a 6-digit code to <strong>{pending_email}</strong>.<br/>Enter it below to proceed.</p>
      <div id="err" class="error"></div>
      <form method="POST" action="/verify-otp">
        <div class="form-group">
          <label>Verification Code</label>
          <input type="text" name="otp" placeholder="······" maxlength="6" required autocomplete="one-time-code"/>
        </div>
        <button class="btn-submit" type="submit">Verify & Continue</button>
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