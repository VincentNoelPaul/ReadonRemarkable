import os
import re
import email
from email import policy
from imapclient import IMAPClient
from utils import log

IMAP_HOST = os.getenv("IMAP_HOST")
IMAP_USER = os.getenv("IMAP_USER")
IMAP_PASSWORD = os.getenv("IMAP_PASSWORD")

URL_REGEX = r"https?://[^\s<>\"')]+"


def _extract_body(msg):
    """Extract plain text body from an email message."""
    body = msg.get_body(preferencelist=("plain", "html"))
    if body:
        return body.get_content()
    return ""


def fetch_new_urls():
    if not IMAP_HOST or not IMAP_USER:
        log("IMAP_HOST and IMAP_USER must be configured")
        return []

    if not IMAP_PASSWORD:
        log("IMAP_PASSWORD must be set")
        return []

    urls = []

    try:
        log(f"Connecting to IMAP server {IMAP_HOST} as {IMAP_USER}...")
        with IMAPClient(IMAP_HOST, ssl=True) as client:
            client.login(IMAP_USER, IMAP_PASSWORD)

            log("IMAP login successful")
            client.select_folder("INBOX")

            messages = client.search(["UNSEEN"])
            log(f"Found {len(messages)} unseen message(s)")

            for msgid, data in client.fetch(messages, ["RFC822"]).items():
                raw = data[b"RFC822"]
                msg = email.message_from_bytes(raw, policy=policy.default)
                subject = msg.get("Subject", "(no subject)")
                log(f"Processing email: {subject}")
                body = _extract_body(msg)

                found = re.findall(URL_REGEX, body)
                if found:
                    urls.append(found[0])
                    log(f"Found URL: {found[0]}")
                else:
                    log(f"No URL found in email body ({len(body)} chars)")

                client.add_flags(msgid, ["\\Seen"])
    except Exception as e:
        log(f"IMAP error: {e}")

    return urls
