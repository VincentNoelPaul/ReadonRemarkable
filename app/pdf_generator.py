import json
import os
import subprocess
import tempfile
import trafilatura
from utils import log, sanitize_filename

SSO_COOKIES_FILE = os.getenv("SSO_COOKIES_FILE", "/data/cookies.json")

# Extensions convertible via LibreOffice headless
_LIBREOFFICE_EXTENSIONS = {
    ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt",
    ".odt", ".ods", ".odp", ".rtf", ".csv",
}
_TEXT_EXTENSIONS = {".txt"}
_HTML_EXTENSIONS = {".html", ".htm"}
_MARKDOWN_EXTENSIONS = {".md", ".markdown"}
CONVERTIBLE_EXTENSIONS = (
    _LIBREOFFICE_EXTENSIONS | _TEXT_EXTENSIONS | _HTML_EXTENSIONS | _MARKDOWN_EXTENSIONS
)


def _load_sso_cookies():
    """Load SSO cookies from a JSON file (exported from browser via Cookie-Editor extension)."""
    if not os.path.exists(SSO_COOKIES_FILE):
        return None
    try:
        with open(SSO_COOKIES_FILE) as f:
            cookies = json.load(f)
        log(f"Loaded {len(cookies)} SSO cookies from {SSO_COOKIES_FILE}")
        return cookies
    except Exception as e:
        log(f"Failed to load SSO cookies: {e}")
        return None


def _needs_sso(url, cookies):
    """Check if the URL matches any domain in the SSO cookies."""
    if not cookies:
        return False
    for cookie in cookies:
        domain = cookie.get("domain", "")
        # Strip leading dot from domain for comparison
        clean_domain = domain.lstrip(".")
        if clean_domain and clean_domain in url:
            return True
    return False


def _url_to_pdf_playwright(url, cookies):
    """Use Playwright (headless Chromium) to fetch an SSO-protected page and generate a PDF."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log("Playwright not installed, cannot handle SSO URLs")
        return None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            context = browser.new_context()

            # Normalize cookies for Playwright (needs 'name', 'value', 'domain', 'path')
            pw_cookies = []
            for c in cookies:
                pw_cookie = {
                    "name": c.get("name", ""),
                    "value": c.get("value", ""),
                    "domain": c.get("domain", ""),
                    "path": c.get("path", "/"),
                }
                if c.get("sameSite"):
                    # Playwright expects "Strict", "Lax", or "None"
                    same_site = c["sameSite"].capitalize()
                    if same_site in ("Strict", "Lax", "None"):
                        pw_cookie["sameSite"] = same_site
                if c.get("expirationDate"):
                    pw_cookie["expires"] = c["expirationDate"]
                if c.get("secure"):
                    pw_cookie["secure"] = True
                pw_cookies.append(pw_cookie)

            context.add_cookies(pw_cookies)

            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            # Give JS a moment to render dynamic content (paywalled articles, etc.)
            page.wait_for_timeout(3000)

            title = sanitize_filename(page.title() or "article")
            pdf_path = f"/tmp/{title}.pdf"

            page.pdf(
                path=pdf_path,
                format="A4",
                margin={"top": "20mm", "right": "15mm", "bottom": "20mm", "left": "15mm"},
                print_background=True,
            )

            browser.close()
            log(f"Generated PDF via Playwright: {title}")
            return pdf_path

    except Exception as e:
        log(f"Playwright PDF generation failed: {e}")
        return None


def _url_to_pdf_trafilatura(url):
    """Use trafilatura + wkhtmltopdf for public URLs (fast, lightweight)."""
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
        log(f"Trafilatura PDF generation failed: {e}")
        return None

    finally:
        if html_path and os.path.exists(html_path):
            os.remove(html_path)


def _html_to_pdf_wkhtmltopdf(html_content, safe_title):
    """Fallback: convert HTML to PDF using wkhtmltopdf."""
    html_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as f:
            f.write(html_content.encode("utf-8"))
            html_path = f.name
        pdf_path = f"/tmp/{safe_title}.pdf"
        subprocess.run(
            ["wkhtmltopdf", "--encoding", "utf-8", html_path, pdf_path],
            check=True, capture_output=True, timeout=120,
        )
        log(f"Generated PDF via wkhtmltopdf fallback: {safe_title}")
        return pdf_path
    except Exception as e:
        log(f"wkhtmltopdf fallback also failed: {e}")
        return None
    finally:
        if html_path and os.path.exists(html_path):
            os.remove(html_path)


def html_to_pdf(html_content, title):
    """Convert an HTML string (email body) to a PDF.

    Tries Playwright first, falls back to wkhtmltopdf.
    """
    safe_title = sanitize_filename(title)

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_content(html_content, wait_until="domcontentloaded")
            page.wait_for_timeout(1000)

            pdf_path = f"/tmp/{safe_title}.pdf"
            page.pdf(
                path=pdf_path,
                format="A4",
                margin={"top": "20mm", "right": "15mm", "bottom": "20mm", "left": "15mm"},
                print_background=True,
            )
            browser.close()
            log(f"Generated PDF from email body: {safe_title}")
            return pdf_path
    except Exception as e:
        log(f"Playwright HTML-to-PDF failed ({e}), trying wkhtmltopdf fallback")

    return _html_to_pdf_wkhtmltopdf(html_content, safe_title)


def url_to_pdf(url):
    """Convert a URL to PDF. Uses Playwright for SSO-protected URLs, trafilatura otherwise."""
    cookies = _load_sso_cookies()

    if _needs_sso(url, cookies):
        log(f"SSO cookies match URL domain, using Playwright: {url}")
        result = _url_to_pdf_playwright(url, cookies)
        if result:
            return result
        log("Playwright failed, falling back to trafilatura")

    return _url_to_pdf_trafilatura(url)


def _file_to_pdf_libreoffice(file_path):
    """Convert an office document to PDF using LibreOffice headless."""
    try:
        outdir = tempfile.gettempdir()
        subprocess.run(
            ["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", outdir, file_path],
            check=True, capture_output=True, timeout=120,
        )
        base = os.path.splitext(os.path.basename(file_path))[0]
        pdf_path = os.path.join(outdir, f"{base}.pdf")
        if os.path.exists(pdf_path):
            log(f"Converted to PDF via LibreOffice: {os.path.basename(file_path)}")
            return pdf_path
        log(f"LibreOffice conversion produced no output for {os.path.basename(file_path)}")
        return None
    except Exception as e:
        log(f"LibreOffice conversion failed for {os.path.basename(file_path)}: {e}")
        return None


def _text_file_to_pdf(file_path):
    """Convert a plain text file to PDF by wrapping in HTML."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        html = (
            '<pre style="font-family: monospace; font-size: 12px; '
            'white-space: pre-wrap; word-wrap: break-word;">'
            f"{escaped}</pre>"
        )
        title = os.path.splitext(os.path.basename(file_path))[0]
        return html_to_pdf(html, title)
    except Exception as e:
        log(f"Text-to-PDF conversion failed for {os.path.basename(file_path)}: {e}")
        return None


