"""The Claude option stays reachable in manual edit mode (Board B-1121-CLAUDE-IN-EDIT, Luke L-1121-HOLO-NONE).

While editing, the edit pill (with its Edit with Claude half) is hidden; the edit bar (#alto-edit-exit) carries a Claude button built from the pill's own first half and calling
the same window._altoEditTimeline. Real WebKit at d1440, p390, l844 (844x390) and 320x640 in Classic, Holo and Retro: visible, clickable, 44pt on phones, no rect overlap, same flow as
the pill, saved first (an unsaved edit is stored in the account before Claude opens), and gone again after Done. Shots: CLAUDE_EDIT_SHOTS=<dir>."""
import functools
import http.server
import json
import os
import socketserver
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SHOTS = os.environ.get("CLAUDE_EDIT_SHOTS", "")
UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"


def _page():
    from alto.build.builder import build_timeline, load_brief
    from alto.build.single_file import private_page
    samples = json.loads((ROOT / "samples" / "outline_brief.json").read_text("utf-8"))
    b, nodes, conns = load_brief({"brief": samples["brief"], "nodes": samples["nodes"], "connections": samples.get("connections", [])})
    html, _ = build_timeline(b, nodes, conns)
    return private_page(b, html, "x")


def _star_d():
    import re
    from alto.build.manual_edit import MANUAL_JS
    return re.search(r"var STAR_SVG = '<svg[^']*?<path d=\"([^\"]+)\"", MANUAL_JS).group(1)


STAR_D = _star_d()


def test_the_bar_button_is_the_pills_own_first_half_and_the_pill_stays_hidden_while_editing():
    from alto.build.manual_edit import MANUAL_CSS, MANUAL_JS
    assert "pillHTML().split('<span')[0].replace('aep-half', 'ee-h ee-claude')" in MANUAL_JS      # reused, not a second copy of the star
    assert "ee-claude')) claude();" in MANUAL_JS
    assert "html.mobile #alto-edit-pill,html.alto-editing #alto-edit-pill,html.printing #alto-edit-pill{display:none !important;}" in MANUAL_CSS


pw = pytest.importorskip("playwright.sync_api")
FAKE = """(function(){ var store=null; window.__log=[];
 var C={enabled:true, known:true, user:{uid:'u1', email:'tester@example.com'}, getEdits:function(){ return Promise.resolve(store); },
  putEdits:function(t,d){ store=JSON.parse(JSON.stringify(d)); window.__log.push(['put', Object.keys(store.ops||{})]); return Promise.resolve(); }, watchEdits:function(){ return function(){}; }};
 Object.defineProperty(window,'AltoCloud',{get:function(){return C;}, set:function(){}, configurable:true}); })();"""
