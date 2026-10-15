"""The Mind Palace's chrome: the zoom controls beside the account toggle (and the phone's map
page), the board that never scrolls past the city's edge, and the map-only backgrounds
(palace_backgrounds.py). A synthetic city is used; nothing here touches the network, Firebase
or any ALTO_* setting. The browser parts are skipped when Playwright is not installed."""
import copy
import http.server
import json
import math
import re
import socketserver
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import backgrounds as bg                       # noqa: E402
from alto.build import fingerprint                              # noqa: E402
from alto.build import palace, palace_place as pp               # noqa: E402
from alto.build import palace_backgrounds as pbg                # noqa: E402
from alto.build.backgrounds_catalog import COLOURS, PATTERNS, SCENES   # noqa: E402
from alto.build.builder import build_timeline, load_brief       # noqa: E402

# ── a city big enough to scroll ─────────────────────────────────────────────
W, H = 5200, 3600
BBOX = [39.95, -75.17, 39.95 + H / 110574, -75.17 + W / (math.cos(math.radians(39.95 + H / 221148)) * 111320)]


def city_map():
    streets = [{"n": f"{i + 1}th Street", "k": 4, "p": [x, 0, x, H]} for i, x in enumerate(range(150, W, 260))]
    streets += [{"n": f"{chr(65 + i)} Avenue", "k": 3, "p": [0, y, W, y]} for i, y in enumerate(range(130, H, 260))]
    return {"v": 1, "place": "Gridville", "bbox": list(BBOX), "scale": 1.0, "W": W, "H": H,
            "attribution": "© OpenStreetMap contributors", "water": [], "rivers": [], "parks": [],
            "streets": streets, "trails": [], "rails": [], "stations": [], "landmarks": [],
            "majors": ["1th Street", "A Avenue"],
            # what the drawn grid is made of (palace_grid): every street as a run of line
            "edges": [s["p"] for s in streets]}


def bundle(mode="palace"):
    m = city_map()
    s, w, n, e = BBOX
    third = (e - w) / 3
    pal = {"place": "Gridville", "bbox": list(BBOX),
           "districts": [{"unit": i, "name": f"District {i}", "bounds": [s, w + i * third, n, w + (i + 1) * third]} for i in range(3)],
           "data_z": palace.pack({"map": m, "blocks": pp.lots(m)})}
    brief = {"title": "Grid Palace", "subject": "A made-up city", "timeline_id": "grid-palace", "mode": mode,
             "node_noun": "Room", "period_noun": "Wing", "accent": "#5b8def",
             "acts": [{"label": "ONE", "short": "One", "color": "#4a9eff"},
                      {"label": "TWO", "short": "Two", "color": "#22c55e"},
                      {"label": "THREE", "short": "Three", "color": "#f59e0b"}], "palace": pal}
    nodes = [{"id": f"n{i}", "act": i % 3, "tag": "Room", "title": f"Room {i}", "desc": f"About room {i}."} for i in range(18)]
    return {"brief": brief, "nodes": nodes, "connections": []}


class Served:
    """The page over http (a file: page keeps the Alto wallpaper: only the map grounds, which are CSS, apply there)."""
    def __init__(self, url, path):
        self.url, self.path = url, path

    def as_uri(self):
        return self.url


@pytest.fixture(scope="module")
def page_file(tmp_path_factory):
    html, _ = build_timeline(*load_brief(copy.deepcopy(bundle())))
    d = tmp_path_factory.mktemp("pal")
    (d / "palace.html").write_text(html, encoding="utf-8")

    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(d), **k)

        def log_message(self, *a):
            pass
    srv = socketserver.TCPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield Served(f"http://127.0.0.1:{srv.server_address[1]}/palace.html", d / "palace.html")
    srv.shutdown()


# ── the map backgrounds, without a browser ──────────────────────────────────

