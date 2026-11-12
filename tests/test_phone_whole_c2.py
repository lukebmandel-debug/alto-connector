"""The phone whole view's unit index (alto/build/phone_index.py; chunk 6, C2, Art sheet ORG/notes-art/sheet-1111c).

Luke, 2026-11-11: "I agree C2, but just to be clear, the progress bar is for study plan, right?" The whole view of a timeline
or an outline opens on unit tiles (the real branch shape, lead cards titled at 11 px, links drawn or named); a tap opens a tile
in place at reading size and folds the others to 44 pt bars; a pinch out past the index is still the real board. The progress
rule, "N of M done" and the dot states come from the study plan only.

Run in Playwright WebKit as an iPhone at the boxes Mobile Safari gives the page (402 x 874, 874 x 292); skipped without it."""
import copy
import datetime
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

from alto.build import phone, phone_index  # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None

LONG = "UNIT ONE — PERSONAL JURISDICTION, SERVICE OF PROCESS AND NOTICE UNDER RULE 4 AND THE LONG-ARM STATUTES"


def _pages():
    import phone_matrix as pm
    from alto.build import palace_assets
    from alto.build.builder import build_timeline, load_brief
    man = {f: "/%s/%s" % (f, n) for f, n, _t in palace_assets.assets() if f in ("retro", "holo")}

    def page(plan=False, long=False):
        d = json.loads((ROOT / "samples" / "outline_brief.json").read_text(encoding="utf-8"))
        d["connections"].append(["offer", "mitigation", "limits"])            # a link to a unit that is not next door: a named chip
        if long:
            d["brief"]["acts"][0]["label"] = LONG
        if plan:
            t, ids = datetime.date.today(), [n["id"] for n in d["nodes"]]
            d["brief"]["study_plan"] = {"v": 1, "exam_date": (t + datetime.timedelta(days=20)).isoformat(), "days_per_week": 5, "minutes_per_day": 40,
                                        "items": [{"node": ids[i], "day": (t + datetime.timedelta(days=dd)).isoformat(), "why": "weak on this", "signal": "told"}
                                                  for i, dd in ((1, -1), (3, 0), (4, 0), (6, 2), (12, 5))]}
        html = build_timeline(*load_brief(copy.deepcopy(d)))[0]
        raw = html
        i = html.rfind("</body>")
        html = html[:i] + pm.LOADER % json.dumps(man) + html[i:]
        j = html.find('<script id="alto-shell-js">')
        return html[:j] + pm.SEED + html[j:], raw
    out, raw = {}, {}
    for name, kw in (("plan", {"plan": True}), ("bare", {}), ("long", {"long": True})):
        out[name], raw[name] = page(**kw)
    return pm, out, raw


@pytest.fixture(scope="module")
def built():
    return _pages()


@pytest.fixture(scope="module")
def site(built):
    if pw is None:
        pytest.skip("Playwright is not installed")
    pm, pages, _raw = built
    s = pm.serve(pages, {}, {})
    yield pm, f"http://127.0.0.1:{s.server_address[1]}"
    s.shutdown()


@pytest.fixture(scope="module")
def browser():
    if pw is None:
        pytest.skip("Playwright is not installed")
    with pw.sync_playwright() as p:
        try:
            b = p.webkit.launch()
        except Exception as e:
            pytest.skip(f"no WebKit: {e}")
        yield b
        b.close()


INSET = "document.addEventListener('DOMContentLoaded',()=>{const s=document.createElement('style');s.textContent='#sh-probe{padding-left:60px!important;padding-right:60px!important}';document.head.appendChild(s);});"
UP = "!!(window._altoPhoneIx && _altoPhoneIx.state().shown && document.querySelector('#ph-ix .ix-tile'))"


def _open(site, browser, page="plan", query="view=whole", w=402, h=874, init=None, until=UP, phone=True, **ctx):
    pm, base = site
    kw = dict(viewport={"width": w, "height": h})
    if phone:
        kw.update(is_mobile=True, has_touch=True, user_agent=pm.UA)
    c = browser.new_context(**kw, **ctx)
    if init:
        c.add_init_script(init)
    pg = c.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(f"{base}/{page}.html?{query}", wait_until="load", timeout=45000)
    if until:
        pg.wait_for_function(until, timeout=20000)
        pg.wait_for_timeout(1500)            # the index redraws once more after the engine settles (fonts, the chips' second layout)
    else:
        pg.wait_for_timeout(3000)
    pg._errors = errors
    return pg


