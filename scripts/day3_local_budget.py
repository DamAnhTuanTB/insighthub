#!/usr/bin/env python3
"""Summarize Kubernetes requests/limits for the local Day 3 deployment."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import yaml


CPU_SUFFIXES = {"m": 0.001}
MEMORY_SUFFIXES = {
    "Ki": 1024,
    "Mi": 1024**2,
    "Gi": 1024**3,
    "Ti": 1024**4,
    "K": 1000,
    "M": 1000**2,
    "G": 1000**3,
    "T": 1000**4,
}
WORKLOAD_KINDS = {"Deployment", "StatefulSet"}


def _quantity(value: object, suffixes: dict[str, float]) -> float:
    text = str(value)
    for suffix, multiplier in suffixes.items():
        if text.endswith(suffix):
            number = float(text[: -len(suffix)])
            break
    else:
        number = float(text)
        multiplier = 1.0
    result = number * multiplier
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"invalid resource quantity: {text}")
    return result


def _containers(document: dict[str, Any]) -> list[dict[str, Any]]:
    return document["spec"]["template"]["spec"].get("containers", [])


def summarize(documents: list[dict[str, Any]]) -> dict[str, object]:
    totals = {
        "cpu_request_cores": 0.0,
        "cpu_limit_cores": 0.0,
        "memory_request_bytes": 0.0,
        "memory_limit_bytes": 0.0,
    }
    workloads = []
    for document in documents:
        if document.get("kind") not in WORKLOAD_KINDS:
            continue
        replicas = int(document.get("spec", {}).get("replicas", 1))
        name = document.get("metadata", {}).get("name", "unknown")
        workloads.append({"kind": document["kind"], "name": name, "replicas": replicas})
        for container in _containers(document):
            resources = container.get("resources", {})
            requests = resources.get("requests", {})
            limits = resources.get("limits", {})
            required = {
                "cpu request": requests.get("cpu"),
                "cpu limit": limits.get("cpu"),
                "memory request": requests.get("memory"),
                "memory limit": limits.get("memory"),
            }
            missing = [key for key, value in required.items() if value is None]
            if missing:
                raise ValueError(f"{name}/{container.get('name')} missing {', '.join(missing)}")
            totals["cpu_request_cores"] += replicas * _quantity(requests["cpu"], CPU_SUFFIXES)
            totals["cpu_limit_cores"] += replicas * _quantity(limits["cpu"], CPU_SUFFIXES)
            totals["memory_request_bytes"] += replicas * _quantity(requests["memory"], MEMORY_SUFFIXES)
            totals["memory_limit_bytes"] += replicas * _quantity(limits["memory"], MEMORY_SUFFIXES)
    if not workloads:
        raise ValueError("manifest contains no Deployment or StatefulSet")
    totals["cpu_request_cores"] = round(totals["cpu_request_cores"], 6)
    totals["cpu_limit_cores"] = round(totals["cpu_limit_cores"], 6)
    totals["memory_request_bytes"] = int(totals["memory_request_bytes"])
    totals["memory_limit_bytes"] = int(totals["memory_limit_bytes"])
    return {
        "deployment_profile": "local-kubernetes",
        "aws_verified": False,
        "workloads": workloads,
        "totals": totals,
        "note": "Capacity declaration only; this is not an AWS or monetary estimate.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    documents = [item for item in yaml.safe_load_all(args.manifest.read_text()) if isinstance(item, dict)]
    result = json.dumps(summarize(documents), indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(result, encoding="utf-8")
    else:
        print(result, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
