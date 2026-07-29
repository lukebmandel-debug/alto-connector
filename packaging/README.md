# Packaging

Two artifacts come out of here:

| Artifact | Who it's for | Built by |
|---|---|---|
| `Alto-<platform>.mcpb` | anyone on Claude Desktop — double-click to install | `build_mcpb.py` |
| `alto_connector-*.whl` | people who prefer `uvx alto-connector`, and the MCP Registry listing | `python -m build` |

## Build

```bash
python packaging/build_mcpb.py                 # all three platforms
python packaging/build_mcpb.py macos-arm64     # just one
```

Output lands in `packaging/dist/`. Requires `uv` (for cross-platform wheel
resolution) and the `mcpb` CLI (`npm install -g @anthropic-ai/mcpb`). The
CPython runtimes are downloaded once and cached in `packaging/build/_cache/`.

`stage_engine.py` runs first and copies the three runtime templates from
`engine/` into `alto/engine/`. Those copies are generated and gitignored;
`engine/FROZEN/` and `TEMPLATE_MANIFEST.json` are build-time proofs and are
deliberately excluded from every shipped artifact.

## Why each bundle is ~50MB

Claude Desktop ships Node, not Python, and stock macOS still has Python 3.9 —
too old for this server. So each bundle carries a relocatable CPython 3.12 from
[python-build-standalone](https://github.com/astral-sh/python-build-standalone)
plus wheels resolved for that platform. The alternative — telling users to
install Python first — defeats the point of a double-click installer.

Only `mcp` is vendored. The hosted variant's dependencies (fastapi, uvicorn,
firebase-admin, google-cloud-storage) live in `requirements-remote.txt` and
would add tens of megabytes to a file people have to download.

## Verifying a bundle

`tests/test_packaging.py` covers the manifest. The bundle itself is checked by
hand, because building one takes minutes:

```bash
cd /tmp && mkdir -p mcpbtest && cd mcpbtest
unzip -q "…/packaging/dist/Alto-macos-arm64.mcpb" -d ext

# 1. self-contained handshake — PATH deliberately broken so nothing can fall
#    back to a system Python
EXT=$(pwd)/ext
PYTHONPATH="$EXT/server:$EXT/server/lib" PATH=/nonexistent \
  "$EXT/server/python/bin/python3.12" -m alto.mcp_server   # then speak JSON-RPC

# 2. architectures really are cross-built
file ext/server/python/bin/python3.12
file ext/server/lib/pydantic_core/*.so        # or *.pyd on the Windows bundle
```

What to look for: `serverInfo.version` is Alto's own version (not the MCP
SDK's), the icon list leads with a PNG, and `tools/list` returns 14.

## Platforms

`macos-arm64` and `macos-x64` are verified on this machine. `windows-x64` is
cross-built and its manifest, wheel architecture (`*.pyd`, `win_amd64`) and
interpreter (`PE32+ x86-64`) are checked, but **it has not been run on
Windows** — it ships unverified until someone installs it there.