def _done(pg):
    errs = pg._errors
    pg.context.close()
    assert not errs, errs


# what the index is, measured: tiles, text sizes, edges
LOOK = """() => { const ix=document.getElementById('ph-ix'), R=e=>{const r=e.getBoundingClientRect();return {l:r.left,t:r.top,r:r.right,b:r.bottom,w:r.width,h:r.height}};
 const vis=e=>{const r=e.getBoundingClientRect(),c=getComputedStyle(e);return r.width>0&&r.height>0&&c.visibility!=='hidden'&&c.display!=='none'};
 const texts=[...ix.querySelectorAll('*')].filter(e=>vis(e)&&[...e.childNodes].some(n=>n.nodeType===3&&n.textContent.trim()));
 const cs=getComputedStyle(ix), cv=document.getElementById('canvas'), sw=document.getElementById('summary-wrap');
 return {state:_altoPhoneIx.state(), iw:innerWidth, ih:innerHeight, bg:cs.backgroundColor, canvas:getComputedStyle(cv).visibility, rule:sw?sw.getBoundingClientRect().bottom:0,
  tiles:[...ix.querySelectorAll('.ix-tile')].map(t=>({...R(t), cls:t.className, cnt:t.querySelector('.ix-cnt').textContent, name:t.querySelector('.ix-name').firstChild.textContent, rule:!!t.querySelector('.ix-rule'),
     bg:getComputedStyle(t).backgroundColor, pills:[...t.querySelectorAll('.ix-mini .ix-pill')].filter(vis).map(p=>p.textContent), dots:t.querySelectorAll('.ix-mini .ix-dot').length,
     chips:[...t.querySelectorAll('.ix-chip')].filter(vis).map(p=>p.textContent), paths:t.querySelectorAll('svg path').length})),
  minFont:Math.min(...texts.map(e=>parseFloat(getComputedStyle(e).fontSize))), texts:texts.length,
  split:texts.filter(e=>{const c=getComputedStyle(e);return c.wordBreak==='break-all'||c.overflowWrap==='anywhere'||c.overflowWrap==='break-word'||(e.scrollWidth>e.clientWidth+1&&c.display!=='inline')}).map(e=>e.className+':'+e.textContent.slice(0,30)),
  states:[...new Set([...ix.querySelectorAll('.ix-tile .ix-dot')].map(d=>d.className.replace('ix-dot','').trim()))].sort(), key:!!ix.querySelector('.ix-key'), cross:ix.querySelectorAll('.ix-x path').length,
  radius:getComputedStyle(ix.querySelector('.ix-dot')).borderTopLeftRadius,
  chrome:['hamburger-tab','pmin-find'].map(i=>{const e=document.getElementById(i);return !!e&&vis(e)}), title:(document.getElementById('nav-drawer-title')||{}).textContent||'', brand:!!document.querySelector('#nav svg, #nav .brand, #nav img'),
  rail:(()=>{const e=document.getElementById('tab-rail');return !!e&&vis(e)})(),
  cards:[...ix.querySelectorAll('.ix-open .ix-card')].filter(vis).map(c=>({...R(c), f:parseFloat(getComputedStyle(c).fontSize), t:c.querySelector('.ix-ct').textContent, here:c.classList.contains('here'), fit:c.scrollWidth<=c.clientWidth+1})),
  flags:[...ix.querySelectorAll('.ix-flag')].filter(vis).length}; }"""
PINCH = """([x, y, d0, d1]) => { const t = document.elementFromPoint(x, y);
  const ev = (type, d) => { const a = {identifier:1, target:t, clientX:x-d/2, clientY:y}, b = {identifier:2, target:t, clientX:x+d/2, clientY:y};
    const e = new Event(type, {bubbles:true, cancelable:true}); const ts = type === 'touchend' ? [] : [a, b];
    Object.defineProperty(e, 'touches', {value:ts}); Object.defineProperty(e, 'changedTouches', {value:[a, b]}); t.dispatchEvent(e); };
  ev('touchstart', d0); for(let i = 1; i <= 8; i++) ev('touchmove', d0 + (d1-d0)*i/8); ev('touchend', d1); }"""


