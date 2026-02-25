FROM debian:bookworm

# Install Python + wkhtmltopdf dependencies
RUN apt-get update && apt-get install -y \
    python3 python3-pip \
    wkhtmltopdf \
    libxrender1 \
    libxext6 \
    libfontconfig1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY app/ ./app/

CMD ["python3", "app/main.py"]
