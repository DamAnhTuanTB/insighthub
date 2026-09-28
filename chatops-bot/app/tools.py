"""Bounded client for the read-only Kubernetes and Prometheus MCP backends."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Protocol


class ToolError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class ToolClient(Protocol):
    async def call(self, backend: str, tool: str, arguments: dict[str, Any]) -> dict[str, Any]: ...


class FixtureToolClient:
    """Deterministic adapter used only by tests and an explicitly labelled fixture run."""

    async def call(self, backend: str, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if backend == "prometheus" and tool == "query":
            query = str(arguments.get("query", ""))
            value = "4" if "worker_jobs_total" in query else "1"
            return {"content": [{"type": "text", "text": value}], "fixture": True}
        if backend == "kubernetes" and tool == "pods_list_in_namespace":
            return {
                "content": [{"type": "text", "text": "NAME READY STATUS\napi-0 1/1 Running\nworker-0 1/1 Running"}],
                "fixture": True,
            }
        raise ToolError("TOOL_NOT_ALLOWED")


class StdioMcpClient:
    """One-shot MCP stdio client reusing the constrained Day 2 launchers."""

    _ALLOWED = {
        ("prometheus", "query"),
        ("kubernetes", "pods_list_in_namespace"),
    }

    def __init__(
        self,
        repository_root: Path,
        timeout_seconds: int = 15,
        kubeconfig: Path | None = None,
    ) -> None:
        self.repository_root = repository_root.resolve()
        self.timeout_seconds = timeout_seconds
        self.kubeconfig = kubeconfig.resolve() if kubeconfig else None
        self.launcher = self.repository_root / "tools" / "mcp" / "day2" / "launch.mjs"

    async def call(self, backend: str, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if (backend, tool) not in self._ALLOWED:
            raise ToolError("TOOL_NOT_ALLOWED")
        if not self.launcher.is_file():
            raise ToolError("MCP_LAUNCHER_MISSING")
        environment = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": os.environ.get("HOME", ""),
        }
        command = self._command(backend)
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(self.repository_root),
            env=environment,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            await self._write(
                process,
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {},
                        "clientInfo": {"name": "insighthub-chatops", "version": "1.0.0"},
                    },
                },
            )
            await self._response(process, 1)
            await self._write(
                process,
                {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
            )
            await self._write(
                process,
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": tool, "arguments": arguments},
                },
            )
            response = await self._response(process, 2)
            if "error" in response:
                raise ToolError("MCP_CALL_REJECTED")
            result = response.get("result")
            if not isinstance(result, dict) or result.get("isError") is True:
                raise ToolError("MCP_TOOL_FAILED")
            return result
        except (asyncio.TimeoutError, json.JSONDecodeError, BrokenPipeError) as exc:
            raise ToolError("MCP_TRANSPORT_FAILED") from exc
        finally:
            if process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=2)
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()

    def _command(self, backend: str) -> list[str]:
        if backend == "prometheus":
            return ["node", str(self.launcher), "prometheus"]
        binary = self.repository_root / "tmp" / "day2" / "bin" / "kubernetes"
        policy = self.repository_root / "tools" / "mcp" / "day2" / "kubernetes.toml"
        if self.kubeconfig is None or not self.kubeconfig.is_file():
            raise ToolError("MCP_KUBECONFIG_MISSING")
        if not binary.is_file() or not policy.is_file():
            raise ToolError("MCP_BACKEND_MISSING")
        return [
            str(binary),
            "--config",
            str(policy),
            "--kubeconfig",
            str(self.kubeconfig),
            "--read-only",
            "--disable-multi-cluster",
            "--toolsets=core",
            "--list-output=table",
        ]

    async def _write(self, process: asyncio.subprocess.Process, message: dict[str, Any]) -> None:
        if process.stdin is None:
            raise ToolError("MCP_TRANSPORT_FAILED")
        process.stdin.write(json.dumps(message, separators=(",", ":")).encode("utf-8") + b"\n")
        await process.stdin.drain()

    async def _response(self, process: asyncio.subprocess.Process, request_id: int) -> dict[str, Any]:
        if process.stdout is None:
            raise ToolError("MCP_TRANSPORT_FAILED")

        async def read_matching() -> dict[str, Any]:
            for _ in range(50):
                line = await process.stdout.readline()
                if not line:
                    break
                message = json.loads(line)
                if message.get("id") == request_id:
                    return message
            raise ToolError("MCP_RESPONSE_MISSING")

        return await asyncio.wait_for(read_matching(), timeout=self.timeout_seconds)


def content_text(result: dict[str, Any], limit: int = 2_000) -> str:
    blocks = result.get("content")
    if not isinstance(blocks, list):
        raise ToolError("MCP_RESULT_INVALID")
    texts = [block.get("text", "") for block in blocks if isinstance(block, dict) and block.get("type") == "text"]
    value = "\n".join(str(text) for text in texts).strip()
    if not value:
        raise ToolError("MCP_RESULT_EMPTY")
    return value[:limit]