# ── what is hosted, what a page carries ──────────────────────────────────────

def test_the_index_rides_in_the_hosted_script_and_adds_nothing_to_the_page(built):
    _pm, _pages_, raw = built
    a = phone.ASSET
    for part in ("ph-ix", "_altoPhoneIx", "_altoStudyPlan", "You are here", "ix=0"):
        assert part in a, part
    assert "/*" not in a
    for page in raw.values():
        assert "ph-ix" not in page and "_altoPhoneIx" not in page and "ix-tile" not in page
    assert phone.PATH in raw["plan"]
    # no rule here is below 11 px
    sizes = [float(x) for x in re.findall(r"font(?:-size)?:[^;{}]*?(\d+(?:\.\d+)?)px", phone_index.CSS)]
    assert sizes and min(sizes) >= 11, sorted(set(sizes))


def test_the_page_stays_inside_the_private_page_budget(built):
    from alto.build.private_shell import MAX_PAGE_BYTES, stored_bytes
    _pm, _pages_, raw = built
    for name in ("plan", "bare"):
        n = stored_bytes(raw[name])
        assert n < min(MAX_PAGE_BYTES, 976 * 1024), (name, n, MAX_PAGE_BYTES)     # the tool's cap, and the 976 KB private-page wall


# ── step 1: the rest view (C1) ───────────────────────────────────────────────

def test_whole_view_opens_on_unit_tiles_with_the_real_shape(site, browser):
    pg = _open(site, browser)
    m = pg.evaluate(LOOK)
    assert m["state"]["shown"] and m["state"]["open"] == -1 and m["state"]["units"] == 5
    assert m["canvas"] == "hidden"                                           # the fitted board is not under the tiles
    assert [t["name"] for t in m["tiles"]] == ["Formation", "Consideration", "Defenses", "Terms & Performance", "Remedies"]
    for t in m["tiles"]:
        assert t["l"] >= 16 - .5 and t["r"] <= m["iw"] - 16 + .5, t          # 16 pt in from the edges
        assert t["t"] >= m["rule"] - 1 or t["t"] > 0                          # under the header rule
        assert t["pills"] and t["paths"] >= 3 and t["dots"] >= 8, t           # lead cards titled, the unit's links drawn, a dot a card
    assert "Formation" in m["tiles"][0]["pills"] and "Offer" in m["tiles"][0]["pills"]
    assert m["minFont"] >= 11 and not m["split"], (m["minFont"], m["split"])
    assert m["cross"] >= 1                                                   # III -> II runs through the gap
    assert any("→ V Mitigation" in c for c in m["tiles"][0]["chips"]), m["tiles"][0]["chips"]     # I -> V is a named chip
    assert m["bg"] in ("rgba(0, 0, 0, 0)", "transparent")                     # the ground shows through: no painted band
    assert all(re.search(r"rgba?\(.*,\s*0?\.\d+\)|color\(.*/\s*0?\.\d+\)", t["bg"]) for t in m["tiles"]), m["tiles"][0]["bg"]
    assert m["chrome"] == [True, True] and m["title"].strip() and not m["rail"]   # MENU, FIND, the title stay; no side chrome
    _done(pg)


def test_progress_is_the_study_plans_and_only_when_there_is_one(site, browser):
    pg = _open(site, browser)
    m = pg.evaluate(LOOK)
    assert m["state"]["plan"] and m["key"]
    assert m["tiles"][0]["cnt"] == "0 of 4 done" and m["tiles"][0]["rule"]            # four planned cards in unit I
    assert m["tiles"][1]["cnt"] == "0 of 1 done" and m["tiles"][3]["cnt"] == "8 cards" and not m["tiles"][3]["rule"]   # a unit with nothing planned: no rule
    assert "is-today" in m["states"] and "is-late" in m["states"] and "is-todo" in m["states"] and "is-done" not in m["states"]
    # tick one item in the plan's own list: the count, the rule and the dot follow
    pg.evaluate("document.getElementById('sp-chip').click()")
    pg.wait_for_timeout(300)
    pg.evaluate("(() => { const c=document.querySelector('#sp-sheet .sp-body input[type=checkbox]'); c.click(); })()")
    pg.wait_for_timeout(300)
    pg.evaluate("document.getElementById('sp-chip').click(); window.dispatchEvent(new Event('alto-study-sync'))")
    pg.wait_for_timeout(700)
    m2 = pg.evaluate(LOOK)
    assert m2["tiles"][0]["cnt"] == "1 of 4 done" and "is-done" in m2["states"], (m2["tiles"][0]["cnt"], m2["states"])
    assert pg.evaluate("document.querySelector('#ph-ix .ix-tile .ix-rule i').style.width") == "25%"
    _done(pg)
    pg = _open(site, browser, page="bare")
    b = pg.evaluate(LOOK)
    assert not b["state"]["plan"] and not b["key"] and b["states"] == [""]            # plain dots
    assert all(re.fullmatch(r"\d+ cards?", t["cnt"]) and not t["rule"] for t in b["tiles"]), [t["cnt"] for t in b["tiles"]]
    assert "done" not in pg.evaluate("document.getElementById('ph-ix').textContent")
    _done(pg)


