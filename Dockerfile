FROM debian:bookworm

# Install Python + wkhtmltopdf dependencies
RUN apt-get update && apt-get install -y \
    python3 python3-pip python3-venv \
    wkhtmltopdf \
    libxrender1 \
    libxext6 \
    libfontconfig1 \
    libxml2-dev \
    libxslt-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create a virtual environment
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies inside the venv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your app
COPY app/ ./app/

CMD ["python", "app/main.py"]
