"""Slack request authentication performed on the untouched HTTP body."""

from __future__ import annotations

import hashlib
import hmac
import time


class SignatureError(ValueError):
    """A public-safe Slack authentication failure."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def slack_signature(secret: str, timestamp: str, body: bytes) -> str:
    base = b"v0:" + timestamp.encode("ascii") + b":" + body
    digest = hmac.new(secret.encode("utf-8"), base, hashlib.sha256).hexdigest()
    return f"v0={digest}"


def verify_slack_signature(
    *,
    secret: str,
    timestamp: str | None,
    signature: str | None,
    body: bytes,
    now: float | None = None,
    tolerance_seconds: int = 300,
) -> None:
    if not secret:
        raise SignatureError("SIGNING_SECRET_NOT_CONFIGURED")
    if not timestamp or not signature:
        raise SignatureError("SLACK_SIGNATURE_MISSING")
    try:
        request_time = int(timestamp)
    except ValueError as exc:
        raise SignatureError("SLACK_TIMESTAMP_INVALID") from exc
    current_time = time.time() if now is None else now
    if abs(current_time - request_time) > tolerance_seconds:
        raise SignatureError("SLACK_REQUEST_EXPIRED")
    expected = slack_signature(secret, timestamp, body)
    if not hmac.compare_digest(expected, signature):
        raise SignatureError("SLACK_SIGNATURE_INVALID")