def test_a_titled_card_opens_that_card_and_a_chip_goes_to_its_unit(site, browser):
    pg = _open(site, browser)
    pg.tap("#ph-ix .ix-pill[data-n=offer]")
    pg.wait_for_function("document.documentElement.classList.contains('detail-open') && window._currentDetailId==='offer'", timeout=8000)
    pg.evaluate("showTimeline()")
    pg.wait_for_timeout(700)
    m = pg.evaluate(LOOK)
    assert m["state"]["shown"] and m["state"]["here"] == "offer" and m["state"]["open"] == -1
    assert pg.evaluate("(() => { const p=document.querySelector('#ph-ix .ix-pill.here'), f=document.querySelector('#ph-ix .ix-map > .ix-flag'); return [p&&p.textContent, f&&f.textContent, f&&f.getBoundingClientRect().width>0]; })()") == ["Offer", "You are here", True]
    assert m["minFont"] >= 11
    pg.tap("#ph-ix .ix-tile[data-u='0'] .ix-chip")                              # Offer -> V Mitigation
    pg.wait_for_timeout(700)
    m = pg.evaluate(LOOK)
    assert m["state"]["open"] == 4 and m["state"]["here"] == "mitigation"
    assert [c["t"] for c in m["cards"] if c["here"]] == ["Mitigation"]
    _done(pg)


# ── step 2: open in place ────────────────────────────────────────────────────

def test_a_tap_opens_the_tile_in_place_and_the_others_fold_to_bars(site, browser):
    pg = _open(site, browser)
    pg.tap("#ph-ix .ix-tile[data-u='1'] .ix-map", position={"x": 6, "y": 4})
    anims = pg.evaluate("""(() => { const b=document.querySelector('#ph-ix .ix-tile.open .ix-body'), o=b.querySelector('.ix-open');
      return [b.getAnimations().map(a=>a.effect.getTiming().duration), o.getAnimations().map(a=>a.effect.getKeyframes().map(k=>Object.keys(k).filter(x=>x==='transform'||x==='opacity').sort().join('+')).join('|'))]; })()""")
    assert anims[0] == [280] and anims[1] == ["opacity+transform|opacity+transform"], anims
    pg.wait_for_timeout(600)
    m = pg.evaluate(LOOK)
    assert m["state"]["open"] == 1
    t = m["tiles"]
    assert "open" in t[1]["cls"] and all("fold" in x["cls"] and 44 <= x["h"] <= 48 for i, x in enumerate(t) if i != 1), [(x["cls"], x["h"]) for x in t]
    assert t[2]["b"] <= m["ih"] and t[0]["t"] >= m["rule"]                    # the units on either side are in view, one tap away
    assert len(m["cards"]) == 8 and all(c["f"] >= 11 and c["h"] >= 44 and c["w"] >= 44 and c["fit"] for c in m["cards"]), m["cards"]
    assert max(c["f"] for c in m["cards"]) == 12.5
    assert all(c["l"] >= 16 and c["r"] <= m["iw"] - 16 for c in m["cards"])
    assert m["minFont"] >= 11 and not m["split"]
    assert any("← III Unconscionability" in c for c in t[1]["chips"]), t[1]["chips"]   # a link that leaves the unit ends in a named chip
    pg.tap("#ph-ix .ix-tile.open .ix-card[data-n=adequacy]")                     # every card is tappable
    pg.wait_for_function("document.documentElement.classList.contains('detail-open') && window._currentDetailId==='adequacy'", timeout=8000)
    pg.evaluate("showTimeline()")
    pg.wait_for_timeout(700)
    assert pg.evaluate("_altoPhoneIx.state()") == {"shown": True, "open": 1, "here": "adequacy", "units": 5, "plan": True}
    pg.tap("#ph-ix .ix-tile[data-u='3'] .ix-hd")                                # a bar is one tap from its unit
    pg.wait_for_timeout(600)
    assert pg.evaluate("_altoPhoneIx.state().open") == 3
    pg.tap("#ph-ix .ix-tile.open .ix-hd")                                        # the open header folds back
    pg.wait_for_timeout(700)
    m = pg.evaluate(LOOK)
    assert m["state"]["open"] == -1 and not any("fold" in x["cls"] or "open" in x["cls"] for x in m["tiles"]) and m["cross"] >= 1
    _done(pg)


