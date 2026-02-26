import os
import requests
from utils import log

DEVICE_TOKEN = os.getenv("REMARKABLE_DEVICE_TOKEN")

RM_BASE = "https://document-storage-production-dot-remarkable-production.appspot.com"


def upload_pdf(pdf_path):
    if not DEVICE_TOKEN:
        log("REMARKABLE_DEVICE_TOKEN not configured")
        return False

    try:
        with open(pdf_path, "rb") as f:
            content = f.read()

        headers = {
            "Authorization": f"Bearer {DEVICE_TOKEN}",
            "Content-Type": "application/pdf",
        }

        resp = requests.post(f"{RM_BASE}/upload", headers=headers, data=content)

        if resp.status_code == 200:
            log("Upload successful")
            return True
        else:
            log(f"Upload failed: {resp.status_code} {resp.text}")
            return False

    except Exception as e:
        log(f"Upload error: {e}")
        return False
