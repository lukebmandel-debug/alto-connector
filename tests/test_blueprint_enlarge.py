"""The Memory Blueprint enlarges a card where it stands (Luke, 2026-11-13: "we need the ability to enlarge nodes in memory blueprint").

Before, a click on a room tag left the plan for the card's detail page, and a click on a room opened the room's panel. Now the tag (or its room)
enlarges the timeline's own card over the plan beside its chip, as the Memory Atlas does: the timeline's enlarge (the same face, zoom and text
size), and engine_patches.py's enlarge-safe-box keeps it clear of every bar (the floor tabs, the dock, the name card, the side rail, the title).
The arrows and A.tour hop card by card; Esc, the close button or a click on the plan shrinks it; a search hit lands on it. A phone enlarges too,
as the Atlas's does. Also the plan's wheel (Luke: "two finger zoom in, and two finger scroll moves around"): a pinch (ctrl+wheel, Safari's
gesture events) zooms around the pointer, a plain wheel pans, and over an enlarged card the wheel scrolls the card.

Real HTTP, WebKit first (Luke uses Safari), Chromium where installed. Skipped without Playwright."""
import http.server
import json
import socketserver
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests.test_building_blueprint_live import ACTS, PLAN  # noqa: E402
from alto.build import building_schema as bs, palace_assets  # noqa: E402
from alto.build.builder import build_timeline, load_brief  # noqa: E402
from alto.build.palace_building_asset import BLUEPRINT_ALL_FLOORS  # noqa: E402

# All floors is behind a build switch, off by default (palace_building_asset.BLUEPRINT_ALL_FLOORS; ALTO_BP_ALL_FLOORS=1 turns it on): its tests wait for it.
needs_all = pytest.mark.skipif(not BLUEPRINT_ALL_FLOORS, reason="Blueprint All floors is off (ALTO_BP_ALL_FLOORS=1 builds it in)")

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None

STYLES = ("classic", "retro", "holo")
DESKTOP = {"d1440": {"width": 1440, "height": 900}, "d1280": {"width": 1280, "height": 720}}
_IPHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) "
           "Version/18.0 Mobile/15E148 Safari/604.1")
PHONE = dict(viewport={"width": 390, "height": 844}, device_scale_factor=3, is_mobile=True, has_touch=True, user_agent=_IPHONE)


LONG = ("In a diversity action, federal judges cannot depart from state substantive law. If the federal rule is silent or agnostic toward the "
        "state procedural rule, state law controls; if it directly conflicts, federal law controls (supremacy clause). ") * 6


def _html():
    """A page shaped like civ-pro-museum (92 cards on the PMA plan), the second card a long one (it cannot enlarge whole on a short window)."""
    nodes = [{"id": f"n{i}", "act": i * 6 // 92, "title": f"Concept number {i + 1}", "tag": "", "desc": LONG if i == 1 else "d"} for i in range(92)]
    b = {"title": "Civil Procedure — Memory Blueprint", "timeline_id": "civ-pro-museum", "mode": "palace", "palace_view": "building", "columns": 5,
         "node_noun": "Room", "period_noun": "Wing", "acts": ACTS,
         "building": {"plan_z": bs.pack(PLAN), "plan_h": bs.plan_hash(PLAN), "mode": "room", "assign": {}}}
    br, ns, cs = load_brief({"brief": b, "nodes": nodes})
    return build_timeline(br, ns, cs)[0]


def _timeline_html():
    d = json.loads((ROOT / "samples" / "outline_brief.json").read_text(encoding="utf-8"))
    brief, nodes, conns = load_brief(d)
    return build_timeline(brief, nodes, conns)[0]


@pytest.fixture(scope="module")
def site():
    if pw is None:
        pytest.skip("Playwright is not installed")
    pages = {"/index.html": _html(), "/t.html": _timeline_html()}
    plan = bs.hosted_json(PLAN)[1]
    cache = {}

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            path = self.path.split("?")[0]
            body, ct, code = b"no", "text/plain", 404
            if path in pages:
                body, ct, code = pages[path].encode(), "text/html; charset=utf-8", 200
            elif path == "/alto-cloud.js":
                body, ct, code = b"", "text/javascript", 200
            elif path.startswith("/bldg/plan-"):
                body, ct, code = plan.encode(), "application/json", 200
            else:
                if path not in cache:
                    cache[path] = palace_assets.find(path)
                hit = cache[path]
                if hit:
                    body, ct, code = hit[1].encode(), hit[0], 200
            self.send_response(code)
            self.send_header("Content-Type", ct)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    socketserver.TCPServer.allow_reuse_address = True
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), H)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield "http://127.0.0.1:%d" % srv.server_address[1]
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


def _open(browser, site, style="classic", ctx_kw=None, path="/index.html"):
    ctx = browser.new_context(**(ctx_kw or {"viewport": DESKTOP["d1440"]}))
    ctx.add_init_script("try{localStorage.setItem('alto-bg-v1-style',%s)}catch(e){}" % json.dumps(style))
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(site + path, wait_until="load")
    if path == "/index.html":
        pg.wait_for_function("window.AltoBuilding && AltoBuilding.plan", timeout=30000)
    pg.wait_for_timeout(1000)
    pg.evaluate("s=>window._altoStyle&&window._altoStyle.set(s)", style)
    pg.wait_for_timeout(1000)
    if style != "classic":
        assert pg.evaluate("s=>document.documentElement.classList.contains('alto-'+s)", style), f"{style} did not load"
    return ctx, pg, errors


# the floor the blueprint opened on before B-1126 (where the walk starts), for the tests of one floor
ONE_FLOOR = "AltoBuilding.selectLevel((AltoBuilding.plan.sp||{}).l||document.querySelector('#bldg-root .bl-tab:not([data-level=outside]):not([data-level=all])').dataset.level)"


# Everything drawn over the plan, found independently of the page's own walk: the Blueprint's bars (tabs, dock, name card, rail, footer) and
# every positioned element outside #bldg-root and the board that is not a full-window layer.
CHROME = r"""()=>{const vw=innerWidth,vh=innerHeight,out=[];
 const vis=(c,cs)=>cs.display!=='none'&&cs.visibility!=='hidden'&&parseFloat(cs.opacity)>0;
 // what of it is on screen: the part an overflow-clipping ancestor cuts away is not chrome (Holographic's logo is a 38 px window on a 450 px animated sheet in the
 // title bar; the sheet's own box sweeps the page as it plays and met the card at 1280 px, though none of it shows outside the window)
 const seen=c=>{let r=c.getBoundingClientRect(), q={left:r.left,top:r.top,right:r.right,bottom:r.bottom};
   for(let p=c.parentElement;p&&p!==document.body;p=p.parentElement){ const ps=getComputedStyle(p); if(ps.overflow==='visible'&&ps.overflowX==='visible'&&ps.overflowY==='visible') continue;
     const b=p.getBoundingClientRect(); q={left:Math.max(q.left,b.left),top:Math.max(q.top,b.top),right:Math.min(q.right,b.right),bottom:Math.min(q.bottom,b.bottom)}; }
   return q;};
 const add=(c,r)=>{const iw=Math.min(r.right,vw)-Math.max(r.left,0), ih=Math.min(r.bottom,vh)-Math.max(r.top,0);
   if(iw>1&&ih>1&&iw*ih<0.4*vw*vh) out.push({id:c.id||String(c.className).slice(0,30),l:r.left,t:r.top,r:r.right,b:r.bottom});};
 document.querySelectorAll('#bldg-root .bl-head,#bldg-root .bl-dock,#bldg-root .bl-tabs,#bldg-root .bl-zoom,#bldg-root .bl-foot,#bldg-root .bl-info,#bldg-root .bl-dock button').forEach(c=>{const cs=getComputedStyle(c); if(vis(c,cs)&&cs.display!=='contents') add(c,c.getBoundingClientRect());});
 (function walk(e){for(const c of e.children){ if(c.id==='bldg-root'||c.id==='world'||c.tagName==='SCRIPT'||c.tagName==='STYLE') continue;
   const cs=getComputedStyle(c); if(!vis(c,cs)) continue;
   if(/^(fixed|absolute|sticky)$/.test(cs.position)) add(c,seen(c));
   walk(c);}})(document.body);
 return out;}"""

