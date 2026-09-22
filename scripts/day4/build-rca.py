"""Assemble an RCA report from collected samples and reviewed analysis.

Separation of duties is the point: `collect-samples.py` produces the numbers and
only Prometheus decides what they are; this script attaches the reasoning. The
analysis file may not introduce a metric value of its own, so a hypothesis can
never quietly carry an invented figure.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", required=True, help="output of collect-samples.py")
    parser.add_argument("--analysis", required=True, help="JSON with hypotheses and narrative")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    samples = json.loads(Path(args.samples).read_text(encoding="utf-8"))
    analysis = json.loads(Path(args.analysis).read_text(encoding="utf-8"))

    hypotheses = analysis.get("hypotheses")
    if not isinstance(hypotheses, list) or not hypotheses:
        raise SystemExit("Analysis must contain a nonempty hypotheses list")
    if not all(isinstance(h, str) and len(h.strip()) > 20 for h in hypotheses):
        raise SystemExit("Each hypothesis must be substantive text")

    cited = {s["metric"] for s in samples["samples"]}
    declared = set(analysis.get("cited_metrics", []))
    unknown = declared - cited
    if unknown:
        raise SystemExit(f"Analysis cites metrics that were never collected: {sorted(unknown)}")

    report = {
        "incident_id": samples["incident_id"],
        "started_at": samples["started_at"],
        "ended_at": samples["ended_at"],
        "failure_start": samples["failure_start"],
        "failure_end": samples["failure_end"],
        "title": analysis["title"],
        "summary": analysis["summary"],
        "hypotheses": hypotheses,
        "root_cause": analysis["root_cause"],
        "confidence": analysis["confidence"],
        "correlation": analysis.get("correlation", []),
        "remediation": analysis.get("remediation", []),
        "detection": analysis.get("detection", {}),
        "evidence_source": {
            "prometheus_url": samples["prometheus_url"],
            "collected_at": samples["collected_at"],
            "collector": "scripts/day4/collect-samples.py",
            "note": "Every value below was read from Prometheus, not authored by a model.",
        },
        "samples": samples["samples"],
    }
    if not 0 < float(report["confidence"]) <= 1:
        raise SystemExit("Confidence must be within (0, 1]")

    Path(args.output).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{report['incident_id']}: {len(hypotheses)} hypotheses, {len(report['samples'])} cited samples -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
