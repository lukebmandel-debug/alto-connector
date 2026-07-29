#!/usr/bin/env python3
"""Unpack a .mcpb and exercise it exactly the way Claude Desktop would.

Reads the bundle's own manifest, launches the interpreter it names with the
environment it declares, speaks JSON-RPC over stdio, then builds a real
timeline inside the bundle. The point is to test the *shipped artifact* rather
than the source tree — a bundle can be wrong in ways the source is not
(missing files, the wrong architecture's wheels, a PYTHONPATH separator that
is right on one platform and wrong on another).

PATH is deliberately replaced with a nonexistent directory, so nothing can
quietly fall back to a Python already installed on the machine. If the bundle
is not self-contained, this fails.

    python packaging/probe_bundle.py path/to/Alto-macos-arm64.mcpb
"""
from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


class ProbeFailure(SystemExit):
    pass


def unpack(mcpb: Path, dest: Path) -> Path:
    """Extract, preserving the Unix executable bit.

    `extractall` drops permissions, which leaves the bundled interpreter
    non-executable — so this restores the mode recorded in each zip entry.
    Claude Desktop does its own extraction; this only has to match it well
    enough that the probe exercises the same files.
    """
    with zipfile.ZipFile(mcpb) as z:
        for info in z.infolist():
            path = z.extract(info, dest)
            mode = info.external_attr >> 16
            if mode and not info.is_dir():
                os.chmod(path, mode & 0o7777)
    if not (dest / "manifest.json").exists():
        raise ProbeFailure(f"no manifest.json at the root of {mcpb.name}")
    return dest


def launch(ext: Path, store: Path) -> subprocess.Popen:
    cfg = json.loads((ext / "manifest.json").read_text())["server"]["mcp_config"]
    sub = lambda s: s.replace("${__dirname}", str(ext))

    env = {k: sub(v) for k, v in cfg["env"].items()
           if "${user_config" not in v}
    env["PATH"] = str(ext / "__no_system_python__")
    env["ALTO_STORE_DIR"] = str(store)
    for passthrough in ("SYSTEMROOT", "TEMP", "TMP", "HOME", "USERPROFILE",
                        "APPDATA", "LOCALAPPDATA"):
        if passthrough in os.environ:
            env[passthrough] = os.environ[passthrough]

    command = sub(cfg["command"])
    if not Path(command).exists():
        raise ProbeFailure(f"interpreter missing from the bundle: {command}")

    return subprocess.Popen([command, *cfg["args"]],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, env=env,
                            cwd=str(ext))


def handshake(proc: subprocess.Popen) -> tuple[dict, list]:
    def send(obj):
        proc.stdin.write(json.dumps(obj) + "\n")
        proc.stdin.flush()

    send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
          "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                     "clientInfo": {"name": "probe", "version": "0"}}})
    init = proc.stdout.readline()
    if not init:
        raise ProbeFailure("no response to initialize\n"
                           + proc.stderr.read()[-3000:])
    send({"jsonrpc": "2.0", "method": "notifications/initialized"})
    send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    tools = proc.stdout.readline()
    return (json.loads(init)["result"]["serverInfo"],
            json.loads(tools)["result"]["tools"])


def build_a_timeline(ext: Path, brief: Path) -> dict:
    """Prove the bundle can do the actual work, not just answer a handshake.

    Runs from a temp cwd so nothing can resolve relative to a source checkout.
    """
    cfg = json.loads((ext / "manifest.json").read_text())["server"]["mcp_config"]
    sub = lambda s: s.replace("${__dirname}", str(ext))
    env = dict(os.environ)
    env["PYTHONPATH"] = sub(cfg["env"]["PYTHONPATH"])

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
        "'nodes':rep['nodes'],'warnings':len(rep['warnings'])}))\n")

    with tempfile.TemporaryDirectory() as cwd:
        r = subprocess.run([sub(cfg["command"]), "-c", script, str(brief)],
                           capture_output=True, text=True, env=env, cwd=cwd)
    if r.returncode != 0:
        raise ProbeFailure(f"build inside the bundle failed:\n{r.stderr[-3000:]}")
    return json.loads(r.stdout.strip().splitlines()[-1])


def main() -> None:
    if len(sys.argv) < 2:
        raise ProbeFailure(__doc__)
    mcpb = Path(sys.argv[1]).resolve()
    brief = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else (
        Path(__file__).resolve().parent.parent / "samples" / "contracts_brief.json")

    print(f"host      : {platform.system()} {platform.machine()} "
          f"(python {platform.python_version()})")
    print(f"bundle    : {mcpb.name}  {mcpb.stat().st_size / 1048576:.0f} MB")

    with tempfile.TemporaryDirectory() as tmp:
        ext = unpack(mcpb, Path(tmp) / "ext")
        store = Path(tmp) / "store"
        store.mkdir()

        proc = launch(ext, store)
        try:
            info, tools = handshake(proc)
        finally:
            try:
                proc.stdin.close()
                proc.wait(timeout=10)
            except Exception:
                proc.kill()

        print(f"serverInfo: {info['name']} {info['version']}")
        print(f"website   : {info.get('websiteUrl')}")
        icons = info.get("icons") or []
        print(f"icons     : {len(icons)} "
              f"({', '.join(sorted({i['mimeType'] for i in icons}))})")
        print(f"tools     : {len(tools)}")

        if info["version"].startswith("1.28"):
            raise ProbeFailure("server is reporting the MCP SDK version as its own")
        if not any(i["mimeType"] == "image/png" for i in icons):
            raise ProbeFailure("no PNG icon — clients are only required to "
                               "support PNG, so an SVG-only list may not render")
        if len(tools) != 14:
            raise ProbeFailure(f"expected 14 tools, got {len(tools)}")

        built = build_a_timeline(ext, brief)
        print(f"built     : timeline {built['html']:,} B, "
              f"offline {built['offline']:,} B, "
              f"{built['nodes']} nodes, {built['warnings']} warnings")

    print("\nPASS — the bundle is self-contained and builds a real timeline "
          "with no system Python on PATH.")


if __name__ == "__main__":
    main()
