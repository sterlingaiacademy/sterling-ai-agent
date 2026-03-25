# agent/auth_middleware.py
from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
import os, hashlib, secrets

router = APIRouter()

# ── Credentials (change these!) ───────────────────────────────────────────────
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "sterlingai")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "sterling@2024")

# Session store (in-memory — fine for single user)
_sessions: set = set()


def hash_password(pwd: str) -> str:
    return hashlib.sha256(pwd.encode()).hexdigest()


def is_authenticated(request: Request) -> bool:
    token = request.cookies.get("sa_session")
    return token in _sessions


def login_required(request: Request):
    """Call this in routes to check auth."""
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=302)
    return None


# ── Login page ─────────────────────────────────────────────────────────────────
@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = ""):
    if is_authenticated(request):
        return RedirectResponse(url="/setup")
    return HTMLResponse(_login_html(error=""))


@router.post("/login")
async def do_login(request: Request):
    form = await request.form()
    username = form.get("username", "").strip()
    password = form.get("password", "").strip()

    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        token = secrets.token_urlsafe(32)
        _sessions.add(token)
        response = RedirectResponse(url="/setup", status_code=302)
        response.set_cookie(
            "sa_session", token,
            max_age=86400 * 7,   # 7 days
            httponly=True,
            samesite="lax"
        )
        return response

    return HTMLResponse(_login_html(error="Incorrect username or password."))


@router.get("/logout")
async def logout(request: Request):
    token = request.cookies.get("sa_session")
    if token in _sessions:
        _sessions.discard(token)
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("sa_session")
    return response