def test_eight_map_backgrounds_each_with_a_light_and_a_dark_ground():
    assert len(pbg.PALACE_BGS) == 8
    ids = [i for i, _n, _b in pbg.PALACE_BGS]
    names = [n for _i, n, _b in pbg.PALACE_BGS]
    assert len(set(ids)) == 8 and len(set(names)) == 8 and ids[0] == pbg.DEFAULT == "m-atlas"
    other = {c["id"] for c in COLOURS} | {c["id"] for c in PATTERNS} | {c["id"] for c in SCENES}
    other_names = {c["name"] for c in COLOURS} | {c["name"] for c in PATTERNS}
    assert not other & set(ids) and not other_names & set(names)
    for i, e in pbg.client_entries().items():
        assert e["g"] == "Mind Palace" and e["k"] == "m" and re.fullmatch(r"m-[a-z]+", i)
        for th in ("l", "d"):
            t = e[th]
            assert t["b"].count("(") == t["b"].count(")") and "linear-gradient(" in t["b"]
            assert re.fullmatch(r"#[0-9a-f]{6}", t["a"]) and re.fullmatch(r"#[0-9a-f]{6}", t["q"]) and re.fullmatch(r"#[0-9a-f]{6}", t["s"])
            assert set(t["v"]) >= {"--pal-ground", "--pal-glass", "--pal-glass-edge", "--pal-halo", "--pal-text", "--pal-park", "--pal-lm"}
            assert len(json.dumps(t)) < 4500, (i, th)            # CSS, never an image payload


def _lum(rgb):
    def c(v):
        v /= 255
        return v / 12.92 if v <= .03928 else ((v + .055) / 1.055) ** 2.4
    r, g, b = rgb
    return .2126 * c(r) + .7152 * c(g) + .0722 * c(b)


def _rgba(s):
    if s.startswith("#"):
        return pbg._rgb(s) + (1.0,)
    m = re.fullmatch(r"rgba?\(([^)]+)\)", s.strip())
    p = [float(x) for x in m.group(1).split(",")]
    return (p[0], p[1], p[2], p[3] if len(p) > 3 else 1.0)


def test_each_ground_is_calm_and_keeps_names_and_chips_legible():
    for i, e in pbg.client_entries().items():
        for th in ("l", "d"):
            v = e[th]["v"]
            ground = tuple(float(x) for x in v["--pal-ground"].split(","))
            gl = _lum(ground)
            # light ground stays pale, dark ground stays deep: the streets (coloured, on top) are the contrast
            assert gl > .55 if th == "l" else gl < .12, (i, th, gl)
            # a street name's ink on its halo (the halo over the ground) reads as text
            r, g, b, a = _rgba(v["--pal-halo"])
            halo = tuple(a * c + (1 - a) * gc for c, gc in zip((r, g, b), ground))
            t = pbg._rgb(v["--pal-text"])
            hi, lo = max(_lum(halo), _lum(t)), min(_lum(halo), _lum(t))
            assert (hi + .05) / (lo + .05) >= 9, (i, th)
            # the top strip behind the bars is the same family as the ground
            assert abs(_lum(pbg._rgb(e[th]["a"])) - gl) < .12, (i, th)


def test_a_map_page_carries_the_set_and_opens_on_the_first():
    assert "m-atlas" not in bg.catalog_json()
    assert all(not k.startswith("m-") for k in bg.client_catalog())
    cat = bg.client_catalog(palace=True)
    assert list(cat)[:8] == [i for i, _n, _b in pbg.PALACE_BGS]
    assert len(cat) == len(bg.client_catalog()) + 8
    assert 'DEF="m-atlas"' in bg.head_block("k", palace=True)
    assert 'DEF=""' in bg.head_block("k")


