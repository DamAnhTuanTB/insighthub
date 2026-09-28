#!/usr/bin/env python3
"""Run pinned Promptfoo without placing virtual keys on the command line."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("initial", "final"))
    args = parser.parse_args()
    keys = json.loads((ROOT / "tmp/day6/keys.json").read_text(encoding="utf-8"))
    target = "http://127.0.0.1:14000" if args.phase == "initial" else "http://127.0.0.1:4001"
    report_dir = ROOT / "security/reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    command = [
        str(ROOT / "security/node_modules/.bin/promptfoo"),
        "eval",
        "-c",
        "eval-config.yaml",
        "--no-cache",
        "--no-share",
        "--no-progress-bar",
        "--no-table",
        "--max-concurrency",
        "1",
        "--output",
        f"reports/red-team-{args.phase}.json",
        f"reports/red-team-{args.phase}.html",
    ]
    env = dict(
        os.environ,
        DAY6_TARGET_URL=target,
        DAY6_API_KEY=keys["insighthub"],
        PROMPTFOO_DISABLE_TELEMETRY="1",
    )
    result = subprocess.run(command, cwd=ROOT / "security", env=env)
    # Assertion failures are expected in the unguarded baseline. Infrastructure
    # errors still fail because they do not produce a complete JSON report.
    output = report_dir / f"red-team-{args.phase}.json"
    if not output.is_file() or output.stat().st_size == 0:
        raise SystemExit(result.returncode or 1)
    payload = json.loads(output.read_text(encoding="utf-8"))
    table = payload.get("results", {}).get("results")
    if not isinstance(table, list) or len(table) != 62:
        raise SystemExit("Promptfoo did not execute all 62 fixed cases")
    if args.phase == "final" and result.returncode != 0:
        raise SystemExit("Final Promptfoo evaluation contains a failed assertion")
    print(f"Promptfoo {args.phase}: executed 62 live cases (secrets not displayed).")


if __name__ == "__main__":
    main()
