import re
from datetime import datetime

def log(msg):
    print(f"[{datetime.utcnow().isoformat()}] {msg}")

def sanitize_filename(name):
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", name)[:80]
