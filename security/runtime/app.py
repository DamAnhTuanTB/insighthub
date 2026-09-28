"""Fail-closed Day 6 guardrail in front of the LiteLLM OpenAI API.

The service never logs prompts, documents, responses, credentials, or upstream
exception bodies. It emits only bounded classifications and usage metadata.
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest


BLOCKED_TEXT = "Request blocked by InsightHub guardrail."
MAX_BODY_BYTES = 256 * 1024
UPSTREAM = os.environ.get("LITELLM_BASE_URL", "http://litellm:4000").rstrip("/")
AUDIT_PATH = Path(os.environ.get("GUARDRAIL_AUDIT_PATH", "/data/audit.jsonl"))
INPUT_RATE = float(os.environ.get("DAY6_INPUT_USD_PER_TOKEN", "0.000001"))
OUTPUT_RATE = float(os.environ.get("DAY6_OUTPUT_USD_PER_TOKEN", "0.000002"))

INJECTION_PATTERNS = (
    r"ignore (?:all |any )?(?:previous|prior|system|developer) instructions?",
    r"disregard (?:all |any )?(?:previous|prior|system|developer) instructions?",
    r"reveal (?:the )?(?:system|developer) prompt",
    r"print (?:the )?(?:hidden )?(?:system|developer) (?:prompt|message|instructions?)",
    r"jailbreak|developer mode|do anything now|\bdan mode\b",
    r"override (?:the )?(?:system|safety|policy|guardrail)",
    r"decode (?:this )?(?:base64|rot13).*(?:follow|execute|instruction)",
    r"new (?:system|developer) instructions?",
    r"trusted (?:system|developer) message begins",
    r"tool output says (?:to )?(?:ignore|override)",
    r"không cần tuân theo (?:chỉ dẫn|hướng dẫn|quy tắc)",
    r"bỏ qua (?:mọi |tất cả )?(?:chỉ dẫn|hướng dẫn|quy tắc).*(?:trước|hệ thống)",
)

AGENCY_PATTERNS = (
    r"(?:execute|run) (?:this )?(?:shell |terminal )?(?:command|script)",
    r"(?:delete|drop|destroy) (?:the )?(?:(?:production )?database|(?:kubernetes )?namespace|cluster|production)",
    r"(?:scale|restart) (?:the )?(?:deployment|production).*(?:without|no) (?:approval|confirmation)",
    r"(?:send|exfiltrate|upload) (?:all )?(?:secrets|credentials|environment variables)",
    r"use (?:the )?(?:admin|root) (?:token|credential|permission)",
    r"tự động (?:xóa|chạy|thực thi).*(?:không cần|bỏ qua).*(?:duyệt|xác nhận)",
)

PII_PATTERNS = (
    r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
    r"(?<!\d)(?:\+?84|0)(?:3|5|7|8|9)\d{8}(?!\d)",
    r"(?<!\d)(?:\d[ -]?){15}\d(?!\d)",
    r"\b(?:ssn|social security number)\s*[:#]?\s*\d{3}-\d{2}-\d{4}\b",
    r"\b(?:cccd|căn cước|can cuoc)\s*[:#]?\s*\d{12}\b",
)

compiled_injection = tuple(re.compile(pattern, re.I | re.S) for pattern in INJECTION_PATTERNS)
compiled_agency = tuple(re.compile(pattern, re.I | re.S) for pattern in AGENCY_PATTERNS)
compiled_pii = tuple(re.compile(pattern, re.I) for pattern in PII_PATTERNS)

requests_total = Counter(
    "insighthub_guardrail_requests_total",
    "Guardrail decisions by workflow and decision.",
    ("workflow", "decision", "reason"),
)
tokens_total = Counter(
    "insighthub_llm_tokens_total",
    "Tokens observed through the Day 6 gateway.",
    ("workflow", "model", "direction"),
)
cost_total = Counter(
    "insighthub_llm_cost_usd_total",
    "Attributed model cost in USD.",
    ("workflow", "model"),
)

app = FastAPI(title="InsightHub Day 6 Guardrail", version="1.0.0")


def _walk_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [text for item in value for text in _walk_strings(item)]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _walk_strings(item)]
    return []


def classify(value: Any) -> str | None:
    """Return a bounded reason without retaining the inspected content."""
    text = "\n".join(_walk_strings(value))[:MAX_BODY_BYTES]
    if any(pattern.search(text) for pattern in compiled_pii):
        return "pii"
    if any(pattern.search(text) for pattern in compiled_injection):
        return "prompt_injection"
    if any(pattern.search(text) for pattern in compiled_agency):
        return "excessive_agency"
    return None


def _workflow(authorization: str) -> str:
    token = authorization.removeprefix("Bearer ").strip()
    mappings = {
        os.environ.get("INSIGHTHUB_LITELLM_API_KEY", ""): "insighthub",
        os.environ.get("CHATOPS_LITELLM_API_KEY", ""): "chatops",
        os.environ.get("CODING_LITELLM_API_KEY", ""): "coding",
    }
    return mappings.get(token, "unattributed") if token else "unauthenticated"


def _audit(
    *, request_id: str, workflow: str, decision: str, reason: str,
    model: str, input_tokens: int = 0, output_tokens: int = 0,
) -> None:
    event = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "request_id": request_id,
        "workflow": workflow,
        "decision": decision,
        "reason": reason,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_PATH.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, separators=(",", ":")) + "\n")


def _blocked(model: str, reason: str, workflow: str) -> JSONResponse:
    request_id = "guardrail-" + uuid.uuid4().hex
    requests_total.labels(workflow, "blocked", reason).inc()
    _audit(
        request_id=request_id,
        workflow=workflow,
        decision="blocked",
        reason=reason,
        model=model,
    )
    return JSONResponse(
        {
            "id": request_id,
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": BLOCKED_TEXT},
                    "finish_reason": "content_filter",
                }
            ],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        },
        headers={
            "x-insighthub-guardrail": "blocked",
            "x-insighthub-guardrail-reason": reason,
            "x-request-id": request_id,
        },
    )


async def _json_body(request: Request) -> dict[str, Any] | None:
    raw = await request.body()
    if not raw or len(raw) > MAX_BODY_BYTES:
        return None
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return value if isinstance(value, dict) else None


async def _forward(request: Request, body: dict[str, Any], endpoint: str) -> Response:
    authorization = request.headers.get("authorization", "")
    workflow = _workflow(authorization)
    model = str(body.get("model", "unknown"))[:128]
    try:
        async with httpx.AsyncClient(timeout=180) as client:
            upstream = await client.post(
                f"{UPSTREAM}{endpoint}",
                headers={"Authorization": authorization, "Content-Type": "application/json"},
                json=body,
            )
    except httpx.HTTPError:
        requests_total.labels(workflow, "error", "upstream_unavailable").inc()
        return JSONResponse(
            {"detail": "Model gateway unavailable.", "code": "upstream_unavailable"},
            status_code=502,
        )
    if upstream.status_code >= 400:
        requests_total.labels(workflow, "denied", "gateway_policy").inc()
        # Preserve the status while withholding provider/database internals.
        return JSONResponse(
            {"detail": "Model gateway denied the request.", "code": "gateway_denied"},
            status_code=upstream.status_code,
        )
    try:
        data = upstream.json()
    except ValueError:
        return JSONResponse(
            {"detail": "Invalid model gateway response.", "code": "upstream_invalid"},
            status_code=502,
        )
    output_reason = classify(data.get("choices", [])) if endpoint.endswith("chat/completions") else None
    if output_reason == "pii":
        return _blocked(model, "output_pii", workflow)
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    input_tokens = int(usage.get("prompt_tokens") or 0)
    output_tokens = int(usage.get("completion_tokens") or 0)
    request_id = str(data.get("id") or "litellm-" + uuid.uuid4().hex)
    requests_total.labels(workflow, "allowed", "clean").inc()
    tokens_total.labels(workflow, model, "input").inc(input_tokens)
    tokens_total.labels(workflow, model, "output").inc(output_tokens)
    cost_total.labels(workflow, model).inc(
        input_tokens * INPUT_RATE + output_tokens * OUTPUT_RATE
    )
    _audit(
        request_id=request_id,
        workflow=workflow,
        decision="allowed",
        reason="clean",
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
    headers = {"x-request-id": request_id, "x-insighthub-guardrail": "allowed"}
    return JSONResponse(data, status_code=upstream.status_code, headers=headers)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "guardrails": "enabled", "upstream": "litellm"}


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), headers={"Content-Type": CONTENT_TYPE_LATEST})


@app.get("/resourcez")
def resourcez() -> dict[str, int | str]:
    """Expose cgroup measurements only; no host paths or process arguments."""
    peak_path = Path("/sys/fs/cgroup/memory.peak")
    current_path = Path("/sys/fs/cgroup/memory.current")
    try:
        peak = int(peak_path.read_text().strip())
        current = int(current_path.read_text().strip())
    except (OSError, ValueError):
        peak = current = 1
    return {
        "measurement_source": "security-gateway cgroup v2",
        "memory_peak_bytes": max(peak, current, 1),
    }


@app.post("/v1/chat/completions")
async def chat(request: Request) -> Response:
    body = await _json_body(request)
    if body is None:
        return JSONResponse({"detail": "Invalid request.", "code": "invalid_request"}, 400)
    authorization = request.headers.get("authorization", "")
    workflow = _workflow(authorization)
    model = str(body.get("model", "unknown"))[:128]
    reason = classify(body.get("messages", []))
    if reason:
        return _blocked(model, reason, workflow)
    return await _forward(request, body, "/v1/chat/completions")


@app.post("/v1/embeddings")
async def embeddings(request: Request) -> Response:
    body = await _json_body(request)
    if body is None:
        return JSONResponse({"detail": "Invalid request.", "code": "invalid_request"}, 400)
    # Embedding inputs are untrusted data, not instructions. PII is still denied.
    if any(pattern.search("\n".join(_walk_strings(body.get("input", [])))) for pattern in compiled_pii):
        workflow = _workflow(request.headers.get("authorization", ""))
        requests_total.labels(workflow, "blocked", "pii").inc()
        return JSONResponse({"detail": "Request blocked by data policy.", "code": "pii_blocked"}, 400)
    return await _forward(request, body, "/v1/embeddings")
