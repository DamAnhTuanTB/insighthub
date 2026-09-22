"""Collect real Prometheus samples for an incident window.

The Day 4 verifier re-queries every cited sample and compares it to live
telemetry within 1e-6. Values therefore have to come out of Prometheus, never
out of a model's summary of it. This script is the only thing that writes the
numbers an RCA report is allowed to cite.
"""

from __future__ import annotations

import argparse
import json
import math
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Signals worth citing per incident: the breached band, its inputs, and the
# dependency that explains it.
INCIDENT_QUERIES = {
    "incident-1": [
        "insighthub:llm_latency_p95:5m",
        "insighthub:llm_latency_p95:anomaly_upper",
        "insighthub:rag_latency_p95:5m",
        'insighthub_llm_call_latency_seconds_count{job="insighthub-api"}',
    ],
    "incident-2": [
        'insighthub_worker_queue_depth{job="insighthub-worker"}',
        "insighthub:queue_depth:avg5m",
        "insighthub:queue_depth:anomaly_upper",
        'insighthub_worker_up{job="insighthub-worker"}',
    ],
    "incident-3": [
        "insighthub:http_error_ratio:5m",
        "insighthub:http_error_ratio:anomaly_upper",
        'pg_up{job="insighthub-postgres-exporter"}',
        'up{job="insighthub-api"}',
    ],
}


def rfc3339(epoch: float) -> str:
    """Round a sample timestamp UP to whole seconds.

    The verifier re-queries each citation at exactly this second, and Prometheus
    answers with the most recent sample at or before it. Truncating downwards can
    land just before the sample being cited and return the previous value
    instead, which reads as a mismatch even though the number is real.
    """
    return datetime.fromtimestamp(math.ceil(epoch), UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse(value: str) -> float:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC).timestamp()


def query_range(base: str, expr: str, start: float, end: float, step: int, timeout: float):
    params = urllib.parse.urlencode({"query": expr, "start": start, "end": end, "step": step})
    with urllib.request.urlopen(f"{base}/api/v1/query_range?{params}", timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("status") != "success":
        raise SystemExit(f"Prometheus rejected the query: {expr}")
    return payload["data"].get("result", [])


def pick(series_list, wanted: int):
    """Take evenly spaced points from the longest series so the citation covers
    the whole window rather than one convenient spike."""
    if not series_list:
        return []
    series = max(series_list, key=lambda s: len(s.get("values", [])))
    labels = {k: v for k, v in series.get("metric", {}).items() if k != "__name__"}
    name = series.get("metric", {}).get("__name__")
    points = [(float(ts), value) for ts, value in series.get("values", [])]
    points = [(ts, v) for ts, v in points if v not in {"NaN", "+Inf", "-Inf"}]
    if not points:
        return []
    if len(points) <= wanted:
        chosen = points
    else:
        stride = (len(points) - 1) / (wanted - 1) if wanted > 1 else 1
        chosen = [points[round(i * stride)] for i in range(wanted)]
    return [(name, labels, ts, float(v)) for ts, v in chosen]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--window", required=True, help="incident window JSON from scripts/chaos")
    parser.add_argument("--prometheus-url", default="http://127.0.0.1:9090")
    parser.add_argument("--step", type=int, default=30)
    parser.add_argument("--samples-per-query", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=20)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    window = json.loads(Path(args.window).read_text(encoding="utf-8"))
    incident = window["incident_id"]
    queries = INCIDENT_QUERIES.get(incident)
    if not queries:
        raise SystemExit(f"No query set defined for {incident}")

    start = parse(window["baseline_start"])
    end = parse(window["recovery_end"])

    samples = []
    for expr in queries:
        result = query_range(args.prometheus_url.rstrip("/"), expr, start, end, args.step, args.timeout)
        for name, labels, ts, value in pick(result, args.samples_per_query):
            if not name:
                # Recording rules and bare selectors always carry __name__; an
                # expression without one cannot be re-queried by the verifier.
                continue
            at = rfc3339(ts)
            if at > window["recovery_end"]:
                # Rounding up must not push a citation past the declared window.
                continue
            samples.append({
                "metric": name,
                "labels": labels,
                "timestamp": at,
                "value": value,
            })

    if not samples:
        raise SystemExit("No samples collected; is the incident window inside Prometheus retention?")

    document = {
        "incident_id": incident,
        "started_at": window["baseline_start"],
        "ended_at": window["recovery_end"],
        "failure_start": window["failure_start"],
        "failure_end": window["failure_end"],
        "prometheus_url": args.prometheus_url,
        "collected_at": rfc3339(datetime.now(UTC).timestamp()),
        "samples": samples,
    }
    Path(args.output).write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print(f"{incident}: {len(samples)} samples from {len(queries)} queries -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
