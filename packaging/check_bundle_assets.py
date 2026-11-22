#!/usr/bin/env python3
"""Release check A: the bundle's alto/assets tree must equal the repo's, folder by folder.

    python packaging/check_bundle_assets.py packaging/dist/Alto-macos-arm64.mcpb

Fails (exit 1) naming each folder with a file the repo has and the bundle lacks, unless
the file is on build_mcpb.ASSETS_EXCLUDE (an explicit, commented list). Also compares
bytes, since the hosted names are hashes of them.
"""
from __future__ import annotations

import hashlib
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "packaging"))
import build_mcpb  # noqa: E402

BASE = ROOT / "alto" / "assets"
_JUNK = {".DS_Store", "Thumbs.db"}


def repo_tree() -> dict:
    return {f.relative_to(BASE).as_posix(): hashlib.sha256(f.read_bytes()).hexdigest()
            for f in sorted(BASE.rglob("*")) if f.is_file() and f.name not in _JUNK}


def bundle_tree(src: Path) -> dict:
    """{relative path under alto/assets: sha256} from a .mcpb or an unpacked/staged directory."""
    out = {}
    if src.is_file():
        with zipfile.ZipFile(src) as z:
            for n in z.namelist():
                if "/alto/assets/" in "/" + n and not n.endswith("/"):
                    out[("/" + n).split("/alto/assets/", 1)[1]] = hashlib.sha256(z.read(n)).hexdigest()
    else:
        root = src / "alto" / "assets"
        for f in root.rglob("*"):
            if f.is_file():
                out[f.relative_to(root).as_posix()] = hashlib.sha256(f.read_bytes()).hexdigest()
    return out


def problems(bundle: dict) -> list:
    excl = build_mcpb.ASSETS_EXCLUDE
    skip = lambda r: any(r == e or r.startswith(e.rstrip("/") + "/") for e in excl)  # noqa: E731
    repo = repo_tree()
    bad = []
    by_folder: dict = {}
    for rel, h in repo.items():
        if skip(rel):
            continue
        if rel not in bundle:
            by_folder.setdefault(rel.rsplit("/", 1)[0] if "/" in rel else ".", []).append(rel)
        elif bundle[rel] != h:
            bad.append(f"changed: alto/assets/{rel}")
    for folder, files in sorted(by_folder.items()):
        bad.append(f"missing folder alto/assets/{folder}: {len(files)} file(s), e.g. {files[0]}")
    for rel in bundle:
        if rel not in repo:
            bad.append(f"not in the repo: alto/assets/{rel}")
    return bad


def main(argv: list) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    bad = problems(bundle_tree(Path(argv[1])))
    for b in bad:
        print("FAIL", b)
    print("bundle assets match the repo" if not bad else f"{len(bad)} problem(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