def test_reduce_motion_is_a_plain_cross_fade(site, browser):
    pg = _open(site, browser, reduced_motion="reduce")
    pg.tap("#ph-ix .ix-tile[data-u='0'] .ix-map", position={"x": 6, "y": 4})
    anims = pg.evaluate("""(() => { const b=document.querySelector('#ph-ix .ix-tile.open .ix-body'), o=b.querySelector('.ix-open');
      return [b.getAnimations().length, o.getAnimations().map(a=>a.effect.getKeyframes().map(k=>Object.keys(k).filter(x=>x==='transform'||x==='opacity').join('+')).join('|')), [...document.querySelectorAll('#ph-ix .ix-tile.fold')].length]; })()""")
    assert anims == [0, ["opacity|opacity"], 4], anims
    _done(pg)


def test_pinch_out_folds_then_shows_the_real_board_and_comes_back(site, browser):
    pg = _open(site, browser)
    pg.evaluate("_altoPhoneIx.open(0, true)")
    pg.evaluate(PINCH, [200, 400, 220, 90])                                       # on an open unit: fold
    pg.wait_for_timeout(600)
    assert pg.evaluate("_altoPhoneIx.state()")["open"] == -1 and pg.evaluate("_altoPhoneIx.state()")["shown"]
    pg.evaluate(PINCH, [200, 400, 220, 90])                                       # past the index: the real board, fitted
    pg.wait_for_timeout(600)
    b = pg.evaluate("""(() => { const w=document.getElementById('world'), r=w.getBoundingClientRect(), c=document.getElementById('canvas');
      return {shown:_altoPhoneIx.state().shown, vis:getComputedStyle(c).visibility, zoom:parseFloat(getComputedStyle(w).zoom), l:r.left, r:r.right, ix:getComputedStyle(document.getElementById('ph-ix')).display}; })()""")
    assert not b["shown"] and b["vis"] == "visible" and b["ix"] == "none" and b["zoom"] < .5 and b["l"] >= 8 and b["r"] <= 402 - 8, b
    pg.evaluate(PINCH, [200, 400, 220, 90])                                       # and out again on the fitted board: the index
    pg.wait_for_timeout(600)
    assert pg.evaluate("_altoPhoneIx.state().shown") and pg.evaluate("getComputedStyle(document.getElementById('canvas')).visibility") == "hidden"
    pg.evaluate(PINCH, [200, 300, 90, 240])                                       # fingers apart over a tile: open it
    pg.wait_for_timeout(600)
    assert pg.evaluate("_altoPhoneIx.state().open") >= 0
    _done(pg)


def test_a_search_hit_opens_its_unit_with_the_card_flagged(site, browser):
    pg = _open(site, browser)
    pg.evaluate("window._altoSearch.land('statute-of-frauds')")
    pg.wait_for_timeout(700)
    m = pg.evaluate(LOOK)
    assert m["state"]["shown"] and m["state"]["open"] == 2 and [c["t"] for c in m["cards"] if c["here"]] == ["Statute of Frauds"], m["state"]
    _done(pg)


# ── every look, both ways up ────────────────────────────────────────────────

