"""Writes what the browser tests in this folder serve: the share shell, the
site's CSP, and a real share page. Usage: python fixtures.py OUT_DIR KEY"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from alto.build.builder import build_timeline, load_brief   # noqa: E402
from alto.build.reidentify import reidentify                 # noqa: E402
from alto.build.share_shell import shell                     # noqa: E402
from alto.build.single_file import private_page              # noqa: E402
from alto.publish_static import _security_headers            # noqa: E402

out, key = Path(sys.argv[1]), sys.argv[2]
out.mkdir(parents=True, exist_ok=True)
(out / "shell.html").write_text(shell(), encoding="utf-8")
csp = next(h["value"] for h in _security_headers()[0]["headers"]
           if h["key"] == "Content-Security-Policy")
(out / "csp.txt").write_text(csp, encoding="utf-8")
b, nodes, conns = load_brief(json.loads(
    (ROOT / "samples" / "contracts_brief.json").read_text(encoding="utf-8")))
html, _ = build_timeline(b, nodes, conns)
(out / "page.html").write_text(reidentify(private_page(b, html, "Contracts"), key),
                               encoding="utf-8")
