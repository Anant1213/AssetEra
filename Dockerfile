FROM python:3.12-slim

# curl → container HEALTHCHECK; ca-certificates → S3/HTTPS/OpenAI TLS
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8501

# Install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (see .dockerignore for exclusions: .venv, .git, .env, data_cache…)
COPY . .

RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app
USER appuser

# Local default; Railway/other PaaS override $PORT at runtime.
EXPOSE 8501

# Shell form so ${PORT} expands at runtime. Bind all interfaces, run headless.
HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 \
  CMD curl -fsS "http://localhost:${PORT}/_stcore/health" || exit 1

CMD streamlit run app.py \
    --server.port=${PORT} \
    --server.address=0.0.0.0 \
    --server.headless=true