def test_only_a_palace_page_offers_them():
    pal, _ = build_timeline(*load_brief(copy.deepcopy(bundle())))
    assert '"m-midnight"' in pal and '"g":"Mind Palace"' in pal
    for sample in ("contracts_brief.json", "lanes_brief.json", "outline_brief.json"):
        d = json.loads((ROOT / "samples" / sample).read_text())
        html, _ = build_timeline(*load_brief(d))
        head = re.search(r'<script id="alto-bg-head">.*?</script>', html, re.S).group(0)
        assert '"g":"Mind Palace"' not in head and "m-atlas" not in head and 'DEF=""' in head, sample


def test_a_change_to_the_map_grounds_changes_the_timeline_fingerprint():
    assert "palace_backgrounds.py" in fingerprint._TIMELINE_SOURCES


# ── in a browser ────────────────────────────────────────────────────────────

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None


@pytest.fixture(params=["chromium", "webkit"])
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


def open_page(browser, page_file, w=1500, h=900, dark=False):
    pg = browser.new_page(viewport={"width": w, "height": h})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(page_file.as_uri()); pg.wait_for_timeout(2500)
    if dark:
        pg.evaluate("toggleMode()"); pg.wait_for_timeout(500)
    pg._errs = errs
    return pg


RECT = """(sel)=>{const e=document.querySelector(sel); if(!e) return null; const s=getComputedStyle(e);
  if(s.display==='none'||s.visibility==='hidden') return null; const r=e.getBoundingClientRect();
  return r.width?{l:r.left,t:r.top,r:r.right,b:r.bottom}:null}"""


def hit(a, b, pad=0):
    return a and b and a["l"] < b["r"] + pad and b["l"] < a["r"] + pad and a["t"] < b["b"] + pad and b["t"] < a["b"] + pad


@pytest.mark.parametrize("size", [(1280, 720), (1500, 900), (2000, 1200)])
@pytest.mark.parametrize("dark", [False, True])
def test_the_zoom_row_sits_beside_the_account_toggle_and_covers_nothing(browser, page_file, size, dark):
    pg = open_page(browser, page_file, *size, dark=dark)
    acct = pg.evaluate(RECT, "#account-btn")
    pill, city = pg.evaluate(RECT, "#pal-ctl .pc-pill"), pg.evaluate(RECT, "#pal-ctl .pc-city")
    assert acct and pill and city, (acct, pill, city)
    # one baseline: the row's centre is the account toggle's, and the heights are the same circle's
    mid = lambda r: (r["t"] + r["b"]) / 2
    assert abs(mid(pill) - mid(acct)) <= 1 and abs(mid(city) - mid(acct)) <= 1
    assert abs((pill["b"] - pill["t"]) - (acct["b"] - acct["t"])) <= 1.5
    # to its right, one gap away, in order: account, [+ | -], [City]
    gap = pill["l"] - acct["r"]
    assert 8 <= gap <= 16 and abs((city["l"] - pill["r"]) - gap) <= 1.5
    assert not hit(acct, pill) and not hit(acct, city) and not hit(pill, city)
    # nothing else in the corners is under it
    for sel in ("#mode-toggle", "#info-btn", "#search-btn", "#key-toggle", "#alto-edit-pill", "#tab-rail", "#notes-panel", "#bg-panel"):
        r = pg.evaluate(RECT, sel)
        assert not (hit(r, pill) or hit(r, city)), sel
    # an Alto control: the glass of the round buttons, a divider in the pill, an icon in each button
    assert pg.evaluate("document.querySelectorAll('#pal-ctl .pc-pill svg').length") == 2
    assert pg.evaluate("document.querySelectorAll('#pal-ctl .pc-pill .pc-div').length") == 1
    st = pg.evaluate("""()=>{const s=getComputedStyle(document.querySelector('#pal-ctl .pc-pill')), a=getComputedStyle(document.getElementById('account-btn'));
      return {bg:s.backgroundColor, ref:a.backgroundColor, bd:s.borderTopWidth, refbd:a.borderTopWidth, rad:parseFloat(s.borderTopLeftRadius)}}""")
    assert st["bg"] == st["ref"] and st["bd"] == st["refbd"] and st["rad"] > 15
    assert pg._errs == []
    pg.close()


