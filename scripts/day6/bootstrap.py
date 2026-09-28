#!/usr/bin/env python3
"""Create ignored local secrets and three budgeted LiteLLM virtual keys."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets
import stat
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DIR = ROOT / "tmp" / "day6"
ENV_PATH = RUNTIME_DIR / "runtime.env"
KEYS_PATH = RUNTIME_DIR / "keys.json"


def read_env() -> dict[str, str]:
    values: dict[str, str] = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key] = value
    return values


def write_env(values: dict[str, str]) -> None:
    ENV_PATH.write_text(
        "\n".join(f"{key}={values[key]}" for key in sorted(values)) + "\n",
        encoding="utf-8",
    )
    ENV_PATH.chmod(stat.S_IRUSR | stat.S_IWUSR)


def initialize() -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    (RUNTIME_DIR / "audit").mkdir(exist_ok=True)
    values = read_env()
    values.setdefault("LITELLM_MASTER_KEY", "sk-" + secrets.token_hex(32))
    values.setdefault("LITELLM_SALT_KEY", "sk-" + secrets.token_hex(32))
    # Compose validates these before the management API has minted real keys.
    values.setdefault("INSIGHTHUB_LITELLM_API_KEY", "sk-pending-insighthub")
    values.setdefault("CHATOPS_LITELLM_API_KEY", "sk-pending-chatops")
    values.setdefault("CODING_LITELLM_API_KEY", "sk-pending-coding")
    write_env(values)
    print("Initialized ignored Day 6 runtime credentials (values not displayed).")


def post(url: str, token: str, payload: dict) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            value = json.load(response)
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"LiteLLM management request failed with HTTP {exc.code}") from None
    if not isinstance(value, dict):
        raise SystemExit("LiteLLM management response was not an object")
    return value


def generate_keys(base_url: str) -> None:
    initialize()
    values = read_env()
    if KEYS_PATH.exists():
        saved = json.loads(KEYS_PATH.read_text(encoding="utf-8"))
        if all(saved.get(name) for name in ("insighthub", "chatops", "coding")):
            values.update(
                {
                    "INSIGHTHUB_LITELLM_API_KEY": saved["insighthub"],
                    "CHATOPS_LITELLM_API_KEY": saved["chatops"],
                    "CODING_LITELLM_API_KEY": saved["coding"],
                }
            )
            write_env(values)
            print("Reused three ignored LiteLLM virtual keys (values not displayed).")
            return
    keys: dict[str, str] = {}
    for workflow in ("insighthub", "chatops", "coding"):
        result = post(
            base_url.rstrip("/") + "/key/generate",
            values["LITELLM_MASTER_KEY"],
            {
                "key_alias": f"day6-{workflow}",
                "models": ["insighthub-chat", "insighthub-embedding"],
                "max_budget": 1.0,
                "budget_duration": "30d",
                "rpm_limit": 120,
                "tpm_limit": 100000,
                "max_parallel_requests": 4,
                "metadata": {"workflow": workflow, "environment": "local-day6"},
            },
        )
        key = result.get("key")
        if not isinstance(key, str) or not key.startswith("sk-"):
            raise SystemExit(f"LiteLLM did not return a virtual key for {workflow}")
        keys[workflow] = key
    KEYS_PATH.write_text(json.dumps(keys, indent=2) + "\n", encoding="utf-8")
    KEYS_PATH.chmod(stat.S_IRUSR | stat.S_IWUSR)
    values.update(
        {
            "INSIGHTHUB_LITELLM_API_KEY": keys["insighthub"],
            "CHATOPS_LITELLM_API_KEY": keys["chatops"],
            "CODING_LITELLM_API_KEY": keys["coding"],
        }
    )
    write_env(values)
    print("Created three budgeted LiteLLM virtual keys (values not displayed).")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("init", "keys"))
    parser.add_argument("--base-url", default="http://127.0.0.1:14000")
    args = parser.parse_args()
    if args.action == "init":
        initialize()
    else:
        generate_keys(args.base_url)


if __name__ == "__main__":
    main()
