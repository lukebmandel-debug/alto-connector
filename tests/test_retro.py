"""Retro for every format (alto/build/retro.py): the Star chart's Retro (black and gold, the art-deco frame, spaced capitals)
as a per-timeline style, Classic | Retro, of the timeline, the horizontal timeline, the outline and both palaces' plans.

A page carries only the switch's hook; the look is a hosted script fetched only when Retro is chosen. The browser parts are
skipped when Playwright is not installed."""
import http.server
import json
import re
import socketserver
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import backgrounds as bg, backgrounds_import as bi, palace_assets, retro   # noqa: E402
from alto.build.builder import build_timeline, load_brief       # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None


def _build(name, **over):
    d = json.loads((ROOT / "samples" / f"{name}_brief.json").read_text(encoding="utf-8"))
    d["brief"].update(over)
    brief, nodes, conns = load_brief(d)
    return build_timeline(brief, nodes, conns)[0]


@pytest.fixture(scope="module")
def outline():
    return _build("outline")


# ── what a page carries ─────────────────────────────────────────────────────

def test_the_look_is_a_hosted_script_and_the_page_holds_only_its_hook(outline):
    name, text = retro.retro_asset()
    assert retro.PATH == "/retro/" + name and ("retro", name, text) in palace_assets.assets()
    assert palace_assets.find(retro.PATH)[1] == text
    head = re.search(r'<script id="alto-bg-head">(.*?)</script>', outline, re.S).group(1)
    assert json.dumps(retro.PATH) in head and "-style" in head
    assert "alto-retro-css" not in outline and "html.alto-retro" not in outline     # none of the rules ride in the page


@pytest.mark.parametrize("anchor", ["#sk-frame", "#sk-mark", "#world .phase-band", "#world .node-card", "#river-svg path",
                                    "#detail-page", "#lanes-svg .ln-main", ".pal-svg .pl-tube", "#bldg-root", ".lu-chip"])
def test_every_format_has_its_rules(anchor):
    assert "html.alto-retro" in retro.css() and anchor in retro.css()
    assert "X " not in retro.css() and "X:" not in retro.css() and "FONT" not in retro.css()


def test_the_system_keeps_its_own_styles_and_shares_the_frame():
    page = _build("outline", layout="solar")
    head = re.search(r'<script id="alto-bg-head">(.*?)</script>', page, re.S).group(1)
    assert retro.PATH not in head and "if(0)" in head
    from alto.build.solar_stars import STARS_CSS
    frame = retro.FRAME_CSS.strip().split("\n")[2].strip().replace("X ", "html.alto-stars.sk-retro:not(.mobile) ")
    assert frame in STARS_CSS


def test_the_homepage_offers_no_style():
    head = bg.head_block("alto-bg-home-v1")
    assert retro.PATH not in head


def test_the_picker_draws_the_switch_from_the_hosted_library():
    js = bi.lib_js()
    assert "function styles()" in js and "window._altoStyle" in js and "'Retro'" in js


# ── in a browser ────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def site(outline, tmp_path_factory):
    if pw is None:
        pytest.skip("Playwright is not installed")
    d = tmp_path_factory.mktemp("retrosite")
    (d / "t.html").write_text(outline, encoding="utf-8")
    (d / "old.html").write_text(outline.replace(retro.PATH, "/retro/alto-retro-0000000000.js"), encoding="utf-8")   # a file the site lacks
    (d / "retro").mkdir()
    name, text = retro.retro_asset()
    (d / "retro" / name).write_text(text, encoding="utf-8")
    lib, js = bi.site_file()
    (d / lib).write_text(js, encoding="utf-8")
    hits = []

    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(d), **k)

        def do_GET(self):
            hits.append(self.path)
            return super().do_GET()

        def log_message(self, *a):
            pass
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), H)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", hits
    srv.shutdown()
    srv.server_close()


@pytest.fixture(params=["webkit", "chromium"])
def browser(request):
    if pw is None:
        pytest.skip("Playwright is not installed")
    with pw.sync_playwright() as p:
        try:
            b = getattr(p, request.param).launch()
        except Exception as e:
            try:
                if request.param != "chromium":
                    raise e
                b = p.chromium.launch(channel="chrome")
            except Exception:
                pytest.skip(f"no {request.param}: {e}")
        yield b
        b.close()


_STATE = """[document.documentElement.classList.contains('alto-retro'), !!document.getElementById('alto-retro-css'),
  !!document.getElementById('sk-frame'), document.documentElement.classList.contains('dark'), window._altoStyle.get()]"""


def test_classic_fetches_nothing_and_retro_is_kept_per_timeline(browser, site):
    base, hits = site
    ctx = browser.new_context(viewport={"width": 1400, "height": 900})
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    hits.clear()
    pg.goto(base + "/t.html")
    pg.wait_for_timeout(600)
    assert pg.evaluate(_STATE) == [False, False, False, False, "classic"]
    assert not any(h.startswith("/retro/") for h in hits)                  # Classic never fetches the look
    # chosen in the picker: the switch heads it
    pg.click("#bg-toggle")
    pg.wait_for_selector("#bg-style .bg-segb[data-sty=retro]", timeout=8000)
    assert pg.eval_on_selector_all("#bg-style .bg-segb", "b => b.map(x => x.textContent)") == ["Classic", "Retro"]
    pg.click("#bg-style .bg-segb[data-sty=retro]")
    assert pg.evaluate(_STATE) == [True, True, True, True, "retro"]
    assert pg.get_attribute("#bg-style .bg-segb[data-sty=retro]", "aria-pressed") == "true"
    assert pg.evaluate("getComputedStyle(document.getElementById('page-bg')).backgroundColor") == "rgb(0, 0, 0)"
    assert pg.evaluate("!!document.querySelector('#sk-mark') && document.querySelector('#sk-mark').textContent.length > 0")
    # remembered: the next visit opens in Retro before anything is drawn
    pg.add_init_script("document.addEventListener('DOMContentLoaded', function(){ window.__atReady=document.documentElement.classList.contains('alto-retro'); });")
    pg.reload()
    pg.wait_for_timeout(600)
    assert pg.evaluate("window.__atReady") is True
    assert pg.evaluate(_STATE)[:4] == [True, True, True, True]
    # back to Classic: the reader's own (light) theme returns
    pg.evaluate("window._altoStyle.set('classic')")
    assert pg.evaluate(_STATE) == [False, True, False, False, "classic"]
    assert pg.evaluate("getComputedStyle(document.getElementById('page-bg')).backgroundColor") != "rgb(0, 0, 0)"
    assert not errors, errors
    ctx.close()


def test_a_page_without_the_hosted_file_stays_classic(browser, site):
    base, _ = site
    ctx = browser.new_context()
    pg = ctx.new_page()
    pg.goto(base + "/old.html")
    pg.wait_for_timeout(300)
    pg.evaluate("window._altoStyle.set('retro')")
    st = pg.evaluate(_STATE)
    assert st[:3] == [False, False, False] and st[4] == "retro"
    ctx.close()
