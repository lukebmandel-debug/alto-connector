"""The real-iPhone FAILs of sim1112a (ORG/sim-main/sim1112a/report.md; private alto-rel-223 9d10f730), each held by a WebKit check at 874 x 292 with the island's 62 pt insets
(headless, offline, silent; no cloud env, no account). Every test here fails on 9d10f730.

  R7  Classic's homepage on its side: Safari's toolbar zone was a flat peach band (the root kept Classic's peach) over a page whose top is the header's pale glass, and the "Home" tab
      was a solid white box (frost over a pane that is already .82 white). The root takes the page's real colour at the top; the glass is cut away under the tab, so the tab frosts
      the page itself, as the corner toggles do. (The dark theme's header glass was the light one: it is the dark one.)
  R4  the horizontal timeline on its side: the board was cut off at the insets, hard edges and cut lines. The canvas runs the screen's full width, the board is held between the insets
      by the canvas's padding, and the slab (the ground) is one piece from edge to edge: no strips beside it.
  R1  Holo dark on one of its own backgrounds, on its side: each page's plate kept the island's inset, so a 124 pt band of the bare scene rode between the two pages of a swipe. The plate
      runs to the page's edges, as it does upright; the text stays inset and nothing moves on landing.
  and: the Holo one-card view's previous / next strip in Holo's colours; Retro's "Back to" pill in Retro's; no pale strip between the header row and the names strip of a detail page
  on its side.
WebKit has no safe areas: the insets are injected the way tests/test_phone_shell.py does."""
import asyncio
import io
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

W, H, ISL = 874, 292, 62


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
    for name, sample in (("timeline", "contracts"), ("lanes", "lanes")):
        put(name, build_timeline(*load_brief(json.loads((ROOT / "samples" / f"{sample}_brief.json").read_text(encoding="utf-8"))))[0])
    put("home", build_home([{"name": "Law school %d" % p, "pid": "p%d" % p, "courses": [
        {"title": "Civil Procedure %d.%d" % (p, c), "href": "outline.html", "sub": "%d units" % (c + 3), "courseId": "c%d%d" % (p, c), "units": []} for c in range(8)]} for p in range(4)]))
    s = pm.serve(pages, {}, {})
    yield pm, f"http://127.0.0.1:{s.server_address[1]}"
    s.shutdown()


INSET = ("document.addEventListener('DOMContentLoaded',()=>{const s=document.createElement('style');"
         "s.textContent='#sh-probe{padding-left:%dpx!important;padding-right:%dpx!important}';document.head.appendChild(s);});")
R = "const R=e=>{if(!e)return null;const r=e.getBoundingClientRect();return [r.left,r.top,r.right,r.bottom].map(v=>Math.round(v*10)/10)},$=i=>document.getElementById(i);"


def _run(site, fn, url, w=W, h=H, inset=ISL, wait=1500, theme="light"):
    pm, base = site

    async def go():
        async with pm._playwright().async_playwright() as p:
            b = await p.webkit.launch()
            ctx = await b.new_context(viewport={"width": w, "height": h}, is_mobile=True, has_touch=True, user_agent=pm.UA)
            if inset:
                await ctx.add_init_script(INSET % (inset, inset))
            await ctx.add_init_script("try{localStorage.setItem('alto-theme-v1',%r)}catch(e){}" % theme)
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


def _img(png):
    from PIL import Image
    return Image.open(io.BytesIO(png)).convert("RGB")


def _d(a, b):
    return max(abs(p - q) for p, q in zip(a, b))


def _rgb(s):
    import re
    return tuple(round(float(v)) for v in re.findall(r"[\d.]+", s)[:3])


# ── R7: Classic's homepage on its side ──
HOME = "()=>{" + R + """const de=document.documentElement, cs=e=>getComputedStyle(e), t=$('title-text'), sb=$('search-btn'), k=e=>[cs(e).backgroundColor, cs(e).webkitBackdropFilter||cs(e).backdropFilter];
 return {cls:de.className, root:cs(de).backgroundColor, theme:document.querySelector('meta[name=theme-color]').content, early:window._altoShell&&_altoShell.early, top:window._altoShell&&_altoShell.top,
  tab:R(t), bar:R($('title-bar')), tabGlass:k(t), toggleGlass:k(sb)}}"""
