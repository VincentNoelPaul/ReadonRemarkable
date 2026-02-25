import os
import re
from imapclient import IMAPClient
from utils import log

IMAP_HOST = os.getenv("IMAP_HOST")
IMAP_USER = os.getenv("IMAP_USER")
IMAP_PASSWORD = os.getenv("IMAP_PASSWORD")

URL_REGEX = r"https?://[^\s]+"


def fetch_new_urls():
    urls = []

    with IMAPClient(IMAP_HOST) as client:
        client.login(IMAP_USER, IMAP_PASSWORD)
        client.select_folder("INBOX")

        messages = client.search(["UNSEEN"])
        for msgid, data in client.fetch(messages, ["RFC822"]).items():
            raw = data[b"RFC822"].decode("utf-8", errors="ignore")

            found = re.findall(URL_REGEX, raw)
            if found:
                urls.append(found[0])
                log(f"Found URL: {found[0]}")
            else:
                log("No URL found in email")

            client.add_flags(msgid, ["\\Seen"])

    return urls
