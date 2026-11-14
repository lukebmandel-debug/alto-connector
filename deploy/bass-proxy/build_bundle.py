#!/usr/bin/env python3
"""Copies the whole alto package (the build tools need it, and tested == deployed) and the function files into a clean folder,
without tests or caches, and writes the bundle's requirements.txt = this folder's pins + the connector's own requirements.
Prints the folder. Deploys nothing."""
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / "deploy" / "bass-proxy"


def _name(line: str) -> str:
    return re.split(r"[<>=!~\[; ]", line.strip(), 1)[0].lower().replace("_", "-")


def merged_requirements() -> str:
    pins = [l for l in (HERE / "requirements.txt").read_text("utf-8").splitlines() if l.strip() and not l.startswith("#")]
    have = {_name(l) for l in pins}
    extra = [l for l in (ROOT / "requirements.txt").read_text("utf-8").splitlines()
             if l.strip() and not l.startswith("#") and _name(l) not in have]
    return "\n".join(pins + ["# from the connector's requirements.txt"] + extra) + "\n"


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp(prefix="bass-proxy-"))
    out.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / "alto", out / "alto", dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for n in ("main.py", "firestore_store.py", "gcs_object_store.py"):
        shutil.copy(HERE / n, out / n)
    (out / "requirements.txt").write_text(merged_requirements(), "utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
