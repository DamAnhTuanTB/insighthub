#!/usr/bin/env python3
"""Aggregate the week's lab cost from recorded evidence only.

Every figure comes from a committed artifact. A cost that no artifact records
is listed as unmeasured with a null amount; it is never estimated or typed in.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

AWS_UNVERIFIED = re.compile(r"AWS verified:\s*\*\*false\*\*")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} is not a JSON object")
    return data


def source(repo: Path, rel: str) -> dict[str, str]:
    return {"path": rel, "sha256": sha256(repo / rel)}


def gateway_line(repo: Path) -> dict[str, Any]:
    rel = "security/reports/cost-report.json"
    report = load(repo / rel)
    entries = report["entries"]
    total = round(sum(float(e["cost_usd"]) for e in entries), 6)
    if abs(total - float(report["total_usd"])) > 1e-6:
        raise ValueError("cost-report total does not match its entries")
    return {
        "day": 6,
        "component": "LiteLLM gateway -> Ollama (security eval)",
        "cost_usd": total,
        "budget_usd": float(report["budget_usd"]),
        "requests": len(entries),
        "basis": report["pricing_basis"],
        "source": source(repo, rel),
    }


def aws_line(repo: Path) -> dict[str, Any]:
    day6 = load(repo / "evidence/day6.json")
    reviews = ["evidence/day3-local-review.md", "evidence/day4-review.md"]
    unverified = all(AWS_UNVERIFIED.search((repo / r).read_text(encoding="utf-8")) for r in reviews)
    if day6["review"]["aws_used"] is not False or not unverified:
        raise ValueError("AWS usage is recorded; add its billing export instead of reporting zero")
    return {
        "day": "3-6",
        "component": "AWS (EKS/RDS/ElastiCache/Budgets)",
        "cost_usd": 0.0,
        "basis": "No AWS resource was provisioned; all profiles ran on local Docker/kind.",
        "source": [source(repo, "evidence/day6.json")] + [source(repo, r) for r in reviews],
    }


def provider_line(repo: Path) -> dict[str, Any]:
    day2 = load(repo / "evidence/day2.json")
    deployment = (repo / "evidence/day3-local-deployment.yaml").read_text(encoding="utf-8")
    if day2.get("application_provider_mode") != "fixture" or 'LLM_PROVIDER: "fixture"' not in deployment:
        raise ValueError("Application provider was not fixture; add its usage export instead of reporting zero")
    return {
        "day": "2-5",
        "component": "Application LLM/embedding provider",
        "cost_usd": 0.0,
        "basis": "Labeled fixture provider (Day 2, Day 3 deployment, Day 4 no provider token series); "
                 "the Day 5 bot calls MCP backends only, no LLM.",
        "source": [source(repo, r) for r in
                   ("evidence/day2.json", "evidence/day3-local-deployment.yaml", "evidence/day4-review.md")],
    }


def unmeasured() -> list[dict[str, Any]]:
    return [
        {"component": "Day 1 application provider", "cost_usd": None,
         "basis": "Day 1 evidence does not record the provider mode; owner confirms fixture or adds usage."},
        {"component": "Coding agent host subscription (IDE/CLI quota)", "cost_usd": None,
         "basis": "Reported separately from API cost per specification; owner fills from own billing."},
        {"component": "Slack workspace, HTTPS tunnel, GitHub account", "cost_usd": None,
         "basis": "No billing artifact in repository; owner confirms plan (free tier or paid)."},
    ]


def build(repo: Path) -> dict[str, Any]:
    lines = [provider_line(repo), aws_line(repo), gateway_line(repo)]
    measured = round(sum(line["cost_usd"] for line in lines), 6)
    budget = next(line["budget_usd"] for line in lines if "budget_usd" in line)
    return {
        "schema_version": 1,
        "day": 7,
        "observed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "currency": "USD",
        "measured_total_usd": measured,
        "lab_budget_usd": budget,
        "within_budget": measured <= budget,
        "aws_running": False,
        "lines": lines,
        "unmeasured": unmeasured(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--out", type=Path, default=Path("evidence/day7-cost-report.json"))
    args = parser.parse_args()
    report = build(args.repo)
    out = args.out if args.out.is_absolute() else args.repo / args.out
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"measured_total_usd={report['measured_total_usd']} within_budget={report['within_budget']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
