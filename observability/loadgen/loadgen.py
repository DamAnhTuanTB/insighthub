"""Steady synthetic workload so anomaly bands have a real baseline.

Day 4 requires at least one hour of telemetry before an anomaly alert means
anything. This generator produces a flat, boring load: that flatness is the
baseline the bands are computed from.

It only talks to the InsightHub API over HTTP and never touches the database,
Redis, or provider credentials directly.
"""

from __future__ import annotations

import os
import time
import uuid

import httpx

API_URL = os.environ.get("INSIGHTHUB_API_URL", "http://insighthub-api:8000")
CHAT_INTERVAL = float(os.environ.get("LOADGEN_CHAT_INTERVAL", "10"))
UPLOAD_INTERVAL = float(os.environ.get("LOADGEN_UPLOAD_INTERVAL", "300"))
QUESTION = os.environ.get("LOADGEN_QUESTION", "InsightHub xử lý tài liệu như thế nào?")

DOCUMENT = (
    "InsightHub ingestion pipeline notes.\n"
    "Documents are uploaded, chunked, embedded and stored atomically.\n"
    "A document becomes ready only after a successful transaction.\n"
    "Failures are retried at most three times with exponential backoff.\n"
)


def wait_for_api(client: httpx.Client) -> None:
    while True:
        try:
            if client.get("/readyz").status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(5)


def upload(client: httpx.Client) -> None:
    name = f"baseline-{uuid.uuid4().hex[:12]}.txt"
    files = {"file": (name, DOCUMENT.encode("utf-8"), "text/plain")}
    try:
        client.post("/documents", files=files)
    except httpx.HTTPError:
        # The generator must never crash the baseline; the API metrics already
        # record the failure.
        pass


def chat(client: httpx.Client) -> None:
    try:
        client.post("/chat", json={"question": QUESTION})
    except httpx.HTTPError:
        pass


def main() -> None:
    with httpx.Client(base_url=API_URL, timeout=30) as client:
        wait_for_api(client)
        upload(client)
        # Give the worker time to reach ready before the first retrieval.
        time.sleep(20)
        last_upload = time.monotonic()
        while True:
            chat(client)
            try:
                client.get("/documents")
            except httpx.HTTPError:
                pass
            if time.monotonic() - last_upload >= UPLOAD_INTERVAL:
                upload(client)
                last_upload = time.monotonic()
            time.sleep(CHAT_INTERVAL)


if __name__ == "__main__":
    main()
