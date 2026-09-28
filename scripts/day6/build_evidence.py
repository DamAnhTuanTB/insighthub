#!/usr/bin/env python3
"""Bind live Day 6 reports to the settled source fingerprint."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fingerprint() -> str:
    result = subprocess.run(
        ["python3", "-B", "scripts/verify.py", "fingerprint"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def main() -> None:
    paths = {
        "dataset": ROOT / "security/datasets/day6-cases.json",
        "eval_initial": ROOT / "security/reports/eval-initial.json",
        "eval_final": ROOT / "security/reports/eval-final.json",
        "cost": ROOT / "security/reports/cost-report.json",
    }
    for path in [
        *paths.values(),
        ROOT / "security/reports/red-team-initial.json",
        ROOT / "security/reports/red-team-final.json",
        ROOT / "security/reports/workload-traces.json",
    ]:
        if not path.is_file() or path.stat().st_size == 0:
            raise SystemExit(f"missing live report: {path.relative_to(ROOT)}")
    source = fingerprint()
    initial = json.loads(paths["eval_initial"].read_text(encoding="utf-8"))
    final = json.loads(paths["eval_final"].read_text(encoding="utf-8"))
    cost = json.loads(paths["cost"].read_text(encoding="utf-8"))
    if initial.get("source_sha256") != source or final.get("source_sha256") != source:
        raise SystemExit("evaluation source fingerprint is stale")
    if not any(not row.get("passed") for row in initial.get("results", [])):
        raise SystemExit("initial scan did not record an open finding")
    if not final.get("results") or not all(row.get("passed") for row in final["results"]):
        raise SystemExit("final scan is not clean")
    if cost.get("source_sha256") != source:
        raise SystemExit("cost report source fingerprint is stale")
    evidence = {
        "schema_version": 1,
        "day": 6,
        "mode": "real",
        "observed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_sha256": source,
        "artifacts": {
            role: {
                "path": str(path.relative_to(ROOT)),
                "sha256": digest(path),
            }
            for role, path in paths.items()
        },
        "review": {
            "cases": len(final["results"]),
            "final_high_or_critical_open": final["summary"]["high_or_critical_open"],
            "runtime": "LiteLLM/PostgreSQL -> Ollama, guarded by security-gateway",
            "aws_used": False,
        },
    }
    output = ROOT / "evidence/day6.json"
    output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {output.relative_to(ROOT)} for source {source[:12]}.")


if __name__ == "__main__":
    main()
