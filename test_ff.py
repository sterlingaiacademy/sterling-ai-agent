import requests, os, json, sys
from dotenv import load_dotenv
load_dotenv()

API = "https://api.fireflies.ai/graphql"

# ── Get Fireflies key directly from Supabase REST API ─────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

FF_KEY = ""
try:
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/clients",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        },
        params={"select": "fireflies_api_key,email", "fireflies_api_key": "neq.null"},
        timeout=10
    )
    rows = resp.json()
    for r in (rows if isinstance(rows, list) else []):
        if r.get("fireflies_api_key"):
            FF_KEY = r["fireflies_api_key"]
            print(f"Found key for: {r.get('email','?')}")
            break
except Exception as e:
    print(f"Supabase REST error: {e}")

if not FF_KEY:
    print("ERROR: No Fireflies API key found in database!")
    print("Make sure the user completed Setup Step 3 (Fireflies API key).")
    sys.exit(1)

headers = {"Authorization": f"Bearer {FF_KEY}", "Content-Type": "application/json"}

print(f"\nKey preview: {FF_KEY[:14]}...")
print("\n" + "="*50)
print("AUTH TEST — verify key works")
print("="*50)
r1 = requests.post(API, json={"query": "query { user { email name minutes_consumed } }"}, headers=headers, timeout=10)
print(json.dumps(r1.json(), indent=2))

print("\n" + "="*50)
print("MUTATION TEST 1 — field: meeting_url")
print("="*50)
r2 = requests.post(API, json={"query": 'mutation { addToLiveMeeting(meeting_url: "https://meet.google.com/test-abc-def") { success message } }'}, headers=headers, timeout=10)
d2 = r2.json()
print(json.dumps(d2, indent=2))

print("\n" + "="*50)
print("MUTATION TEST 2 — field: meeting_link")
print("="*50)
r3 = requests.post(API, json={"query": 'mutation { addToLiveMeeting(meeting_link: "https://meet.google.com/test-abc-def") { success message } }'}, headers=headers, timeout=10)
d3 = r3.json()
print(json.dumps(d3, indent=2))

print("\n" + "="*50)
print("DIAGNOSIS")
print("="*50)
def check(d, field):
    result = (d.get("data") or {}).get("addToLiveMeeting") or {}
    errors = d.get("errors") or []
    if result.get("success"):
        return f"✅ {field}: SUCCESS"
    elif errors:
        err = errors[0].get("message","?")
        if "Cannot query field" in err or "Unknown argument" in err:
            return f"❌ {field}: WRONG FIELD NAME — {err}"
        elif "not found" in err.lower() or "invalid" in err.lower():
            return f"⚠️ {field}: FIELD OK but URL error (expected for fake URL) — {err}"
        else:
            return f"⚠️ {field}: Other error — {err}"
    else:
        return f"⚠️ {field}: No data, no errors — {d}"

print(check(d2, "meeting_url"))
print(check(d3, "meeting_link"))
