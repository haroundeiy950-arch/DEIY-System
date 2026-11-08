FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DEIY_DATABASE_URL=sqlite:////data/deiy.db \
    DEIY_STORAGE_ROOT=/data/storage \
    DEIY_PUBLIC_BASE_URL=http://localhost:8000

WORKDIR /app

RUN useradd --create-home --uid 10001 deiy

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY deiy ./deiy
COPY web ./web
COPY seed.py run.py pyproject.toml README.md ./

RUN mkdir -p /data/storage && chown -R deiy:deiy /app /data

USER deiy

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import json, urllib.request; response = json.load(urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)); raise SystemExit(0 if response.get('status') == 'ok' else 1)"

CMD ["python", "-m", "deiy"]

