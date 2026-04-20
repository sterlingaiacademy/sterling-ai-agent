import os
import random
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# In-memory OTP store keyed by email
# { "user@email.com": { "otp": "123456", "password_hash": "...", "expires_at": 1234 } }
_otp_store: dict = {}


def generate_otp() -> str:
    """Generate a 6-digit OTP."""
    return str(random.randint(100000, 999999))


def send_otp_email(email: str, otp: str, subject: str = "Your Sterling AI verification code") -> bool:
    """Send a 6-digit OTP to the user's email via Gmail SMTP."""
    smtp_email    = os.getenv("SMTP_EMAIL")
    smtp_password = os.getenv("SMTP_PASSWORD")

    if not smtp_email or not smtp_password:
        print("[OTPService] ERROR: SMTP_EMAIL or SMTP_PASSWORD not set.")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"Sterling AI <{smtp_email}>"
        msg["To"]      = email

        html = f"""
        <div style="font-family:'Plus Jakarta Sans',Arial,sans-serif;max-width:480px;
                    margin:0 auto;background:#f4f1ec;padding:40px 20px;">
          <div style="background:#fff;border-radius:16px;padding:40px;
                      box-shadow:0 4px 24px rgba(0,0,0,.08);text-align:center;">
            <div style="width:48px;height:48px;background:#1a3a2a;border-radius:10px;
                        display:inline-flex;align-items:center;justify-content:center;
                        color:#fff;font-size:22px;font-weight:700;margin-bottom:20px;">S</div>
            <h2 style="font-size:22px;color:#1a1714;margin:0 0 8px;">
              Verify your email
            </h2>
            <p style="color:#6b6358;font-size:14px;margin:0 0 32px;">
              Use the code below to complete your Sterling AI registration.
              It expires in <strong>10 minutes</strong>.
            </p>
            <div style="background:#f4f1ec;border-radius:12px;padding:24px;
                        font-size:36px;font-weight:700;letter-spacing:12px;
                        color:#1a3a2a;margin-bottom:32px;">
              {otp}
            </div>
            <p style="color:#6b6358;font-size:12px;margin:0;">
              If you didn't request this, you can safely ignore this email.
            </p>
          </div>
        </div>
        """

        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_email, smtp_password)
            server.sendmail(smtp_email, email, msg.as_string())

        print(f"[OTPService] OTP sent to {email}")
        return True

    except Exception as e:
        print(f"[OTPService] Email send error: {e}")
        return False


def store_otp_data(email: str, otp: str, password_hash: str):
    """Store OTP + password hash temporarily for 10 minutes."""
    _otp_store[email] = {
        "otp":           otp,
        "password_hash": password_hash,
        "expires_at":    time.time() + 600
    }


def verify_otp(email: str, otp_attempt: str) -> dict | None:
    """Verify OTP. Returns stored record if correct, None if invalid/expired."""
    record = _otp_store.get(email)
    if not record:
        return None
    if time.time() > record["expires_at"]:
        del _otp_store[email]
        return None
    if record["otp"] == otp_attempt:
        return record
    return None


def clear_otp_data(email: str):
    """Remove OTP record after successful registration."""
    _otp_store.pop(email, None)