@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
@pytest.mark.parametrize("dark", [False, True], ids=["light", "dark"])
def test_classic_retro_holo_light_and_dark(site, browser, style, dark):
    cls = {"classic": "", "retro": "alto-retro", "holo": "alto-holo"}[style]
    pg = _open(site, browser, query="view=whole" + ("" if style == "classic" else "&style=" + style),
               until=UP + (" && document.documentElement.classList.contains('%s')" % cls if cls else ""))
    was = pg.evaluate("document.documentElement.classList.contains('dark')")
    if was != dark and not (style == "retro"):
        pg.evaluate("toggleMode()")
        pg.wait_for_timeout(900)
    if style == "retro" and not dark:
        pg.context.close()
        pytest.skip("Retro is always dark (retro.py: its light / dark button is gone)")
    assert pg.evaluate("document.documentElement.classList.contains('dark')") == dark
    for step in (None, "_altoPhoneIx.open(0, true)"):
        if step:
            pg.evaluate(step)
            pg.wait_for_timeout(300)
        m = pg.evaluate(LOOK)
        assert m["state"]["shown"] and len(m["tiles"]) == 5 and m["minFont"] >= 11 and not m["split"], (style, dark, m["minFont"], m["split"])
        assert m["bg"] in ("rgba(0, 0, 0, 0)", "transparent") and m["chrome"] == [True, True]
        assert all(t["l"] >= 15.5 and t["r"] <= m["iw"] - 15.5 for t in m["tiles"])
        assert (m["radius"] == "0px") == (style == "retro")                    # squares in Retro
        if step:
            assert len(m["cards"]) == 11 and all(c["f"] >= 11 and c["h"] >= 44 and c["fit"] for c in m["cards"])
    # ink on the tile: the unit's name reads against the tile under it
    c = pg.evaluate("""(() => { const n=document.querySelector('#ph-ix .ix-name'); return [getComputedStyle(n).color, getComputedStyle(document.documentElement).getPropertyValue('--bg').trim()]; })()""")
    assert c[0] and c[1]
    _done(pg)


def test_landscape_is_two_across_under_the_header_inside_the_safe_area(site, browser):
    pg = _open(site, browser, w=874, h=292, init=INSET)
    m = pg.evaluate(LOOK)
    t = m["tiles"]
    assert abs(t[0]["t"] - t[1]["t"]) < 1 and t[1]["l"] > t[0]["r"] and t[2]["t"] > t[0]["t"] and abs(t[2]["l"] - t[0]["l"]) < 1     # two across
    assert t[0]["t"] >= m["rule"] and all(x["l"] >= 60 + 16 - .5 and x["r"] <= 874 - 60 - 16 + .5 for x in t), (m["rule"], t[0])
    assert m["minFont"] >= 11 and not m["split"] and m["chrome"] == [True, True]
    pg.evaluate("_altoPhoneIx.open(0, true)")
    pg.wait_for_timeout(300)
    m = pg.evaluate(LOOK)
    t = m["tiles"]
    assert "open" in t[0]["cls"] and t[0]["w"] > 1.8 * t[1]["w"] and all(x["l"] > t[0]["r"] and 44 <= x["h"] <= 72 for x in t[1:]), [(x["l"], x["h"]) for x in t]   # two thirds, bars down the right third
    assert t[4]["r"] <= 874 - 60 - 16 + .5 and all(c["f"] >= 11 and c["fit"] for c in m["cards"])
    _done(pg)


