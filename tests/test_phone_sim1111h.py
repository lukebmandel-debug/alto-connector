"""The real-iPhone FAILs of sim1111h (ORG/sim-main/sim1111h/report.md), each held by a WebKit check (headless, offline, silent; no cloud env, no account):

  (a) the first tap after FIND / MENU fade was swallowed: the faded controls rest at opacity .01, never at a state Safari's tap-to-click counts as hidden;
  (b) a page loaded on its side and turned upright kept the landscape-wide card: the card's width follows the window;
  (c) the horizontal timeline on its side: a pastel strip along the foot: the board's slab reaches the canvas's foot, so the real ground runs under it;
  (d) the FIND tab lay on the detail page's text: it joins MARK and NOTES in the bottom corners and fades with them;
  (e) a detail page on its side ignored the island's inset, and the "Back to" pill lay on the first summary line;
  (f) the Holo clef "a thin sliver on a fresh load": the clef's own box is whole; what was seen is its turn (a 10 s spin about its upright axis) caught edge-on.
WebKit has no safe areas: the island's insets are injected the way tests/test_phone_shell.py does. Safari's own tap-to-click cannot run here, so (a) stays a Simulator row too."""
import asyncio
import io
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from alto.build import phone_minimal  # noqa: E402


def test_the_faded_controls_rest_at_a_hair_not_at_nothing():
    css = phone_minimal._expand(phone_minimal.CSS)
    rule = re.search(r"html\.pmin\.pmin-idle :is\(([^)]*\)?[^{]*)\{([^}]*)\}", css)
    assert rule and "opacity:.01 !important" in rule.group(2), rule and rule.group(0)
    assert "#search-toggle" in rule.group(1), "a detail page's FIND fades with MARK and NOTES"
    assert not re.search(r"pmin-idle[^{]*\{[^}]*opacity:0[ ;!}]", css)


def _pw():
    import phone_matrix as pm
    try:
        pm._playwright()
    except ImportError:
        pytest.skip("Playwright is not installed")
    return pm


@pytest.fixture(scope="module")
def site():
    pm = _pw()
    from alto.build.builder import build_timeline, load_brief
    from alto.build import palace_assets
    man = {f: "/%s/%s" % (f, n) for f, n, _t in palace_assets.assets() if f in ("retro", "holo")}
    pages = {}
    for name, sample in (("timeline", "contracts"), ("lanes", "lanes")):
        html = build_timeline(*load_brief(json.loads((ROOT / "samples" / f"{sample}_brief.json").read_text(encoding="utf-8"))))[0]
        i = html.rfind("</body>")
        html = html[:i] + pm.LOADER % json.dumps(man) + html[i:]
        j = html.find('<script id="alto-shell-js">')
        pages[name] = html[:j] + pm.SEED + html[j:] if j >= 0 else html
    s = pm.serve(pages, {}, {})
    yield pm, f"http://127.0.0.1:{s.server_address[1]}"
    s.shutdown()


INSET = ("document.addEventListener('DOMContentLoaded',()=>{const s=document.createElement('style');"
         "s.textContent='#sh-probe{padding-left:%dpx!important;padding-right:%dpx!important}';document.head.appendChild(s);});")
R = "const R=e=>{if(!e)return null;const r=e.getBoundingClientRect();return [r.left,r.top,r.right,r.bottom].map(v=>Math.round(v*10)/10)},$=i=>document.getElementById(i);"


def _run(site, fn, url, w, h, inset=0, wait=1500):
    pm, base = site

    async def go():
        async with pm._playwright().async_playwright() as p:
            b = await p.webkit.launch()
            ctx = await b.new_context(viewport={"width": w, "height": h}, is_mobile=True, has_touch=True, user_agent=pm.UA)
            if inset:
                await ctx.add_init_script(INSET % (inset, inset))
            pg = await ctx.new_page()
            await pg.goto(base + url, wait_until="load", timeout=45000)
            await pg.wait_for_timeout(wait)
            try:
                return await fn(pg)
            finally:
                await ctx.close()
                await b.close()
    try:
        return asyncio.run(go())
    except Exception as e:
        if "Executable doesn't exist" in str(e):
            pytest.skip(f"no WebKit: {e}")
        raise


