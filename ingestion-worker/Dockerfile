FROM python:3.12.14-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea AS base
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/app/api:/app/ingestion-worker
WORKDIR /app

FROM base AS deps
COPY api/requirements.txt api/requirements.txt
COPY ingestion-worker/requirements.txt ingestion-worker/requirements.txt
RUN pip install --no-cache-dir --require-hashes -r ingestion-worker/requirements.txt

FROM base AS runtime
RUN groupadd --system --gid 1001 appuser \
    && useradd --system --uid 1001 --gid appuser appuser
COPY --from=deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin
COPY --chown=appuser:appuser api/app api/app
COPY --chown=appuser:appuser ingestion-worker/worker.py ingestion-worker/worker.py
COPY --chown=appuser:appuser ingestion-worker/tests ingestion-worker/tests
WORKDIR /app/ingestion-worker
USER appuser
HEALTHCHECK --interval=20s --timeout=5s --start-period=10s --retries=3 \
    CMD ["arq", "--check", "worker.WorkerSettings"]
CMD ["arq", "--custom-log-dict", "worker.LOGGING_CONFIG", "worker.WorkerSettings"]