NO_GLASS = ("()=>{const s=document.createElement('style');s.textContent='#title-bar:not(#_):not(#__):not(#___),#title-bar:not(#_):not(#__):not(#___)::before"
            "{background:none!important;-webkit-backdrop-filter:none!important;backdrop-filter:none!important}';document.head.appendChild(s);}")


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_classic_home_on_its_side_gives_safari_the_pages_real_colour_and_a_frosted_tab(site, theme):
    async def fn(pg):
        d = await pg.evaluate(HOME)
        d["png"] = await pg.screenshot()
        await pg.evaluate(NO_GLASS)               # the tab with no header glass under it at all: what frost over the page itself looks like
        await pg.wait_for_timeout(300)
        d["bare"] = await pg.screenshot()
        return d
    d = _run(site, fn, "/home.html", theme=theme, wait=2200)
    assert "alto-home" in d["cls"] and "sh-landscape" in d["cls"] and "alto-retro" not in d["cls"] and "alto-holo" not in d["cls"], d["cls"]
    assert ("dark" in d["cls"].split()) == (theme == "dark"), d["cls"]
    im, bare = _img(d["png"]), _img(d["bare"])
    root, (l, t, r, b) = _rgb(d["root"]), d["tab"]
    # the toolbar: Safari tints it from the root's colour. The page's top is the header glass: the root is that colour, not Classic's peach
    glass = im.getpixel((int(l) - 40, 3))
    print("R7", theme, "root", d["root"], "theme-color", d["theme"], "early", d["early"], "header glass", glass)
    assert _d(root, (255, 201, 138)) > 30, f"the root is still Classic's peach: {d['root']}"
    assert _d(root, glass) <= 12, f"the root {root} is not the page's colour at the top {glass}"
    assert _rgb(d["theme"].replace("#", "0x")) is not None and d["theme"].lower() == "#%02x%02x%02x" % root, f"theme-color {d['theme']} is the root's colour {root}"
    # ... from the first layout (Safari reads it then, and again only on a turn): the colour set in <head> is the measured one
    assert d["early"], "no colour was set before the first layout"
    e = tuple(int(d["early"][i:i + 2], 16) for i in (1, 3, 5))
    assert _d(e, root) <= 6, f"the first layout's colour {d['early']} is not the measured one {root}"
    if theme == "dark":
        assert sum(glass) / 3 < 90, f"the dark theme's header glass is dark: {glass}"
    # the tab: the corner toggles' own glass ...
    assert d["tabGlass"][0] == d["toggleGlass"][0] and "blur(18px)" in d["tabGlass"][1] and "blur(18px)" in d["toggleGlass"][1], f"{d['tabGlass']} / {d['toggleGlass']}"
    # ... over the page itself: its pixels are what they are with no header glass under it (a solid white box was 30+ levels off)
    worst = 0
    for y in range(int(t) + 3, int(b) - 15, 3):
        for x in range(int(l) + 4, int(r) - 4, 3):
            worst = max(worst, _d(im.getpixel((x, y)), bare.getpixel((x, y))))
    print("R7", theme, "tab vs tab over the bare page: worst", worst)
    assert worst <= 4, f"the tab is drawn over the header glass, not over the page: {worst} levels from frost over the page"
    if theme == "light":
        assert _d(im.getpixel((int((l + r) / 2), int(t) + 3)), (255, 255, 255)) > 12, "the tab is a solid white box"
    # and the glass comes up to the tab's edge: no hairline of bare page beside it or under its feet
    for x, y in ((round(l) - 2, 12), (round(r) + 1, 12), (round(l) + 1, round(b) + 1), (round(r) - 2, round(b) + 1), (round(l), round(b) - 1), (round(r) - 1, round(b) - 1)):
        assert _d(im.getpixel((x, y)), bare.getpixel((x, y))) > 8, f"bare page shows beside the tab at {x},{y}: {im.getpixel((x, y))}"