# ── (a) ──
HID = """ids => ids.map(i => { const e = document.getElementById(i); if(!e) return null; const c = getComputedStyle(e), r = e.getBoundingClientRect();
  return {id:i, shown:c.display !== 'none' && r.width > 2, op:+c.opacity, vis:c.visibility}; }).filter(x => x && x.shown)"""


def test_a_tap_after_the_fade_wakes_the_controls_and_acts(site):
    async def fn(pg):
        await pg.evaluate("window.__clicks=0; document.addEventListener('click',()=>{window.__clicks++},true); window._altoPhoneMinApi.rest()")
        await pg.wait_for_timeout(900)
        idle = await pg.evaluate("document.documentElement.classList.contains('pmin-idle')")
        tl = await pg.evaluate(HID, ["pmin-find", "hamburger-tab"])
        await pg.touchscreen.tap(200, 150)          # the page, away from every control: one tap
        await pg.wait_for_timeout(250)
        woke = await pg.evaluate("[!document.documentElement.classList.contains('pmin-idle'), window.__clicks]")
        await pg.evaluate("showDetail('node', NODE_ORDER[1])")
        await pg.wait_for_timeout(400)
        await pg.evaluate("window._altoPhoneMinApi.rest()")
        await pg.wait_for_timeout(900)
        det = await pg.evaluate(HID, ["search-toggle", "hl-mode-btn", "notes-toggle"])
        return idle, tl, woke, det
    idle, tl, woke, det = _run(site, fn, "/timeline.html?view=card", 402, 874)
    assert idle and len(tl) == 2 and len(det) == 3, (idle, tl, det)
    for c in tl + det:
        assert 0 < c["op"] <= .02 and c["vis"] == "visible", f"{c['id']} rests unseen but not hidden (Safari counts opacity 0 / visibility:hidden as hidden, and eats the tap that shows it): {c}"
    assert woke == [True, 1], f"one tap woke the controls and was a click: {woke}"


# ── (b) ──
CARD = "()=>{" + R + "return {card:R(document.querySelector('.node.mobile-featured .node-card')), vw:innerWidth, sw:document.documentElement.scrollWidth}}"


def test_a_page_loaded_on_its_side_and_turned_upright_refits_its_card(site):
    async def turned(pg):
        await pg.set_viewport_size({"width": 402, "height": 874})
        await pg.wait_for_timeout(1200)
        return await pg.evaluate(CARD)

    async def fresh(pg):
        return await pg.evaluate(CARD)
    a = _run(site, turned, "/timeline.html?view=card", 874, 292)
    b = _run(site, fresh, "/timeline.html?view=card", 402, 874)
    assert a["vw"] == 402 and a["sw"] == 402
    assert a["card"][0] >= 8 - .5 and a["card"][2] <= 402 - 8 + .5, f"the card is inside the screen: {a['card']}"
    assert max(abs(x - y) for x, y in zip(a["card"], b["card"])) <= 1, f"turned {a['card']} is the card a portrait load draws {b['card']}"


