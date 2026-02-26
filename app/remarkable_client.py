import os
import smtplib
from email.message import EmailMessage
from utils import log

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465
SMTP_USER = os.getenv("IMAP_USER")
SMTP_PASSWORD = os.getenv("IMAP_PASSWORD")
DROPBOX_EMAIL = os.getenv("DROPBOX_EMAIL")


def upload_pdf(pdf_path):
    if not DROPBOX_EMAIL:
        log("DROPBOX_EMAIL not configured")
        return False

    if not SMTP_USER or not SMTP_PASSWORD:
        log("IMAP_USER and IMAP_PASSWORD must be set for sending emails")
        return False

    try:
        filename = os.path.basename(pdf_path)

        msg = EmailMessage()
        msg["From"] = SMTP_USER
        msg["To"] = DROPBOX_EMAIL
        msg["Subject"] = filename

        with open(pdf_path, "rb") as f:
            msg.add_attachment(
                f.read(),
                maintype="application",
                subtype="pdf",
                filename=filename,
            )

        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)

        log(f"Emailed {filename} to Dropbox ({DROPBOX_EMAIL})")
        return True

    except Exception as e:
        log(f"Email send error: {e}")
        return False
