import re
from datetime import datetime, timezone


def log(msg):
    print(f"[{datetime.now(timezone.utc).isoformat()}] {msg}")


def sanitize_filename(name):
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", name)[:80]
