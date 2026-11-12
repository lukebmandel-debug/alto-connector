"""sim1112b (the real-iPhone check of rel-223 e3a97017): the FAILs left were all on a turn.

  S1  Classic's homepage opened upright and turned on its side: Safari's toolbar zone stayed flat peach. html.rw (the runway class) was set once, in <head>, from the
      phone layout's media query and never taken off, so on its side the page was still pinned 80 px down a runway it no longer had and the shell took it for a
      runway page (homeTop() declines those): the root stayed Classic's peach, and its kept colour for that way up was deleted. A new tab then depended on the
      <head> script reading the window's box, which a new tab does not have yet. Now the class follows the media query, the root has the colour from the stylesheet
      itself (a media query, there at the first layout and at the layout of a turn), the script sets it on orientationchange / the first resize, and a kept colour is
      only used if it is a measured, recent one.
  S6  the horizontal timeline turned upright: the first card cut off at the right; turned back: 1.5x the size of a fresh open.
  S4  the detail page scrolled on its side: FIND over the first letter of a heading.

WebKit, the phone's own boxes (402 x 874; 874 x 292 with Safari's bars up), a turn as the phone sends it: resizes at +78 ms and +418 ms.
"""
import asyncio
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

from test_phone_sim1112a import site, _img, _d, _rgb, R  # noqa: E402,F401  (the fixture and the helpers)

P, L, MID, ISL = (402, 874), (874, 292), (874, 402), 62
# the island's insets only on its side, as on the phone
INSET = ("document.addEventListener('DOMContentLoaded',()=>{const s=document.createElement('style');"
         "s.textContent='@media (orientation:landscape){#sh-probe{padding-left:%dpx!important;padding-right:%dpx!important}}';document.head.appendChild(s);});" % (ISL, ISL))
# the root's colour as the page's own DOMContentLoaded handlers find it: what <head> alone set, before anything was measured
DCL = ("document.addEventListener('DOMContentLoaded',function(){window.__dcl=getComputedStyle(document.documentElement).backgroundColor;"
       "window.__dclm=document.querySelector('meta[name=theme-color]').content;},{once:true});")
PEACH = (255, 201, 138)


async def _turn(pg, to):
    """The phone's turn: to its side it resizes at +78 ms (the new width, the old bars) and +418 ms (Safari's bars up); upright in one step."""
    if to == L:
        await pg.set_viewport_size({"width": MID[0], "height": MID[1]})
        await pg.wait_for_timeout(78)
        first = await pg.evaluate("getComputedStyle(document.documentElement).backgroundColor")
        await pg.wait_for_timeout(262)
        await pg.set_viewport_size({"width": L[0], "height": L[1]})
        return first
    await pg.set_viewport_size({"width": to[0], "height": to[1]})


def _session(site, fn, size=P, init=""):
    pm, base = site

    async def go():
        async with pm._playwright().async_playwright() as p:
            b = await p.webkit.launch()
            ctx = await b.new_context(viewport={"width": size[0], "height": size[1]}, is_mobile=True, has_touch=True, user_agent=pm.UA)
            await ctx.add_init_script(INSET + DCL + init)

            async def page(url, sz=None, wait=2200):
                pg = await ctx.new_page()
                if sz:
                    await pg.set_viewport_size({"width": sz[0], "height": sz[1]})
                await pg.goto(base + url, wait_until="load", timeout=45000)
                await pg.wait_for_timeout(wait)
                return pg
            try:
                return await fn(page)
            finally:
                await ctx.close()
                await b.close()
    try:
        return asyncio.run(go())
    except Exception as e:
        if "Executable doesn't exist" in str(e):
            pytest.skip(f"no WebKit: {e}")
        raise


# ── S1: Classic's homepage, upright then on its side ──
HOME = "()=>{" + R + """const de=document.documentElement, cs=e=>getComputedStyle(e);
 return {cls:de.className, root:cs(de).backgroundColor, dcl:window.__dcl, dclm:window.__dclm, theme:document.querySelector('meta[name=theme-color]').content, y:pageYOffset, store:localStorage.getItem('alto-sh-root'),
  tab:R($('title-text')), bar:R($('title-bar')), list:R(document.querySelector('#projects-wrap .project, #projects-wrap > *')), barPos:cs($('title-bar')).position, vw:innerWidth, vh:innerHeight}}"""