# ── (c) ──
@pytest.mark.parametrize("h", [402, 338, 292])
def test_lanes_on_its_side_the_ground_runs_to_the_foot(site, h):
    async def fn(pg):
        await pg.wait_for_timeout(1500)
        d = await pg.evaluate("()=>{" + R + "return {slab:R($('glass-slab')), canvas:R($('canvas')), bb:!!$('sh-bb'), bl:R($('sh-bl')), br:R($('sh-br')), cls:document.documentElement.className}}")
        d["png"] = await pg.screenshot()
        return d
    d = _run(site, fn, "/lanes.html", 874, h, 62)
    assert "alto-lanes" in d["cls"] and "sh-landscape" in d["cls"]
    assert d["slab"][3] >= d["canvas"][3] - .5, f"the slab ends at the canvas's foot: slab {d['slab']}, canvas {d['canvas']}"
    assert d["bb"], "the runway under the foot carries the slab on (it does only where the slab reaches the foot)"
    # (sim1112a R4: there are no bands beside the board any more: the slab itself runs from edge to edge under the island's insets, tests/test_phone_sim1112a.py)
    assert not d["bl"] and not d["br"] and d["slab"][0] <= .5 and d["slab"][2] >= 873.5, f"the slab runs under the island's insets, with no band beside it: {d['slab']} {d['bl']} {d['br']}"
    from PIL import Image
    im = Image.open(io.BytesIO(d["png"])).convert("RGB")
    for x in (30, 250, 620, 845):                  # the island's bands and the board: the foot's last rows are the ground 40 px above them, not another colour
        a, b = im.getpixel((x, h - 3)), im.getpixel((x, h - 42))
        assert max(abs(p - q) for p, q in zip(a, b)) <= 14, f"x={x}: the foot {a} is not the ground above it {b}"
    for y in (60, h // 2, h - 20):                 # no seam between the board and the bands beside it
        for xa, xb in ((56, 68), (806, 818)):
            a, b = im.getpixel((xa, y)), im.getpixel((xb, y))
            assert max(abs(p - q) for p, q in zip(a, b)) <= 6, f"y={y}: the band {a} and the board {b} differ at x={xa}/{xb}"


# ── (d), (e) ──
DET = "()=>{" + R + """const dp=$('detail-page'), c=getComputedStyle(dp), g=document.createRange(), p=dp.querySelector('.detail-section p,.detail-section .ol-row')||dp.querySelector('.detail-section');
 g.selectNodeContents(p); const l=g.getClientRects()[0], lines=[...g.getClientRects()].map(q=>[q.left,q.top,q.right,q.bottom].map(Math.round));
 return {vw:innerWidth, vh:innerHeight, sw:document.documentElement.scrollWidth, sym:R(dp.querySelector('.detail-symbol')), name:R(dp.querySelector('.detail-name')), line:l&&[l.left,l.top,l.right,l.bottom].map(Math.round), lines:lines,
  find:R($('search-toggle')), mark:R($('hl-mode-btn')), notes:R($('notes-toggle')), pill:R($('alto-back-prev')), pillOn:!$('alto-back-prev').hasAttribute('hidden'), cls:document.documentElement.className}}"""


def _detail(site, style, w, h, inset):
    async def fn(pg):
        await pg.evaluate("showDetail('node', NODE_ORDER[1])")
        await pg.wait_for_timeout(500)
        # a link inside the page: the page it opens carries the "Back to" pill
        await pg.evaluate("(()=>{const a=document.querySelector('#detail-content [onclick*=showDetail]'); a.dispatchEvent(new Event('touchstart',{bubbles:true})); a.click();})()")
        await pg.wait_for_timeout(500)
        await pg.evaluate("window._altoPhoneMinApi.wake()")
        await pg.wait_for_timeout(900)
        return await pg.evaluate(DET)
    return _run(site, fn, "/timeline.html?view=card" + ("" if style == "classic" else f"&style={style}"), w, h, inset, wait=2600 if style != "classic" else 1300)


def _hit(a, b, pad=0):
    return bool(a and b) and a[0] < b[2] + pad and b[0] < a[2] + pad and a[1] < b[3] + pad and b[1] < a[3] + pad


@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
def test_detail_page_find_sits_in_the_corner_with_mark_and_notes(site, style):
    d = _detail(site, style, 402, 874, 0)
    assert d["pillOn"] and d["sw"] == d["vw"]
    f, n, m, p = d["find"], d["notes"], d["mark"], d["pill"]
    assert abs(f[0] - 14) <= 1 and abs((d["vh"] - f[3]) - 14) <= 1, f"FIND is 14 pt in from the bottom-left corner: {f}"
    assert abs((d["vw"] - n[2]) - 14) <= 1 and abs(f[3] - n[3]) <= 1, f"NOTES is its mirror: {n}"
    assert f[1] > d["vh"] * .85, "not a third of the way up the text's left edge"
    assert not _hit(p, f, 8) and not _hit(p, n, 8) and not _hit(p, m, 4), f"the pill is clear of the three tiles: pill {p}, FIND {f}, NOTES {n}, MARK {m}"


@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
@pytest.mark.parametrize("h", [292, 402])
def test_detail_page_on_its_side_keeps_clear_of_the_island_and_the_pill_off_the_text(site, style, h):
    d = _detail(site, style, 874, h, 62)
    assert "sh-landscape" in d["cls"] and d["pillOn"] and d["sw"] == d["vw"]
    assert d["sym"][0] >= 62 + 16 and d["name"][0] >= 62 + 16, f"the symbol and the title start clear of the island: {d['sym']} {d['name']}"
    assert all(q[0] >= 62 + 16 and q[2] <= 874 - 62 - 16 for q in d["lines"]), f"every line of the first section is between the insets: {d['lines'][:3]}"
    p = d["pill"]
    assert p[2] <= 874 - 62 - 16 + .5 and p[0] >= 874 * .4, f"the pill is at the right, inside the inset: {p}"
    assert not any(_hit(p, q, 4) for q in d["lines"]), f"the pill is off the summary: pill {p}, first line {d['line']}"
    assert not _hit(p, d["name"], 2) and not _hit(p, d["sym"], 2), f"and off the title and the symbol: {p} {d['name']} {d['sym']}"
    assert not _hit(p, d["mark"], 2) and not _hit(p, d["notes"], 2) and not _hit(p, d["find"], 2)
    assert d["find"][0] >= 62 + 14 - 1 and d["notes"][2] <= 874 - 62 - 14 + 1, "the corner tiles are inside the insets"


# ── (e) scrolled: Art's look at rel-223 (2026-11-12): the pill was fixed to the screen, so once the page was scrolled it stayed where it was, over the text ──
PILL = "()=>{" + R + """const b=$('alto-back-prev'), dp=$('detail-page'), c=getComputedStyle(b), r=b.getBoundingClientRect(), g=document.createRange(), over=[];
 dp.querySelectorAll('.detail-name,.detail-section p,.detail-section .ol-row,.detail-section li,.detail-section-title').forEach(e=>{ g.selectNodeContents(e); for(const q of g.getClientRects())
   if(q.width>2 && q.left<r.right && r.left<q.right && q.top<r.bottom && r.top<q.bottom && r.bottom>0 && r.top<innerHeight) over.push(Math.round(q.top)); });
 const top=document.elementFromPoint(Math.min(innerWidth-2,(r.left+r.right)/2), Math.max(1,Math.min(innerHeight-2,(r.top+r.bottom)/2)));
 return {pill:R(b), name:R(dp.querySelector('.detail-name')), dp:R(dp), parent:b.parentNode.id||b.parentNode.tagName, pos:c.position, shown:!b.hasAttribute('hidden') && c.display!=='none' && c.visibility!=='hidden' && +c.opacity>.9,
  over:over.length, hit:!!(top && top.closest && top.closest('#alto-back-prev')), st:dp.scrollTop, max:dp.scrollHeight-dp.clientHeight, text:b.textContent.trim(), n:document.querySelectorAll('#alto-back-prev').length}}"""


@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
def test_the_pill_on_its_side_is_in_the_page_and_scrolls_away_with_the_title(site, style):
    async def fn(pg):
        await pg.evaluate("showDetail('node', NODE_ORDER[1])")
        await pg.wait_for_timeout(500)
        await pg.evaluate("(()=>{const a=document.querySelector('#detail-content [onclick*=showDetail]'); a.dispatchEvent(new Event('touchstart',{bubbles:true})); a.click();})()")
        await pg.wait_for_timeout(500)
        out = {}
        for key, y in (("top", 0), ("s40", 40), ("s150", 150), ("s300", 300), ("back", 0)):
            await pg.evaluate("y=>{ document.getElementById('detail-page').scrollTop=y; }", y)
            await pg.evaluate("window._altoPhoneMinApi.wake()")
            await pg.wait_for_timeout(350)
            out[key] = await pg.evaluate(PILL)
        # a finger drags the page aside and lets go: the page coming in is drawn without this page's pill (it would vanish on landing), and the pill is back as it was
        out["drag"] = await pg.evaluate("""async()=>{ const raf=()=>new Promise(r=>requestAnimationFrame(r)), tg=document.querySelector('#detail-page .detail-section')||document.getElementById('detail-page'), y=200;
          const ev=(type,cx)=>{ const a={identifier:1,target:tg,clientX:cx,clientY:y,pageX:cx,pageY:y,screenX:cx,screenY:y}, e=new Event(type,{bubbles:true,cancelable:true});
            Object.defineProperty(e,'touches',{value:type==='touchend'?[]:[a]}); Object.defineProperty(e,'targetTouches',{value:type==='touchend'?[]:[a]}); Object.defineProperty(e,'changedTouches',{value:[a]}); tg.dispatchEvent(e); };
          ev('touchstart',540); await raf(); for(let i=1;i<=8;i++){ ev('touchmove',540-30*i); await raf(); }
          const r=[document.querySelectorAll('.det-peek').length, document.querySelectorAll('.det-peek #alto-back-prev').length, document.querySelectorAll('#detail-page #alto-back-prev').length];
          for(let i=7;i>=1;i--){ ev('touchmove',540-30*i); await raf(); await raf(); } ev('touchend',540-20); await new Promise(q=>setTimeout(q,500));
          return r.concat([document.querySelectorAll('.det-peek').length, document.querySelectorAll('#alto-back-prev').length]); }""")
        await pg.wait_for_timeout(4200)                       # at rest (the corner tiles have faded): the pill is still not hidden
        out["rest"] = await pg.evaluate(PILL)
        # the pill still works: it goes back to the page it names
        await pg.evaluate("document.getElementById('alto-back-prev').click()")
        await pg.wait_for_timeout(400)
        out["went"] = await pg.evaluate("[NODE_ORDER.indexOf(window._currentDetailId), document.getElementById('alto-back-prev').hasAttribute('hidden')]")
        # upright again: the floating pill at the foot, in <body> (another hop first, so there is a pill to show)
        await pg.evaluate("(()=>{const a=document.querySelector('#detail-content [onclick*=showDetail]'); a.dispatchEvent(new Event('touchstart',{bubbles:true})); a.click();})()")
        await pg.set_viewport_size({"width": 402, "height": 874})
        await pg.wait_for_timeout(900)
        out["upright"] = await pg.evaluate(PILL)
        return out
    d = _run(site, fn, "/timeline.html?view=card" + ("" if style == "classic" else f"&style={style}"), 874, 292, 62, wait=2600 if style != "classic" else 1300)
    t = d["top"]
    print("PILL", style, json.dumps({k: [d[k]["pill"][1], d[k]["name"][1], d[k]["over"]] for k in ("top", "s40", "s150", "s300", "back", "rest")}))
    assert t["parent"] == "detail-page" and t["pos"] == "absolute" and t["n"] == 1, f"the pill is inside the page, not fixed to the screen: {t['parent']} {t['pos']}"
    assert t["shown"] and t["hit"] and t["over"] == 0 and t["text"].startswith("←Back to"), f"at the top it shows, in the clear: {t}"
    assert t["pill"][1] >= t["dp"][1] and t["pill"][3] <= t["name"][1], f"in the page's top margin, above the title: pill {t['pill']}, page {t['dp']}, title {t['name']}"
    assert t["pill"][2] <= 874 - 62 - 16 + .5 and t["pill"][0] >= 874 * .4, f"at the right, inside the inset: {t['pill']}"
    assert t["max"] >= 300, "the page scrolls far enough to tell"
    for k, y in (("s40", 40), ("s150", 150), ("s300", 300)):
        q = d[k]
        assert q["st"] == y and q["pill"][1] == t["pill"][1] - y and q["name"][1] == t["name"][1] - y, f"scrolled {y}: the pill moved with the title: pill {q['pill']}, title {q['name']} (top: {t['pill']}, {t['name']})"
        assert q["over"] == 0, f"scrolled {y}: the pill lies on {q['over']} lines of text"
        assert q["shown"], f"scrolled {y}: the pill is not hidden, it has scrolled out with the title"
    assert d["s150"]["pill"][3] <= d["s150"]["dp"][1] and not d["s150"]["hit"], f"scrolled 150 it is off the page's top: {d['s150']['pill']}"
    assert d["back"]["pill"] == t["pill"] and d["back"]["hit"] and d["rest"]["pill"] == t["pill"] and d["rest"]["shown"], "scrolled back it is where it was, and it stays at rest"
    assert d["drag"] == [1, 0, 1, 0, 1], f"mid-drag: one page coming in, no pill in it, the pill still in this page; let go: no preview left, one pill: {d['drag']}"
    assert d["went"] == [1, True], f"a tap goes back to the page it names: {d['went']}"
    u = d["upright"]
    assert u["parent"] == "BODY" and u["shown"] and u["pill"][3] > 874 * .85 and u["n"] == 1, f"upright it is the floating pill at the foot: {u}"


# ── (f) ──
def test_holo_clef_is_whole_on_a_fresh_load_and_its_swing_never_goes_edge_on(site):
    """In Holographic the corner clef moves about its upright axis on a 10 s period (holo.py's ho-logo, and holo_trace.py's tube that stands in for it). It used to turn right
    round: 2.5 s and 7.5 s in it was edge-on, a few px wide, the "thin sliver" a still frame of sim1111h caught, which read as a broken logo. It swings now, 55deg to each
    side of facing front: a fresh load starts it facing front, whole, and no moment of the 10 s shows it under 40% of that width. Reduce Motion holds it still (test_holo)."""
    async def fn(pg):
        return await pg.evaluate("""()=>{ const m=document.querySelector('#nav svg.brand-mark'), tb=document.querySelector('#nav .ho-tube'), sp=tb&&tb.querySelector('.sp'), el=sp||m, c=getComputedStyle(el), mr=m.getBoundingClientRect();
          const drawn=()=>{ if(!sp) return m.getBoundingClientRect().width; let a=1e9,b=-1e9; sp.querySelectorAll('path,circle').forEach(p=>{ const r=p.getBoundingClientRect(); if(r.width||r.height){ a=Math.min(a,r.left); b=Math.max(b,r.right); } }); return b-a; };
          const an=el.getAnimations(); an.forEach(a=>{ a.pause(); a.currentTime=0; }); const front=drawn(); const ws=[]; for(let t=0;t<10000;t+=125){ an.forEach(a=>{ a.currentTime=t; }); ws.push(drawn()); }
          return {cls:document.documentElement.className, box:[mr.width, mr.height], tube:tb?[tb.getBoundingClientRect().width, tb.getBoundingClientRect().height]:null, front:front, ws:ws, name:c.animationName, dur:c.animationDuration, ease:c.animationTimingFunction}; }""")
    d = _run(site, fn, "/timeline.html?view=card&style=holo", 402, 874, wait=2800)
    assert "alto-holo" in d["cls"]
    assert d["box"][0] >= 20 and d["box"][0] / d["box"][1] == pytest.approx(78 / 98, abs=.06), f"the clef's own box is whole (its viewBox is 78 x 98): {d['box']}"
    if d["tube"]:
        assert d["tube"] == pytest.approx(d["box"], abs=1), "the tube stands exactly where the clef is"
    assert d["front"] >= d["box"][0] * .75, f"facing front (a fresh load) it is drawn whole: {d['front']} of {d['box'][0]} px"
    assert d["name"] in ("ho-tube", "ho-logo-p") and d["dur"] == "10s" and d["ease"] == "ease-in-out", "the look's own 10 s motion, eased"
    # Art's call (rel-223 look), the Board's decision: a swing of about 55deg to each side, not a full turn. It was edge-on at 2.5 s and 7.5 s, about 3 px wide.
    lo = min(d["ws"])
    print("CLEF", json.dumps({"front": round(d["front"], 1), "min": round(lo, 1), "ratio": round(lo / d["front"], 3), "at_2.5s": round(d["ws"][20], 1), "at_7.5s": round(d["ws"][60], 1)}))
    assert lo >= d["front"] * .4, f"the clef is never edge-on: at its narrowest {lo:.1f} of {d['front']:.1f} px"
    assert lo <= d["front"] * .8, "and it does swing"
