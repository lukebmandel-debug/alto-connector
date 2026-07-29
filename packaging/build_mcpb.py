#!/usr/bin/env python3
"""Build a self-contained .mcpb desktop extension, one per platform.

Why a bundled Python: Claude Desktop ships Node, not Python, and stock macOS
still has 3.9 — too old for this server. Requiring users to install Python
first would defeat the point of a double-click installer, so each bundle
carries a relocatable CPython from python-build-standalone plus the wheels it
needs. That costs ~50MB per bundle and buys zero prerequisites.

Usage (from the repo root):
    python packaging/build_mcpb.py                # every platform
    python packaging/build_mcpb.py macos-arm64    # just one

Output: packaging/dist/Alto-<platform>.mcpb
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.mcp_server import __version__, WEBSITE_URL  # noqa: E402

BUILD = ROOT / "packaging" / "build"
DIST = ROOT / "packaging" / "dist"
CACHE = ROOT / "packaging" / "build" / "_cache"

PY = "3.12.13"
PBS_TAG = "20260718"
PBS_URL = ("https://github.com/astral-sh/python-build-standalone/releases/"
           f"download/{PBS_TAG}/cpython-{PY}+{PBS_TAG}-{{triple}}-install_only.tar.gz")

# platform key -> (triple, mcpb platform id, interpreter, site-packages dir)
PLATFORMS = {
    "macos-arm64": ("aarch64-apple-darwin", "darwin", "python/bin/python3.12",
                    "python/lib/python3.12/site-packages"),
    "macos-x64": ("x86_64-apple-darwin", "darwin", "python/bin/python3.12",
                  "python/lib/python3.12/site-packages"),
    "windows-x64": ("x86_64-pc-windows-msvc", "win32", "python/python.exe",
                    "python/Lib/site-packages"),
}

# Only what the stdio server imports. The hosted variant's dependencies
# (fastapi, uvicorn, firebase-admin, …) would add tens of megabytes.
REQUIREMENTS = ["mcp>=1.28,<2"]

PACKAGE_INCLUDE = [
    ("alto", "*.py"),
    ("alto/build", "*.py"),
    ("alto/store", "*.py"),
    ("alto/auth", "*.py"),
    ("alto/engine", "*.py"),
    ("alto/engine", "*.html"),
    ("alto/cloud", "*.py"),
    ("alto/cloud", "*.js"),
    ("alto/assets", "*.svg"),
    ("alto/assets/png", "*.png"),
]


def log(msg: str) -> None:
    print(msg, flush=True)


def fetch_runtime(triple: str) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    url = PBS_URL.format(triple=triple)
    dest = CACHE / url.rsplit("/", 1)[-1]
    if not dest.exists():
        log(f"  ↓ {dest.name}")
        urllib.request.urlretrieve(url, dest)
    return dest


def stage_runtime(archive: Path, server: Path) -> None:
    with tarfile.open(archive) as tf:
        tf.extractall(server, filter="data")
    # python-build-standalone unpacks to ./python/
    if not (server / "python").exists():
        raise SystemExit(f"unexpected runtime layout in {archive.name}")


def stage_package(server: Path) -> None:
    for rel, pattern in PACKAGE_INCLUDE:
        src_dir = ROOT / rel
        if not src_dir.exists():
            continue
        out = server / rel
        out.mkdir(parents=True, exist_ok=True)
        for f in sorted(src_dir.glob(pattern)):
            shutil.copy2(f, out / f.name)
    for extra in ("interview_guide.md", "privacy.html"):
        shutil.copy2(ROOT / "alto" / extra, server / "alto" / extra)
    if not (server / "alto" / "engine" / "timeline_template.html").exists():
        raise SystemExit(
            "engine templates missing — run packaging/stage_engine.py first")


def _uv() -> str:
    found = shutil.which("uv")
    if found:
        return found
    import site
    candidate = Path(site.USER_BASE) / "bin" / "uv"
    if candidate.exists():
        return str(candidate)
    raise SystemExit("uv not found — install it with: python3 -m pip install --user uv")


def vendor_wheels(server: Path, triple: str, site_packages: str) -> None:
    """Resolve wheels for the TARGET platform, into the runtime's site-packages.

    Two things this gets right that the obvious approach does not:

    * **Target platform, not this machine's.** Several dependencies
      (pydantic-core, pywin32) ship compiled, platform-specific wheels, so a
      plain install here would produce a bundle that only runs on an
      Apple-silicon Mac. uv resolves against the target triple instead.
    * **The interpreter's real site-packages, not a `lib/` on PYTHONPATH.**
      `.pth` files are only executed for genuine site directories. pywin32
      ships `pywin32.pth`, which is what puts `pywintypes` on the path — drop
      it in an arbitrary PYTHONPATH directory and the import fails on every
      Windows machine, which is exactly what happened.
    """
    lib = server / site_packages
    lib.mkdir(parents=True, exist_ok=True)
    cmd = [_uv(), "pip", "install", "--quiet", "--target", str(lib),
           "--only-binary", ":all:",
           "--python-platform", triple,
           "--python-version", PY,
           *REQUIREMENTS]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"uv pip install failed:\n{r.stdout[-2000:]}\n"
                         f"{r.stderr[-2000:]}")
    for junk in lib.rglob("__pycache__"):
        shutil.rmtree(junk, ignore_errors=True)


def manifest(key: str, mcpb_platform: str, interpreter: str) -> dict:
    dirname = "${__dirname}"
    return {
        "manifest_version": "0.3",
        "name": "alto",
        "display_name": "Alto",
        "version": __version__,
        "description": ("Build an interactive timeline from your own "
                        "materials — never from invented content."),
        "long_description": (
            "Alto interviews you about material you already have — a course, a "
            "novel, a research project — and builds an interactive, filterable "
            "timeline from it: glass cards on coloured act bands, entity chips, "
            "routed connection lines, detail pages using your own schema, "
            "highlights and notes, a mobile layout, and a self-contained "
            "offline file you can send to anyone.\n\n"
            "Alto is a closed knowledge container. It connects and organises "
            "what you provide and never invents facts, events, holdings or "
            "descriptions. Sparse notes make a sparse timeline, on purpose."),
        "author": {"name": "Luke Mandel"},
        "homepage": WEBSITE_URL,
        "documentation": f"{WEBSITE_URL}/get",
        "license": "Apache-2.0",
        "keywords": ["timeline", "study", "notes", "law", "research"],
        "icon": "icon.png",
        "icons": [
            {"src": "assets/alto-light-512.png", "size": "512x512", "theme": "light"},
            {"src": "assets/alto-dark-512.png", "size": "512x512", "theme": "dark"},
            {"src": "assets/alto-light-128.png", "size": "128x128", "theme": "light"},
            {"src": "assets/alto-dark-128.png", "size": "128x128", "theme": "dark"},
        ],
        "privacy_policies": [f"{WEBSITE_URL}/privacy/"],
        "server": {
            "type": "python",
            "entry_point": "server/alto/mcp_server.py",
            "mcp_config": {
                "command": f"{dirname}/server/{interpreter}",
                "args": ["-m", "alto.mcp_server"],
                "env": {
                    "PYTHONPATH": f"{dirname}/server",
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "ALTO_TRANSPORT": "stdio",
                    "ALTO_PUBLISH_MODE": "firebase-static",
                    "ALTO_STORE_DIR": "${user_config.store_dir}",
                    "ALTO_FIREBASE_SITE": "${user_config.firebase_site}",
                    "ALTO_FIREBASE_PROJECT": "${user_config.firebase_project}",
                    "ALTO_FIREBASE_CONFIG": "${user_config.firebase_config}",
                },
            },
        },
        "tools": _tool_entries(),
        "tools_generated": False,
        "user_config": {
            "store_dir": {
                "type": "directory",
                "title": "Where to keep your timelines",
                "description": ("Drafts, built pages and offline files are "
                                "stored here on this Mac."),
                "default": "${HOME}/Documents/Alto",
                "required": False,
            },
            "firebase_site": {
                "type": "string",
                "title": "Firebase Hosting site (optional)",
                "description": ("Your own free Hosting site id, for publishing "
                                "shareable links. Leave blank to keep every "
                                "timeline offline-only."),
                "required": False,
            },
            "firebase_project": {
                "type": "string",
                "title": "Firebase project id (optional)",
                "description": "The project that Hosting site belongs to.",
                "required": False,
            },
            "firebase_config": {
                "type": "string",
                "title": "Firebase web config (optional)",
                "description": ("The web SDK config JSON from your Firebase "
                                "console, which switches on cross-device sync "
                                "of highlights and notes. Yours alone — Alto "
                                "never ships a project of its own."),
                "sensitive": True,
                "required": False,
            },
        },
        # No `runtimes` key on purpose. Declaring one tells Claude Desktop the
        # extension needs that runtime present on the host, and it probes for
        # it before installing. This bundle ships its own CPython, so the
        # requirement is false and the probe is a pointless gate — the spec
        # says to omit `runtimes` for self-contained bundles.
        "compatibility": {"platforms": [mcpb_platform]},
    }


def _tool_entries() -> list[dict]:
    """Read tool names and descriptions off the live server.

    Annotations are mandatory for a Connectors Directory submission, and
    hand-maintaining this list would drift from the code within a release.
    """
    from alto.mcp_server import mcp
    import asyncio
    tools = asyncio.run(mcp.list_tools())
    return [{"name": t.name,
             "description": (t.description or "").strip().split("\n")[0]}
            for t in tools]


def sha256sums(root: Path) -> str:
    lines = []
    for p in sorted(root.rglob("*")):
        if p.is_file():
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
            lines.append(f"{digest}  {p.relative_to(root).as_posix()}")
    return "\n".join(lines) + "\n"


def build(key: str) -> Path:
    triple, mcpb_platform, interpreter, site_packages = PLATFORMS[key]
    log(f"\n▸ {key}")
    stage = BUILD / key
    shutil.rmtree(stage, ignore_errors=True)
    server = stage / "server"
    server.mkdir(parents=True)

    log("  unpacking CPython")
    stage_runtime(fetch_runtime(triple), server)
    log("  staging package")
    stage_package(server)
    log("  vendoring wheels into the runtime")
    vendor_wheels(server, triple, site_packages)

    assets = stage / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    png = ROOT / "alto" / "assets" / "png"
    for theme in ("light", "dark"):
        for size in (512, 128):
            shutil.copy2(png / f"alto-{theme}-{size}.png",
                         assets / f"alto-{theme}-{size}.png")
    shutil.copy2(png / "alto-light-512.png", stage / "icon.png")
    shutil.copy2(ROOT / "README.md", stage / "README.md")

    (stage / "manifest.json").write_text(
        json.dumps(manifest(key, mcpb_platform, interpreter), indent=2) + "\n",
        encoding="utf-8")
    (stage / "SHA256SUMS").write_text(sha256sums(stage), encoding="utf-8")

    DIST.mkdir(parents=True, exist_ok=True)
    out = DIST / f"Alto-{key}.mcpb"
    out.unlink(missing_ok=True)
    env = {**os.environ, "PATH": f"{Path.home()}/.local/node/bin:{os.environ.get('PATH','')}"}
    r = subprocess.run(["mcpb", "pack", str(stage), str(out)],
                       capture_output=True, text=True, env=env)
    if r.returncode != 0:
        raise SystemExit(f"mcpb pack failed:\n{r.stdout}\n{r.stderr}")
    log(f"  ✓ {out.relative_to(ROOT)}  {out.stat().st_size / 1048576:.0f} MB")
    return out


def main() -> None:
    keys = sys.argv[1:] or list(PLATFORMS)
    unknown = [k for k in keys if k not in PLATFORMS]
    if unknown:
        raise SystemExit(f"unknown platform(s) {unknown}; "
                         f"choose from {list(PLATFORMS)}")
    subprocess.run([sys.executable, str(ROOT / "packaging" / "stage_engine.py")],
                   check=True)
    for key in keys:
        build(key)


if __name__ == "__main__":
    main()