def _home_top_ok(d, png, what):
    root = _rgb(d["root"])
    glass = _img(png).getpixel((int(d["tab"][0]) - 40, 3))
    assert _d(root, PEACH) > 30, f"{what}: the root is still Classic's peach: {d['root']}"
    assert _d(root, glass) <= 12, f"{what}: the root {root} is not the page's colour at the top {glass}"
    assert d["theme"].lower() == "#%02x%02x%02x" % root, f"{what}: theme-color {d['theme']} is not the root's colour {root}"
    return root


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_classic_home_turned_on_its_side_then_a_new_tab_on_its_side(site, theme):
    async def fn(page):
        pg = await page("/home.html")
        up = await pg.evaluate(HOME)
        first = await _turn(pg, L)
        await pg.wait_for_timeout(1300)
        side = await pg.evaluate(HOME)
        png = await pg.screenshot()
        new = await page("/home.html", L)                          # a new tab, already on its side
        nd = await new.evaluate(HOME)
        npng = await new.screenshot()
        fresh_list = nd["list"]
        return up, first, side, png, nd, npng, fresh_list
    up, first, side, png, nd, npng, fresh_list = _session(site, fn, init="try{localStorage.setItem('alto-theme-v1',%r)}catch(e){}" % theme)
    assert "rw" in up["cls"].split() and up["y"] == 80, up
    # the turn: by the first resize (78 ms in, long before the measured pass) the root is no longer peach
    assert _d(_rgb(first), _rgb(up["root"])) > 30, f"78 ms into the turn the root is still the upright page's {up['root']}: {first}"
    assert "rw" not in side["cls"].split() and "sh-landscape" in side["cls"], f"on its side the page has no runway: {side['cls']}"
    root = _home_top_ok(side, png, "turned")
    assert _d(_rgb(first), root) <= 12, f"the colour set as the screen turns {first} is the one measured after it {root}"
    assert side["y"] == 0, f"the page is no longer pinned 80 px down a runway it does not have: {side['y']}"
    kept = json.loads(side["store"] or "{}")
    k = [v for n, v in kept.items() if n.endswith("|L")]
    assert k and k[0][0] == "#%02x%02x%02x" % root, f"the colour kept for this way up is the measured one: {kept}"
    assert not any(v[0].lower() in ("#ffc98a", "#ffc59e") for v in kept.values()), kept
    # a new tab on its side: right from <head>, and the same page as the turned one
    nroot = _home_top_ok(nd, npng, "new tab")
    assert _d(_rgb(nd["dcl"]), nroot) <= 2, f"the new tab's root at its first layout {nd['dcl']} is its measured one {nroot}"
    assert nd["dclm"].lower() == "#%02x%02x%02x" % _rgb(nd["dcl"]), f"and theme-color says the same from <head> on: {nd['dclm']}"
    assert max(abs(a - b) for a, b in zip(side["list"], fresh_list)) <= 1, f"turned, the list sits where a page opened on its side has it: {side['list']} vs {fresh_list}"
    print("S1", theme, "first", first, "turned", side["root"], "new tab at head", nd["dcl"], "kept", kept)


@pytest.mark.parametrize("bad", ['{"/home.html||l|c|L":"#ffc98a"}', '{"/home.html||l|c|L":["#ffc98a",%d]}', '{"/home.html||l|c|L":["#b4d6ff",%d]}', '{"/home.html||l|c|L":["#f7eef0",1]}', '[1]', 'x'],
                         ids=["old-format-peach", "peach", "another-pages-colour", "expired", "not-a-map", "not-json"])