SIZES = (("d1440", 1440, 900), ("p390", 390, 844), ("l844", 844, 390), ("p320", 320, 640))
STYLES = (("classic", "light"), ("holo", "dark"), ("retro", "dark"))
MEASURE = """() => {
  const bar = document.getElementById('alto-edit-exit'), cl = bar && bar.querySelector('.ee-claude'), R = e => e.getBoundingClientRect();
  if(!cl) return {none: true, barShown: !!bar && getComputedStyle(bar).display !== 'none'};
  const b = R(bar), c = R(cl), vis = e => { const s = getComputedStyle(e); return s.display !== 'none' && s.visibility !== 'hidden' && R(e).width > 0; };
  const kids = [...bar.children].filter(vis).map(e => ({cls: e.className, r: R(e)}));
  const over = [];
  for(let i = 0; i < kids.length; i++) for(let j = i + 1; j < kids.length; j++){ const a = kids[i].r, d = kids[j].r;
    if(a.left < d.right - .5 && d.left < a.right - .5 && a.top < d.bottom - .5 && d.top < a.bottom - .5) over.push([kids[i].cls, kids[j].cls]); }
  const ctl = [...document.querySelectorAll('button,a,[role=button],#search-btn,#info-btn,#account-btn,#key-toggle,#mode-toggle,.tab-rail button,#sx-toggle,#scroll-hint')].filter(e => !bar.contains(e) && vis(e) && e.id !== 'alto-edit-exit')
    .filter(e => { const s = getComputedStyle(e), r = R(e); return +s.opacity > 0.05 && s.pointerEvents !== 'none' && r.width * r.height < innerWidth * innerHeight * .3; });
  const pad = innerWidth < 900 ? 8 : 0;   // phones: 8px of clear space beside the bar, not just no overlap
  const hit = ctl.filter(e => { const r = R(e); return r.left < b.right + pad - .5 && b.left - pad < r.right - .5 && r.top < b.bottom - .5 && b.top < r.bottom - .5; }).map(e => (e.id || (e.innerText || '').trim().slice(0, 12) || e.className.toString().slice(0, 20)));
  const mid = document.elementFromPoint(c.left + c.width / 2, c.top + c.height / 2);
  const pill = document.getElementById('alto-edit-pill'), ip = document.querySelector('.alto-edit-pill.in-page');
  return {w: c.width, h: c.height, over, hit, bar: [b.left, b.top, b.right, b.bottom], vw: innerWidth, vh: innerHeight, topIsBtn: !!mid && cl.contains(mid),
    label: cl.getAttribute('aria-label'), svgd: cl.querySelector('svg path').getAttribute('d'), svgw: cl.querySelector('svg').getAttribute('width'), drawn: R(cl.querySelector('svg')).width, text: getComputedStyle(cl, '::after').content, before: ['top', 'right', 'bottom', 'left'].map(k => getComputedStyle(cl, '::before')[k]), pillShown: [pill, ip].some(e => e && vis(e)), cls: document.documentElement.className};
}"""


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    from alto.build import holo, retro
    root = tmp_path_factory.mktemp("cie")
    (root / "p.html").write_text(_page(), "utf-8")
    for m, fn in ((retro, retro.retro_asset), (holo, holo.holo_asset)):
        f = root / m.PATH.lstrip("/"); f.parent.mkdir(parents=True, exist_ok=True); f.write_text(fn()[1], encoding="utf-8")
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root)); h.log_message = lambda *a: None
    socketserver.TCPServer.allow_reuse_address = True
    srv = socketserver.TCPServer(("127.0.0.1", 0), h); threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def _open(b, server, w, h, style, theme):
    phone = w < 700 or h < 500
    ctx = b.new_context(viewport={"width": w, "height": h}, is_mobile=phone, has_touch=phone, user_agent=UA if phone else None, device_scale_factor=2 if phone else 1)
    ctx.add_init_script(FAKE + ";try{localStorage.setItem('alto-theme-v1','%s')}catch(e){}" % theme)
    pg = ctx.new_page()
    pg.goto(f"{server}/p.html", wait_until="domcontentloaded")
    pg.wait_for_function("typeof showDetail === 'function' && window._altoManual", timeout=30000); pg.wait_for_timeout(1200)
    if style != "classic":
        pg.evaluate("window._altoStyle.set('%s');0" % style); pg.wait_for_timeout(1500)
    return ctx, pg


@pytest.fixture(scope="module")
def runs(server):
    out = {}
    with pw.sync_playwright() as p:
        b = p.webkit.launch()
        for style, theme in STYLES:
            for tag, w, h in SIZES:
                ctx, pg = _open(b, server, w, h, style, theme)
                pg.evaluate("window._altoManual.enter();0"); pg.wait_for_timeout(900)
                m = pg.evaluate(MEASURE)
                if SHOTS:
                    pg.screenshot(path=f"{SHOTS}/{style}-{tag}-edit.png")
                m["clicks"] = pg.evaluate("() => { window.__n = 0; window._altoEditTimeline = function(){ window.__n++; }; return 0; }")
                pg.click("#alto-edit-exit .ee-claude", timeout=5000); pg.wait_for_timeout(300)
                m["opened"] = pg.evaluate("window.__n")
                pg.evaluate("document.querySelector('#alto-edit-exit .ee-done').click();0"); pg.wait_for_timeout(700)
                m["after"] = pg.evaluate(MEASURE)
                if tag != "d1440":
                    pg.evaluate("showDetail('node', 'definiteness');0"); pg.wait_for_timeout(900)      # a phone has its pill at the foot of a page
                m["pill_after"] = pg.evaluate("""() => { const vis = e => e && getComputedStyle(e).display !== 'none' && e.getBoundingClientRect().width > 0;
                  const d = document.getElementById('alto-edit-pill'), ip = document.querySelector('.alto-edit-pill.in-page');
                  return {desk: vis(d), inpage: !!ip, html: !!document.querySelector('.alto-edit-pill .aep-claude')}; }""")
                if SHOTS:
                    pg.screenshot(path=f"{SHOTS}/{style}-{tag}-done.png")
                out[(style, tag)] = m; ctx.close()
        b.close()
    return out


