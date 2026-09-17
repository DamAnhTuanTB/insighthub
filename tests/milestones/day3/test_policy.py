"""Behavioral contract for the local Day 3 policy gates."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(os.environ.get("INSIGHTHUB_REPO_ROOT", Path(__file__).parents[3])).resolve()
POLICY = ROOT / "infra" / "policy"
FIXTURES = POLICY / "tests"


def _conftest(policy: str, fixture: str) -> subprocess.CompletedProcess[str]:
    executable = shutil.which("conftest")
    assert executable, "conftest is required for Day 3 policy tests"
    return subprocess.run(
        [executable, "test", "--policy", str(POLICY / policy), str(FIXTURES / fixture)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_policy_allows_valid() -> None:
    terraform = _conftest("terraform", "terraform-safe.json")
    kubernetes = _conftest("kubernetes", "kubernetes-safe.yaml")
    assert terraform.returncode == 0, terraform.stdout + terraform.stderr
    assert kubernetes.returncode == 0, kubernetes.stdout + kubernetes.stderr


def test_policy_denies_unsafe() -> None:
    terraform = _conftest("terraform", "terraform-unsafe.json")
    kubernetes = _conftest("kubernetes", "kubernetes-unsafe.yaml")
    assert terraform.returncode != 0
    assert "default namespace" in terraform.stdout
    assert kubernetes.returncode != 0
    assert "must run as non-root" in kubernetes.stdout
    assert "latest image tag" in kubernetes.stdout


def test_local_budget_is_finite_and_explicitly_not_aws(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(
        (FIXTURES / "kubernetes-safe.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "day3_local_budget.py"), "--manifest", str(manifest)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["deployment_profile"] == "local-kubernetes"
    assert report["aws_verified"] is False
    assert report["totals"]["cpu_request_cores"] > 0
    assert report["totals"]["memory_limit_bytes"] > 0
