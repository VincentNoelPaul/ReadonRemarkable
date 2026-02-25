import time
from email_reader import fetch_new_urls
from pdf_generator import url_to_pdf
from remarkable_client import upload_pdf
from utils import log

POLL_INTERVAL = 60  # seconds

def main():
    log("Starting Read-Later service...")

    while True:
        try:
            urls = fetch_new_urls()
            for url in urls:
                log(f"Processing URL: {url}")

                pdf_path = url_to_pdf(url)
                if pdf_path:
                    upload_pdf(pdf_path)
                    log(f"Uploaded to reMarkable: {pdf_path}")
                else:
                    log(f"Failed to generate PDF for {url}")

        except Exception as e:
            log(f"Error in main loop: {e}")

        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
