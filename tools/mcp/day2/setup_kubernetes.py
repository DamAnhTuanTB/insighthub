"""Apply lab RBAC and write a short-lived, private, namespace-scoped kubeconfig."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
ADMIN = ROOT / "tmp/day2/admin-kubeconfig.yaml"
READONLY = ROOT / "tmp/day2/mcp-readonly.yaml"
CONTEXT = "kind-insighthub-day2"


def kubectl(*args: str) -> str:
    result = subprocess.run(
        ["kubectl", "--kubeconfig", str(ADMIN), "--context", CONTEXT, *args],
        capture_output=True, text=True, check=False, timeout=30,
    )
    if result.returncode:
        raise SystemExit("Kubernetes lab setup failed; verify local cluster connectivity.")
    return result.stdout


def setup() -> None:
    kubectl("apply", "-f", str(ROOT / "tools/mcp/day2/rbac.yaml"))
    kubectl("apply", "-f", str(ROOT / "tools/mcp/day2/sample-pod.yaml"))
    config = json.loads(kubectl("config", "view", "--raw", "--minify", "-o", "json"))
    token = kubectl("create", "token", "mcp-readonly", "-n", "insighthub", "--duration=8h").strip()
    if not token:
        raise SystemExit("ServiceAccount token was not issued.")
    output = {
        "apiVersion": "v1", "kind": "Config",
        "clusters": [{"name": "insighthub-day2", "cluster": config["clusters"][0]["cluster"]}],
        "users": [{"name": "mcp-readonly", "user": {"token": token}}],
        "contexts": [{"name": CONTEXT, "context": {
            "cluster": "insighthub-day2", "user": "mcp-readonly", "namespace": "insighthub",
        }}],
        "current-context": CONTEXT,
    }
    READONLY.parent.mkdir(parents=True, exist_ok=True)
    # JSON is accepted as Kubernetes configuration, even with a .yaml suffix.
    descriptor = os.open(READONLY, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        stream.write(json.dumps(output, indent=2) + "\n")
    READONLY.chmod(0o600)
    ADMIN.chmod(0o600)
    print("Applied namespace-scoped RBAC and sample pod; private 8-hour kubeconfig written.")


if __name__ == "__main__":
    setup()
