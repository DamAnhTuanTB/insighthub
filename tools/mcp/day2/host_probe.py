"""Call read-only MCP tools through Codex's host API; never start a model turn."""

from __future__ import annotations

import json
import selectors
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]


class HostClient:
    def __init__(self) -> None:
        self.process = subprocess.Popen(
            ["codex", "app-server", "--stdio"], cwd=ROOT,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, bufsize=1,
        )
        self.sequence = 0
        self.startup: list[dict[str, Any]] = []
        self.selector = selectors.DefaultSelector()
        assert self.process.stdout is not None
        self.selector.register(self.process.stdout, selectors.EVENT_READ)

    def send(self, message: dict[str, Any]) -> None:
        assert self.process.stdin is not None
        self.process.stdin.write(json.dumps(message) + "\n")
        self.process.stdin.flush()

    def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self.sequence += 1
        sequence = self.sequence
        self.send({"id": sequence, "method": method, "params": params})
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if not self.selector.select(timeout=min(1, deadline - time.monotonic())):
                continue
            assert self.process.stdout is not None
            line = self.process.stdout.readline()
            if not line:
                raise RuntimeError("HOST_DISCONNECTED")
            message = json.loads(line)
            if message.get("method") == "mcpServer/startupStatus/updated":
                row = message["params"]
                if row.get("name") in {"filesystem", "docker", "kubernetes", "prometheus"}:
                    self.startup.append({"name": row["name"], "status": row.get("status")})
            if message.get("id") == sequence:
                if "error" in message:
                    raise RuntimeError(f"HOST_RPC_ERROR_{message['error'].get('code', 'UNKNOWN')}")
                return message["result"]
            if "id" in message and "method" in message:
                # No approval/elicitation is necessary for the selected read-only tools.
                self.send({"id": message["id"], "error": {"code": -32601, "message": "Unsupported host request"}})
        raise RuntimeError("HOST_REQUEST_TIMEOUT")

    def close(self) -> None:
        if self.process.stdin:
            self.process.stdin.close()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            self.process.wait(timeout=5)
        self.selector.close()


def probe() -> None:
    client = HostClient()
    result: dict[str, Any] = {
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "host": subprocess.check_output(["codex", "--version"], text=True).strip(),
        "host_api": "Codex app-server mcpServer/tool/call",
        "mode": "live", "model_turn_started": False, "milestone_complete": False,
        "calls": [],
    }
    try:
        client.request("initialize", {"clientInfo": {"name": "insighthub_day2_lab", "version": "1.0.0"}, "capabilities": {"experimentalApi": True}})
        client.send({"method": "initialized"})
        # Initialize MCP in an ephemeral control session, without invoking turn/start.
        thread = client.request("thread/start", {"cwd": str(ROOT), "ephemeral": True, "sandbox": "read-only", "approvalPolicy": "never"})
        thread_id = thread["thread"]["id"]
        result["thread_id"] = thread_id
        for backend, tool, arguments in [
            ("filesystem", "list_directory", {"path": "."}),
            ("docker", "docker_list_containers", {}),
            ("docker", "docker_inspect_container", {"service": "ingestion-worker"}),
            ("docker", "docker_worker_events", {"tail": 10}),
            ("kubernetes", "pods_list_in_namespace", {"namespace": "insighthub"}),
            ("prometheus", "query", {"query": "up"}),
        ]:
            output = client.request("mcpServer/tool/call", {"threadId": thread_id, "server": backend, "tool": tool, "arguments": arguments})
            passed = output.get("isError") is not True
            result["calls"].append({"backend": backend, "tool": tool, "input": arguments, "output": output,
                "timestamp": datetime.now(timezone.utc).isoformat(), "passed": passed})
            print(json.dumps({"host": "codex", "backend": backend, "tool": tool, "passed": passed}), flush=True)
        inventory = client.request("mcpServerStatus/list", {"threadId": thread_id, "detail": "toolsAndAuthOnly", "limit": 100})
        result["servers"] = [{"name": row["name"], "tools": list(row.get("tools", {})), "auth_status": row.get("authStatus"),
            "runtime_status": row.get("runtimeStatus"), "server_info": row.get("serverInfo")}
            for row in inventory["data"] if row["name"] in {"filesystem", "docker", "kubernetes", "prometheus"}]
        result["configured_model"] = thread.get("model")
        account = client.request("account/read", {"refreshToken": False})
        result["auth_mode"] = (account.get("account") or {}).get("type")
        result["passed"] = len(result["servers"]) == 4 and all(row["tools"] for row in result["servers"]) and all(call["passed"] for call in result["calls"])
    except (RuntimeError, KeyError) as error:
        result["passed"] = False
        result["error_code"] = str(error) if isinstance(error, RuntimeError) else "HOST_RESPONSE_SHAPE_FAILED"
        print(json.dumps({"passed": False, "error_code": result["error_code"]}), flush=True)
    finally:
        result["startup"] = client.startup
        client.close()
        destination = ROOT / "evidence/day2-host.json"
        destination.parent.mkdir(exist_ok=True)
        destination.write_text(json.dumps(result, indent=2) + "\n")
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    probe()
