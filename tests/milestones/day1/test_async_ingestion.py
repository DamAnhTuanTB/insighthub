"""Day 1 black-box contract tests against the running five-service stack."""

import json
import os
import time
import urllib.error
import urllib.request
import uuid

API_URL = os.environ.get("INSIGHTHUB_API_URL", "http://localhost:8000").rstrip("/")


def _json_request(path, *, method="GET", data=None, headers=None):
    request = urllib.request.Request(
        API_URL + path, data=data, method=method, headers=headers or {}
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _upload(content: bytes, filename: str | None = None):
    filename = filename or f"day1-{uuid.uuid4().hex}.txt"
    boundary = "----insighthub-" + uuid.uuid4().hex
    body = (
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            "Content-Type: text/plain\r\n\r\n"
        ).encode()
        + content
        + f"\r\n--{boundary}--\r\n".encode()
    )
    started = time.monotonic()
    status, payload = _json_request(
        "/documents",
        method="POST",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    return status, payload, time.monotonic() - started


def _documents():
    status, payload = _json_request("/documents")
    assert status == 200
    return payload


def _wait(document_id: int, expected: set[str], timeout: float = 30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        document = next(
            (item for item in _documents() if item["id"] == document_id), None
        )
        if document and document["status"] in expected:
            return document
        time.sleep(0.2)
    raise AssertionError(f"document {document_id} did not reach {sorted(expected)}")


def test_async_upload():
    status, document, elapsed = _upload(b"asynchronous upload contract")
    assert status == 202
    assert document["status"] == "pending"
    assert document["chunk_count"] == 0
    assert elapsed < 1.0


def test_worker_ingests():
    status, document, _ = _upload(b"worker creates searchable vector chunks")
    assert status == 202
    ready = _wait(document["id"], {"ready"})
    assert ready["chunk_count"] > 0
    assert ready["error_code"] is None


def test_retry_idempotent():
    status, document, _ = _upload(
        b"idempotent retry must never append duplicate chunks"
    )
    assert status == 202
    first = _wait(document["id"], {"ready"})
    assert first["chunk_count"] > 0
    time.sleep(0.5)
    settled = next(item for item in _documents() if item["id"] == document["id"])
    assert settled["status"] == "ready"
    assert settled["chunk_count"] == first["chunk_count"]


def test_empty_input():
    status, payload, _ = _upload(b"")
    assert status == 422
    assert payload["code"] == "invalid_document"
    status, document, _ = _upload(b"   \n")
    assert status == 202
    failed = _wait(document["id"], {"failed"})
    assert failed["chunk_count"] == 0
    assert failed["error_code"] == "invalid_document"


def test_duplicate_or_invalid():
    status, _, _ = _upload(b"not accepted", filename="invalid.exe")
    assert status == 400
    status, document, _ = _upload(b"one successful document has one stable result")
    assert status == 202
    ready = _wait(document["id"], {"ready"})
    matching = [item for item in _documents() if item["id"] == document["id"]]
    assert len(matching) == 1
    assert matching[0]["chunk_count"] == ready["chunk_count"]


def test_refactor_regression():
    marker = uuid.uuid4().hex
    filename = f"regression-{marker}.txt"
    content = f"The Day One regression marker is {marker}.".encode()
    status, document, _ = _upload(content, filename=filename)
    assert status == 202
    _wait(document["id"], {"ready"})
    status, answer = _json_request(
        "/chat",
        method="POST",
        data=json.dumps({"question": content.decode()}).encode(),
        headers={"Content-Type": "application/json"},
    )
    assert status == 200
    assert answer["answer"].strip()
    assert filename in answer["sources"]