def test_holo_dark_home_on_its_side_keeps_its_ground_behind_safaris_toolbar(site):
    async def fn(pg):
        d = await pg.evaluate(HOME)
        d["png"] = await pg.screenshot()
        return d
    d = _run(site, fn, "/home.html?style=holo", theme="dark", wait=3600)
    assert "alto-holo" in d["cls"] and "dark" in d["cls"].split(), d["cls"]
    assert _rgb(d["root"]) == (1, 10, 14) and d["theme"].lower() == "#010a0e", f"{d['root']} {d['theme']}"
    im = _img(d["png"])
    assert _d(im.getpixel((int(d["tab"][0]) - 40, 3)), (1, 10, 14)) <= 10, "the page's top is the root's colour"


# ── R4: the horizontal timeline on its side ──
LANES = "()=>{" + R + """const c=$('canvas'), cards=[...document.querySelectorAll('#world .node-card')].map(R).filter(q=>q[2]>0&&q[0]<innerWidth);
 return {cls:document.documentElement.className, canvas:R(c), world:R($('world')), slab:R($('glass-slab')), bl:R($('sh-bl')), br:R($('sh-br')), nav:R($('lanes-nav')), cards:cards, sl:c.scrollLeft, max:c.scrollWidth-c.clientWidth,
  sky:!!$('lanes-ov-sky')}}"""


