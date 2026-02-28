FROM debian:bookworm

RUN apt-get update && apt-get install -y \
    python3 python3-pip python3-venv \
    wkhtmltopdf \
    libxrender1 \
    libxext6 \
    libfontconfig1 \
    && apt-get install -y --no-install-recommends libreoffice \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright's Chromium browser and its OS dependencies
RUN playwright install --with-deps chromium

COPY app/ ./app/

ENV PYTHONUNBUFFERED=1
CMD ["python", "app/main.py"]
