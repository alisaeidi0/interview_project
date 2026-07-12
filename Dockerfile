# Manufacturing Floor Assistant — application image.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# libgomp1 is required by onnxruntime (fastembed); curl is used by the healthcheck.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first so they cache across code changes.
COPY requirements.txt .
RUN pip install -r requirements.txt

# Application code and entrypoint.
COPY app ./app
COPY docker-entrypoint.sh .
RUN chmod +x docker-entrypoint.sh

EXPOSE 8000

# The entrypoint generates a session secret if none is set, ingests the corpus on
# first run, then starts the server.
ENTRYPOINT ["./docker-entrypoint.sh"]