CARD = r"""()=>{const w=document.querySelector('#bldg-root .bl-enl:not(.bl-out)'), c=w&&w.querySelector('.node-card'); if(!c) return null;
 const q=c.getBoundingClientRect(), t=c.querySelector('.node-title'), tr=t.getBoundingClientRect(), pad=3, hit=(x,y)=>{const e=document.elementFromPoint(x,y); return !!(e&&c.contains(e));};
 const x=w.querySelector('.bl-enlx').getBoundingClientRect();
 return {id:w.getAttribute('data-node'), l:q.left,t:q.top,r:q.right,b:q.bottom,w:q.width,h:q.height, zoom:c.style.zoom, sf:c._sf?{w:c._sf.w,h:c._sf.h,f:c._sf.f}:null,
   fs:parseFloat(getComputedStyle(t).fontSize)*(parseFloat(c.style.zoom)||1), th:tr.height, scroll:[c.scrollHeight,c.clientHeight],
   x:{l:x.left,t:x.top,r:x.right,b:x.bottom}, corners:[hit(tr.left+pad,tr.top+pad), hit(Math.min(tr.right,q.right)-pad,tr.top+pad)],
   en:AltoBuilding.enlarged(), vb:document.querySelector('#bldg-root svg.bl-svg').getAttribute('viewBox'), vw:innerWidth, vh:innerHeight};}"""

REF = r"""()=>{const n=document.querySelector('#world .node.focused'), c=n&&n.querySelector('.node-card'), t=c&&c.querySelector('.node-title');
 return c?{fs:parseFloat(getComputedStyle(t).fontSize)*(parseFloat(c.style.zoom)||1), zoom:c.style.zoom}:null;}"""


# Art 2026-11-14: no tag draws over the enlarged card or its close button; one whose rect meets them is hidden AND under the card (elementFromPoint),
# and the card's own tag is never covered by it (any width from 360 px)
TAGS = r"""()=>{ const w=document.querySelector('#bldg-root .bl-enl:not(.bl-out)'); if(!w) return null; const id=w.getAttribute('data-node');
 const c=w.querySelector('.node-card').getBoundingClientRect(), x=w.querySelector('.bl-enlx').getBoundingClientRect(), bad=[];
 const meet=(q,r)=>Math.min(q.right,r.right)-Math.max(q.left,r.left)>0.5&&Math.min(q.bottom,r.bottom)-Math.max(q.top,r.top)>0.5;
 const strip={left:Math.min(c.left,x.left),right:Math.max(c.right,x.right),top:x.top,bottom:c.top};
 document.querySelectorAll('#bldg-root .bl-pill[data-node]').forEach(p=>{ const q=p.getBoundingClientRect(), own=p.getAttribute('data-node')===id;
   for(const r of [c,x,strip]){ if(!meet(q,r)) continue;
     if(own){ bad.push('own '+p.textContent.slice(0,5)); break; }
     const cx=(Math.max(q.left,r.left)+Math.min(q.right,r.right))/2, cy=(Math.max(q.top,r.top)+Math.min(q.bottom,r.bottom))/2, e=document.elementFromPoint(cx,cy);
     if(getComputedStyle(p).visibility!=='hidden'||!(e&&w.contains(e))) { bad.push(p.textContent.slice(0,5)); break; } } });
 return bad; }"""


def _inter(a, b):
    return min(a["r"], b["r"]) - max(a["l"], b["l"]) > 0.5 and min(a["b"], b["b"]) - max(a["t"], b["t"]) > 0.5


_REFS = {}


def _reference(browser, site, style):
    """The timeline's own enlarge in the same browser and style: the text size an enlarged card must have."""
    key = (browser.browser_type.name, style)
    if key not in _REFS:
        ctx, pg, _ = _open(browser, site, style, {"viewport": {"width": 2400, "height": 2400}}, "/t.html")
        try:
            nid = pg.evaluate("document.querySelector('#world .node').id.slice(5)")
            pg.evaluate("id=>enterFocus(id)", nid)
            pg.wait_for_timeout(1300)
            _REFS[key] = pg.evaluate(REF)
        finally:
            ctx.close()
    return _REFS[key]


def _tag(pg, nid):
    """Click the room tag of card `nid` (opening its floor first) and return the enlarged card's measure."""
    lv = pg.evaluate("id=>{const r=AltoBuilding.data.nodes[id].r; return AltoBuilding.plan.rm.find(x=>x.id===r).l;}", nid)
    if pg.evaluate("AltoBuilding.enlarged()"):
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(400)
    pg.evaluate("l=>AltoBuilding.selectLevel(l)", lv)
    pg.wait_for_timeout(700)
    pg.locator(f'#bldg-root .bl-pill[data-node="{nid}"]').click()
    pg.mouse.move(2, 300)                                                                # (off the chip: its hover tip is not chrome)
    pg.wait_for_timeout(900)
    return pg.evaluate(CARD)


def _check(pg, m, label, ref, desk=True):
    assert m, f"{label}: no enlarged card"
    bad = [c["id"] for c in pg.evaluate(CHROME) if _inter(m, c) or _inter(m["x"], c)]
    assert not bad, f"{label}: the enlarged card {m['l']:.0f},{m['t']:.0f}-{m['r']:.0f},{m['b']:.0f} meets the chrome {bad}"
    assert m["t"] >= -0.5 and m["b"] <= m["vh"] + 0.5 and m["l"] >= -0.5 and m["r"] <= m["vw"] + 0.5, (label, m)
    assert all(m["corners"]), f"{label}: the title's first line is covered at a top corner ({m})"
    assert pg.evaluate(TAGS) == [], f"{label}: tags over the enlarged card or its close button, or its own tag covered"
    if desk:
        assert m["zoom"] == "1.7", (label, m["zoom"])
        assert abs(m["fs"] - ref["fs"]) < 0.05, (label, m["fs"], ref)                 # the timeline enlarge's text size, never shrunk


# Controls for the chrome walker above (Board B-1114-bpd1280): it leaves out only what an overflow-clipping ancestor cuts away, never real overlap.
PLANT = r"""([kind, m])=>{ const old=document.getElementById('mut-probe'); if(old) old.remove(); if(!kind) return;
 const d=document.createElement('div'); d.id='mut-probe'; d.style.cssText='position:fixed;pointer-events:none;background:rgba(255,0,0,.3);z-index:99999;';
 const box=(e,l,t,w,h)=>{ e.style.left=l+'px'; e.style.top=t+'px'; e.style.width=w+'px'; e.style.height=h+'px'; };
 const cx=(m.l+m.r)/2, cy=(m.t+m.b)/2, sheet=()=>{ const c=document.createElement('canvas'); c.id='mut-sheet'; c.setAttribute('aria-hidden','true'); c.style.cssText='position:absolute;'; return c; };
 if(kind==='open') box(d,cx-20,cy-20,40,40);                                       // (a) an unclipped element on the card
 else if(kind==='window-on'){ box(d,cx-20,cy-20,40,40); d.style.overflow='hidden'; const c=sheet(); box(c,-200,-150,450,350); d.appendChild(c); }   // (b) a clipping window on the card
 else if(kind==='window-off'){ box(d,2,2,38,44); d.style.overflow='hidden'; const c=sheet(); box(c,-10,-10,m.r+50,m.b+50); d.appendChild(c); }   // the logo's case: the window far away, its sheet's box over the card
 document.body.appendChild(d); }"""


@pytest.mark.parametrize("style", ("classic", "holo"))
def test_the_chrome_walker_counts_real_overlap_and_only_drops_what_is_clipped_away(browser, site, style):
    ctx, pg, errors = _open(browser, site, style, {"viewport": DESKTOP["d1280"]})
    try:
        ids = pg.evaluate("AltoBuilding.data.order.filter(id=>AltoBuilding.data.nodes[id].r)")
        m = _tag(pg, ids[-1])
        hits = lambda: [c["id"] for c in pg.evaluate(CHROME) if _inter(m, c) or _inter(m["x"], c)]   # what _check would call 'meets the chrome'
        assert hits() == [], hits()
        pg.evaluate(PLANT, ["open", m])
        assert "mut-probe" in hits()                                                     # (a) RED: an unclipped element over the card is counted
        with pytest.raises(AssertionError, match="meets the chrome"):
            _check(pg, m, "mutation a", _reference(browser, site, style))
        pg.evaluate(PLANT, ["window-on", m])
        got = hits()
        assert "mut-probe" in got and "mut-sheet" in got, got                            # (b) RED: a clipping window on the card is counted, and its sheet's part inside it
        with pytest.raises(AssertionError, match="meets the chrome"):
            _check(pg, m, "mutation b", _reference(browser, site, style))
        pg.evaluate(PLANT, ["window-off", m])
        assert hits() == [], hits()                                                      # the sheet's box is over the card, all of it clipped away: not chrome
        seen = [c for c in pg.evaluate(CHROME) if c["id"] == "mut-sheet"]
        assert seen and seen[0]["r"] <= 41 and seen[0]["b"] <= 47, seen                  # (it is counted, as its window)
        raw = pg.evaluate("(()=>{ const r=document.getElementById('mut-sheet').getBoundingClientRect(); return {l:r.left,t:r.top,r:r.right,b:r.bottom}; })()")
        assert _inter(m, raw)                                                            # (and its own box does lie over the card: the old walker went red here)
        pg.evaluate(PLANT, [None, m])
        if style == "holo":                                                              # the real logo: its sheet is counted only inside its 38 px window
            lg = pg.evaluate("""()=>{ const c=document.querySelector('.ho-tube .cl canvas'); if(!c) return null; const w=c.parentNode.getBoundingClientRect(), r=c.getBoundingClientRect();
              return {w:[w.left,w.top,w.right,w.bottom], big:r.width>w.width*3}; }""")
            if lg:
                assert lg["big"]
                tube = [c for c in pg.evaluate(CHROME) if c["id"] == "" and c["r"] - c["l"] <= lg["w"][2] - lg["w"][0] + 1 and c["l"] >= lg["w"][0] - 1 and c["b"] <= lg["w"][3] + 1]
                assert tube, pg.evaluate(CHROME)
    finally:
        ctx.close()
    assert not errors, errors


