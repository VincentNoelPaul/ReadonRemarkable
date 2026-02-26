import os
import signal
import time
from email_reader import fetch_new_urls
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

    while running:
        try:
            urls = fetch_new_urls()
            for url in urls:
                log(f"Processing URL: {url}")

                pdf_path = url_to_pdf(url)
                if pdf_path:
                    success = upload_pdf(pdf_path)
                    if success:
                        log(f"Uploaded to reMarkable: {pdf_path}")
                    else:
                        log(f"Failed to upload {pdf_path}")
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
