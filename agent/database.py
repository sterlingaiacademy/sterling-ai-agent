import os
from supabase import create_client

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

def get_client_by_phone(wa_phone: str):
    result = supabase.table("clients").select("*").eq("wa_phone", wa_phone).single().execute()
    return result.data

def get_client_by_email(email: str):
    result = supabase.table("clients").select("*").eq("email", email).single().execute()
    return result.data

def save_google_token(client_id: str, token_json: str):
    supabase.table("clients").update({
        "google_token_json": token_json
    }).eq("id", client_id).execute()

def update_client(client_id: str, data: dict):
    supabase.table("clients").update(data).eq("id", client_id).execute()

def create_client_account(email: str, password_hash: str):
    result = supabase.table("clients").insert({
        "email": email,
        "password_hash": password_hash
    }).execute()
    return result.data[0]