def test_visible_clickable_44pt_on_phones_and_overlapping_nothing(runs):
    for (style, tag), m in runs.items():
        assert not m.get("none"), (style, tag, m)
        assert m["topIsBtn"], (style, tag)                       # nothing sits over the button's centre
        assert m["over"] == [] and m["hit"] == [], (style, tag, m["over"], m["hit"])
        l, t, r, b = m["bar"]
        assert l >= 20 and m["vw"] - r >= 20 and t >= 0 and b <= m["vh"], (style, tag, m["bar"])      # 20px from both screen edges at every width
        assert m["label"] == "Edit with Claude" and m["svgd"] == STAR_D and m["svgw"] == "19" and m["drawn"] >= 15.5, (style, tag, m["drawn"])   # the pill's own mark, 19px like the pill's (the desktop page is drawn at 0.85)
        assert m["label"] == "Edit with Claude"
        if tag != "d1440":
            assert m["w"] + 4 >= 43.5 and m["h"] >= 39.5 and m["before"] == ["-2px", "-2px", "-2px", "-2px"], (style, tag, m["w"], m["h"], m["before"])      # drawn 40 x 40, tap box 44 x 44 (its ::before)
        else:
            assert m["h"] >= 22, (style, tag)


def test_it_opens_the_same_claude_flow_as_the_pill(runs):
    assert all(m["opened"] == 1 for m in runs.values()), {k: m["opened"] for k, m in runs.items()}


def test_after_done_the_pill_is_back_and_the_bar_button_is_gone(runs):
    for (style, tag), m in runs.items():
        assert (m["after"].get("none") or m["after"]["w"] == 0) and not m["after"].get("barShown"), (style, tag, m["after"])
        assert m["pill_after"]["html"], (style, tag)
        if tag == "d1440":
            assert m["pill_after"]["desk"], (style, tag)


def test_an_unsaved_edit_is_stored_in_the_account_before_claude_opens(server):
    with pw.sync_playwright() as p:
        b = p.webkit.launch()
        ctx, pg = _open(b, server, 1440, 900, "classic", "light")
        pg.evaluate("window._altoManual.enter();0"); pg.wait_for_timeout(700)
        pg.evaluate("""() => { window.__first = null; window._altoEditTimeline = function(){ window.__log.push(['claude', Object.keys(JSON.parse(localStorage.getItem(Object.keys(localStorage).filter(k => k.indexOf('alto-ed-') === 0)[0] || '{}') || '{}').ops || {})]); };
          return window._altoManual.change('n|definiteness|title', 'An edit made a moment ago'); }""")
        assert pg.evaluate("window._altoManual.ops()['n|definiteness|title'].v") == "An edit made a moment ago"
        assert pg.evaluate("window.__log.length") == 0                       # still inside the 600 ms debounce: nothing sent yet
        pg.click("#alto-edit-exit .ee-claude"); pg.wait_for_timeout(500)
        log = pg.evaluate("window.__log")
        kinds = [x[0] for x in log]
        assert kinds.index("put") < kinds.index("claude"), log                  # stored first, then Claude
        assert "n|definiteness|title" in log[kinds.index("put")][1]
        assert "n|definiteness|title" in log[kinds.index("claude")][1]          # (and in this device's own copy)
        ctx.close(); b.close()


def test_a_field_still_being_typed_is_saved_by_the_button_before_claude_opens(server):
    """A field that edits in place (the page's own title), typed into and never left: the button commits it, stores it, and only then opens Claude."""
    with pw.sync_playwright() as p:
        b = p.webkit.launch()
        ctx, pg = _open(b, server, 1440, 900, "classic", "light")
        pg.evaluate("window._altoManual.enter();0"); pg.wait_for_timeout(500)
        pg.evaluate("showDetail('node', 'definiteness');0"); pg.wait_for_timeout(900)
        pg.click("#detail-content .detail-name"); pg.wait_for_timeout(300)
        assert pg.evaluate("!!document.querySelector('.aed-on')"), "the page title did not open in place"
        pg.evaluate("""() => { const e = document.querySelector('.aed-on'); e.textContent = 'Typed and never left'; e.dispatchEvent(new Event('input', {bubbles: true}));
          window._altoEditTimeline = function(){ window.__log.push(['claude', Object.keys(JSON.parse(localStorage.getItem(Object.keys(localStorage).filter(k => k.indexOf('alto-ed-') === 0)[0] || '{}') || '{}').ops || {})]); }; }""")
        assert pg.evaluate("window.__log.length") == 0
        pg.click("#alto-edit-exit .ee-claude"); pg.wait_for_timeout(600)
        log = pg.evaluate("window.__log"); kinds = [x[0] for x in log]
        assert "put" in kinds and kinds.index("put") < kinds.index("claude"), log
        assert "n|definiteness|title" in log[kinds.index("put")][1] and "n|definiteness|title" in log[kinds.index("claude")][1], log
        assert pg.evaluate("window._altoManual.ops()['n|definiteness|title'].v") == "Typed and never left"
        ctx.close(); b.close()