def test_the_zoom_row_zooms_and_says_where_the_board_is(browser, page_file):
    pg = open_page(browser, page_file)
    z = lambda: pg.evaluate("window._altoPalaceGeo.Z")
    pg.click("#pal-ctl [data-z=fit]"); pg.wait_for_timeout(900)          # the page opens on the neighbourhoods; City is the farthest (the whole city)
    z0 = z()
    assert pg.evaluate("document.querySelector('#pal-ctl [data-z=out]').classList.contains('off')")      # at the farthest
    assert pg.evaluate("document.querySelector('#pal-ctl [data-z=fit]').classList.contains('on')")
    pg.click("#pal-ctl [data-z=in]"); pg.wait_for_timeout(700)
    z1 = z()
    assert z1 > z0 * 1.4
    assert not pg.evaluate("document.querySelector('#pal-ctl [data-z=out]').classList.contains('off')")
    assert not pg.evaluate("document.querySelector('#pal-ctl [data-z=fit]').classList.contains('on')")
    pg.click("#pal-ctl [data-z=out]"); pg.wait_for_timeout(700)
    assert abs(z() - z0) < 1e-3
    pg.click("#pal-ctl [data-z=in]"); pg.wait_for_timeout(600)
    pg.click("#pal-ctl [data-z=fit]"); pg.wait_for_timeout(700)
    assert abs(z() - z0) < 1e-3
    pg.close()


# ── the board never scrolls past the city ───────────────────────────────────
GAPS = """()=>{const cv=document.getElementById('canvas'), c=cv.getBoundingClientRect(), q=document.getElementById('palace-svg').getBoundingClientRect();
  return {top:q.top-c.top, bottom:c.bottom-q.bottom, left:q.left-c.left, right:c.right-q.right, st:cv.scrollTop, bars:document.getElementById('nav').getBoundingClientRect().bottom-c.top}}"""


def check_edges(pg, label):
    for name, dx, dy, side in (("up", 0, -1, "top"), ("down", 0, 1, "bottom"), ("left", -1, 0, "left"), ("right", 1, 0, "right")):
        for _ in range(30):
            pg.mouse.wheel(dx * 700, dy * 700)
        pg.wait_for_timeout(250)
        g = pg.evaluate(GAPS)
        # no empty page between the bars and the city (or past its other three sides)
        assert g[side] <= 0.6, (label, name, g)
        assert g["bars"] <= 1.5, (label, name, g)                  # the canvas starts where the bars end


def test_panning_never_shows_the_page_beyond_the_city(browser, page_file):
    pg = open_page(browser, page_file)
    pg.mouse.move(700, 500)
    check_edges(pg, "far")
    for _ in range(2):
        pg.click("#pal-ctl [data-z=in]"); pg.wait_for_timeout(650)
        check_edges(pg, "zoomed")
    # setting the scroll directly (the engine does: scrollTop = 0), dragging, and the keyboard
    pg.evaluate("document.getElementById('canvas').scrollTop = 0")
    assert pg.evaluate(GAPS)["top"] <= 0.6
    pg.mouse.move(500, 400); pg.mouse.down(); pg.mouse.move(520, 900, steps=8); pg.mouse.up(); pg.wait_for_timeout(200)
    assert pg.evaluate(GAPS)["top"] <= 0.6
    pg.evaluate("document.getElementById('canvas').scrollLeft = 1e6; document.getElementById('canvas').scrollTop = 1e6")
    g = pg.evaluate(GAPS)
    assert g["bottom"] <= 0.6 and g["right"] <= 0.6
    assert pg._errs == []
    pg.close()