# ── Login HTML ─────────────────────────────────────────────────────────────────
def _login_html(error: str = "") -> str:
    err_html = f"""
    <div class="error-box">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
      {error}
    </div>""" if error else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Sterling AI · Sign In</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,600;0,700;1,600&family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet"/>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{
  --bg:#f4f1ec;--card:#ffffff;--border:#d4cec4;--border2:#b8b0a4;
  --text:#1a1714;--text2:#3d3830;--muted:#6b6358;--faint:#9e9690;
  --accent:#1a3a2a;--accent2:#b8860b;--accent3:#2d5a3d;--accent-l:#e8f0eb;
  --err:#7a1f1f;--err-l:#fdf0f0;
}}
body{{
  background:var(--bg);
  font-family:'Plus Jakarta Sans',sans-serif;
  min-height:100vh;
  display:flex;align-items:center;justify-content:center;
  padding:20px;
}}
body::before{{
  content:'';position:fixed;inset:0;
  background:radial-gradient(circle at 25% 25%,rgba(26,58,42,.06) 0%,transparent 50%),
             radial-gradient(circle at 75% 75%,rgba(184,134,11,.05) 0%,transparent 50%);
  pointer-events:none;
}}
.wrap{{
  width:100%;max-width:440px;
  animation:rise .6s cubic-bezier(.16,1,.3,1) both;
}}
/* Brand */
.brand{{
  text-align:center;margin-bottom:40px;
}}
.brand-logo{{
  display:inline-flex;align-items:center;justify-content:center;
  width:56px;height:56px;
  background:var(--accent);border-radius:16px;
  color:white;font-size:24px;font-weight:800;
  margin-bottom:16px;
  box-shadow:0 8px 24px rgba(26,58,42,.25);
}}
.brand h1{{
  font-family:'Playfair Display',serif;
  font-size:28px;font-weight:700;color:var(--text);
  letter-spacing:-.3px;margin-bottom:4px;
}}
.brand p{{font-size:13px;color:var(--muted);font-weight:400;}}
/* Card */
.card{{
  background:var(--card);
  border:1px solid var(--border);
  border-radius:16px;
  box-shadow:0 2px 8px rgba(26,23,20,.06),0 16px 48px rgba(26,23,20,.1);
  overflow:hidden;
}}
.card-top{{height:3px;background:linear-gradient(90deg,var(--accent),var(--accent2));}}
.card-body{{padding:40px;}}
.card-body h2{{
  font-family:'Playfair Display',serif;
  font-size:24px;font-weight:600;color:var(--text);
  margin-bottom:4px;
}}
.card-body .sub{{
  font-size:13px;color:var(--muted);margin-bottom:28px;
}}
/* Error */
.error-box{{
  display:flex;align-items:center;gap:8px;
  background:var(--err-l);border:1px solid rgba(122,31,31,.2);
  color:var(--err);border-radius:8px;padding:11px 14px;
  font-size:13px;font-weight:500;margin-bottom:20px;
}}
/* Fields */
.field{{margin-bottom:18px;}}
.field label{{
  display:block;font-size:11px;font-weight:700;
  text-transform:uppercase;letter-spacing:1.2px;
  color:var(--accent);margin-bottom:8px;
}}
.field-wrap{{position:relative;}}
.field input{{
  width:100%;
  background:var(--bg);
  border:1.5px solid var(--border);
  border-radius:10px;
  padding:13px 16px;
  font-family:'Plus Jakarta Sans',sans-serif;
  font-size:14px;font-weight:500;color:var(--text);
  outline:none;transition:all .2s;
}}
.field input:focus{{
  border-color:var(--accent);
  background:white;
  box-shadow:0 0 0 3px rgba(26,58,42,.08);
}}
.field input::placeholder{{color:var(--faint);font-weight:400;}}
.toggle-pw{{
  position:absolute;right:14px;top:50%;transform:translateY(-50%);
  background:none;border:none;cursor:pointer;color:var(--faint);
  font-size:16px;padding:4px;transition:color .2s;
}}
.toggle-pw:hover{{color:var(--muted);}}
/* Button */
.btn-login{{
  width:100%;padding:14px;border-radius:10px;border:none;
  background:var(--accent);color:white;
  font-family:'Plus Jakarta Sans',sans-serif;
  font-size:14px;font-weight:700;letter-spacing:.3px;
  cursor:pointer;transition:all .2s;margin-top:8px;
  display:flex;align-items:center;justify-content:center;gap:8px;
}}
.btn-login:hover{{background:#0f2a1c;box-shadow:0 4px 16px rgba(26,58,42,.3);transform:translateY(-1px);}}
.btn-login:active{{transform:translateY(0);}}
/* Footer */
.card-footer{{
  padding:16px 40px;
  border-top:1px solid var(--border);
  background:var(--bg);
  text-align:center;
  font-size:12px;color:var(--faint);
}}
.footer-note{{
  text-align:center;margin-top:20px;
  font-size:12px;color:var(--faint);
}}
@keyframes rise{{from{{opacity:0;transform:translateY(20px)}}to{{opacity:1;transform:translateY(0)}}}}
</style>
</head>
<body>
<div class="wrap">

  <div class="brand">
    <div class="brand-logo">S</div>
    <h1>Sterling AI Assistant</h1>
    <p>Intelligent WhatsApp Automation</p>
  </div>

  <div class="card">
    <div class="card-top"></div>
    <div class="card-body">
      <h2>Welcome back</h2>
      <p class="sub">Sign in to access your agent dashboard</p>

      {err_html}

      <form method="POST" action="/login">
        <div class="field">
          <label>Username</label>
          <input
            type="text"
            name="username"
            placeholder="Enter your username"
            autocomplete="username"
            required
          />
        </div>

        <div class="field">
          <label>Password</label>
          <div class="field-wrap">
            <input
              type="password"
              name="password"
              id="pw-field"
              placeholder="Enter your password"
              autocomplete="current-password"
              required
            />
            <button type="button" class="toggle-pw" onclick="togglePw()" title="Show/hide password">
              <span id="pw-eye">👁</span>
            </button>
          </div>
        </div>

        <button type="submit" class="btn-login">
          Sign In &rarr;
        </button>
      </form>
    </div>
    <div class="card-footer">
      Your credentials are stored securely on the server
    </div>
  </div>

  <div class="footer-note">
    Sterling AI Assistant &nbsp;·&nbsp; Powered by OpenAI &amp; WhatsApp Cloud API
  </div>

</div>
<script>
function togglePw() {{
  const f = document.getElementById('pw-field');
  const e = document.getElementById('pw-eye');
  if (f.type === 'password') {{
    f.type = 'text'; e.textContent = '🙈';
  }} else {{
    f.type = 'password'; e.textContent = '👁';
  }}
}}
</script>
</body>
</html>"""
