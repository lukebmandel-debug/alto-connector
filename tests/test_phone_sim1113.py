"""The iPhone Simulator findings of sim1113 on 1.9.225 (ORG/sim-main/sim1113-225/), each held by a WebKit check (headless, offline, silent; no cloud env, no account):

  (1) Retro's homepage turned upright -> on its side -> upright: the list stopped hard at 776 of 874 pt, a flat black band behind Safari's toolbar, the gold frame's
      foot gone. Retro's #sk-frame (now only a rule under the title) was still a fixed layer over the whole screen, z-index 299; on its side the homepage has no
      runway, so it was fixed to the screen's foot, the one such layer over the content (Holo's and Classic's grounds lie under it), and Safari kept the flat tint
      it keys on that through the turn. The frame is as tall as its rule now. WebKit has no toolbar: the check is that no fixed layer reaches the foot over the
      content at any layout of the turn (the viewport resized 402x874 -> 874x402 -> 402x874), and the list and its frame run to the foot.
  (2) The New-project picker on a phone: tiles 86 / 83 / 116 / 85 pt; every tile is the tallest one's height.
  (3) Holo's focused search field: a teal ring with a gold line inside it (Retro's brighter focus gold, never re-inked); one teal rim.
  (4) The long-unit card: the kicker (the unit's title, inside the card on a phone) ran into the card number "1.a"; it stops 10px short and wraps."""
import asyncio
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from alto.build import holo, retro  # noqa: E402


def test_holo_reinks_retros_focus_gold():
    assert "#f6d98a" in retro.HOME_CSS + retro.CHROME_CSS + retro.BOARD_CSS + retro.FORMAT_CSS + retro.COMMON_CSS
    assert "#f6d98a" not in holo.css().lower()


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
    from alto.build.pages import build_home
    from alto.build import palace_assets
    man = {f: "/%s/%s" % (f, n) for f, n, _t in palace_assets.assets() if f in ("retro", "holo")}
    pages = {}

    def put(name, html):
        i = html.rfind("</body>")
        html = html[:i] + pm.LOADER % json.dumps(man) + html[i:]
        j = html.find('<script id="alto-shell-js">')
        pages[name] = html[:j] + pm.SEED + html[j:] if j >= 0 else html
    put("home", build_home([{"name": "Law school %d" % p, "pid": "p%d" % p, "courses": [
        {"title": "Civil Procedure %d.%d" % (p, c), "href": "outline.html", "sub": "%d units" % (c + 3), "courseId": "c%d%d" % (p, c), "units": []} for c in range(8)]} for p in range(4)]))
    d = json.loads((ROOT / "samples" / "outline_brief.json").read_text(encoding="utf-8"))
    for a, t in zip(d["brief"]["acts"], pm.LONG):
        a["label"] = t
        a["short"] = t.title()
    put("outline-long", build_timeline(*load_brief(d))[0])
    s = pm.serve(pages, {}, {})
    yield pm, f"http://127.0.0.1:{s.server_address[1]}"
    s.shutdown()


def _run(site, url, w, h, fn, wait=3500):
    pm, base = site

    async def go():
        async with pm._playwright().async_playwright() as p:
            b = await p.webkit.launch()
            ctx = await b.new_context(viewport={"width": w, "height": h}, is_mobile=True, has_touch=True, user_agent=pm.UA)
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


# ── (1) Retro's homepage turned upright, on its side, upright ──
# every fixed / sticky layer that reaches the screen's foot and is drawn over the page's content (Safari's toolbar tint keys on it, ignoring pointer-events);
# a ground layer under the content (z-index < 0) is not one
EDGE = """()=>{const y=innerHeight-1,o=[];for(const e of document.querySelectorAll('body *')){const c=getComputedStyle(e);if(!/fixed|sticky/.test(c.position)||c.display==='none'||c.visibility==='hidden')continue;
 const r=e.getBoundingClientRect();if(r.width<1||r.height<1||r.top>y||r.bottom<y+1||r.left>innerWidth/2||r.right<innerWidth/2)continue;const z=parseInt(c.zIndex,10);if(!isNaN(z)&&z<0)continue;o.push(e.id||String(e.className));}
 const sl=document.querySelector('.project-slab').getBoundingClientRect(),w=document.getElementById('projects-wrap'),hit=document.elementFromPoint(innerWidth/2,y);
 return {over:o,w:innerWidth,cls:document.documentElement.className,slabFoot:sl.bottom,list:!!(hit&&w.contains(hit)),hit:hit&&(hit.id||String(hit.className))}}"""