@pytest.mark.parametrize("w,h,init", [(402, 874, None), (874, 292, INSET)], ids=["portrait", "landscape-island"])
@pytest.mark.parametrize("style", ["classic", "holo", "retro"])
def test_the_ground_is_full_bleed_round_the_tiles_never_a_flat_band(site, browser, w, h, init, style):
    """Luke's no-colour-bars concern: with the index up, the ground runs unbroken through the runway above and below the screen box and through the bands beside
    the island's insets (the page's own ground, not a painted strip), and the tiles run on through the foot runway rather than ending in a cut edge."""
    import io
    from PIL import Image
    cls = {"classic": "", "retro": "alto-retro", "holo": "alto-holo"}[style]
    pg = _open(site, browser, page="long", query="view=whole" + ("" if style == "classic" else "&style=" + style), w=w, h=h, init=init,
               until=UP + " && document.documentElement.classList.contains('sh')" + (" && document.documentElement.classList.contains('%s')" % cls if cls else ""))
    pg.wait_for_timeout(1800)
    m = pg.evaluate("""() => ({strips:['sh-bt','sh-bb','sh-bl','sh-br'].filter(i=>document.getElementById(i)), foot:document.getElementById('ph-ix').getBoundingClientRect().bottom, ih:innerHeight,
       side:(()=>{const t=document.querySelector('#ph-ix .ix-tile').getBoundingClientRect(); return [t.left, innerWidth-[...document.querySelectorAll('#ph-ix .ix-tile')].reduce((a,e)=>Math.max(a,e.getBoundingClientRect().right),0)]})()})""")
    assert not m["strips"], m                                     # no slab strip is left standing without its slab
    assert m["foot"] >= m["ih"] + 100, m                          # the tiles run on under Safari's foot bar
    L = 60 if init else 0
    assert m["side"][0] >= L + 16 - .5 and m["side"][1] >= L + 16 - .5, m
    im = Image.open(io.BytesIO(pg.screenshot(full_page=True))).convert("RGB")
    assert im.size[1] == h + 220, im.size

    def mean(x, y, n=4):
        return im.crop((x, y, x + n, y + n)).resize((1, 1), Image.BOX).getpixel((0, 0))

    def far(a, b):
        return max(abs(a[i] - b[i]) for i in range(3))
    bad = []
    xs = [4, w - 8] if not init else [20, 66, w - 70, w - 24]          # in the 16 pt margin beside the tiles (and, on its side, in the island's bands)
    for x in xs:                                                      # the seams of the screen box: 80 px of runway above it, 140 below
        d = 14 if style == "retro" else 2                              # (Retro draws its own gold frame rule just inside the screen box: sample past it)
        for name, ya, yb in (("top", 80 - 6, 80 + d), ("foot", 80 + h - d - 4, 80 + h + 2)):
            if far(mean(x, ya), mean(x, yb)) > (12 if style != "holo" else 40):      # (Holo's ground is a ruled grid: a sample may sit on a rule)
                bad.append((name, x, mean(x, ya), mean(x, yb)))
    if init:                                                          # the band beside the island and the margin inside it are one ground
        for y in range(80 + 110, 80 + h + 100, 36):
            for xa, xb in ((24, 66), (w - 28, w - 70)):
                if far(mean(xa, y), mean(xb, y)) > (14 if style != "holo" else 40):
                    bad.append(("band", y, mean(xa, y), mean(xb, y)))
    assert not bad, (style, bad)
    _done(pg)


def test_a_long_unit_name_wraps_whole_words(site, browser):
    pg = _open(site, browser, page="long")
    m = pg.evaluate(LOOK)
    assert m["minFont"] >= 11 and not m["split"]
    r = pg.evaluate("""(() => { const n=document.querySelector('#ph-ix .ix-name'), t=n.closest('.ix-tile').getBoundingClientRect(), r=n.getBoundingClientRect(), c=getComputedStyle(n);
      return [r.left>=t.left, r.right<=t.right+.5, r.height>30, c.hyphens||c.webkitHyphens, c.overflowWrap, n.scrollWidth<=n.clientWidth+1]; })()""")
    assert r[:3] == [True, True, True] and r[3] == "manual" and r[4] == "normal" and r[5], r
    _done(pg)


# ── what does not change ────────────────────────────────────────────────────

def test_ix_0_is_the_board_as_before_and_a_desktop_never_sees_the_index(site, browser):
    pg = _open(site, browser, query="view=whole&ix=0", until="!!window._altoPhone && document.readyState==='complete'")
    assert pg.evaluate("[!!document.getElementById('ph-ix'), document.documentElement.classList.contains('ph-ix'), getComputedStyle(document.getElementById('canvas')).visibility]") == [False, False, "visible"]
    _done(pg)
    pg = _open(site, browser, query="", w=1280, h=800, phone=False, until="document.readyState==='complete'")
    assert pg.evaluate("[!!document.getElementById('ph-ix'), !!window._altoPhoneIx, !!window._altoPhone, document.documentElement.classList.contains('phone-whole')]") == [False, False, False, False]
    _done(pg)
    pg = _open(site, browser, query="view=card", until="document.readyState==='complete'")          # the one-card phone page
    assert pg.evaluate("[!!document.getElementById('ph-ix'), document.documentElement.classList.contains('mobile')]") == [False, True]
    _done(pg)
