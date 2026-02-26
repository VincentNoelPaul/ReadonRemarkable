import os
import subprocess
import tempfile
import requests
from readability import Document
from utils import log, sanitize_filename

def url_to_pdf(url):
    html_path = None
    try:
        html = requests.get(url, timeout=10).text
        readable = Document(html)
        title = sanitize_filename(readable.short_title() or "article")

        html_content = readable.summary()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as f:
            f.write(html_content.encode("utf-8"))
            html_path = f.name

        pdf_path = f"/tmp/{title}.pdf"

        cmd = ["wkhtmltopdf", html_path, pdf_path]
        subprocess.run(cmd, check=True, capture_output=True)

        return pdf_path

    except Exception as e:
        log(f"PDF generation failed: {e}")
        return None

    finally:
        if html_path and os.path.exists(html_path):
            os.remove(html_path)