def test_a_bad_kept_colour_cannot_colour_a_later_load(site, bad):
    """What a page kept for "this page, this look, on its side" is used at the next first layout (the one Safari tints from). An entry that is not a measured,
    recent colour for this page is not used, and the load replaces it."""
    import time
    bad = bad % int(time.time() // 86400) if "%d" in bad else bad

    async def fn(page):
        pg = await page("/home.html", L)
        return await pg.evaluate(HOME), await pg.screenshot()
    d, png = _session(site, fn, size=L, init="try{if(!sessionStorage.getItem('s')){sessionStorage.setItem('s','1');localStorage.setItem('alto-sh-root',%r);}}catch(e){}" % bad)
    root = _home_top_ok(d, png, "after a bad entry")
    assert _d(_rgb(d["dcl"]), root) <= 2, f"the root at the first layout {d['dcl']} is not the bad entry's but the page's own {root}"
    kept = json.loads(d["store"])
    assert kept == {"/home.html||l|c|L": ["#%02x%02x%02x" % root, int(time.time() // 86400)]}, f"and the load left the measured colour in its place: {kept}"


def test_a_new_tabs_head_runs_before_the_tab_has_its_size(site):
    """A new tab on a phone on its side: <head> runs while innerWidth / innerHeight are not yet the screen's (they read upright). The root must be the landscape
    colour all the same: from the phone's own orientation, and from the stylesheet's media query."""
    fake = ("(function(){var w=Object.getOwnPropertyDescriptor(window,'innerWidth'),h=Object.getOwnPropertyDescriptor(window,'innerHeight');"
            "Object.defineProperty(window,'innerWidth',{configurable:true,get:function(){return 402}});Object.defineProperty(window,'innerHeight',{configurable:true,get:function(){return 874}});"
            "window.orientation=90;document.addEventListener('DOMContentLoaded',function(){Object.defineProperty(window,'innerWidth',w);Object.defineProperty(window,'innerHeight',h);},{once:true});})();")

    async def fn(page):
        pg = await page("/home.html", L)
        return await pg.evaluate(HOME), await pg.screenshot()
    d, png = _session(site, fn, size=L, init=fake)
    root = _home_top_ok(d, png, "new tab")
    assert _d(_rgb(d["dcl"]), root) <= 2, f"the root at the first layout {d['dcl']} is the measured one {root}"


def test_classic_home_opened_on_its_side_and_turned_upright_is_the_upright_page(site):
    async def fn(page):
        pg = await page("/home.html", L)
        await _turn(pg, P)
        await pg.wait_for_timeout(1500)
        a = await pg.evaluate(HOME)
        fresh = await (await page("/home.html", P)).evaluate(HOME)
        return a, fresh
    a, fresh = _session(site, fn, size=L)
    a["list"], fresh["list"] = a["list"][:3], fresh["list"][:3]      # (its foot: a turned page's tiles are 20 px taller, as they were before this; not this test's)
    for k in ("root", "y", "barPos", "bar", "tab", "list"):
        assert a[k] == fresh[k] or (isinstance(a[k], list) and max(abs(x - y) for x, y in zip(a[k], fresh[k])) <= 1), f"{k}: turned {a[k]}, a page opened upright {fresh[k]}"
    assert "rw" in a["cls"].split() and a["y"] == 80 and a["barPos"] == "absolute", f"upright the page rests on its runway (no flat bands under Safari's bars): {a}"


# ── S6: the horizontal timeline on a turn ──
LANES = "()=>{" + R + """const c=window._altoLanesCurrent&&_altoLanesCurrent(), f=window._altoLanesFit||{};
 return {cur:c, card:R(c&&document.querySelector('#node-'+c+' .node-card')), ch:f.room&&f.room.ch, cz:f.mode&&f.mode.cz, nav:R($('lanes-nav')), vw:innerWidth, vh:innerHeight, sw:document.documentElement.scrollWidth}}"""


def _same(a, b, what, tol=3):
    assert a["cur"] == b["cur"] and a["card"] and b["card"], (what, a, b)
    d = max(abs(x - y) for x, y in zip(a["card"], b["card"]))
    assert d <= tol, f"{what}: the card {a['card']} is not the one a page opened this way up draws {b['card']} (off by {d} pt)"
    assert max(abs(x - y) for x, y in zip(a["nav"], b["nav"])) <= tol, f"{what}: the step bar {a['nav']} vs {b['nav']}"


@pytest.mark.parametrize("start", ["on-its-side", "upright"])
def test_lanes_turned_is_the_board_a_fresh_open_draws(site, start):
    """Opened on its side and turned upright the first card began at x 185 and ran off the right edge (the view was left at the start of time); turned back, the board
    was still fitted to the 874 x 402 box of the turn's first resize (the second changes the height alone), its card 1.5x a fresh open's."""
    async def fn(page):
        fp = await (await page("/lanes.html", P, 3200)).evaluate(LANES)
        pg = await page("/lanes.html", L if start == "on-its-side" else P, 3200)
        fl = await pg.evaluate(LANES) if start == "on-its-side" else await (await page("/lanes.html", L, 3200)).evaluate(LANES)
        out = []
        for to in ([P, L, P] if start == "on-its-side" else [L, P, L]):
            await _turn(pg, to)
            await pg.wait_for_timeout(2200)
            out.append((to, await pg.evaluate(LANES)))
        return fp, fl, out
    fp, fl, out = _session(site, fn, size=L)
    assert fp["card"][0] >= 8 and fp["card"][2] <= P[0] - 8, fp
    for i, (to, d) in enumerate(out):
        assert d["vw"] == to[0] and d["vh"] == to[1] and d["sw"] == to[0], d
        _same(d, fp if to == P else fl, f"turn {i + 1} ({'upright' if to == P else 'on its side'})")
        print("S6", start, "turn", i + 1, to, "card", d["card"], "fresh", (fp if to == P else fl)["card"], "fit box", d["ch"], "cz", d["cz"])


# ── S4: the detail page scrolled on its side ──
TILES = "()=>{" + R + """const dp=$('detail-page'), g=document.createRange(), T={find:$('search-toggle'), mark:$('hl-mode-btn'), notes:$('notes-toggle')}, out={over:[], tiles:{}, st:dp.scrollTop, max:dp.scrollHeight-dp.clientHeight};
 for(const k in T){ const c=getComputedStyle(T[k]); out.tiles[k]=R(T[k]); out[k+'On']=c.display!=='none'&&c.visibility!=='hidden'&&+c.opacity>.5; }
 const dc=$('detail-content'), cc=getComputedStyle(dc); out.col=R(dc); out.pad=[cc.paddingLeft, cc.paddingRight]; out.text=[1e9,-1e9];
 dp.querySelectorAll('.detail-name,.detail-section-title,.detail-section p,.detail-section li,.detail-section .ol-row,.detail-symbol').forEach(e=>{ g.selectNodeContents(e);
   for(const q of g.getClientRects()){ if(q.width<2) continue; out.text[0]=Math.min(out.text[0],Math.round(q.left)); out.text[1]=Math.max(out.text[1],Math.round(q.right));
     for(const k in T){ const r=T[k].getBoundingClientRect(); if(q.left<r.right+PAD && r.left<q.right+PAD && q.top<r.bottom && r.top<q.bottom) out.over.push([k, e.className||e.tagName, Math.round(q.left), Math.round(q.right), Math.round(q.top)]); } } });
 return out}""".replace("PAD", "4")


@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
def test_detail_page_on_its_side_scrolled_the_corner_tiles_are_never_over_the_text(site, style):
    """Holo light, scrolled: FIND lay on the F of FACTS and MARK touched the end of a title line. The text column runs between the tiles' columns, so wherever the
    page is scrolled to, no heading, line or symbol is under a tile or within 4 pt of one."""
    async def fn(page):
        pg = await page("/timeline.html?view=card" + ("" if style == "classic" else f"&style={style}"), L, 2600 if style != "classic" else 1300)
        await pg.evaluate("showDetail('node', NODE_ORDER[1])")
        await pg.wait_for_timeout(600)
        out = []
        mx = await pg.evaluate("(()=>{const d=document.getElementById('detail-page');return d.scrollHeight-d.clientHeight})()")
        for y in range(0, int(mx) + 1, 23):
            await pg.evaluate("y=>{ document.getElementById('detail-page').scrollTop=y; window._altoPhoneMinApi.wake(); }", y)
            out.append(await pg.evaluate(TILES))
        return out
    out = _session(site, fn, size=L)
    assert len(out) >= 8 and out[-1]["st"] > 100, f"the page scrolls: {out[-1]['st']} of {out[-1]['max']}"
    assert all(d["findOn"] and d["markOn"] and d["notesOn"] for d in out), "the three tiles are awake"
    over = [(d["st"], o) for d in out for o in d["over"]]
    t = out[0]["tiles"]
    print("S4", style, "tiles", t, "text column", [min(d["text"][0] for d in out), max(d["text"][1] for d in out)], "over at", len(over), "of", len(out), "scroll stops:", over[:3])
    assert not over, f"{style}: text under or touching a corner tile at {len(over)} places, e.g. (scrollTop, [tile, element, left, right, top]) {over[:4]}"
    assert min(d["text"][0] for d in out) >= t["find"][2] + 4 and max(d["text"][1] for d in out) <= min(t["mark"][0], t["notes"][0]) - 4, "the text column is between the tiles"
