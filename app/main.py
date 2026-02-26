import os
import signal
import time
from email_reader import fetch_new_emails
from pdf_generator import url_to_pdf
from remarkable_client import upload_pdf
from utils import log

POLL_INTERVAL = 60

running = True


def shutdown_handler(signum, frame):
    global running
    log("Shutdown signal received, stopping...")
    running = False


signal.signal(signal.SIGTERM, shutdown_handler)
signal.signal(signal.SIGINT, shutdown_handler)


def main():
    log("Starting Read-Later service...")
    log(f"IMAP_HOST={'set' if os.getenv('IMAP_HOST') else 'MISSING'}")
    log(f"IMAP_USER={'set' if os.getenv('IMAP_USER') else 'MISSING'}")
    log(f"IMAP_PASSWORD={'set' if os.getenv('IMAP_PASSWORD') else 'MISSING'}")
    log(f"RESEND_API_KEY={'set' if os.getenv('RESEND_API_KEY') else 'MISSING'}")
    log(f"RESEND_FROM={'set' if os.getenv('RESEND_FROM') else 'MISSING'}")
    log(f"DROPBOX_EMAIL={'set' if os.getenv('DROPBOX_EMAIL') else 'MISSING'}")
    sso_cookies = os.getenv("SSO_COOKIES_FILE", "/data/cookies.json")
    log(f"SSO_COOKIES_FILE={sso_cookies} ({'found' if os.path.exists(sso_cookies) else 'not found'})")
    log(f"Poll interval: {POLL_INTERVAL}s")

    while running:
        try:
            urls, attached_pdfs = fetch_new_emails()

            # Process attached PDFs
            for pdf_path in attached_pdfs:
                log(f"Processing attached PDF: {pdf_path}")
                success = upload_pdf(pdf_path)
                if success:
                    log(f"Sent to Dropbox: {pdf_path}")
                else:
                    log(f"Failed to send {pdf_path}")
                try:
                    os.remove(pdf_path)
                except OSError:
                    pass

            # Process URLs (generate PDF then send)
            for url in urls:
                log(f"Processing URL: {url}")
                pdf_path = url_to_pdf(url)
                if pdf_path:
                    success = upload_pdf(pdf_path)
                    if success:
                        log(f"Sent to Dropbox: {pdf_path}")
                    else:
                        log(f"Failed to send {pdf_path}")
                    try:
                        os.remove(pdf_path)
                    except OSError:
                        pass
                else:
                    log(f"Failed to generate PDF for {url}")

        except Exception as e:
            log(f"Error in main loop: {e}")

        time.sleep(POLL_INTERVAL)

    log("Service stopped.")


if __name__ == "__main__":
    main()
