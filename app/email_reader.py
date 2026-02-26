import os
import re
import email
from email import policy
from imapclient import IMAPClient
import msal
from utils import log

IMAP_HOST = os.getenv("IMAP_HOST")
IMAP_USER = os.getenv("IMAP_USER")
IMAP_PASSWORD = os.getenv("IMAP_PASSWORD")

# Microsoft OAuth2 settings (optional — used when MS_CLIENT_ID is set)
MS_CLIENT_ID = os.getenv("MS_CLIENT_ID")
MS_CLIENT_SECRET = os.getenv("MS_CLIENT_SECRET")
MS_TENANT_ID = os.getenv("MS_TENANT_ID", "common")

URL_REGEX = r"https?://[^\s<>\"')]+"


def _extract_body(msg):
    """Extract plain text body from an email message."""
    body = msg.get_body(preferencelist=("plain", "html"))
    if body:
        return body.get_content()
    return ""


def _get_oauth2_access_token():
    """Acquire an OAuth2 access token for IMAP using client credentials."""
    authority = f"https://login.microsoftonline.com/{MS_TENANT_ID}"
    app = msal.ConfidentialClientApplication(
        MS_CLIENT_ID,
        authority=authority,
        client_credential=MS_CLIENT_SECRET,
    )
    scopes = ["https://outlook.office365.com/.default"]
    result = app.acquire_token_for_client(scopes=scopes)
    if "access_token" in result:
        log("OAuth2 token acquired successfully")
        return result["access_token"]
    error = result.get("error_description", result.get("error", "unknown error"))
    log(f"OAuth2 token acquisition failed: {error}")
    return None


def _use_oauth2():
    """Return True if Microsoft OAuth2 credentials are configured."""
    return bool(MS_CLIENT_ID and MS_CLIENT_SECRET)


def fetch_new_urls():
    if not IMAP_HOST or not IMAP_USER:
        log("IMAP_HOST and IMAP_USER must be configured")
        return []

    use_oauth = _use_oauth2()

    if not use_oauth and not IMAP_PASSWORD:
        log("Either IMAP_PASSWORD or MS_CLIENT_ID + MS_CLIENT_SECRET must be set")
        return []

    urls = []

    try:
        log(f"Connecting to IMAP server {IMAP_HOST} as {IMAP_USER}...")
        with IMAPClient(IMAP_HOST, ssl=True) as client:
            if use_oauth:
                log("Authenticating with OAuth2...")
                token = _get_oauth2_access_token()
                if not token:
                    return []
                client.oauth2_login(IMAP_USER, token)
            else:
                log("Authenticating with password...")
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
