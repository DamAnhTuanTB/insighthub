"""Download pinned lab executables, verify hashes, and keep them outside Git."""

from __future__ import annotations

import hashlib
import io
import json
import platform
import tarfile
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def install() -> None:
    system = platform.system().lower()
    machine = {"aarch64": "arm64", "x86_64": "amd64"}.get(
        platform.machine(), platform.machine()
    )
    if system not in {"darwin", "linux"} or machine not in {"arm64", "amd64"}:
        raise SystemExit("Supported platforms: macOS/Linux, arm64/amd64.")
    manifest = json.loads(Path(__file__).with_name("artifacts.json").read_text())
    destination = ROOT / "tmp/day2/bin"
    destination.mkdir(parents=True, exist_ok=True)
    for name, info in manifest.items():
        version = info["version"].removeprefix("v")
        asset_name = (
            f"prometheus-mcp-server_{version}_{system}_"
            f"{'all' if system == 'darwin' else machine}.tar.gz"
            if name == "prometheus"
            else f"{'kind' if name == 'kind' else 'kubernetes-mcp-server'}-{system}-{machine}"
        )
        artifact = info["artifacts"][asset_name]
        cache = destination / asset_name
        if not cache.exists():
            with urllib.request.urlopen(artifact["url"], timeout=60) as response:
                cache.write_bytes(response.read(150_000_001))
        data = cache.read_bytes()
        if len(data) > 150_000_000 or hashlib.sha256(data).hexdigest() != artifact["sha256"]:
            cache.unlink(missing_ok=True)
            raise SystemExit(f"Artifact verification failed: {name}")
        target = destination / name
        if name == "prometheus":
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
                members = [m for m in archive.getmembers() if m.isfile() and Path(m.name).name == "prometheus-mcp-server"]
                if len(members) != 1 or members[0].size > 150_000_000:
                    raise SystemExit("Unexpected Prometheus archive layout.")
                stream = archive.extractfile(members[0])
                assert stream is not None
                target.write_bytes(stream.read(150_000_001))
        else:
            target.write_bytes(data)
        target.chmod(0o755)
        print(f"Verified {name} {info['version']} ({system}/{machine})")


if __name__ == "__main__":
    install()
