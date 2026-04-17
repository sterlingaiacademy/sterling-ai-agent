import os
import random
import time
import httpx

# In-memory store for OTPs. 
# Format: { "mobile_number": {"otp": "123456", "expires_at": 1690000000, "email": "...", "password": "..."} }
# Note: In production with multiple workers, use Redis or DB instead.
_otp_store = {}

def generate_otp() -> str:
    """Generate a 6-digit OTP."""
    return str(random.randint(100000, 999999))

async def send_otp_fast2sms(mobile_number: str, otp: str) -> bool:
    """
    Send an OTP via Fast2SMS DLT route or standard routing.
    Note: 'variables_values' is the standard way to pass OTP in Fast2SMS V3 API.
    """
    api_key = os.getenv("FAST2SMS_API_KEY")
    if not api_key:
        print("[OTPService] ERROR: FAST2SMS_API_KEY is not set.")
        return False
        
    url = "https://www.fast2sms.com/dev/bulkV2"
    
    # Clean the mobile number. Fast2SMS expects a 10-digit number without country code
    # if sending to India directly via Quick transactional route.
    clean_number = mobile_number.replace("+91", "").replace("-", "").replace(" ", "").strip()
    if len(clean_number) > 10 and clean_number.startswith("91"):
        clean_number = clean_number[2:]

    payload = {
        "route": "otp",
        "variables_values": otp,
        "numbers": clean_number
    }
    
    headers = {
        "authorization": api_key,
        "Content-Type": "application/x-www-form-urlencoded"
    }

    print(f"[OTPService] Sending OTP {otp} to {clean_number} via Fast2SMS...")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, data=payload, headers=headers)
            data = response.json()
            if data.get("return") == True:
                print("[OTPService] OTP sent successfully.")
                return True
            else:
                print(f"[OTPService] Fast2SMS Error: {data}")
                return False
    except Exception as e:
        print(f"[OTPService] Exception while sending OTP: {str(e)}")
        return False

def store_otp_data(mobile_number: str, otp: str, email: str, password_hash: str):
    """Store the OTP and pending user details temporarily for 10 minutes."""
    _otp_store[mobile_number] = {
        "otp": otp,
        "email": email,
        "password_hash": password_hash,
        "expires_at": time.time() + 600  # 10 minutes
    }

def verify_otp(mobile_number: str, otp_attempt: str) -> dict:
    """
    Verify the OTP. Returns the stored data if correct, or None if invalid/expired.
    """
    record = _otp_store.get(mobile_number)
    if not record:
        return None
        
    if time.time() > record["expires_at"]:
        del _otp_store[mobile_number]
        return None
        
    if record["otp"] == otp_attempt:
        # We don't delete yet, let the auth_middleware delete it upon DB insertion success
        return record
        
    return None

def clear_otp_data(mobile_number: str):
    """Clean up after successful registration."""
    if mobile_number in _otp_store:
        del _otp_store[mobile_number]