def test_the_edge_holds_after_a_fly_and_with_the_detail_page_opened_and_closed(browser, page_file):
    pg = open_page(browser, page_file)
    pg.mouse.move(700, 500)
    # a click on a building flies the board to it, then enlarges it
    nid = pg.evaluate("Object.keys(window._ALTO_PALACE.at)[0]")
    pg.evaluate("(id)=>{ const e=document.getElementById('node-'+id); e.scrollIntoView({block:'center',inline:'center'}); }", nid)
    pg.wait_for_timeout(300)
    pg.click(f"#node-{nid} .node-card"); pg.wait_for_timeout(1600)
    assert pg.evaluate("!!window._focusedNodeId")
    pg.evaluate("window.exitFocus && window.exitFocus()"); pg.wait_for_timeout(900)
    check_edges(pg, "after fly")
    # the detail page opens over the board and closes again
    pg.evaluate("(id)=>window.showDetail('node', id)", nid); pg.wait_for_timeout(700)
    pg.evaluate("window.showTimeline()"); pg.wait_for_timeout(700)
    check_edges(pg, "after the detail page")
    pg.close()


def test_a_card_enlarged_at_the_edge_is_never_cut_off_and_the_city_stays_under_it(browser, page_file):
    pg = open_page(browser, page_file)
    corner = pg.evaluate("""()=>{const P=window._ALTO_PALACE; let best=null;
      for(const id in P.at){const k=P.at[id].split('.'), L=P.b[+k[0]][+k[1]]; if(!best||L[1]<best[2]) best=[id,L[0],L[1]];} return best[0];}""")
    pg.evaluate("document.getElementById('canvas').scrollTop = 0; document.getElementById('canvas').scrollLeft = 0"); pg.wait_for_timeout(200)
    pg.evaluate("(id)=>window.enterFocus(id)", corner); pg.wait_for_timeout(1600)
    r = pg.evaluate("""()=>{const cv=document.getElementById('canvas').getBoundingClientRect(), c=document.querySelector('.node.focused .node-card').getBoundingClientRect(),
      g=document.querySelector('#palace-svg .pl-glass').getBoundingClientRect();
      return {cardTop:c.top-cv.top, cardLeft:c.left-cv.left, cardBottom:cv.bottom-c.bottom, glass:[g.left<=cv.left, g.top<=cv.top, g.right>=cv.right, g.bottom>=cv.bottom]}}""")
    assert r["cardTop"] >= 0 and r["cardLeft"] >= 0 and r["cardBottom"] >= 0, r      # the bars do not cut it
    assert all(r["glass"]), r                                                        # glass, not bare page, around it
    pg.evaluate("window.exitFocus()"); pg.wait_for_timeout(900)
    assert pg.evaluate("document.getElementById('world').style.getPropertyValue('--ppan-y')") == ""
    pg.close()


# ── the map backgrounds, in a page ──────────────────────────────────────────

def test_a_palace_opens_on_the_atlas_and_the_picker_offers_the_set_first(browser, page_file):
    pg = open_page(browser, page_file)
    s = pg.evaluate("({on:document.documentElement.classList.contains('alto-bg'), map:document.documentElement.classList.contains('alto-bg-map'), id:window._altoBgId})")
    assert s == {"on": True, "map": True, "id": "m-atlas"}
    assert pg.evaluate("localStorage.getItem(window._altoBg.key)") is None            # a default is not a choice: nothing to sync
    pg.click("#bg-toggle"); pg.wait_for_timeout(400)
    heads = pg.evaluate("[...document.querySelectorAll('#bg-panel .bg-h')].map(e=>e.textContent)")
    assert heads[0] == "Mind Palace" and heads.index("Colors") > 0
    tiles = pg.evaluate("[...document.querySelector('#bg-panel .bg-grid').children].map(e=>e.getAttribute('data-bg'))")
    assert tiles == [i for i, _n, _b in pbg.PALACE_BGS] + [""]
    assert pg.evaluate("[...document.querySelectorAll('.bg-tile.active')].map(e=>e.getAttribute('data-bg'))") == ["m-atlas"]
    pg.close()