def _html_file_to_pdf(file_path):
    """Convert an HTML file attachment to PDF."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            html_content = f.read()
        title = os.path.splitext(os.path.basename(file_path))[0]
        return html_to_pdf(html_content, title)
    except Exception as e:
        log(f"HTML-to-PDF conversion failed for {os.path.basename(file_path)}: {e}")
        return None


def _markdown_file_to_pdf(file_path):
    """Convert a Markdown file to PDF by rendering to HTML first."""
    try:
        import markdown as md

        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        body = md.markdown(text, extensions=["tables", "fenced_code"])
        html = (
            '<!DOCTYPE html><html><head><meta charset="utf-8">'
            '<style>body { font-family: serif; max-width: 700px; margin: 40px auto; '
            'padding: 0 20px; font-size: 14px; line-height: 1.6; color: #333; } '
            'pre { background: #f4f4f4; padding: 12px; overflow-x: auto; } '
            'code { background: #f4f4f4; padding: 2px 4px; } '
            'table { border-collapse: collapse; } '
            'th, td { border: 1px solid #ccc; padding: 6px 12px; }'
            '</style></head><body>' + body + '</body></html>'
        )
        title = os.path.splitext(os.path.basename(file_path))[0]
        return html_to_pdf(html, title)
    except Exception as e:
        log(f"Markdown-to-PDF conversion failed for {os.path.basename(file_path)}: {e}")
        return None


def file_to_pdf(file_path):
    """Convert a file to PDF based on its extension."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext in _LIBREOFFICE_EXTENSIONS:
        return _file_to_pdf_libreoffice(file_path)
    if ext in _TEXT_EXTENSIONS:
        return _text_file_to_pdf(file_path)
    if ext in _HTML_EXTENSIONS:
        return _html_file_to_pdf(file_path)
    if ext in _MARKDOWN_EXTENSIONS:
        return _markdown_file_to_pdf(file_path)
    log(f"Unsupported file type for conversion: {ext}")
    return None
