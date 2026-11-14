"""The Bass Documents sheet in a real headless browser (tests/bass_docs_browser.cjs, Node Playwright), on the in-page simulator: no network, no
key, no proxy. Chromium always when Playwright is there; WebKit too when its browser is installed. ALTO_SHOTS=<dir> also writes the Art
screenshots."""
import json
import os
import shutil
import subprocess

import pytest

from bass_support import ROOT  # noqa: F401

NODE = shutil.which("node")
PAGE = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>:root{--surface:#fff;--text:#1a1a2e;--muted:#5a5a80;--border:#c8c8d8;--accent:#3b4a9e}
html[data-theme=dark]{--surface:#14151f;--text:#ecebf5;--muted:#a3a3c2;--border:#3a3b52;--accent:#9aa6ff}
body{margin:0;font:14px -apple-system,system-ui,sans-serif;background:linear-gradient(135deg,#6c78c6,#c0788f 38%,#c9906f 62%,#5fa592);min-height:100vh}
html[data-theme=dark] body{background:#0b0c12}</style></head><body><script>__BUNDLE__</script></body></html>"""


def _has_playwright():
    if not NODE:
        return False
    return subprocess.run([NODE, "-e", "require('playwright')"], capture_output=True).returncode == 0


@pytest.mark.parametrize("engine", ["chromium", "webkit"])
def test_documents_sheet_in_a_browser(tmp_path, engine, monkeypatch):
    if not _has_playwright():
        pytest.skip("node + playwright are not installed")
    monkeypatch.setenv("ALTO_BASS_UI", "1")
    from alto.build import bass_ui
    page = tmp_path / "page.html"
    page.write_text(PAGE.replace("__BUNDLE__", bass_ui.ASSET.replace("</script", "<\\/script")), "utf-8")
    shots = os.environ.get("ALTO_SHOTS", "")
    if shots:
        shots = os.path.join(shots, engine)
        os.makedirs(shots, exist_ok=True)
    run = subprocess.run([NODE, str(ROOT / "tests" / "bass_docs_browser.cjs"), str(page), shots, engine], capture_output=True, text=True, timeout=240)
    line = (run.stdout.strip().splitlines() or ["{}"])[-1]
    out = json.loads(line)
    if engine == "webkit" and "Executable doesn't exist" in out.get("error", ""):
        pytest.skip("the WebKit browser is not installed here (real Safari runs on Home Desktop)")
    bad = [c for c in out.get("checks", []) if not c["ok"]]
    assert out.get("ok") and not bad, (out.get("error"), bad)
