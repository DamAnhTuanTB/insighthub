"""Narrow mutation adapter using a separate kubeconfig identity."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Protocol


class MutationExecutor(Protocol):
    async def execute(self, action: str, arguments: dict[str, Any]) -> str: ...


class MutationError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class KubectlMutationExecutor:
    _ALLOWED_DEPLOYMENTS = {"api", "worker", "insighthub-api", "insighthub-worker"}

    def __init__(self, kubeconfig: Path | None, context: str, namespace: str) -> None:
        self.kubeconfig = kubeconfig
        self.context = context
        self.namespace = namespace

    async def execute(self, action: str, arguments: dict[str, Any]) -> str:
        if action != "scale_deployment":
            raise MutationError("MUTATION_NOT_ALLOWED")
        deployment = arguments.get("deployment")
        replicas = arguments.get("replicas")
        if deployment not in self._ALLOWED_DEPLOYMENTS or type(replicas) is not int or not 1 <= replicas <= 5:
            raise MutationError("MUTATION_ARGUMENTS_DENIED")
        if self.kubeconfig is None or not self.kubeconfig.is_file():
            raise MutationError("MUTATION_IDENTITY_NOT_CONFIGURED")
        command = ["kubectl", "--kubeconfig", str(self.kubeconfig)]
        if self.context:
            command.extend(["--context", self.context])
        command.extend(
            ["--namespace", self.namespace, "scale", "deployment", str(deployment), f"--replicas={replicas}"]
        )
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=15)
        if process.returncode != 0:
            raise MutationError("MUTATION_FAILED")
        return stdout.decode("utf-8", errors="replace").strip()[:256] or "scale accepted"


class MemoryMutationExecutor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def execute(self, action: str, arguments: dict[str, Any]) -> str:
        self.calls.append((action, arguments))
        return "fixture mutation accepted"
