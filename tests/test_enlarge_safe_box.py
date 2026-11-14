"""An enlarged card never draws under the page's chrome (Luke, 2026-11-13, his Civil Procedure outline in Holo: the card ran up under
the title tab and a second, wrapped row of filter chips; "find a solution so this can't happen").

engine_patches.py, enlarge-safe-box: the card is enlarged as ever (same zoom, same text size) and left alone when it fits. When
today's enlarged box would cross the chrome — measured, however many rows the chips wrap to — its box is made smaller, width and
height together (the small card's shape), until it fits between the chrome with a margin; the text re-flows and scrolls inside.

Measured in a real browser for Classic, Retro and Holo; desktop 1440x900 and 1280x720; the phone's Whole view, portrait and
landscape; chips wrapping to 2 and to 3 rows. WebKit first (Luke uses Safari), Chromium where installed. Skipped without Playwright."""
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

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None

ELEMENTS = ["Due Process", "Minimum Contacts", "Consent & Waiver", "Full Faith and Credit", "Federal Rule 4", "Gravamen",
            "Statute of Limitations", "Collateral Attack", "Notice", "Standing", "Ripeness", "Mootness", "Venue Transfer",
            "Forum Non Conveniens", "Supplemental Jurisdiction", "Removal", "Claim Preclusion", "Issue Preclusion", "Joinder",
            "Impleader", "Interpleader", "Intervention", "Class Actions", "Discovery Scope", "Work Product", "Summary Judgment",
            "Directed Verdict", "New Trial", "Appeal", "Erie Doctrine", "Rule 11"]
CHIPS = {2: 13, 3: 31}                     # element chips that wrap the bar to 2 / 3 rows at 1440
TALL, SHORT = "offer", "revocation"
DESKTOP = {"d1440": dict(viewport={"width": 1440, "height": 900}),
           "d1280": dict(viewport={"width": 1280, "height": 720})}
_IPHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) "
           "Version/18.0 Mobile/15E148 Safari/604.1")
PHONE = {"portrait": dict(viewport={"width": 390, "height": 844}, device_scale_factor=3, is_mobile=True, has_touch=True, user_agent=_IPHONE),
         "landscape": dict(viewport={"width": 844, "height": 390}, device_scale_factor=3, is_mobile=True, has_touch=True, user_agent=_IPHONE)}
STYLES = ("classic", "retro", "holo")


def page_html(n_el):
    """The outline sample with a wrapping chip bar and one Civ Pro-like long card (TALL)."""
    d = json.loads((ROOT / "samples" / "outline_brief.json").read_text(encoding="utf-8"))
    b = d["brief"]
    b["axes"].append({"label": "Elements", "singular": "Element", "values": [{"id": "el%d" % i, "name": n} for i, n in enumerate(ELEMENTS[:n_el])]})
    cases = [v["id"] for v in b["axes"][0]["values"]]
    for i, n in enumerate(d["nodes"]):
        n["axis2_values"] = ["el%d" % (i % n_el)]
        if n["id"] == TALL:
            n["title"] = "Federal Rules vs. State Law: Direct Conflict or Silence"
            n["desc"] = ("In a diversity action, federal judges cannot depart from state substantive law. If the federal rule is silent "
                         "or agnostic toward the state procedural rule, state law controls; if it directly conflicts, federal law "
                         "controls (supremacy clause). ") * 3
            n["axis1_values"] = cases[:4]
    brief, nodes, conns = load_brief(d)
    return build_timeline(brief, nodes, conns)[0]


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    if pw is None:
        pytest.skip("Playwright is not installed")
    d = tmp_path_factory.mktemp("enlarge_safe")
    for rows, n in CHIPS.items():
        (d / f"t{rows}.html").write_text(page_html(n), encoding="utf-8")
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


# Everything drawn over the canvas, found independently of the page's own walk: the bars, every chip, the corner buttons and
# rails, and any other positioned element outside the canvas that is not a full-window layer.
CHROME = r"""()=>{const vw=innerWidth,vh=innerHeight,cv=document.getElementById('canvas'),out=[];
 const vis=(c,cs)=>cs.display!=='none'&&cs.visibility!=='hidden'&&parseFloat(cs.opacity)>0;
 const add=(c,r)=>{const iw=Math.min(r.right,vw)-Math.max(r.left,0), ih=Math.min(r.bottom,vh)-Math.max(r.top,0);
   if(iw>1&&ih>1&&iw*ih<0.4*vw*vh) out.push({id:c.id||String(c.className).slice(0,24)||(c.tagName+'<'+(c.parentNode.id||String(c.parentNode.className).slice(0,20))),l:r.left,t:r.top,r:r.right,b:r.bottom});};
 (function walk(e){for(const c of e.children){ if(c===cv||c.tagName==='SCRIPT'||c.tagName==='STYLE') continue;
   const cs=getComputedStyle(c); if(!vis(c,cs)) continue; const r=c.getBoundingClientRect();
   if(/^(fixed|absolute|sticky)$/.test(cs.position)&&!c.contains(cv)){ add(c,r); }
   walk(c);}})(document.body);
 document.querySelectorAll('#nav button.nav-btn,#nav .nav-group-label').forEach(c=>{const cs=getComputedStyle(c); if(vis(c,cs)) add(c,c.getBoundingClientRect());});
 return out;}"""

