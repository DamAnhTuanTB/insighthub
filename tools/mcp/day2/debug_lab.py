"""Exercise a bounded worker outage, investigate through MCP, and recover."""

from __future__ import annotations

import json
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from host_probe import HostClient, ROOT


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def api_request(origin: str, route: str, data: bytes | None = None,
                headers: dict[str, str] | None = None, method: str = "GET") -> tuple[int, Any]:
    request = urllib.request.Request(origin + route, data=data, headers=headers or {}, method=method)
    with urllib.request.urlopen(request, timeout=5) as response:
        body = response.read(262145)
        if len(body) > 262144:
            raise RuntimeError("API_RESPONSE_TOO_LARGE")
        return response.status, json.loads(body) if body else None


def run() -> None:
    host = HostClient()
    record: dict[str, Any] = {"incident_id": "day2-controlled-worker-outage", "mode": "live",
        "started_at": timestamp(), "host_api": "Codex app-server", "model_turn_started": False,
        "fault": "Operator-controlled Compose stop with timeout 0 (SIGKILL); no volume teardown.", "calls": []}
    document_id: int | None = None
    stopped = False
    origin = "http://" + subprocess.check_output(["docker", "compose", "port", "api", "8000"], cwd=ROOT, text=True).strip()
    try:
        host.request("initialize", {"clientInfo": {"name": "insighthub_day2_debug", "version": "1.0.0"}, "capabilities": {"experimentalApi": True}})
        host.send({"method": "initialized"})
        thread = host.request("thread/start", {"cwd": str(ROOT), "ephemeral": True, "sandbox": "read-only", "approvalPolicy": "never"})
        thread_id = thread["thread"]["id"]
        record["thread_id"] = thread_id

        def call(backend: str, tool: str, arguments: dict[str, Any], phase: str) -> dict[str, Any]:
            output = host.request("mcpServer/tool/call", {"threadId": thread_id, "server": backend, "tool": tool, "arguments": arguments})
            if output.get("isError"):
                raise RuntimeError("DEBUG_MCP_CALL_FAILED")
            record["calls"].append({"phase": phase, "backend": backend, "tool": tool, "input": arguments, "output": output, "timestamp": timestamp()})
            return output

        before = call("docker", "docker_inspect_container", {"service": "ingestion-worker"}, "before")
        assert before["structuredContent"]["running"] is True
        stopped = True
        subprocess.run(["docker", "compose", "stop", "-t", "0", "ingestion-worker"], cwd=ROOT, check=True, timeout=20, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        call("docker", "docker_list_containers", {}, "outage")
        during = call("docker", "docker_inspect_container", {"service": "ingestion-worker"}, "outage")
        state = during["structuredContent"]
        assert state["running"] is False and state["exit_code"] == 137 and state["oom_killed"] is False
        call("docker", "docker_worker_events", {"tail": 10}, "outage")
        call("prometheus", "query", {"query": 'up{job="insighthub-api"}'}, "outage")
        status, _ = api_request(origin, "/healthz")
        assert status == 200
        record["api_live_during_outage"] = True
        boundary = "insighthubday2boundedlab"
        data = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"day2-local-outage.txt\"\r\nContent-Type: text/plain\r\n\r\n"
                "Day 2 local worker availability lab. No credentials or personal information.\r\n"
                f"--{boundary}--\r\n").encode()
        start = time.monotonic()
        status, upload = api_request(origin, "/documents", data, {"Content-Type": f"multipart/form-data; boundary={boundary}"}, "POST")
        record["upload_latency_seconds"] = round(time.monotonic() - start, 4)
        document_id = upload["id"]
        record["document_id"] = document_id
        record["upload_status"] = status
        assert status == 202 and upload["status"] == "pending" and record["upload_latency_seconds"] < 1
        _, documents = api_request(origin, "/documents")
        pending = next(row for row in documents if row["id"] == document_id)
        assert pending["status"] == "pending"
        record["document_pending_during_outage"] = True
        subprocess.run(["docker", "compose", "start", "ingestion-worker"], cwd=ROOT, check=True, timeout=20, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        stopped = False
        start = time.monotonic()
        ready = False
        while time.monotonic() - start < 30:
            _, documents = api_request(origin, "/documents")
            document = next(row for row in documents if row["id"] == document_id)
            if document["status"] == "ready":
                ready = True
                break
            if document["status"] == "failed":
                raise RuntimeError("LAB_INGESTION_FAILED")
            time.sleep(0.25)
        assert ready
        record["ready_after_restart_seconds"] = round(time.monotonic() - start, 4)
        call("docker", "docker_inspect_container", {"service": "ingestion-worker"}, "recovered")
        call("docker", "docker_worker_events", {"tail": 20}, "recovered")
        record["conclusion"] = "The worker was deliberately stopped with SIGKILL. Exit 137 alone does not establish OOM; oom_killed=false. API and queue remained available; the pending job completed after worker restart."
        record["passed"] = True
        print(json.dumps({key: record[key] for key in ["incident_id", "passed", "upload_status", "upload_latency_seconds", "ready_after_restart_seconds"]}), flush=True)
    except Exception:
        record["passed"] = False
        record["error_code"] = "DAY2_DEBUG_LAB_FAILED"
        print(json.dumps({"passed": False, "error_code": record["error_code"]}), flush=True)
    finally:
        if stopped:
            recovery = subprocess.run(["docker", "compose", "start", "ingestion-worker"], cwd=ROOT, timeout=20, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            record["emergency_recovery_started"] = recovery.returncode == 0
        if document_id is not None:
            try:
                status, _ = api_request(origin, f"/documents/{document_id}", method="DELETE")
                record["lab_document_deleted"] = status == 204
            except Exception:
                record["lab_document_deleted"] = False
        host.close()
        record["ended_at"] = timestamp()
        (ROOT / "evidence/day2-debug.json").write_text(json.dumps(record, indent=2) + "\n")
    if not record["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    run()
