#!/usr/bin/env python3
"""Copy the three runtime templates into the package before building.

`engine/` is the working directory: it also holds FROZEN/ and the 255KB
TEMPLATE_MANIFEST.json, which exist to prove the templates were extracted
faithfully and are not needed to run. Only the three HTML files are staged, so
neither a wheel nor an .mcpb carries the proofs.

Run from the repo root:  python packaging/stage_engine.py
Idempotent; safe to run before every build.
"""
from __future__ import annotations

import hashlib
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.engine import RUNTIME_TEMPLATES  # noqa: E402

SRC = ROOT / "engine"
DEST = ROOT / "alto" / "engine"


def stage() -> list[Path]:
    written = []
    for name in RUNTIME_TEMPLATES:
        src = SRC / name
        if not src.exists():
            raise SystemExit(f"missing engine template: {src}")
        dest = DEST / name
        if dest.exists() and dest.read_bytes() == src.read_bytes():
            written.append(dest)
            continue
        shutil.copy2(src, dest)
        written.append(dest)
    return written


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    for p in stage():
        digest = hashlib.sha256(p.read_bytes()).hexdigest()[:12]
        print(f"  staged {p.relative_to(ROOT)}  {p.stat().st_size:>8,} B  {digest}")
    print(f"✓ {len(RUNTIME_TEMPLATES)} runtime templates staged into alto/engine/")


if __name__ == "__main__":
    main()
