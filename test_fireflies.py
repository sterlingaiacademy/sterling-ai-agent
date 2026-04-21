"""
Quick diagnostic: tests Fireflies bot-invite with all known field variants.
Run from project root:  python test_fireflies.py
"""
import requests, os, json
from dotenv import load_dotenv
load_dotenv()

API = "https://api.fireflies.ai/graphql"

# ── PUT YOUR VALUES HERE ──────────────────────────────────────────────────────
FF_KEY      = os.getenv("FIREFLIES_API_KEY") or input("Fireflies API key: ")
MEET_URL    = input("Paste the meeting URL to test (or press Enter for mock): ").strip() \
              or "https://meet.google.com/abc-defg-hij"
# ─────────────────────────────────────────────────────────────────────────────

headers = {
    "Authorization": f"Bearer {FF_KEY}",
    "Content-Type":  "application/json"
}

print(f"\n🔑 Using key: {FF_KEY[:8]}...")
print(f"🔗 Meeting URL: {MEET_URL}\n")

# Test 1: Introspect schema to see exact field names
print("=" * 60)
print("TEST 1: Schema introspection — finding addToLiveMeeting args")
print("=" * 60)
introspect = {
    "query": """
    query {
      __schema {
        mutationType {
          fields {
            name
            args { name type { kind name ofType { name } } }
          }
        }
      }
    }
    """
}
r = requests.post(API, json=introspect, headers=headers, timeout=15)
schema = r.json()
mutations = (schema.get("data") or {}).get("__schema", {}).get("mutationType", {}).get("fields", [])
for m in mutations:
    if "live" in m["name"].lower() or "meeting" in m["name"].lower():
        print(f"  Mutation: {m['name']}")
        for arg in m.get("args", []):
            print(f"    arg: {arg['name']} ({arg.get('type',{}).get('name') or arg.get('type',{}).get('ofType',{}).get('name','?')})")

# Test 2: Try meeting_url variant
print("\n" + "=" * 60)
print("TEST 2: addToLiveMeeting with meeting_url")
print("=" * 60)
q2 = {"query": f'mutation {{ addToLiveMeeting(meeting_url: "{MEET_URL}") {{ success message }} }}'}
r2 = requests.post(API, json=q2, headers=headers, timeout=15)
print(f"Status: {r2.status_code}")
print(json.dumps(r2.json(), indent=2))

# Test 3: Try meeting_link variant
print("\n" + "=" * 60)
print("TEST 3: addToLiveMeeting with meeting_link")
print("=" * 60)
q3 = {"query": f'mutation {{ addToLiveMeeting(meeting_link: "{MEET_URL}") {{ success message }} }}'}
r3 = requests.post(API, json=q3, headers=headers, timeout=15)
print(f"Status: {r3.status_code}")
print(json.dumps(r3.json(), indent=2))

# Test 4: Verify API key works at all
print("\n" + "=" * 60)
print("TEST 4: Auth check — get user info")
print("=" * 60)
q4 = {"query": "query { user { user_id email name minutes_consumed } }"}
r4 = requests.post(API, json=q4, headers=headers, timeout=15)
print(json.dumps(r4.json(), indent=2))

print("\n✅ Done. Share the output above so we can see the exact error.")
