#!/bin/bash
# Alto connector — one-command install for Claude Desktop (macOS).
#   bash setup.sh
# Creates a Python 3.12 venv, installs dependencies, and registers the
# connector in Claude Desktop's config. Costs nothing; no accounts needed.
set -euo pipefail
cd "$(dirname "$0")"
REPO="$(pwd)"

echo "── Alto connector setup ──"

# 1. Python ≥3.10 (installs uv + a managed CPython if the system lacks one)
PY=""
for cand in python3.13 python3.12 python3.11 python3.10; do
  if command -v "$cand" >/dev/null 2>&1; then PY="$cand"; break; fi
done
if [ -z "$PY" ]; then
  echo "No Python 3.10+ found — installing uv (user-space) + Python 3.12…"
  python3 -m pip install --user -q uv
  UV="$(python3 -c 'import site,os;print(os.path.join(site.USER_BASE,"bin","uv"))')"
  "$UV" venv --python 3.12 .venv
else
  "$PY" -m venv .venv
fi

# 2. dependencies
if [ -x .venv/bin/pip ]; then
  .venv/bin/pip install -q -r requirements.txt
else
  UV="$(python3 -c 'import site,os;print(os.path.join(site.USER_BASE,"bin","uv"))')"
  "$UV" pip install --python .venv/bin/python -r requirements.txt
fi
echo "✓ environment ready"

# 3. register with Claude Desktop
.venv/bin/python - "$REPO" <<'EOF'
import json, sys
from pathlib import Path
repo = sys.argv[1]
cfg_path = Path.home() / "Library/Application Support/Claude/claude_desktop_config.json"
cfg_path.parent.mkdir(parents=True, exist_ok=True)
cfg = json.loads(cfg_path.read_text()) if cfg_path.exists() else {}
if cfg_path.exists():
    cfg_path.with_suffix(".json.alto-backup").write_text(cfg_path.read_text())
cfg.setdefault("mcpServers", {})["alto"] = {
    "command": f"{repo}/.venv/bin/python",
    "args": ["-m", "alto.mcp_server"],
    "env": {
        "ALTO_TRANSPORT": "stdio",
        "ALTO_DEV_UID": "local",
        "ALTO_STORE_DIR": str(Path.home() / "Documents" / "Alto"),
        "ALTO_PUBLISH_MODE": "firebase-static",
        "ALTO_SITE_DIR": f"{repo}/firebase/site",
        "PYTHONPATH": repo,
    },
}
cfg_path.write_text(json.dumps(cfg, indent=2))
print("✓ registered in Claude Desktop (backup saved)")
EOF

echo
echo "Done. Quit and reopen the Claude Desktop app, then start a chat with:"
echo "  “I want to build a timeline in Alto — interview me.”"
echo
echo "Optional — shareable web links (also free): create a Firebase project +"
echo "Hosting site, log in the firebase CLI, and add ALTO_FIREBASE_SITE and"
echo "ALTO_FIREBASE_PROJECT to the alto entry in Claude Desktop's config."
echo "Without that, every timeline still works as a self-contained offline file."
