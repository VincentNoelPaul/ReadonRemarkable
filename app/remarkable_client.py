import base64
import os
import requests
from utils import log

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
RESEND_FROM = os.getenv("RESEND_FROM")
DROPBOX_EMAIL = os.getenv("DROPBOX_EMAIL")


def upload_pdf(pdf_path):
    if not DROPBOX_EMAIL:
        log("DROPBOX_EMAIL not configured")
        return False

    if not RESEND_API_KEY:
        log("RESEND_API_KEY must be set")
        return False

    if not RESEND_FROM:
        log("RESEND_FROM must be set (verified sender address in Resend)")
        return False

    try:
        filename = os.path.basename(pdf_path)

        with open(pdf_path, "rb") as f:
            content = base64.b64encode(f.read()).decode("utf-8")

        resp = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
            json={
                "from": RESEND_FROM,
                "to": [DROPBOX_EMAIL],
                "subject": filename,
                "text": filename,
                "attachments": [
                    {"filename": filename, "content": content}
                ],
            },
        )

        if resp.ok:
            log(f"Sent {filename} to Dropbox via Resend ({DROPBOX_EMAIL})")
            return True
        else:
            log(f"Resend API error: {resp.status_code} {resp.text}")
            return False

    except Exception as e:
        log(f"Email send error: {e}")
        return False
