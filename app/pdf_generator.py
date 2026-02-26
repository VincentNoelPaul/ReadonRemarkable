import json
import os
import subprocess
import tempfile
import trafilatura
from utils import log, sanitize_filename

SSO_COOKIES_FILE = os.getenv("SSO_COOKIES_FILE", "/data/cookies.json")


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