def test_lanes_on_its_side_the_board_and_its_lines_run_under_the_island(site):
    async def fn(pg):
        a = await pg.evaluate(LANES)
        a["png"] = await pg.screenshot()
        await pg.evaluate("document.getElementById('canvas').scrollLeft=1e6")
        await pg.wait_for_timeout(500)
        z = await pg.evaluate(LANES)
        await pg.evaluate("document.getElementById('canvas').scrollLeft=0")
        await pg.wait_for_timeout(300)
        await pg.evaluate("[...document.querySelectorAll('#lanes-nav button')].find(e=>/whole timeline/i.test(e.title||'')).click()")
        await pg.wait_for_timeout(1300)
        o = await pg.evaluate(LANES)
        return a, z, o
    a, z, o = _run(site, fn, "/lanes.html", wait=3000)
    assert "alto-lanes" in a["cls"] and "sh-landscape" in a["cls"] and "phone-whole" in a["cls"], a["cls"]
    print("R4 open", {k: a[k] for k in ("canvas", "world", "slab", "bl", "br", "nav")}, "end", {k: z[k] for k in ("world", "slab", "sl", "max")}, "whole", o["world"])
    for d in (a, z):
        assert d["canvas"][0] <= .5 and d["canvas"][2] >= W - .5, f"the canvas is cut off at the island's insets: {d['canvas']}"
        assert d["slab"][0] <= .5 and d["slab"][2] >= W - .5, f"the board's own ground (the slab) runs from edge to edge: {d['slab']}"
        assert not d["bl"] and not d["br"], f"no strip stands in for the ground beside the board: {d['bl']} {d['br']}"
        assert d["nav"][0] >= ISL and d["nav"][2] <= W - ISL, f"the rail keeps clear of the island: {d['nav']}"
    # the board is held between the insets: it opens at the left inset and ends at the right one
    assert abs(a["world"][0] - ISL) <= 1 and a["sl"] == 0, a["world"]
    assert z["sl"] > 1000 and abs(z["sl"] - z["max"]) <= 1 and abs(z["world"][2] - (W - ISL)) <= 1, f"scrolled to its end the board stops at the right inset: {z['world']}"
    assert all(c[0] >= ISL for c in a["cards"]), f"no card under the island as the page opens: {a['cards']}"
    # the lines run on under the island: the main line's own pixels at the right inset are its pixels 30 px and 55 px further on
    im = _img(a["png"])
    y = max(range(50, H - 70), key=lambda q: _d(im.getpixel((780, q)), im.getpixel((780, q - 8))))
    line, ground = im.getpixel((780, y)), im.getpixel((780, y - 8))
    assert _d(line, ground) > 30, f"found the main line at y={y}: {line} on {ground}"
    for x in (800, 811, 814, 840, 868):
        assert _d(im.getpixel((x, y)), line) <= 14, f"the main line is cut at x={x}: {im.getpixel((x, y))}, the line is {line}"
    for yy in (60, H // 2, H - 20):                # and the ground beside it is one ground
        for xa, xb in ((56, 68), (806, 818)):
            assert _d(im.getpixel((xa, yy)), im.getpixel((xb, yy))) <= 6, f"y={yy}: a step in the ground at x={xa}/{xb}"
    # zoomed out to the whole timeline: fitted between the insets, 30 px clear of them
    assert o["sky"] and o["world"][0] >= ISL + 29 and o["world"][2] <= W - ISL - 29, f"the whole timeline is fitted between the insets: {o['world']}"


# ── R1: Holo dark on one of its own backgrounds, a swipe on its side ──
def test_holo_dark_scene_swipe_on_its_side_no_band_of_scene_between_the_pages(site):
    import test_phone_swipe_land as T
    TITLE = "()=>{const e=document.querySelector('#detail-page:not(.det-peek) .detail-name'), r=e.getBoundingClientRect(), p=document.querySelector('#detail-page:not(.det-peek) .detail-section'), q=p.getBoundingClientRect(); return [r.left,r.top,r.width,q.left,q.top,q.width].map(v=>Math.round(v*10)/10)}"

    async def fn(pg):
        await pg.evaluate("_altoBg.choose('h-grid-horizon')")
        await pg.wait_for_timeout(1200)
        await pg.evaluate("showDetail('node', NODE_ORDER[1])")
        await pg.wait_for_timeout(900)
        d = {"cls": await pg.evaluate("document.documentElement.className"), "rest": await pg.screenshot(),
             "text": await pg.evaluate("()=>{const r=document.querySelector('#detail-page .detail-section').getBoundingClientRect();return [r.left,r.right]}")}
        await pg.evaluate(T.SEAM_SAMPLER)
        d["held"] = await pg.evaluate(T.SEAM_DRAG, [round(W * .62), round(H * .55), -round(W * .45), 9])
        d["mid"] = await pg.screenshot()
        await pg.evaluate(T.SEAM_LIFT)
        await pg.wait_for_function("()=>!document.querySelector('.det-peek') && !document.getElementById('detail-page').style.transform", timeout=3000)
        d["t0"] = await pg.evaluate(TITLE)
        d["landed"] = await pg.screenshot()
        await pg.wait_for_timeout(520)
        d["t1"] = await pg.evaluate(TITLE)
        d["later"] = await pg.screenshot()
        d["after"] = await pg.evaluate("[NODE_ORDER.indexOf(window._currentDetailId), document.querySelectorAll('#detail-page').length, document.querySelectorAll('.det-peek').length]")
        return d
    d = _run(site, fn, "/timeline.html?view=card&style=holo", theme="dark", wait=2800)
    assert "alto-holo" in d["cls"] and "alto-bg-h" in d["cls"] and "dark" in d["cls"].split() and "sh-landscape" in d["cls"], d["cls"]
    assert len(d["held"]) == 2 and abs(d["held"][1][0] - d["held"][0][1]) <= .5, f"two pages under the finger, butted: {d['held']}"
    seam = d["held"][0][1]
    mid, rest, landed, later = (_img(d[k]) for k in ("mid", "rest", "landed", "later"))
    # mid-swipe: from the outgoing page's text column to the incoming page's, across both islands' insets, the plate is one ground (the bare scene's purple sky was 60+ levels off)
    band = 0
    for y in (150, 165, 180, 195):
        ref = mid.getpixel((int(seam) - 150, y))
        band = max(band, max(_d(mid.getpixel((x, y)), ref) for x in range(int(seam) - 140, int(seam) + 141, 4)))
    print("R1 band", band, "seam", seam, "title", d["t0"], d["t1"])
    assert band <= 24, f"a band of the bare scene rides between the two pages: {band} levels"
    # at rest the plate reaches the page's edges under the island, the text stays inset
    for x in (8, 40, W - 40, W - 8):
        assert _d(rest.getpixel((x, 170)), rest.getpixel((150, 170))) <= 24, f"at rest the plate stops short of the screen's edge at x={x}: {rest.getpixel((x, 170))}"
    assert d["text"][0] >= ISL + 17 and d["text"][1] <= W - ISL - 17, f"the text keeps clear of the island: {d['text']}"
    # the landing: nothing moves, and the ground under the island does not change
    assert d["after"] == [2, 1, 0], d["after"]
    assert d["t0"] == d["t1"], f"the title or the first section moved after landing: {d['t0']} -> {d['t1']}"
    for x in (8, 40, W - 40, W - 8):
        for y in (150, 180):
            assert _d(landed.getpixel((x, y)), later.getpixel((x, y))) <= 12, f"the ground under the island changed after landing at {x},{y}"


# ── the smaller rows ──
@pytest.mark.parametrize("theme", ["light", "dark"])
def test_holo_card_view_names_strip_is_the_headers_own_bar(site, theme):
    async def fn(pg):
        return await pg.evaluate("()=>{" + R + "const c=e=>getComputedStyle(e); return {cls:document.documentElement.className, strip:R($('timeline-label-bar')), bg:c($('timeline-label-bar')).backgroundColor,"
                                 " bd:c($('timeline-label-bar')).borderBottomColor, nav:c($('nav')).backgroundColor, navbd:c($('nav')).borderBottomColor}}")
    d = _run(site, fn, "/timeline.html?view=card&style=holo", 402, 874, 0, wait=2800, theme=theme)
    assert "alto-holo" in d["cls"] and "dark" in d["cls"].split(), d["cls"]          # (dark only whatever the saved theme, a phone's too: 2026-11-13)
    assert d["strip"] and d["strip"][3] - d["strip"][1] > 20, f"the names are on screen: {d['strip']}"
    # phone navbar B: the strip is now the glass pill at the foot, in Holo's own ground (its --ho-bgrgb at .86), never Classic's unit tint (rgba(74, 158, 255, ...))
    assert d["strip"][1] > 874 * .8, f"the pill is at the foot: {d['strip']}"
    assert "74, 158, 255" not in d["bg"] and d["bg"] != d["nav"], f"Holo's pill carries Holo's ground, not the unit tint: {d['bg']}"
    assert d["bg"].startswith("rgba(") and float(d["bg"].rstrip(")").split(",")[-1]) in (.86, 0.86), d["bg"]


def test_retro_back_to_pill_is_retros(site):
    async def fn(pg):
        return await pg.evaluate("()=>{let b=document.getElementById('alto-back-prev'); if(!b){ b=document.createElement('button'); b.id='alto-back-prev'; document.body.appendChild(b); } const c=getComputedStyle(b); return [document.documentElement.className, c.backgroundColor, c.color, c.borderRadius]}")
    cls, bg, ink, rad = _run(site, fn, "/timeline.html?view=card&style=retro", 402, 874, 0, wait=2800)
    assert "alto-retro" in cls, cls
    assert bg == "rgb(0, 0, 0)" and ink == "rgb(239, 230, 207)" and rad == "0px", f"Retro's pill is Classic's: {bg} {ink} {rad}"


@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
def test_detail_page_on_its_side_no_strip_between_the_header_row_and_the_names(site, style):
    async def fn(pg):
        await pg.evaluate("showDetail('node', NODE_ORDER[2])")
        await pg.wait_for_timeout(900)
        return await pg.evaluate("()=>{" + R + "return {nav:R($('nav')), names:R($('node-nav-bar')), page:R($('detail-page'))}}")
    d = _run(site, fn, "/timeline.html?view=card" + ("" if style == "classic" else f"&style={style}"), wait=2800 if style != "classic" else 1500)
    print("strip", style, d)
    # phone navbar B: the names join the 44 pt title row (as the card view's do), and the page hangs from the row
    assert d["names"][1] <= .5 and abs(d["names"][3] - d["nav"][3]) <= .5, f"{style}: the names {d['names']} are in the header row {d['nav']}"
    assert abs(d["page"][1] - d["nav"][3]) <= 1.5, f"{style}: the page {d['page']} hangs from the row {d['nav']}"