@pytest.mark.parametrize("dark", [False, True])
def test_each_map_background_paints_the_page_and_the_map_with_it(browser, page_file, dark):
    pg = open_page(browser, page_file, dark=dark)
    th = "d" if dark else "l"
    for pid, _n, _b in pbg.PALACE_BGS:
        want = pbg.client_entries()[pid][th]
        pg.evaluate("(i)=>window._altoBg.choose(i)", pid); pg.wait_for_timeout(350)
        got = pg.evaluate("""()=>{const r=document.documentElement, s=r.style, cs=getComputedStyle(r);
          return {id:window._altoBgId, map:r.classList.contains('alto-bg-map'), halo:s.getPropertyValue('--pal-halo'), ground:cs.getPropertyValue('--pal-ground').trim(),
                  bg:s.getPropertyValue('--alto-bg').length>20, rec:JSON.parse(localStorage.getItem(window._altoBg.key)).v,
                  halo2:cs.getPropertyValue('--pal-halo').trim(), top:s.getPropertyValue('--alto-top')}}""")
        assert got["id"] == pid and got["map"] and got["bg"] and got["rec"] == pid
        assert got["halo"] == want["v"]["--pal-halo"] and got["ground"] == want["v"]["--pal-ground"] and got["top"] == want["a"]
        # the street names really take that halo
        assert pg.evaluate("getComputedStyle(document.querySelector('#palace-svg .pl-st')).stroke") != "none"
    # the lines are drawn against the ground chosen, not a fixed one
    pg.evaluate("(i)=>window._altoBg.choose(i)", "m-blueprint"); pg.wait_for_timeout(500)
    g = pg.evaluate("""()=>{const ground=getComputedStyle(document.documentElement).getPropertyValue('--pal-ground').split(',').map(Number);
      const l=c=>{const f=v=>{v/=255;return v<=.03928?v/12.92:Math.pow((v+.055)/1.055,2.4)}; return .2126*f(c[0])+.7152*f(c[1])+.0722*f(c[2])};
      const out=[...document.querySelectorAll('#palace-svg .pl-streets .pl-tube')].map(e=>e.getAttribute('stroke').match(/\\d+/g).slice(0,3).map(Number));
      return {n:out.length, worst:Math.min(...out.map(c=>Math.abs(l(c)-l(ground))))}}""")
    assert g["n"] > 0 and g["worst"] >= .12, g
    assert pg._errs == []
    pg.close()


def test_a_map_choice_persists_follows_the_theme_and_the_alto_wallpaper_stays_a_choice(browser, page_file):
    pg = open_page(browser, page_file)
    pg.evaluate("window._altoBg.choose('m-dusk')"); pg.wait_for_timeout(300)
    light = pg.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--pal-ground').trim()")
    pg.reload(); pg.wait_for_timeout(2500)
    assert pg.evaluate("window._altoBgId") == "m-dusk"
    pg.evaluate("toggleMode()"); pg.wait_for_timeout(600)
    dark = pg.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--pal-ground').trim()")
    assert dark != light and pg.evaluate("window._altoBgId") == "m-dusk"
    # the Alto wallpaper, picked on purpose, is remembered as that (it is not the default again)
    pg.click("#bg-toggle"); pg.wait_for_timeout(300)
    pg.click('.bg-tile[data-bg=""]'); pg.wait_for_timeout(500)
    assert pg.evaluate("window._altoBgId") == "" and not pg.evaluate("document.documentElement.classList.contains('alto-bg')")
    assert json.loads(pg.evaluate("localStorage.getItem(window._altoBg.key)"))["v"] == ""
    pg.reload(); pg.wait_for_timeout(2500)
    assert pg.evaluate("window._altoBgId") == "" and not pg.evaluate("document.documentElement.classList.contains('alto-bg')")
    assert not pg.evaluate("document.documentElement.style.cssText.includes('--pal-')")
    # and an ordinary background still works on a palace (on a web address: a file keeps the Alto look)
    pg.evaluate("window._altoBg.choose('c-ocean')"); pg.wait_for_timeout(300)
    assert pg.evaluate("window._altoBgId") == "c-ocean" and not pg.evaluate("document.documentElement.classList.contains('alto-bg-map')")
    assert not pg.evaluate("document.documentElement.style.cssText.includes('--pal-')")
    pg.close()


