"""Wrap the promtool-validated rule file into a PrometheusRule CRD.

The rule groups under observability/rules are the single source of truth. This
script only adds Kubernetes metadata so the file that promtool tests and the
rules Prometheus evaluates cannot drift apart.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def render(rules_path: Path, name: str, namespace: str, release: str) -> dict:
    document = yaml.safe_load(rules_path.read_text(encoding="utf-8"))
    groups = document.get("groups") if isinstance(document, dict) else None
    if not groups:
        raise SystemExit(f"No rule groups found in {rules_path}")
    return {
        "apiVersion": "monitoring.coreos.com/v1",
        "kind": "PrometheusRule",
        "metadata": {
            "name": name,
            "namespace": namespace,
            "labels": {
                "app.kubernetes.io/name": "insighthub",
                "app.kubernetes.io/component": "observability",
                # kube-prometheus-stack selects rules carrying its release label.
                "release": release,
            },
        },
        "spec": {"groups": groups},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rules", default=str(ROOT / "observability/rules/day4-rules.yaml"))
    parser.add_argument("--name", default="insighthub-day4")
    parser.add_argument("--namespace", default="monitoring")
    parser.add_argument("--release", default="kube-prom-stack")
    parser.add_argument("--output", default="-")
    args = parser.parse_args()

    manifest = render(Path(args.rules), args.name, args.namespace, args.release)
    text = yaml.safe_dump(manifest, sort_keys=False, default_flow_style=False, width=4096)
    if args.output == "-":
        sys.stdout.write(text)
    else:
        Path(args.output).write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
