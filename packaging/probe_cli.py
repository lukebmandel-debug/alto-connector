#!/usr/bin/env python3
"""Exercise the pip-installed `alto-connector` the way a non-Claude-Desktop
MCP client would: launch the console script, speak stdio, build a timeline.

This is a different risk surface from the .mcpb bundle. The bundle carries its
own interpreter and every dependency, so it fails on packaging faults; the
wheel relies on the host's Python and on package data being declared correctly
in pyproject.toml, so it fails when a data file was never included — which
installs cleanly and then cannot render anything.

Run from the repo root, with alto-connector installed:

    python packaging/probe_cli.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
BRIEF = ROOT / "samples" / "contracts_brief.json"


def fail(msg: str) -> None:
    raise SystemExit(f"FAIL: {msg}")


def handshake(exe: str, store: Path) -> tuple[dict, list]:
    env = {**os.environ, "ALTO_STORE_DIR": str(store)}
    env.pop("ALTO_TRANSPORT", None)          # prove the default is stdio
    proc = subprocess.Popen([exe], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            env=env)

    def send(obj):
        proc.stdin.write((json.dumps(obj) + "\n").encode("utf-8"))
        proc.stdin.flush()

    try:
        send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "probe", "version": "0"}}})
        init = proc.stdout.readline()
        if not init:
            fail("no response to initialize\n"
                 + proc.stderr.read().decode("utf-8", "replace")[-2000:])
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tools = proc.stdout.readline()
    finally:
        try:
            proc.stdin.close()
            proc.wait(timeout=10)
        except Exception:
            proc.kill()

    return (json.loads(init)["result"]["serverInfo"],
            json.loads(tools)["result"]["tools"])


def build_a_timeline() -> dict:
    """Run from a temp cwd, so nothing resolves against the checkout."""
    script = (
        "import json,sys,pathlib\n"
        "from alto.build.builder import load_brief, build_timeline\n"
        "from alto.build.single_file import bundle\n"
        "d=json.loads(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8'))\n"
        "b,n,c=load_brief(d)\n"
        "html,rep=build_timeline(b,n,c)\n"
        "off=bundle(b,html)\n"
        "assert 'function initLayout(' in html\n"
        "print(json.dumps({'html':len(html),'offline':len(off),"
        "'nodes':rep['nodes']}))\n")
    with tempfile.TemporaryDirectory() as cwd:
        r = subprocess.run([sys.executable, "-c", script, str(BRIEF)],
                           capture_output=True, text=True, cwd=cwd)
    if r.returncode != 0:
        fail("the installed package could not build a timeline — usually "
             f"missing package data:\n{r.stderr[-2000:]}")
    return json.loads(r.stdout.strip().splitlines()[-1])


def main() -> None:
    exe = shutil.which("alto-connector")
    if not exe:
        fail("alto-connector is not on PATH — install the wheel first")
    print(f"cli       : {exe}")

    with tempfile.TemporaryDirectory() as store:
        info, tools = handshake(exe, Path(store))

    print(f"serverInfo: {info['name']} {info['version']}")
    print(f"icons     : {len(info.get('icons') or [])}")
    print(f"tools     : {len(tools)}")
    if len(tools) != 14:
        fail(f"expected 14 tools, got {len(tools)}")
    if not (info.get("icons") or []):
        fail("no icons advertised")

    built = build_a_timeline()
    print(f"built     : timeline {built['html']:,} B, "
          f"offline {built['offline']:,} B, {built['nodes']} nodes")

    print("\nPASS — the installed CLI serves MCP over stdio and builds a real "
          "timeline, with no Claude Desktop involved.")


if __name__ == "__main__":
    main()
