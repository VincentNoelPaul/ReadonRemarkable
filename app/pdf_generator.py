import os
import subprocess
import tempfile
import trafilatura
from utils import log, sanitize_filename


def url_to_pdf(url):
    html_path = None
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            log(f"Failed to download {url}")
            return None

        content = trafilatura.extract(downloaded, output_format="html", include_images=True)
        if not content:
            log(f"Failed to extract content from {url}")
            return None

        metadata = trafilatura.extract(downloaded, output_format="txt", only_with_metadata=False)
        title = sanitize_filename(trafilatura.extract_metadata(downloaded).title or "article")

        html_content = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{title}</title>
<style>
body {{ font-family: serif; max-width: 700px; margin: 40px auto; padding: 0 20px;
       font-size: 14px; line-height: 1.6; color: #333; }}
h1 {{ font-size: 22px; }}
img {{ max-width: 100%; height: auto; }}
</style>
</head>
<body><h1>{title}</h1>{content}</body>
</html>"""

        with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as f:
            f.write(html_content.encode("utf-8"))
            html_path = f.name

        pdf_path = f"/tmp/{title}.pdf"
        subprocess.run(
            ["wkhtmltopdf", "--encoding", "utf-8", html_path, pdf_path],
            check=True, capture_output=True,
        )
        return pdf_path

    except Exception as e:
        log(f"PDF generation failed: {e}")
        return None

    finally:
        if html_path and os.path.exists(html_path):
            os.remove(html_path)