CARD = r"""()=>{const n=document.querySelector('#world .node.focused'), c=n&&n.querySelector('.node-card'); if(!c) return null;
 const q=c.getBoundingClientRect(), t=c.querySelector('.node-title'), d=c.querySelector('.node-desc');
 const tr=t.getBoundingClientRect(), pad=3, hit=(x,y)=>{const e=document.elementFromPoint(x,y); return !!(e&&c.contains(e));};
 const de=document.documentElement, Z=(parseFloat(getComputedStyle(de).zoom)||1)*(parseFloat(getComputedStyle(document.body).zoom)||1);
 const rows=new Set([...document.querySelectorAll('#nav button.nav-btn')].filter(b=>b.offsetWidth).map(b=>Math.round(b.getBoundingClientRect().top)));
 return {id:n.id, l:q.left,t:q.top,r:q.right,b:q.b,b:q.bottom, w:q.width,h:q.height, zoom:c.style.zoom, sf:c._sf?{w:c._sf.w,h:c._sf.h,f:c._sf.f}:null,
   w0:c.offsetWidth, scroll:[c.scrollHeight,c.clientHeight], Z,
   title:{l:tr.left,t:tr.top,r:tr.right, fs:getComputedStyle(t).fontSize}, body:d?getComputedStyle(d).fontSize:null,
   corners:[hit(tr.left+pad,tr.top+pad), hit(Math.min(tr.right,q.right)-pad,tr.top+pad)], rows:rows.size, vw:innerWidth, vh:innerHeight};}"""


def _inter(a, b):
    return min(a["r"], b["r"]) - max(a["l"], b["l"]) > 0.5 and min(a["b"], b["b"]) - max(a["t"], b["t"]) > 0.5


def _open(browser, site, rows, style, ctx_kw, query=""):
    ctx = browser.new_context(**ctx_kw)
    ctx.add_init_script("try{localStorage.setItem('alto-bg-v1-style',%s)}catch(e){}" % json.dumps(style))
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(f"{site}/t{rows}.html{query}", wait_until="load")
    pg.wait_for_timeout(1200)
    pg.evaluate("s=>window._altoStyle&&window._altoStyle.set(s)", style)
    pg.wait_for_timeout(1300)
    return ctx, pg, errors


def _enlarge(pg, nid):
    pg.evaluate("id=>{ if(window._focusedNodeId) exitFocus(); }", nid)
    pg.wait_for_timeout(500)
    pg.evaluate("id=>enterFocus(id)", nid)
    pg.wait_for_timeout(1300)
    return pg.evaluate(CARD)


def _reference(browser, site, style):
    """Today's enlarged text size: the same card on a window so big nothing is fitted."""
    ctx, pg, _ = _open(browser, site, 2, style, dict(viewport={"width": 2400, "height": 2400}))
    try:
        m = _enlarge(pg, TALL)
    finally:
        ctx.close()
    assert m and not m["sf"], m
    return m