@pytest.mark.parametrize("style", STYLES)
@pytest.mark.parametrize("size", list(DESKTOP))
def test_a_tag_enlarges_its_card_clear_of_the_chrome(browser, site, style, size):
    ref = _reference(browser, site, style)
    ctx, pg, errors = _open(browser, site, style, {"viewport": DESKTOP[size]})
    try:
        ids = pg.evaluate("AltoBuilding.data.order.filter(id=>AltoBuilding.data.nodes[id].r)")
        assert len(ids) > 20
        for nid in (ids[0], "n1", ids[len(ids) // 2], ids[-1]):
            m = _tag(pg, nid)
            assert m and m["id"] == nid and m["en"] == nid, (nid, m)
            _check(pg, m, f"{style} {size} {nid}", ref)
            if nid == "n1" and size == "d1280":
                assert m["sf"] and m["scroll"][0] > m["scroll"][1] + 4, m                # too long to fit: its box is fitted and the rest scrolls inside
            if m["sf"]:
                a0, a1 = m["sf"]["w"] / m["sf"]["h"], m["w"] / m["h"]                  # shrunk: the small card's shape
                assert abs(a1 / a0 - 1) <= 0.02 or m["sf"]["f"] <= 1 / 1.7 + 1e-6, (m, a0, a1)
            assert pg.evaluate("document.getElementById('bldg-root').contains(document.getElementById('node-'+%s))" % json.dumps(nid))
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(400)
        assert pg.evaluate("AltoBuilding.enlarged()") is None
        assert pg.evaluate("document.getElementById('world').contains(document.getElementById('node-'+%s))" % json.dumps(ids[-1]))   # given back
    finally:
        ctx.close()
    assert not errors, errors


def test_a_room_click_enlarges_its_first_card_and_the_plan_does_not_jump(browser, site):
    ctx, pg, errors = _open(browser, site)
    try:
        pg.evaluate(ONE_FLOOR)                                                          # (one floor: since B-1126 the blueprint opens on All floors)
        lv = pg.evaluate("document.querySelector('#bldg-root .bl-tab.on').getAttribute('data-level')")
        nid = pg.evaluate("l=>AltoBuilding.data.order.find(id=>{const n=AltoBuilding.data.nodes[id]; return n.r&&AltoBuilding.plan.rm.find(r=>r.id===n.r).l===l;})", lv)
        room = pg.evaluate("id=>AltoBuilding.data.nodes[id].r", nid)
        first = pg.evaluate("r=>AltoBuilding.nodesIn(r)[0]", room)
        vb0 = pg.evaluate("document.querySelector('#bldg-root svg.bl-svg').getAttribute('viewBox')")
        pos0 = pg.evaluate("[...document.querySelectorAll('#bldg-root .bl-pill')].slice(0,5).map(p=>p.style.transform)")
        pg.evaluate("r=>document.querySelector('#bldg-root [data-room=\"'+r+'\"]').dispatchEvent(new MouseEvent('click',{bubbles:true}))", room)
        pg.wait_for_timeout(900)
        m = pg.evaluate(CARD)
        assert m and m["id"] == first, m
        assert pg.evaluate("document.querySelector('#bldg-root .bl-info').hidden")      # the card, not the room panel
        assert m["vb"] == vb0 or pg.evaluate("AltoBuilding.enlarged()") == first            # (a room off screen is brought in; on screen nothing moves)
        if m["vb"] == vb0:
            assert pg.evaluate("[...document.querySelectorAll('#bldg-root .bl-pill')].slice(0,5).map(p=>p.style.transform)") == pos0
        # the close button and a click on the plan shrink it
        pg.click("#bldg-root .bl-enl .bl-enlx")
        pg.wait_for_timeout(400)
        assert pg.evaluate("AltoBuilding.enlarged()") is None
        pg.locator(f'#bldg-root .bl-pill[data-node="{first}"]').click()
        pg.wait_for_timeout(600)
        assert pg.evaluate("AltoBuilding.enlarged()") == first
        pg.mouse.click(DESKTOP["d1440"]["width"] - 330, 140)
        pg.wait_for_timeout(400)
        assert pg.evaluate("AltoBuilding.enlarged()") is None
    finally:
        ctx.close()
    assert not errors, errors


@pytest.mark.parametrize("style", STYLES)
def test_the_arrows_and_the_tour_hop_card_by_card(browser, site, style):
    ctx, pg, errors = _open(browser, site, style)
    try:
        pg.evaluate(ONE_FLOOR)                                                          # (one floor: since B-1126 the blueprint opens on All floors)
        ids = pg.evaluate("AltoBuilding.data.order.filter(id=>AltoBuilding.data.nodes[id].r)")
        pg.evaluate("AltoBuilding.tour(0)")
        pg.wait_for_timeout(700)
        assert pg.evaluate("AltoBuilding.enlarged()") == ids[0]
        seen = [ids[0]]
        for _ in range(4):
            pg.keyboard.press("ArrowRight")
            pg.wait_for_timeout(500)
            seen.append(pg.evaluate("AltoBuilding.enlarged()"))
        assert seen == ids[:5], seen
        pg.keyboard.press("ArrowLeft")
        pg.wait_for_timeout(500)
        assert pg.evaluate("AltoBuilding.enlarged()") == ids[3]
        assert pg.evaluate("document.querySelectorAll('#bldg-root .bl-enl:not(.bl-out)').length") == 1
        pg.evaluate("AltoBuilding.tour(%d)" % (len(ids) - 1))                          # another floor: the floor tab follows
        pg.wait_for_timeout(900)
        m = pg.evaluate(CARD)
        lv = pg.evaluate("id=>{const r=AltoBuilding.data.nodes[id].r; return AltoBuilding.plan.rm.find(x=>x.id===r).l;}", ids[-1])
        assert m["id"] == ids[-1] and pg.evaluate("document.querySelector('#bldg-root .bl-tab.on').getAttribute('data-level')") == lv
        _check(pg, m, f"{style} tour last", _reference(browser, site, style))
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(400)
        assert pg.evaluate("AltoBuilding.enlarged()") is None
    finally:
        ctx.close()
    assert not errors, errors


def test_a_search_hit_and_a_click_on_the_card(browser, site):
    ctx, pg, errors = _open(browser, site)
    try:
        nid = pg.evaluate("AltoBuilding.data.order.filter(id=>AltoBuilding.data.nodes[id].r)[7]")
        pg.evaluate("id=>{const e=document.getElementById('node-'+id); e.classList.add('search-flash');}", nid)   # what the engine's search does to a hit
        pg.wait_for_timeout(900)
        assert pg.evaluate("AltoBuilding.enlarged()") == nid
        pg.evaluate("id=>enterFocus(id)", pg.evaluate("AltoBuilding.data.order.filter(id=>AltoBuilding.data.nodes[id].r)[9]"))   # a link: the board enlarges it
        pg.wait_for_timeout(900)
        assert pg.evaluate("AltoBuilding.enlarged()") == pg.evaluate("AltoBuilding.data.order.filter(id=>AltoBuilding.data.nodes[id].r)[9]")
        assert not pg.evaluate("window._focusedNodeId")
        m = pg.evaluate(CARD)
        pg.mouse.click((m["l"] + m["r"]) / 2, (m["t"] + m["b"]) / 2)                  # a click on it opens its page
        pg.wait_for_timeout(900)
        assert pg.evaluate("document.documentElement.classList.contains('detail-open')")
    finally:
        ctx.close()
    assert not errors, errors


@pytest.mark.parametrize("style", STYLES)
def test_a_phone_tap_enlarges_the_card_as_the_atlas_does(browser, site, style):
    ctx, pg, errors = _open(browser, site, style, PHONE)
    try:
        assert pg.evaluate("document.documentElement.classList.contains('mobile')")
        for nid in ("n3", "n20", "n1", "n91"):                                         # (n20 stands by the floor rail; n1 is the long card)
            lv = pg.evaluate("id=>{const r=AltoBuilding.data.nodes[id].r; return AltoBuilding.plan.rm.find(x=>x.id===r).l;}", nid)
            if pg.evaluate("AltoBuilding.enlarged()"):
                pg.locator("#bldg-root .bl-enl:not(.bl-out) .bl-enlx").tap()
                pg.wait_for_timeout(400)
            pg.evaluate("l=>AltoBuilding.selectLevel(l)", lv)
            pg.wait_for_timeout(700)
            pill = pg.locator(f'#bldg-root .bl-pill[data-node="{nid}"]')
            if nid == "n3":
                pill.tap()                                                               # a real tap
            else:
                pill.dispatch_event("click")                                             # (crowded chips can overlap at the phone's fit)
            pg.wait_for_timeout(900)
            m = pg.evaluate(CARD)
            assert m and m["id"] == nid, m
            _check(pg, m, f"{style} phone {nid}", None, desk=False)
        assert m["x"]["r"] - m["x"]["l"] >= 31.5                                         # the close button is a finger's size
        assert pg.locator("#bldg-root .bl-tab").count() >= 3 and pg.locator("#bldg-root .bl-zoom .bl-btn").count() == 3   # the phone's controls are all still there
        pg.locator("#bldg-root .bl-enl .bl-enlx").tap()
        pg.wait_for_timeout(400)
        assert pg.evaluate("AltoBuilding.enlarged()") is None
    finally:
        ctx.close()
    assert not errors, errors


# ── All floors (40182020, Art 2026-11-01) with the enlarge, the pinch and the filter dim ──

@needs_all
@pytest.mark.parametrize("style", STYLES)
def test_all_floors_enlarge_pinch_pan_and_the_tabs_stay_in_step(browser, site, style):
    ctx, pg, errors = _open(browser, site, style)
    try:
        pg.click('#bldg-root .bl-tab[data-level="all"]')
        pg.wait_for_timeout(700)
        on = "document.querySelector('#bldg-root .bl-tab.on').getAttribute('data-level')"
        assert pg.evaluate(on) == "all" and pg.locator("#bldg-root .bl-cell").count() >= 3
        stray = pg.evaluate("""()=>{ const D=AltoBuilding.data, P=AltoBuilding.plan, out=[];
          for(const m of AltoMarkers.debug('bldg')){ const l=P.rm.find(r=>r.id===D.nodes[m.id].r).l, c=document.querySelector('#bldg-root .bl-cellbg[data-fade="'+l+'"]').getBoundingClientRect();
            if(m.ax<c.left-2||m.ax>c.right+2||m.ay<c.top-2||m.ay>c.bottom+2) out.push(m.id); } return out; }""")
        assert stray == [], f"chips outside their floor's plate: {stray[:8]}"                 # every chip on its own floor (the plan turned or not)
        ids = pg.evaluate("AltoBuilding.data.order.filter(id=>AltoBuilding.data.nodes[id].r)")
        nid = ids[len(ids) // 3]
        pg.locator(f'#bldg-root .bl-pill[data-node="{nid}"]').click()
        pg.wait_for_timeout(900)
        m = pg.evaluate(CARD)
        assert m and m["id"] == nid and pg.evaluate(on) == "all"                      # enlarged where it stands, the grid stays
        _check(pg, m, f"{style} all floors", _reference(browser, site, style))
        pg.keyboard.press("ArrowRight")                                                 # the arrows stay in the grid too
        pg.wait_for_timeout(600)
        assert pg.evaluate("AltoBuilding.enlarged()") == ids[ids.index(nid) + 1] and pg.evaluate(on) == "all"
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(300)
        vb = """async()=>{ const s=document.querySelector('#bldg-root svg.bl-svg'); for(let i=0;i<60&&s.style.transform;i++) await new Promise(f=>setTimeout(f,20));   // (settled: B-1126 commits the viewBox after a gesture)
          return s.getAttribute('viewBox').split(' ').map(Number); }"""
        a = pg.evaluate(vb)
        pg.evaluate("""()=>{ const s=document.querySelector('#bldg-root svg.bl-svg'), r=s.getBoundingClientRect();
          for(let i=0;i<8;i++) s.dispatchEvent(new WheelEvent('wheel',{deltaY:-6,ctrlKey:true,clientX:r.left+r.width/2,clientY:r.top+r.height/2,bubbles:true,cancelable:true})); }""")
        b = pg.evaluate(vb)
        assert b[2] < a[2] * .8                                                         # the whole grid zooms as one canvas
        pg.evaluate("""()=>{ const s=document.querySelector('#bldg-root svg.bl-svg'), r=s.getBoundingClientRect();
          s.dispatchEvent(new WheelEvent('wheel',{deltaX:40,deltaY:30,clientX:r.left+r.width/2,clientY:r.top+r.height/2,bubbles:true,cancelable:true})); }""")
        c = pg.evaluate(vb)
        assert c[2] == b[2] and c[0] > b[0] and c[1] > b[1]                             # and pans as one
        pg.keyboard.press("2")
        pg.wait_for_timeout(500)
        assert pg.evaluate(on) != "all" and pg.locator("#bldg-root .bl-cell").count() == 0
        pg.keyboard.press("a")
        pg.wait_for_timeout(500)
        assert pg.evaluate(on) == "all"
    finally:
        ctx.close()
    assert not errors, errors


@pytest.mark.parametrize("style", STYLES)
def test_the_filter_dim_on_one_floor_and_all_floors(browser, site, style):
    ctx, pg, errors = _open(browser, site, style)
    try:
        pg.evaluate(ONE_FLOOR)                                                          # (one floor: since B-1126 the blueprint opens on All floors)
        pg.evaluate("document.querySelectorAll('#world .node-card').forEach((c,i)=>{ if(i%2) c.classList.add('ent-dimmed'); })")   # what the engine's filter does
        pg.wait_for_timeout(500)
        DIM = """()=>{ const out=id=>{ const c=document.querySelector('#node-'+id+' .node-card'); return c.classList.contains('ent-dimmed'); };
          const p=[...document.querySelectorAll('#bldg-root .bl-pill[data-node]')];
          return {n:p.length, bad:p.filter(e=>out(e.getAttribute('data-node'))!==e.classList.contains('bl-dim')).length,
                  op:p.filter(e=>e.classList.contains('bl-dim')).map(e=>+getComputedStyle(e).opacity)}; }"""
        one = pg.evaluate(DIM)
        assert one["n"] > 5 and one["bad"] == 0 and one["op"] and all(abs(o - .28) < .01 for o in one["op"]), one
        if not BLUEPRINT_ALL_FLOORS:                                                     # the switch is off: one floor is all there is
            assert not errors, errors
            return
        pg.click('#bldg-root .bl-tab[data-level="all"]')
        pg.wait_for_timeout(700)
        al = pg.evaluate(DIM)
        assert al["n"] > one["n"] and al["bad"] == 0 and all(abs(o - .28) < .01 for o in al["op"]), al
        lit = pg.evaluate("[...document.querySelectorAll('#bldg-root .bl-cell')].map(c=>c.querySelector('.bl-litt').textContent)")
        assert all(t.endswith(" lit") for t in lit) and sum(int(t.split()[0]) for t in lit) == pg.evaluate(
            "AltoBuilding.data.order.filter((id,i)=>AltoBuilding.data.nodes[id].r && !document.querySelector('#node-'+id+' .node-card').classList.contains('ent-dimmed')).length")
        nid = pg.evaluate("AltoBuilding.data.order.find(id=>AltoBuilding.data.nodes[id].r && document.querySelector('#node-'+id+' .node-card').classList.contains('ent-dimmed'))")
        pg.evaluate("id=>AltoBuilding.enlarge(id)", nid)                                 # an enlarged hidden card: its chip stays dim, and unfiltering lights it
        pg.wait_for_timeout(600)
        pg.evaluate("id=>document.querySelector('#node-'+id+' .node-card').classList.remove('ent-dimmed')", nid)
        pg.wait_for_timeout(500)
        assert not pg.evaluate("id=>document.querySelector('#bldg-root .bl-pill[data-node=\"'+id+'\"]').classList.contains('bl-dim')", nid)
    finally:
        ctx.close()
    assert not errors, errors


PANELS = r"""()=>{ const D=AltoBuilding.data, P=AltoBuilding.plan, out=[], vw=innerWidth, vh=innerHeight;
 const bars=[...document.querySelectorAll('#bldg-root .bl-head,#bldg-root .bl-dock,#bldg-root .bl-tabs,#bldg-root .bl-zoom,#bldg-root .bl-foot')].concat(
   [...document.body.children].filter(c=>c.id!=='bldg-root'&&c.id!=='world'&&!/SCRIPT|STYLE/.test(c.tagName)&&/fixed|absolute|sticky/.test(getComputedStyle(c).position)))
   .filter(e=>{ const cs=getComputedStyle(e); return cs.display!=='none'&&cs.display!=='contents'&&cs.visibility!=='hidden'&&+cs.opacity>0; }).map(e=>e.getBoundingClientRect())
   .filter(r=>r.width>1&&r.height>1&&r.width*r.height<.4*vw*vh);
 const meet=(q,r)=>Math.min(q.right,r.right)-Math.max(q.left,r.left)>0.5&&Math.min(q.bottom,r.bottom)-Math.max(q.top,r.top)>0.5;
 let n=0; document.querySelectorAll('#bldg-root .bl-pill[data-node]').forEach(p=>{ if(getComputedStyle(p).visibility==='hidden') return; n++;
   const q=p.getBoundingClientRect(), l=P.rm.find(r=>r.id===D.nodes[p.getAttribute('data-node')].r).l, c=document.querySelector('#bldg-root .bl-cellbg[data-fade="'+l+'"]').getBoundingClientRect();
   if(q.left<c.left-0.5||q.right>c.right+0.5||q.top<c.top-0.5||q.bottom>c.bottom+0.5) out.push(p.textContent.slice(0,5)+' off its floor');
   else if(bars.some(r=>meet(q,r))) out.push(p.textContent.slice(0,5)+' on a bar'); });
 return {n, out}; }"""


@needs_all
@pytest.mark.parametrize("style", STYLES)
@pytest.mark.parametrize("size", ["d1440", "d1280", "phone"])
def test_all_floors_keeps_every_tag_on_its_own_floor_and_off_the_bars(browser, site, style, size):
    """Art 2026-11-14: in All floors no tag spills out of its floor's plate or onto a bar."""
    ctx, pg, errors = _open(browser, site, style, PHONE if size == "phone" else {"viewport": DESKTOP[size]})
    try:
        pg.evaluate("AltoBuilding.selectLevel('all')")
        pg.wait_for_timeout(1200)
        r = pg.evaluate(PANELS)
        assert r["n"] > 20 and r["out"] == [], r
        pg.evaluate("""()=>{ const s=document.querySelector('#bldg-root svg.bl-svg'), b=s.getBoundingClientRect();     // in a little, then settled
          for(let i=0;i<6;i++) s.dispatchEvent(new WheelEvent('wheel',{deltaY:-6,ctrlKey:true,clientX:b.left+b.width/2,clientY:b.top+b.height/2,bubbles:true,cancelable:true})); }""")
        pg.wait_for_timeout(1200)
        r = pg.evaluate(PANELS)
        assert r["out"] == [], r
    finally:
        ctx.close()
    assert not errors, errors


def test_all_floors_is_absent_when_switched_off(browser, site):
    """CHANGED 1.9.269 (was ..._absent_by_default): the build switch (palace_building_asset.BLUEPRINT_ALL_FLOORS) is ON by default; ALTO_BP_ALL_FLOORS=0 builds it out: no All tab or entry anywhere."""
    import os, subprocess
    env = dict(os.environ, ALTO_BP_ALL_FLOORS="0")
    out = subprocess.run([sys.executable, "-c", "from alto.build import palace_building_asset as p; print(p.BLUEPRINT_ALL_FLOORS, 'ALLF_ON=false' in p.BUILDING_ASSET)"],
                         cwd=str(Path(__file__).resolve().parent.parent), env=env, capture_output=True, text=True)
    assert out.stdout.split() == ["False", "True"], out.stdout + out.stderr              # the default build, whatever this run's environment
    dflt = subprocess.run([sys.executable, "-c", "from alto.build import palace_building_asset as p; print(p.BLUEPRINT_ALL_FLOORS, 'ALLF_ON=true' in p.BUILDING_ASSET)"],
                          cwd=str(Path(__file__).resolve().parent.parent), env={k: v for k, v in os.environ.items() if k != "ALTO_BP_ALL_FLOORS"}, capture_output=True, text=True)
    assert dflt.stdout.split() == ["True", "True"], dflt.stdout + dflt.stderr            # the default build has All floors
    if BLUEPRINT_ALL_FLOORS:
        return
    for kw in ({"viewport": DESKTOP["d1440"]}, PHONE, dict(PHONE, viewport={"width": 844, "height": 390})):
        ctx, pg, errors = _open(browser, site, "classic", kw)
        try:
            on = "document.querySelector('#bldg-root .bl-tab.on').getAttribute('data-level')"
            was = pg.evaluate(on)
            assert pg.locator("#bldg-root .bl-tab").count() >= 2
            assert pg.locator('#bldg-root [data-level="all"], #bldg-root .bl-all').count() == 0
            assert not pg.evaluate("[...document.querySelectorAll('#bldg-root *')].some(e=>/all floors/i.test((e.getAttribute('title')||'')+(e.getAttribute('aria-label')||'')+(e.children.length?'':e.textContent)))")
            pg.keyboard.press("a")
            pg.evaluate("AltoBuilding.selectLevel('all')")
            pg.wait_for_timeout(400)
            assert pg.evaluate(on) == was and pg.locator("#bldg-root .bl-cell").count() == 0
        finally:
            ctx.close()
        assert not errors, errors


# ── All floors fills the safe box, and a tag with no room is a dot (brief bp-allfloors-fable-1114) ──
ALL_TAGS = r"""()=>{ const vis=e=>{ const cs=getComputedStyle(e); return cs.visibility!=='hidden'&&cs.display!=='none'&&+cs.opacity>0; }, R=e=>e.getBoundingClientRect();
 const meet=(q,r)=>Math.min(q.right,r.right)-Math.max(q.left,r.left)>0.5&&Math.min(q.bottom,r.bottom)-Math.max(q.top,r.top)>0.5;
 const all=[...document.querySelectorAll('#bldg-root .bl-pill[data-node]')], P=all.filter(vis), q=P.map(e=>R(e.classList.contains('bl-badge')?e.firstChild:e)), out=[];   // (a badge is its disc)
 for(let i=0;i<P.length;i++) for(let j=i+1;j<P.length;j++) if(meet(q[i],q[j])) out.push(P[i].textContent+' on '+P[j].textContent);
 const names=[...document.querySelectorAll('#bldg-root .bl-lab,#bldg-root .bl-celltitle,#bldg-root .bl-lit')].filter(vis);
 names.forEach(n=>{ const r=R(n); if(r.width<1) return; q.forEach((c,i)=>{ if(meet(c,r)) out.push(P[i].textContent+' over the name '+n.textContent.slice(0,14)); }); });
 const cells=[...document.querySelectorAll('#bldg-root .bl-cellbg')].map(R), rr=R(document.getElementById('bldg-root')), B=AltoBuilding.allBox();
 const u={l:Math.min(...cells.map(c=>c.left))-rr.left, t:Math.min(...cells.map(c=>c.top))-rr.top, r:Math.max(...cells.map(c=>c.right))-rr.left, b:Math.max(...cells.map(c=>c.bottom))-rr.top};
 const off=all.filter(e=>!vis(e)).map(e=>{ const m=/translate3d\(([-\d.]+)px, ?([-\d.]+)px/.exec(e.style.transform)||[]; return e.firstChild.textContent+'@'+Math.round(m[1])+','+Math.round(m[2])+' '+e.className.replace(/bl-pill|alto-mk/g,'').trim(); });
 return {off, cells:cells.map(c=>[c.left,c.top,c.right,c.bottom].map(Math.round)), box:B, n:all.length, vis:P.length, dots:P.filter(e=>e.classList.contains('bl-dot')).length, names:names.filter(n=>n.classList.contains('bl-lab')).length, out,
         fill:[(u.r-u.l)/B.w,(u.b-u.t)/B.h], inside:u.l>=B.l-1&&u.t>=B.t-1&&u.r<=B.r+1&&u.b<=B.b+1}; }"""
ALL_SIZES = {"d1440": {"viewport": {"width": 1440, "height": 900}}, "d1280": {"viewport": {"width": 1280, "height": 800}},
             "phone": PHONE, "phone-land": dict(PHONE, viewport={"width": 844, "height": 390})}


@needs_all
@pytest.mark.parametrize("style", STYLES)
@pytest.mark.parametrize("size", list(ALL_SIZES))
def test_all_floors_fills_the_safe_box_and_no_two_tags_overlap(browser, site, style, size, request):
    """No two visible tags overlap and none covers a room's name; the panels fill the safe box; a crowded tag is a dot whose number shows on hover or a tap,
    or once zoomed in.

    CHANGED 1.9.269 (was vis == n == 92): a tag or dot with no room inside its panel's 20 px margin waits hidden (never stacked), so >= 60% must show. That is
    safe ONLY because a hidden tag's card stays reachable: the card list ('Cards, in order', key C) lists every card whether or not its tag shows and picking
    one enlarges it, and the room itself still opens its card (test_a_hidden_tags_card_opens_from_the_card_list proves the list, for every card at the
    sizes that hide any)."""
    import os
    ctx, pg, errors = _open(browser, site, style, ALL_SIZES[size])
    phone = size.startswith("phone")
    try:
        pg.evaluate("AltoBuilding.selectLevel('all')")
        pg.wait_for_timeout(1500)
        r = pg.evaluate(ALL_TAGS)
        shots = os.environ.get("ALTO_SHOT_DIR")
        if shots:
            pg.screenshot(path=os.path.join(shots, f"{size}-{style}-{browser.browser_type.name}-AFTER.png"))
        assert r["out"] == [], r
        assert r["n"] == 92 and r["vis"] >= .6 * r["n"], r   # CHANGED 1.9.269 (was vis == n == 92): a tag or dot with no room inside its panel's 20 px margin waits hidden, never stacked
        if not phone:                                                      # CHANGED round 3: a phone's floors are ONE full-width column and the page scrolls, so the grid is taller than the box
            assert r["inside"] and max(r["fill"]) > .97 and min(r["fill"]) > .5, r            # the grid fills the safe box (one way to the edge)
        if r["dots"]:
            dot = pg.locator("#bldg-root .bl-pill.bl-dot:not(.bl-badge):not(.bl-off)").first
            nid = dot.get_attribute("data-node")
            if phone:                                                   # CHANGED 1.9.269 round 3 (Board B-1120-LOOK269-R2): a tap on a phone's dot opens its card (no number-first step)
                dot.tap(force=True)
                pg.wait_for_timeout(700)
                assert pg.evaluate("AltoBuilding.enlarged()") == nid
            else:
                dot.hover(force=True)
                pg.wait_for_timeout(300)
                shown = pg.evaluate("id=>{ const p=document.querySelector('#bldg-root .bl-pill[data-node=\"'+id+'\"]'), b=p.firstChild.getBoundingClientRect(); return [p.getBoundingClientRect().width, b.width, p.firstChild.textContent]; }", nid)
                assert shown[0] >= 30 and shown[1] > 4 and shown[2], shown
                dot.click(force=True)
                pg.wait_for_timeout(700)
                assert pg.evaluate("AltoBuilding.enlarged()") == nid
            pg.evaluate("AltoBuilding.shrink()")
            pg.wait_for_timeout(500)
            # zoomed in on the dots' own floor, their numbers have room
            pg.evaluate("""()=>{ const s=document.querySelector('#bldg-root svg.bl-svg'), d=document.querySelector('#bldg-root .bl-pill.bl-dot').getBoundingClientRect();
              for(let i=0;i<14;i++) s.dispatchEvent(new WheelEvent('wheel',{deltaY:-8,ctrlKey:true,clientX:d.left+5,clientY:d.top+5,bubbles:true,cancelable:true})); }""")
            pg.wait_for_timeout(1500)
            z = pg.evaluate(ALL_TAGS)
            if shots:
                pg.screenshot(path=os.path.join(shots, f"{size}-{style}-{browser.browser_type.name}-zoomed-AFTER.png"))
            assert z["out"] == [] and z["dots"] < r["dots"], (r["dots"], z)
    finally:
        ctx.close()
    assert not errors, errors


# ── 1.9.269 (Board L-1120-ALLFLOORS): the All floors tab is on; its tags never stack, never touch a title, stay in their own panel and 20 px from every edge ──
TAG_RULE = r"""(m)=>{ const vis=e=>{ const cs=getComputedStyle(e); return cs.visibility!=='hidden'&&cs.display!=='none'&&+cs.opacity>0; }, R=e=>e.getBoundingClientRect(), out=[];
 const meet=(q,r)=>Math.min(q.right,r.right)-Math.max(q.left,r.left)>0.5&&Math.min(q.bottom,r.bottom)-Math.max(q.top,r.top)>0.5;
 const phone=/\b(mobile|pmin)\b/.test(document.documentElement.className), all=[...document.querySelectorAll('#bldg-root .bl-pill[data-node]')], P=all.filter(vis), q=P.map(e=>R(e.classList.contains('bl-badge')?e.firstChild:e)), rr=R(document.getElementById('bldg-root'));   // (a badge is its disc; its 44 pt hit box is invisible)
 for(let i=0;i<P.length;i++) for(let j=i+1;j<P.length;j++) if(meet(q[i],q[j])) out.push('tag '+P[i].textContent+' on tag '+P[j].textContent);
 const names=[...document.querySelectorAll('#bldg-root .bl-lab,#bldg-root .bl-celltitle,#bldg-root .bl-lit')].filter(vis);
 names.forEach(n=>{ const r=R(n); if(r.width<1) return; q.forEach((c,i)=>{ if(meet(c,r)) out.push('tag '+P[i].textContent+' over the title '+n.textContent.slice(0,14)); }); });
 const panel={}; document.querySelectorAll('#bldg-root .bl-cellbg[data-fade]').forEach(e=>{ panel[e.getAttribute('data-fade')]=R(e); });
 P.forEach((p,i)=>{ const c=q[i], pn=panel[p.getAttribute('data-lv')];
   if(!pn) { out.push('tag '+p.textContent+' has no panel'); return; }
   if(c.left<pn.left+m||c.right>pn.right-m||c.top<pn.top+m||c.bottom>pn.bottom-m) out.push('tag '+p.textContent+' within '+m+'px of its panel edge or outside it');
   if(c.left<rr.left+m||c.right>rr.right-m||(!phone&&(c.top<rr.top+m||c.bottom>rr.bottom-m))) out.push('tag '+p.textContent+' within '+m+'px of the window edge'); });   // (a phone's floors scroll: only the sides count)
 const dock=[...document.querySelectorAll(phone?'#bldg-root .bl-tabs,#bldg-root .bl-head':'#bldg-root .bl-dock,#bldg-root .bl-tabs,#bldg-root .bl-head,#bldg-root .bl-zoom')].filter(vis).map(R);
 q.forEach((c,i)=>dock.forEach(d=>{ if(d.width>0&&meet(c,d)) out.push('tag '+P[i].textContent+' under a bar'); }));
 return {out, n:all.length, vis:P.length, dots:P.filter(e=>e.classList.contains('bl-dot')).length, hidden:all.length-P.length}; }"""


@pytest.mark.skipif(not BLUEPRINT_ALL_FLOORS, reason="All floors is switched off in this build")
def test_all_floors_option_shows_every_floor_at_once(browser, site):
    """The 'All floors' button sits with the floor buttons in every style; it shows every floor panel together (and a tag for every card)."""
    for style in STYLES:
        ctx, pg, errors = _open(browser, site, style, {"viewport": DESKTOP["d1440"]})
        try:
            n_floors = pg.evaluate("document.querySelectorAll('#bldg-root .bl-tabs .bl-tab:not([data-level=\"outside\"]):not([data-level=\"all\"])').length")
            b = pg.locator('#bldg-root .bl-tab[data-level="all"]')
            assert b.count() == 1 and b.is_visible(), style
            assert "all floors" in (b.get_attribute("title") or "").lower()
            b.click()
            pg.wait_for_timeout(1500)
            r = pg.evaluate("()=>({cells:document.querySelectorAll('#bldg-root .bl-cellbg[data-fade]').length, on:document.querySelector('#bldg-root .bl-tab.on').dataset.level})")
            assert r["on"] == "all" and r["cells"] == n_floors >= 2, (style, r, n_floors)
            t = pg.evaluate(TAG_RULE, 20)
            assert t["vis"] + t["hidden"] == t["n"] == 92, (style, t)
        finally:
            ctx.close()
        assert not errors, errors


@pytest.mark.skipif(not BLUEPRINT_ALL_FLOORS, reason="All floors is switched off in this build")
@pytest.mark.parametrize("style", STYLES)
@pytest.mark.parametrize("size", list(ALL_SIZES))
def test_all_floors_tags_never_touch_a_tag_a_title_or_an_edge(browser, site, style, size):
    """The tag rule: no tag on another tag or on any floor title or room name; each tag inside its own floor's panel, 20 px from the panel's edges
    and the window's; a tag with no room is a dot (a number on hover or tap), a dot with no room is hidden (never stacked); after a zoom too."""
    ctx, pg, errors = _open(browser, site, style, ALL_SIZES[size])
    try:
        pg.evaluate("AltoBuilding.selectLevel('all')")
        pg.wait_for_timeout(1500)
        mg = 4 if size.startswith("phone") else 20       # CHANGED round 3: on a phone a dot stands in its own room, rooms reach within ~11 px of a panel's edge, so its margin is 4 px (desktop keeps 20)
        r = pg.evaluate(TAG_RULE, mg)
        assert r["out"] == [], (style, size, r["out"][:6])
        assert r["vis"] >= r["n"] * .6 and r["n"] == 92, (style, size, r)          # most cards show (a tag or a dot); only what truly has no room waits hidden
        pg.evaluate("""()=>{ const s=document.querySelector('#bldg-root svg.bl-svg'), b=s.getBoundingClientRect();
          for(let i=0;i<6;i++) s.dispatchEvent(new WheelEvent('wheel',{deltaY:-8,ctrlKey:true,clientX:b.left+b.width/2,clientY:b.top+b.height/2,bubbles:true,cancelable:true})); }""")
        pg.wait_for_timeout(1500)
        z = pg.evaluate(TAG_RULE, mg)
        assert z["out"] == [] or all("edge" in o for o in z["out"]), (style, size, z["out"][:6])   # zoomed, a panel runs off screen: only its edge may be near the window's
    finally:
        ctx.close()
    assert not errors, errors


@pytest.mark.skipif(not BLUEPRINT_ALL_FLOORS, reason="All floors is switched off in this build")
@pytest.mark.parametrize("style", STYLES)
def test_picking_a_floor_returns_to_the_single_floor_view(browser, site, style):
    ctx, pg, errors = _open(browser, site, style, {"viewport": DESKTOP["d1440"]})
    try:
        pg.locator('#bldg-root .bl-tab[data-level="all"]').click()
        pg.wait_for_timeout(1200)
        assert pg.evaluate("document.querySelectorAll('#bldg-root .bl-cellbg[data-fade]').length") >= 2
        fl = pg.locator('#bldg-root .bl-tab:not([data-level="outside"]):not([data-level="all"])').nth(1)
        lv = fl.get_attribute("data-level")
        fl.click()
        pg.wait_for_timeout(1200)
        assert pg.evaluate("document.querySelector('#bldg-root .bl-tab.on').dataset.level") == lv
        assert pg.evaluate("document.querySelectorAll('#bldg-root .bl-cellbg[data-fade]').length") == 0
    finally:
        ctx.close()
    assert not errors, errors


@pytest.mark.skipif(not BLUEPRINT_ALL_FLOORS, reason="All floors is switched off in this build")
@pytest.mark.parametrize("style", STYLES)
@pytest.mark.parametrize("size", ["phone", "phone-land"])
def test_phone_floor_buttons_and_all_are_44pt(browser, site, style, size):
    ctx, pg, errors = _open(browser, site, style, ALL_SIZES[size])
    try:
        r = pg.evaluate("""()=>[...document.querySelectorAll('#bldg-root .bl-tab')].filter(e=>e.getClientRects().length).map(e=>{ const b=e.getBoundingClientRect(); return [e.dataset.level,Math.round(b.width),Math.round(b.height)]; })""")
        assert any(x[0] == "all" for x in r), r
        assert all(x[1] >= 44 and x[2] >= 44 for x in r), (style, size, r)
    finally:
        ctx.close()
    assert not errors, errors


# ── round 2 (CEO 2026-11-20): the grid keeps clear of the name card, the dock and the rail; every panel has its title; a hidden tag's card opens from the list ──
BARS = r"""()=>{ const R=e=>e.getBoundingClientRect(), root=document.getElementById('bldg-root'), out=[];
 const ok=e=>{ const cs=getComputedStyle(e); return cs.display!=='none'&&cs.visibility!=='hidden'&&+cs.opacity>.05; };
 const bars=[]; [...document.body.children].forEach(c=>{ if(c===root||c.id==='world'||/^(SCRIPT|STYLE)$/.test(c.tagName)) return; const cs=getComputedStyle(c);
   if(/^(fixed|absolute|sticky)$/.test(cs.position)&&ok(c)) bars.push(['page:'+(c.id||c.className||c.tagName),R(c)]); });
 const tb=document.getElementById('title-bar'); if(tb&&ok(tb)&&!bars.some(b=>b[0]==='page:title-bar')) bars.push(['page:title-bar',R(tb)]);
 root.querySelectorAll('.bl-head,.bl-dock,.bl-tabs,.bl-zoom,.bl-info,.bl-cards:not([hidden]),.bl-credits:not([hidden])').forEach(c=>{ if(ok(c)) bars.push([c.className.split(' ').slice(-1)[0],R(c)]); });
 const vw=innerWidth, vh=innerHeight, real=bars.filter(([n,r])=>r.width>1&&r.height>1&&r.width*r.height<.4*vw*vh);
 return {bars:real.map(([n,r])=>[n,r.left,r.top,r.right,r.bottom]), vw, vh}; }"""
PANELS2 = r"""(gap)=>{ const R=e=>e.getBoundingClientRect(), out=[], root=document.getElementById('bldg-root'), B=window.__bars;
 const panels=[...document.querySelectorAll('#bldg-root .bl-cellbg[data-fade]')].map(e=>[e.getAttribute('data-fade'),R(e)]);
 const titles=[...document.querySelectorAll('#bldg-root .bl-celltitle')];
 const meet=(a,b,m)=>Math.min(a.right,b[3]+m)-Math.max(a.left,b[1]-m)>0.5&&Math.min(a.bottom,b[4]+m)-Math.max(a.top,b[2]-m)>0.5;
 panels.forEach(([id,r])=>B.forEach(b=>{ if(meet(r,b,gap)) out.push('panel '+id+' within '+gap+'px of '+b[0]); }));
 return {out, panels:panels.length, titles:titles.length, titleVisible:titles.every(t=>{ const q=R(t); return q.width>4&&q.height>4&&getComputedStyle(t).visibility!=='hidden'; }),
   titleClear:titles.map(t=>{ const q=R(t); return B.filter(b=>meet(q,b,0)).map(b=>t.textContent+' under '+b[0]); }).flat()}; }"""


@pytest.mark.skipif(not BLUEPRINT_ALL_FLOORS, reason="All floors is switched off in this build")
@pytest.mark.parametrize("style", STYLES)
@pytest.mark.parametrize("size", list(ALL_SIZES))
def test_all_floors_panels_clear_of_the_label_the_dock_and_the_rail_and_each_has_its_title(browser, site, style, size):
    """No panel (and so no tag) under the building's name card, the dock or the rail: 12 px clear of every bar; every panel shows its LEVEL title, clear of the bars."""
    ctx, pg, errors = _open(browser, site, style, ALL_SIZES[size])
    try:
        pg.locator('#bldg-root .bl-tab[data-level="all"]').click(force=True)
        pg.wait_for_timeout(2000)
        info = pg.evaluate(BARS)
        if size.startswith("phone"):                                      # a phone's floors scroll: only the bars above and beside them count
            info["bars"] = [b for b in info["bars"] if b[0] in ("bl-head", "bl-tabs", "page:title-bar")]
        pg.evaluate("b=>{ window.__bars=b.bars; }", info)
        names = [b[0] for b in info["bars"]]
        assert "bl-head" in names and (size.startswith("phone") or "page:title-bar" in names), names     # the name card (and on a desktop the page's title pill) are among the bars measured
        if not size.startswith("phone"):
            assert any(n.startswith("bl-dock") for n in names), names
        r = pg.evaluate(PANELS2, 12)
        assert r["out"] == [], (style, size, r["out"], info["bars"])
        n_floors = pg.evaluate("document.querySelectorAll('#bldg-root .bl-tabs .bl-tab:not([data-level=\"outside\"]):not([data-level=\"all\"])').length")
        assert r["panels"] == r["titles"] == n_floors and r["titleVisible"] and r["titleClear"] == [], (style, size, r)
        t = pg.evaluate(TAG_RULE, 4)
        assert not [o for o in t["out"] if "under a bar" in o], t["out"][:5]
    finally:
        ctx.close()
    assert not errors, errors


@pytest.mark.skipif(not BLUEPRINT_ALL_FLOORS, reason="All floors is switched off in this build")
@pytest.mark.parametrize("size", ["d1440", "phone"])
def test_a_hidden_tags_card_opens_from_the_card_list(browser, site, size):
    """Answer to the CEO's round-2 question 4: YES. Whatever tag or dot waits hidden in All floors, its card is listed in 'Cards, in order' (key C) and picking it enlarges it."""
    ctx, pg, errors = _open(browser, site, "classic", ALL_SIZES[size])
    try:
        pg.locator('#bldg-root .bl-tab[data-level="all"]').click(force=True)
        pg.wait_for_timeout(2000)
        hidden = pg.evaluate("[...document.querySelectorAll('#bldg-root .bl-pill[data-node]')].filter(p=>getComputedStyle(p).visibility==='hidden'||p.classList.contains('bl-off')).map(p=>p.dataset.node)")
        pg.keyboard.press("c")
        pg.wait_for_timeout(500)
        rows = pg.evaluate("[...document.querySelectorAll('#bldg-root .bl-cards button[data-node]')].map(b=>b.dataset.node)")
        assert len(rows) == 92, len(rows)
        pick = hidden[0] if hidden else rows[40]
        assert pick in rows
        pg.evaluate("id=>document.querySelector('#bldg-root .bl-cards button[data-node=\"'+id+'\"]').click()", pick)
        pg.wait_for_timeout(900)
        assert pg.evaluate("AltoBuilding.enlarged()") == pick, (pick, len(hidden))
    finally:
        ctx.close()
    assert not errors, errors


ROOMS = r"""()=>{ const R=e=>e.getBoundingClientRect(), vis=p=>{ const cs=getComputedStyle(p); return cs.visibility!=='hidden'&&!p.classList.contains('bl-off')&&+cs.opacity>0; };
 const inside=(poly,x,y)=>{ let c=false; for(let i=0,j=poly.length-1;i<poly.length;j=i++){ const a=poly[i], b=poly[j]; if((a[1]>y)!==(b[1]>y)&&x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]) c=!c; } return c; };
 const out=[]; let dots=0, badges=0, rooms=0;
 AltoBuilding.roomPolys().forEach(r=>{ rooms++; const ps=r.ids.map(id=>document.querySelector('#bldg-root .bl-pill[data-node="'+id+'"]')), v=ps.filter(vis);
   const bd=v.filter(p=>p.classList.contains('bl-badge'));
   if(bd.length){ badges++; if(bd.length!==1||v.length!==1||bd[0].firstChild.textContent.trim()!==String(r.n)) out.push('room '+r.id+': badge '+bd.map(p=>p.firstChild.textContent)+' for '+r.n+' cards, '+v.length+' shown'); return; }
   if(v.length!==r.n) { out.push('room '+r.id+': '+v.length+' of '+r.n+' shown, no badge'); return; }
   v.forEach(p=>{ dots++; const b=R(p), x=(b.left+b.right)/2, y=(b.top+b.bottom)/2; if(!inside(r.poly,x,y)) out.push('room '+r.id+': dot '+p.dataset.node+' outside its room'); }); });
 return {out, dots, badges, rooms}; }"""


@pytest.mark.skipif(not BLUEPRINT_ALL_FLOORS, reason="All floors is switched off in this build")
@pytest.mark.parametrize("style", STYLES)
@pytest.mark.parametrize("size", ["phone", "phone-land"])
def test_all_floors_on_a_phone_every_dot_is_in_its_own_room_or_a_count_badge_stands_in(browser, site, style, size):
    """Board B-1120-LOOK269-R2 round 3: on a phone's All floors every dot's centre is inside its own room's polygon, or ONE badge (the room's card count) stands for the
    room's dots (never a re-gridded lattice). A tap on a dot opens its card; a tap on a badge lists that room's cards."""
    ctx, pg, errors = _open(browser, site, style, ALL_SIZES[size])
    try:
        pg.locator('#bldg-root .bl-tab[data-level="all"]').click(force=True)
        pg.wait_for_timeout(2200)
        r = pg.evaluate(ROOMS)
        assert r["out"] == [], (style, size, r["out"][:6], r["dots"], r["badges"])
        assert r["dots"] + r["badges"] > 0 and r["rooms"] > 20, r
        dot = pg.locator("#bldg-root .bl-pill.bl-dot:not(.bl-badge):not(.bl-off)").first
        nid = dot.get_attribute("data-node")
        dot.tap(force=True)
        pg.wait_for_timeout(700)
        assert pg.evaluate("AltoBuilding.enlarged()") == nid                       # a tap on a dot opens its card
        pg.evaluate("AltoBuilding.shrink()")
        pg.wait_for_timeout(500)
        # Board B-1120-269-TARGET: a tap at a dot's centre, and a tap 20 pt off it (where it is the NEAREST dot), opens THAT dot's card
        pts = pg.evaluate("""()=>[...document.querySelectorAll('#bldg-root .bl-pill.bl-dot:not(.bl-off)')].filter(p=>getComputedStyle(p).visibility!=='hidden').map(p=>{ const b=p.getBoundingClientRect(); return [p.dataset.node,(b.left+b.right)/2,(b.top+b.bottom)/2,p.classList.contains('bl-badge')?1:0]; }).filter(q=>q[2]>70&&q[2]<innerHeight-70&&q[1]>10&&q[1]<innerWidth-90)""")   # (on screen, clear of the bars: the floors scroll)
        dots = [q for q in pts if not q[3]]
        assert len(dots) >= 20, len(dots)
        import math
        checked = off_checked = 0
        for id_, x, y, _ in dots[::max(1, len(dots) // 16)]:
            others = [(px, py) for i2, px, py, _b in pts if i2 != id_]
            spot = None
            for a in range(0, 360, 30):
                tx, ty = x + 20 * math.cos(math.radians(a)), y + 20 * math.sin(math.radians(a))
                if 4 < tx < pg.viewport_size["width"] - 4 and 70 < ty < pg.viewport_size["height"] - 70 and all(math.hypot(tx - px, ty - py) > 21.5 for px, py in others):
                    spot = (tx, ty)
                    break
            for tx, ty in ([(x, y)] + ([spot] if spot else [])):
                pg.touchscreen.tap(tx, ty)
                pg.wait_for_timeout(450)
                assert pg.evaluate("AltoBuilding.enlarged()") == id_, (id_, round(tx - x), round(ty - y))
                pg.evaluate("AltoBuilding.shrink()")
                pg.wait_for_timeout(350)
                checked += 1
            off_checked += bool(spot)
        assert off_checked >= 5, off_checked                                   # enough dots stood clear for a 20 pt-off tap
        badges = pg.evaluate("[...document.querySelectorAll('#bldg-root .bl-pill.bl-badge:not(.bl-off)')].map(p=>{ const b=p.getBoundingClientRect(); return [Math.round(b.width),Math.round(b.height)]; })")
        assert all(w >= 44 and h >= 44 for w, h in badges), badges                # every badge is a 44 pt target
        bd = pg.evaluate("""()=>[...document.querySelectorAll('#bldg-root .bl-pill.bl-badge:not(.bl-off)')].map(p=>{ const b=p.getBoundingClientRect(); return [(b.left+b.right)/2,(b.top+b.bottom)/2,p.firstChild.textContent.trim()]; }).filter(q=>q[1]>0&&q[1]<innerHeight-40&&q[0]>0&&q[0]<innerWidth-40)""")
        if bd:
            pg.touchscreen.tap(bd[0][0], bd[0][1])
            pg.wait_for_timeout(500)
            rows = pg.evaluate("document.querySelectorAll('#bldg-root .bl-cards:not([hidden]) button[data-node]').length")
            assert rows == int(bd[0][2]), (rows, bd[0])                                 # a badge lists exactly that room's cards
    finally:
        ctx.close()
    assert not errors, errors


@pytest.mark.parametrize("style", STYLES)
def test_all_floors_phone_landscape_name_card_scrolls_away_with_the_floors(browser, site, style):
    """Round 4: phone All floors at 844x390: the name card sits in flow above the first floor; after scrolling it intersects no floor panel."""
    ctx, pg, errors = _open(browser, site, style, ALL_SIZES["phone-land"])
    try:
        pg.locator('#bldg-root .bl-tab[data-level="all"]').click(force=True)
        pg.wait_for_timeout(2000)
        js = """()=>{ const h=document.querySelector('#bldg-root .bl-head').getBoundingClientRect();
          return {h:[h.left,h.top,h.right,h.bottom], x:[...document.querySelectorAll('#bldg-root .bl-cellbg[data-fade]')].map(e=>{const q=e.getBoundingClientRect(); return [q.left,q.top,q.right,q.bottom];})}; }"""
        ix = lambda a, b: a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]
        r0 = pg.evaluate(js)
        assert not [p for p in r0["x"] if ix(r0["h"], p)], ("unscrolled", r0)
        for dy in (160, 400, 900):
            pg.evaluate("""d=>{ const s=document.querySelector('#bldg-root svg.bl-svg'), b=s.getBoundingClientRect(); s.dispatchEvent(new WheelEvent('wheel',{deltaY:d,clientX:b.left+b.width/2,clientY:b.top+b.height/2,bubbles:true,cancelable:true})); }""", dy)
            pg.wait_for_timeout(900)
            r = pg.evaluate(js)
            assert not [p for p in r["x"] if ix(r["h"], p)], ("scrolled", dy, r)
        assert pg.evaluate(js)["h"][3] < r0["h"][3] - 20, "the card did not scroll away with the floors"
        pg.evaluate("""()=>{ const s=document.querySelector('#bldg-root svg.bl-svg'), b=s.getBoundingClientRect(); s.dispatchEvent(new WheelEvent('wheel',{deltaY:-3000,clientX:b.left+b.width/2,clientY:b.top+b.height/2,bubbles:true,cancelable:true})); }""")
        pg.wait_for_timeout(1200)
        pg.locator('#bldg-root .bl-head .bl-hmin').click(force=True)   # collapse still works
        pg.wait_for_timeout(400)
        assert pg.evaluate("document.querySelector('#bldg-root .bl-head').classList.contains('bl-min')")
    finally:
        ctx.close()
    assert not errors, errors
