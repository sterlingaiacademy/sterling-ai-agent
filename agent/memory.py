import json, os

MEMORY_FILE = "memory.json"

def get_memory(phone: str):
    if not os.path.exists(MEMORY_FILE):
        return []
    with open(MEMORY_FILE) as f:
        data = json.load(f)
    return data.get(phone, [])[-20:]  # Keep last 20 messages

def save_memory(phone: str, history: list):
    data = {}
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE) as f:
            data = json.load(f)
    data[phone] = history[-20:]
    with open(MEMORY_FILE, "w") as f:
        json.dump(data, f)