def _check(m, chrome, label, ref):
    bad = [c["id"] for c in chrome if _inter(m, c)]
    assert not bad, f"{label}: the enlarged card {m['l']:.0f},{m['t']:.0f}-{m['r']:.0f},{m['b']:.0f} meets the chrome {bad}"
    assert m["t"] >= -0.5 and m["b"] <= m["vh"] + 0.5 and m["l"] >= -0.5 and m["r"] <= m["vw"] + 0.5, (label, m)
    assert all(m["corners"]), f"{label}: the title's first line is covered at a top corner ({m['title']})"
    assert m["zoom"] == "1.7", (label, m["zoom"])                                    # the enlarge itself is untouched
    px = lambda v: float(str(v).rstrip("px"))                                         # today's enlarged text size, not shrunk
    assert abs(px(m["title"]["fs"]) - px(ref["title"]["fs"])) < 0.02 and abs(px(m["body"]) - px(ref["body"])) < 0.02, \
        (label, m["title"]["fs"], m["body"], ref["title"]["fs"], ref["body"])
    if m["sf"] and m["sf"]["f"] <= 1 / 1.7 + 1e-6:                                   # as narrow as the small card (a phone on its side):
        assert abs(m["w"] - m["sf"]["w"] * m["Z"]) <= 1, (label, m)                      # the width holds there, the height gives
    elif m["sf"]:                                                                    # fitted: the small card's shape
        a0, a1 = m["sf"]["w"] / m["sf"]["h"], m["w"] / m["h"]
        assert abs(a1 / a0 - 1) <= 0.01, f"{label}: enlarged aspect {a1:.4f} vs small {a0:.4f}"
    else:                                                                            # fits today: today's size, to the pixel
        assert abs(m["w"] - m["w0"] * 1.7 * m["Z"]) <= 1, (label, m)


@pytest.mark.parametrize("style", STYLES)
@pytest.mark.parametrize("rows", (2, 3))
@pytest.mark.parametrize("size", list(DESKTOP))
def test_an_enlarged_card_stays_clear_of_the_chrome_on_a_computer(browser, site, style, rows, size):
    ref = _reference(browser, site, style)
    ctx, pg, errors = _open(browser, site, rows, style, DESKTOP[size])
    try:
        tall = _enlarge(pg, TALL)
        chrome = pg.evaluate(CHROME)
        assert tall["rows"] >= rows, f"the chip bar wraps to {tall['rows']} rows, not {rows}"
        if size == "d1280":
            assert tall["sf"], f"{size}: the long card fits today; the test card is meant to collide ({tall})"
        _check(tall, chrome, f"{style} {size} {rows} rows, long card", ref)
        if tall["sf"]:
            assert tall["scroll"][0] > tall["scroll"][1] + 4                         # the rest of its text scrolls inside it
        short = _enlarge(pg, SHORT)
        assert not short["sf"], f"{size}: a card that fits today was refitted ({short})"
        _check(short, pg.evaluate(CHROME), f"{style} {size} {rows} rows, short card", {"title": short["title"], "body": short["body"]})
    finally:
        ctx.close()
    assert not errors, errors


def test_the_fitted_card_scrolls_under_the_wheel_and_refits_when_the_chips_wrap(browser, site):
    ctx, pg, errors = _open(browser, site, 2, "holo", DESKTOP["d1440"])
    try:
        m = _enlarge(pg, TALL)
        pg.mouse.move((m["l"] + m["r"]) / 2, (m["t"] + m["b"]) / 2)
        pg.mouse.wheel(0, 300)
        pg.wait_for_timeout(500)
        assert pg.evaluate("document.querySelector('#world .node.focused .node-card').scrollTop") > 0
        assert pg.evaluate("window._focusedNodeId") == TALL                             # the wheel scrolled the card, it did not hop
        pg.set_viewport_size({"width": 1100, "height": 900})                            # the chips wrap to more rows
        pg.wait_for_timeout(1400)
        m2 = pg.evaluate(CARD)
        assert m2["rows"] > m["rows"], (m["rows"], m2["rows"])
        _check(m2, pg.evaluate(CHROME), "after the chips wrapped further", m)
    finally:
        ctx.close()
    assert not errors, errors


@pytest.mark.parametrize("style", STYLES)
@pytest.mark.parametrize("rows", (2, 3))
@pytest.mark.parametrize("orient", list(PHONE))
def test_an_enlarged_card_stays_clear_of_the_chrome_on_a_phone(browser, site, style, rows, orient):
    ref = _reference(browser, site, style)
    ctx, pg, errors = _open(browser, site, rows, style, PHONE[orient], "?view=whole&ix=0")
    try:
        assert pg.evaluate("document.documentElement.classList.contains('phone-whole')")
        # A tap on a phone opens the card's detail page (a full-screen readout), not an enlarged card on the board. Any other
        # way in (a search hit, a hop) enlarges it on the full-size board, so the board is brought to full size first.
        pg.evaluate("window._altoPhone.ovSet(1)")
        pg.wait_for_timeout(300)
        for nid in (TALL, SHORT):
            m = _enlarge(pg, nid)
            assert m, f"{orient}: no enlarged card"
            r = ref if nid == TALL else {"title": m["title"], "body": m["body"]}
            _check(m, pg.evaluate(CHROME), f"{style} phone {orient} {rows} rows, {nid}", r)
    finally:
        ctx.close()
    assert not errors, errors
