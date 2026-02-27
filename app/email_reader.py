import json
import os
import re
import email
import tempfile
from email import policy
from imapclient import IMAPClient
from utils import log

IMAP_HOST = os.getenv("IMAP_HOST")
IMAP_USER = os.getenv("IMAP_USER")
IMAP_PASSWORD = os.getenv("IMAP_PASSWORD")
SSO_COOKIES_FILE = os.getenv("SSO_COOKIES_FILE", "/data/cookies.json")

URL_REGEX = r"https?://[^\s<>\"')]+"
# Matches ROM> or ROM1> after optional Fw:/Fwd:/Tr:/Re: prefixes
ROM_REGEX = re.compile(r"^(?:(?:Fw|Fwd|Tr|Re)\s*:\s*)*(ROM1?)>\s*(.*)", re.IGNORECASE)

# Patterns that mark the start of a forwarded/quoted message
_FWD_BOUNDARIES = [
    re.compile(r"-{5,}\s*Forwarded message\s*-{5,}", re.IGNORECASE),
    re.compile(r"-{5,}\s*Message transf[ée]r[ée]\s*-{5,}", re.IGNORECASE),
    re.compile(r"-{5,}\s*Original\s+(?:email|message)\s*-{5,}", re.IGNORECASE),
    re.compile(r"_{20,}"),  # Outlook long underscore separator
    re.compile(r"<div\s+class=\"gmail_quote\"", re.IGNORECASE),
    # Outlook border-top separator (reply/forward boundary)
    re.compile(r"<div\s[^>]*border-top:\s*solid\s[^>]*>", re.IGNORECASE),
    # "From:" or "De:" header block after a line break (common in forwards)
    re.compile(r"<br[^>]*>\s*(?:From|De)\s*:", re.IGNORECASE),
]


def _extract_body(msg):
    """Extract plain text body from an email message."""
    body = msg.get_body(preferencelist=("plain", "html"))
    if body:
        return body.get_content()
    return ""


def _extract_html_body(msg):
    """Extract body as HTML, preferring HTML part. Wraps plain text in basic HTML if needed."""
    html_part = msg.get_body(preferencelist=("html",))
    if html_part:
        return html_part.get_content()
    plain_part = msg.get_body(preferencelist=("plain",))
    if plain_part:
        text = plain_part.get_content()
        escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return f"<pre>{escaped}</pre>"
    return ""


def _truncate_to_latest(html):
    """Remove forwarded/quoted content, keeping only the latest message."""
    for pattern in _FWD_BOUNDARIES:
        match = pattern.search(html)
        if match:
            html = html[:match.start()]
            break
    return html


def _extract_pdf_attachments(msg):
    """Extract PDF attachments from an email, save to temp files."""
    pdf_paths = []
    for part in msg.iter_attachments():
        content_type = part.get_content_type()
        filename = part.get_filename()
        if content_type == "application/pdf" and filename:
            data = part.get_content()
            path = os.path.join(tempfile.gettempdir(), filename)
            with open(path, "wb") as f:
                f.write(data)
            pdf_paths.append(path)
            log(f"Extracted PDF attachment: {filename}")
    return pdf_paths


def _extract_cookies_attachment(msg):
    """Detect a .json attachment and save it as the SSO cookies file.

    Returns True if cookies were updated.
    """
    for part in msg.iter_attachments():
        filename = part.get_filename() or ""
        if not filename.lower().endswith(".json"):
            continue
        try:
            data = part.get_content()
            # get_content() returns str for text types, bytes for binary
            # Use utf-8-sig to handle BOM that Cookie-Editor adds
            text = data if isinstance(data, str) else data.decode("utf-8-sig")
            text = text.lstrip("\ufeff")
            cookies = json.loads(text)
            if not isinstance(cookies, list):
                log(f"Ignoring {filename}: expected a JSON array of cookies")
                continue
            os.makedirs(os.path.dirname(SSO_COOKIES_FILE), exist_ok=True)
            with open(SSO_COOKIES_FILE, "w") as f:
                json.dump(cookies, f)
            log(f"Updated SSO cookies from email attachment ({len(cookies)} cookies)")
            return True
        except Exception as e:
            log(f"Failed to process cookie attachment {filename}: {e}")
    return False


def fetch_new_emails():
    if not IMAP_HOST or not IMAP_USER:
        log("IMAP_HOST and IMAP_USER must be configured")
        return [], [], []

    if not IMAP_PASSWORD:
        log("IMAP_PASSWORD must be set")
        return [], [], []

    urls = []
    pdf_paths = []
    body_contents = []

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

                # Check for cookie file attachment (updates SSO session)
                cookies_updated = _extract_cookies_attachment(msg)

                # Check for ROM> or ROM1> prefix → convert body to PDF
                rom_match = ROM_REGEX.match(subject)
                if rom_match:
                    rom_mode = rom_match.group(1).upper()  # "ROM" or "ROM1"
                    title = rom_match.group(2).strip() or "email"
                    html_body = _extract_html_body(msg)
                    if html_body:
                        if rom_mode == "ROM1":
                            html_body = _truncate_to_latest(html_body)
                            log(f"ROM1> mode: keeping only latest message")
                        body_contents.append((title, html_body))
                        log(f"{rom_mode}> detected, will convert body to PDF: {title}")
                    else:
                        log(f"{rom_mode}> detected but email body is empty")
                    client.add_flags(msgid, ["\\Seen"])
                    continue

                # Extract PDF attachments
                attachments = _extract_pdf_attachments(msg)
                pdf_paths.extend(attachments)

                # Extract URL from body
                body = _extract_body(msg)
                found = re.findall(URL_REGEX, body)
                if found:
                    urls.append(found[0])
                    log(f"Found URL: {found[0]}")
                elif not attachments and not cookies_updated:
                    log(f"No URL, PDF, or cookies found in email ({len(body)} chars)")

                client.add_flags(msgid, ["\\Seen"])
    except Exception as e:
        log(f"IMAP error: {e}")

    return urls, pdf_paths, body_contents