def test_other_timelines_do_not_get_the_map_set_or_the_default(browser, tmp_path):
    d = json.loads((ROOT / "samples" / "outline_brief.json").read_text(encoding="utf-8"))
    html, _ = build_timeline(*load_brief(d))
    f = tmp_path / "o.html"
    f.write_text(html, encoding="utf-8")
    pg = browser.new_page(viewport={"width": 1500, "height": 900})
    pg.goto(f.as_uri()); pg.wait_for_timeout(2000)
    assert pg.evaluate("window._altoBgId") == "" and not pg.evaluate("document.documentElement.classList.contains('alto-bg')")
    assert not [k for k in pg.evaluate("Object.keys(window._altoBg.C)") if k.startswith("m-")]
    pg.close()


# ── the phone's map page ────────────────────────────────────────────────────
PHONE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.5 Mobile/15E148 Safari/604.1")


@pytest.mark.parametrize("size", [(360, 640), (390, 844), (430, 932)])
def test_the_phone_map_page_has_the_same_controls_and_they_cover_nothing(browser, page_file, size):
    if browser.browser_type.name != "chromium":
        pytest.skip("the phone layout is driven by the user agent; Chrome stands in for it")
    ctx = browser.new_context(viewport={"width": size[0], "height": size[1]}, is_mobile=True, has_touch=True, user_agent=PHONE_UA)
    pg = ctx.new_page()
    pg.goto(page_file.as_uri()); pg.wait_for_timeout(2500)
    assert pg.evaluate("document.documentElement.classList.contains('mobile')")
    assert pg.evaluate(RECT, "#pal-ctl") is None                                   # the desktop row is not on a phone
    pg.evaluate("document.getElementById('minimap-toggle').click()"); pg.wait_for_timeout(900)
    zoom, close = pg.evaluate(RECT, "#pal-mmap .pm-zoom"), pg.evaluate(RECT, "#pal-mmap .pm-close")
    assert zoom and close and not hit(zoom, close)
    assert [b for b in pg.evaluate("[...document.querySelectorAll('#pal-mmap .pm-zoom button')].map(e=>e.getAttribute('data-z'))")] == ["in", "out", "fit"]
    for b in pg.evaluate("[...document.querySelectorAll('#pal-mmap .pm-zoom button, #pal-mmap .pm-close')].map(e=>{const r=e.getBoundingClientRect(); return [r.width,r.height]})"):
        assert min(b) >= 43                                                         # a thumb's size
    assert zoom["r"] <= size[0] and zoom["b"] <= size[1]
    # a building's card, once one is tapped, stops short of the zoom column
    pg.evaluate("document.querySelector('#palace-svg-m .pl-bld').dispatchEvent(new MouseEvent('click', {bubbles:true}))"); pg.wait_for_timeout(1200)   # the sheet rises on a spring
    card = pg.evaluate(RECT, "#pal-mmap .pm-card")
    zoom = pg.evaluate(RECT, "#pal-mmap .pm-zoom")                                 # the zoom column rides above the sheet as it rises
    assert card and not hit(card, zoom) and not hit(card, close)
    z0 = pg.evaluate("document.getElementById('palace-svg-m').getAttribute('width')")
    pg.evaluate("document.querySelector('#pal-mmap [data-z=in]').click()"); pg.wait_for_timeout(700)
    assert float(pg.evaluate("document.getElementById('palace-svg-m').getAttribute('width')")) > float(z0)
    ctx.close()