@pytest.mark.parametrize("style", ["retro", "holo", "classic"])
def test_nothing_fixed_lies_over_the_list_at_the_screens_foot_through_a_turn(site, style):
    async def fn(pg):
        out = [await pg.evaluate(EDGE)]
        for w, h in ((874, 402), (402, 874)):
            await pg.set_viewport_size({"width": w, "height": h})
            await pg.wait_for_timeout(2000)
            out.append(await pg.evaluate(EDGE))
        return out
    seq = _run(site, "/home?style=" + style, 402, 874, fn)
    for r, way in zip(seq, ("upright", "on its side", "upright again")):
        assert r["over"] == [], ("a fixed layer over the content at the screen's foot", style, way, r)
    up = seq[-1]
    assert " rw" in " " + up["cls"] and up["list"], up                      # the list runs to the foot of the screen
    assert up["slabFoot"] > 874, up                                         # the project's gold frame runs on past it, under Safari's toolbar


# ── (2) equal picker tiles ──
PICK = """async()=>{document.getElementById('nt-scrim').classList.add('open');await new Promise(r=>setTimeout(r,400));
 return [...document.querySelectorAll('#nt-modal .nt-kinds:not(.nt-sck) .nt-kind')].filter(k=>getComputedStyle(k).display!=='none').map(k=>{const r=k.getBoundingClientRect();return [k.dataset.kind,r.top,r.height]})}"""


@pytest.mark.parametrize("size", [(402, 874), (375, 812), (874, 402)], ids=["p402", "p375", "l874"])
def test_the_picker_tiles_are_all_the_tallest_ones_height(site, size):
    t = _run(site, "/home", size[0], size[1], lambda pg: pg.evaluate(PICK), wait=1500)
    assert len(t) == 4, t
    hs = [round(q[2], 1) for q in t]
    assert max(hs) - min(hs) <= 0.5, t
    if size[0] <= 640:
        assert len({round(q[1]) for q in t}) == 4, t                   # a phone: one tile a row
        tops = sorted(q[1] for q in t)
        assert all(b - a >= hs[0] for a, b in zip(tops, tops[1:])), t  # rows never overlap


# ── (3) one rim on Holo's focused search field ──
RIM = """async()=>{document.getElementById('search-glyph').click();await new Promise(r=>setTimeout(r,500));document.getElementById('search-input').focus();
 await new Promise(r=>setTimeout(r,400));const c=getComputedStyle(document.getElementById('search-btn'));
 return {focus:document.activeElement.id,bd:[c.borderTopWidth,c.borderTopColor,c.borderLeftColor],bs:c.boxShadow,ac:getComputedStyle(document.documentElement).getPropertyValue('--ho-ac').trim()}}"""


def _rgb(s):
    import re
    return tuple(round(float(v)) for v in re.findall(r"[\d.]+", s)[:3])


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_holo_focused_search_is_one_teal_rim(site, theme):
    async def fn(pg):
        await pg.evaluate("d=>document.documentElement.classList.toggle('dark', d)", theme == "dark")
        await pg.wait_for_timeout(300)
        return await pg.evaluate(RIM)
    r = _run(site, "/home?style=holo", 402, 874, fn)
    assert r["focus"] == "search-input", r
    ring = r["bs"].split(" 0px 0px 0px 1px")[0]
    assert _rgb(r["bd"][1]) == _rgb(ring) == _rgb(r["bd"][2]), ("the field's border and its ring are one colour", r)
    assert _rgb(r["bd"][1]) != (246, 217, 138), r


def test_retro_focused_search_keeps_one_gold_rim(site):
    r = _run(site, "/home?style=retro", 402, 874, lambda pg: pg.evaluate(RIM))
    assert _rgb(r["bd"][1]) == (246, 217, 138) == _rgb(r["bs"]), r


# ── (4) the kicker stops short of the card number ──
KICK = """async()=>{featureNode('definiteness');await new Promise(r=>setTimeout(r,900));
 const n=document.querySelector('.node.mobile-featured'),c=n&&n.querySelector('.node-card'),u=n&&n.querySelector('.node-unit'),o=c&&c.querySelector('.node-order');
 if(!u||!o)return null;const O=o.getBoundingClientRect(),r=document.createRange();r.selectNodeContents(u);
 const rs=[...r.getClientRects()].filter(q=>q.width>0&&q.top<O.bottom&&q.bottom>O.top);
 return {num:o.textContent.trim(),inCard:u.classList.contains('in-card'),lines:rs.length,right:Math.max(0,...rs.map(q=>q.right)),numLeft:O.left,unit:u.getBoundingClientRect().height}}"""


@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
@pytest.mark.parametrize("size", [(402, 874), (375, 812), (874, 402)], ids=["p402", "p375", "l874"])
def test_the_kicker_stops_short_of_the_card_number(site, style, size):
    r = _run(site, "/outline-long?view=card&style=" + style, size[0], size[1], lambda pg: pg.evaluate(KICK), wait=4500)
    assert r and r["num"] == "1.a", r
    if r["inCard"]:
        assert r["lines"] >= 1 and r["right"] <= r["numLeft"] - 10 + 0.5, ("the kicker runs into the number", style, r)
