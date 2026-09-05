# mkcert Web-UI
# Flask + mkcert
# amd64
# Single-Stage Build

FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive

# ------------------------------------------------------------
# Systempakete + mkcert
# ------------------------------------------------------------

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        tzdata \
        libnss3-tools \
    && rm -rf /var/lib/apt/lists/* \
    \
    # mkcert herunterladen
    && curl -fL \
        "https://dl.filippo.io/mkcert/v1.4.4?for=linux/amd64" \
        -o /usr/local/bin/mkcert \
    && chmod 755 /usr/local/bin/mkcert \
    \
    # Test
    && /usr/local/bin/mkcert -version

# ------------------------------------------------------------
# App
# ------------------------------------------------------------

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY templates ./templates
COPY static ./static
COPY scripts/entrypoint.sh /usr/local/bin/entrypoint.sh

RUN chmod 755 /usr/local/bin/entrypoint.sh

# ------------------------------------------------------------
# Zertifikatsverzeichnisse
# ------------------------------------------------------------

RUN mkdir -p \
        /certs/ca \
        /certs/certs

ENV CAROOT=/certs/ca \
    MKCERT_CAROOT=/certs/ca \
    MKCERT_CERT_DIR=/certs/certs \
    MKCERT_BIN=/usr/local/bin/mkcert \
    PORT=8080

# ------------------------------------------------------------
# User
# ------------------------------------------------------------

RUN useradd \
        --create-home \
        --uid 1000 \
        --shell /usr/sbin/nologin \
        webapp \
    && chown -R webapp:webapp \
        /app \
        /certs

USER webapp

# ------------------------------------------------------------
# Healthcheck
# ------------------------------------------------------------

HEALTHCHECK \
    --interval=30s \
    --timeout=5s \
    --start-period=15s \
    --retries=3 \
    CMD python3 -c \
        "import urllib.request,os; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8080')+'/health')" \
        || exit 1

# ------------------------------------------------------------
# Docker
# ------------------------------------------------------------

EXPOSE 8080

VOLUME ["/certs/ca", "/certs/certs"]

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
