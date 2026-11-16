"""Cards enlarge in the Horizontal timeline (lanes) as they do in the vertical one (Luke, 2026-11-13: "please make sure user can
enlarge nodes in horizontal timeline").

A click on a card enlarges it (zoom 1.7, the timeline's text size) in the small card's shape, inside the safe box (the step bar
and every other piece of chrome counted: engine_patches.py enlarge-safe-box); a click on the enlarged card opens its page. ← →
and the step bar hop the enlarged card from event to event; Esc lets it go; a search hit lands enlarged. Phones keep the
timeline's phone pattern: a tap opens the card's page. Classic, Retro and Holo; 1440x900 and 1280x720; WebKit first."""
import http.server
import json
import socketserver
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import holo, phone, retro  # noqa: E402
from alto.build.builder import build_timeline, load_brief  # noqa: E402
from tests.test_enlarge_safe_box import CARD, CHROME, PHONE, _inter, page_html  # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None

STYLES = ("classic", "retro", "holo")
SIZES = {"d1440": {"width": 1440, "height": 900}, "d1280": {"width": 1280, "height": 720}}
STOPS = """() => { const o=[].concat.apply([],ACT_SEQS), L=_ALTO_LANES;
  const lg=!(L.flashbacks||[]).length && !Object.values(L.ev).some(e=>(e.present||[]).length);
  return o.filter(id=>L.ev[id] && (lg || (L.ev[id].l||'main')==='main')); }"""
SMALL = "id=>{const r=document.querySelector('#node-'+id+' .node-card').getBoundingClientRect(); return [r.width, r.height];}"
FOCUS = "window._focusedNodeId"
DETAIL = "document.documentElement.classList.contains('detail-open')"


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    if pw is None:
        pytest.skip("Playwright is not installed")
    d = tmp_path_factory.mktemp("lanes_enlarge")
    lanes = json.loads((ROOT / "samples" / "lanes_v2_brief.json").read_text(encoding="utf-8"))
    (d / "lanes.html").write_text(build_timeline(*load_brief(lanes))[0], encoding="utf-8")
    (d / "outline.html").write_text(page_html(13), encoding="utf-8")
    for mod, folder in ((holo, "holo"), (retro, "retro"), (phone, "phone")):
        name, text = getattr(mod, folder + "_asset")()
        (d / folder).mkdir(exist_ok=True)
        (d / folder / name).write_text(text, encoding="utf-8")

    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(d), **k)

        def log_message(self, *a):
            pass
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), H)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


@pytest.fixture(scope="module", params=("webkit", "chromium"))
def browser(request):
    if pw is None:
        pytest.skip("Playwright is not installed")
    with pw.sync_playwright() as p:
        try:
            b = getattr(p, request.param).launch()
        except Exception as e:
            pytest.skip(f"no {request.param}: {e}")
        yield b
        b.close()


def _open(browser, site, page, style, **ctx_kw):
    ctx = browser.new_context(**ctx_kw)
    ctx.add_init_script("try{localStorage.setItem('alto-bg-v1-style',%s)}catch(e){}" % json.dumps(style))
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(f"{site}/{page}", wait_until="load")
    pg.wait_for_timeout(1500)
    pg.evaluate("s=>window._altoStyle&&window._altoStyle.set(s)", style)
    pg.wait_for_timeout(1200)
    return ctx, pg, errors


def _timeline_text(browser, site, style):
    """The vertical timeline's enlarged text in this style: the title and body font sizes and the zoom."""
    ctx, pg, _ = _open(browser, site, "outline.html", style, viewport={"width": 1440, "height": 900})
    try:
        pg.evaluate("enterFocus('revocation')")
        pg.wait_for_timeout(1300)
        m = pg.evaluate(CARD)
    finally:
        ctx.close()
    return m["title"]["fs"], m["body"], m["zoom"]


def _clear(pg, m, label):
    bad = [c["id"] for c in pg.evaluate(CHROME) if _inter(m, c)]
    assert not bad, f"{label}: the enlarged card {m['l']:.0f},{m['t']:.0f}-{m['r']:.0f},{m['b']:.0f} meets the chrome {bad}"
    assert all(m["corners"]), f"{label}: the title's first line is covered ({m['title']})"


