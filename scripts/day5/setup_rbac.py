"""Create a short-lived kubeconfig for the namespace-scoped ChatOps MCP identity."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "tmp" / "day5" / "mcp-readonly.yaml"
CONTEXT = os.environ.get("KUBE_CONTEXT", "kind-insighthub-day2")
NAMESPACE = os.environ.get("NAMESPACE", "insighthub-dev")


def kubectl(*arguments: str) -> str:
    result = subprocess.run(
        ["kubectl", "--context", CONTEXT, *arguments],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if result.returncode:
        raise SystemExit("ChatOps RBAC setup failed; verify the selected local context.")
    return result.stdout


def setup() -> None:
    if NAMESPACE != "insighthub-dev":
        raise SystemExit("ChatOps local RBAC is restricted to insighthub-dev.")
    kubectl("apply", "-f", str(ROOT / "chatops-bot" / "k8s" / "read-only-rbac.yaml"))
    token = kubectl(
        "create",
        "token",
        "chatops-readonly",
        "--namespace",
        NAMESPACE,
        "--duration=8h",
    ).strip()
    config = json.loads(kubectl("config", "view", "--raw", "--minify", "-o", "json"))
    if not token:
        raise SystemExit("ChatOps ServiceAccount token was not issued.")
    output = {
        "apiVersion": "v1",
        "kind": "Config",
        "clusters": [{"name": "insighthub-local", "cluster": config["clusters"][0]["cluster"]}],
        "users": [{"name": "chatops-readonly", "user": {"token": token}}],
        "contexts": [
            {
                "name": CONTEXT,
                "context": {
                    "cluster": "insighthub-local",
                    "user": "chatops-readonly",
                    "namespace": NAMESPACE,
                },
            }
        ],
        "current-context": CONTEXT,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(OUTPUT, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(json.dumps(output, indent=2) + "\n")
    OUTPUT.chmod(0o600)
    print("ChatOps read-only ServiceAccount and private 8-hour kubeconfig are ready.")


if __name__ == "__main__":
    setup()
