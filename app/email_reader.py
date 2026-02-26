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
    if not all([IMAP_HOST, IMAP_USER, IMAP_PASSWORD]):
        log("IMAP credentials not configured (IMAP_HOST, IMAP_USER, IMAP_PASSWORD)")
        return []

    urls = []

    with IMAPClient(IMAP_HOST, ssl=True) as client:
        client.login(IMAP_USER, IMAP_PASSWORD)
        client.select_folder("INBOX")

        messages = client.search(["UNSEEN"])
        for msgid, data in client.fetch(messages, ["RFC822"]).items():
            raw = data[b"RFC822"]
            msg = email.message_from_bytes(raw, policy=policy.default)
            body = _extract_body(msg)

            found = re.findall(URL_REGEX, body)
            if found:
                urls.append(found[0])
                log(f"Found URL: {found[0]}")
            else:
                log("No URL found in email")

            client.add_flags(msgid, ["\\Seen"])

    return urls