@pytest.mark.parametrize("style", STYLES)
@pytest.mark.parametrize("size", list(SIZES))
def test_a_click_enlarges_the_card_and_the_keys_and_the_step_bar_move_it(browser, site, style, size):
    ref = _timeline_text(browser, site, style)
    ctx, pg, errors = _open(browser, site, "lanes.html", style, viewport=SIZES[size])
    try:
        S = pg.evaluate(STOPS)
        pg.evaluate("id=>window._altoLanesStep(id)", S[2])
        pg.wait_for_timeout(1400)
        small = pg.evaluate(SMALL, S[2])
        pg.click(f"#node-{S[2]} .node-card")
        pg.wait_for_timeout(1400)
        label = f"{style} {size}"
        assert pg.evaluate(FOCUS) == S[2] and not pg.evaluate(DETAIL), label             # enlarged, the card it was clicked on
        m = pg.evaluate(CARD)
        px = lambda v: round(float(str(v).rstrip("px")), 2)                              # the timeline's enlarged text, not shrunk
        assert (px(m["title"]["fs"]), px(m["body"]), m["zoom"]) == (px(ref[0]), px(ref[1]), ref[2]), (label, m["title"]["fs"], m["body"], m["zoom"], ref)
        assert abs((m["w"] / m["h"]) / (small[0] / small[1]) - 1) <= 0.01, (label, m["w"], m["h"], small)   # the small card's shape
        assert m["w"] > small[0] * 1.3, (label, m["w"], small)                         # and enlarged
        _clear(pg, m, label)
        assert pg.evaluate("getComputedStyle(document.getElementById('lanes-nav')).opacity") == "1"   # the step bar stays, as chrome
        pg.keyboard.press("ArrowRight")
        pg.wait_for_timeout(1300)
        assert pg.evaluate(FOCUS) == S[3], label
        pg.click("#lanes-nav .lnv-next")
        pg.wait_for_timeout(1300)
        assert pg.evaluate(FOCUS) == S[4], label
        _clear(pg, pg.evaluate(CARD), label + " after the step bar")
        pg.click("#lanes-nav .lnv-prev")
        pg.wait_for_timeout(1300)
        assert pg.evaluate(FOCUS) == S[3], label
        pg.keyboard.press("ArrowLeft")
        pg.wait_for_timeout(1300)
        assert pg.evaluate(FOCUS) == S[2], label
        pg.mouse.move(30, 520)                                                   # (off the card: over a card's own scrolling text the wheel scrolls the text)
        pg.mouse.wheel(0, 100)                                                   # the first scroll closes the card (Esc does nothing here)
        pg.wait_for_timeout(900)
        assert pg.evaluate(FOCUS) is None, label
        assert pg.evaluate("document.querySelectorAll('#world .node-card.alto-sf').length") == 0     # back to the small card
    finally:
        ctx.close()
    assert not errors, errors


def test_a_search_hit_lands_enlarged_and_the_enlarged_card_opens_its_page(browser, site):
    ctx, pg, errors = _open(browser, site, "lanes.html", "holo", viewport=SIZES["d1440"])
    try:
        S = pg.evaluate(STOPS)
        pg.evaluate("id=>window._altoSearch ? window._altoSearch.land(id) : searchGoToNode(id)", S[4])
        pg.wait_for_timeout(1600)
        assert pg.evaluate(FOCUS) == S[4] and not pg.evaluate(DETAIL)
        _clear(pg, pg.evaluate(CARD), "search hit")
        pg.click(f"#node-{S[4]} .node-card .node-title")
        pg.wait_for_timeout(900)
        assert pg.evaluate(DETAIL)
    finally:
        ctx.close()
    assert not errors, errors


@pytest.mark.parametrize("orient", list(PHONE))
def test_a_phone_tap_keeps_the_timelines_phone_pattern(browser, site, orient):
    """On a phone a tap opens the card's page in the vertical timeline; Horizontal does the same, and keeps its phone UI."""
    seen = {}
    for page in ("outline.html", "lanes.html"):
        ctx, pg, errors = _open(browser, site, page, "classic", **PHONE[orient])
        try:
            ids = pg.evaluate("[...document.querySelectorAll('#world .node .node-card')].filter(n=>{const r=n.getBoundingClientRect();"
                              "return r.width>40&&r.top>90&&r.bottom<innerHeight-90&&r.left>=0&&r.right<=innerWidth}).map(n=>n.parentNode.id)")
            assert ids, f"{page} {orient}: no card on the screen"
            pg.tap(f"#{ids[0]} .node-card")
            pg.wait_for_timeout(1500)
            seen[page] = (pg.evaluate(FOCUS) is not None, pg.evaluate(DETAIL))
        finally:
            ctx.close()
        assert not errors, errors
    assert seen["lanes.html"] == seen["outline.html"], seen
