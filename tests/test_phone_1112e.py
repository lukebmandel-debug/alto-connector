"""Luke's two iPhone screenshots of 2026-11-12 (the live site, Holo dark, upright), each held by a WebKit check (headless, offline, silent; no cloud env, no account).

  1  The Memory Atlas, "a line that shouldn't be on top of the screen ... covering the globe, and I've seen it in other formats as well": the shut Overview
     (#summary-wrap, an accordion 0 px tall under the top bars) kept its border: a rule across the whole screen at 96 pt (44 pt on its side), 1 px in Classic,
     2 px in Retro (with a 4 px black ring) and Holo, over whatever came up under it (his Atlas card). Shut, it paints nothing, in every format and look;
     open, it is the panel it was.
  2  The homepage, "you can see the background above it. The top bar is meant to be an actual top bar there, so we shouldn't have stuff showing up above
     it": the 80 px of page above the header (what Safari shows under the clock) showed the list scrolling by. It is the bar's own colour, and the list
     does not show there. On its side there is no page above the header: Safari's toolbar takes the root's colour, which is the header's (held here too).

Each upright test fails on alto-rel-223 64323e33; the sideways homepage one passed there already (sim1112a R7, sim1112b S1)."""
import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

from test_phone_sim1112a import _pw, _img, _d, _rgb, INSET  # noqa: E402

P, L = (402, 874), (874, 292)
STYLES = ("classic", "retro", "holo")
FORMATS = (("timeline", "view=card"), ("timeline", "view=whole"), ("outline-long", "view=card"), ("outline-long", "view=whole"), ("lanes", ""), ("system", ""), ("atlas", ""))


@pytest.fixture(scope="module")
def site():
    pm = _pw()
    pages, plans, art = pm.build_pages()
    s = pm.serve(pages, plans, art)
    yield pm, f"http://127.0.0.1:{s.server_address[1]}"
    s.shutdown()


def _session(site, fn, size, theme="dark", inset=0):
    pm, base = site

    async def go():
        async with pm._playwright().async_playwright() as p:
            b = await p.webkit.launch()
            ctx = await b.new_context(viewport={"width": size[0], "height": size[1]}, is_mobile=True, has_touch=True, user_agent=pm.UA)
            await ctx.add_init_script(("try{localStorage.setItem('alto-theme-v1',%r)}catch(e){}" % theme) + (INSET % (inset, inset) if inset else ""))

            async def page(url, wait=3000):
                pg = await ctx.new_page()
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


# ── 1: no rule across the screen ──
# every box on screen that is at least 60 % of the screen wide and at most 6 px tall, and what it paints (its borders, its fill, a shadow, a backdrop blur).
# (Holo's card traces, .ho-nt, are part of a card.)
LINES = """()=>{const vw=innerWidth,vh=innerHeight,out=[],al=c=>{const m=/rgba?\\(([^)]+)\\)/.exec(c||'');if(!m)return 0;const p=m[1].split(',');return p.length>3?parseFloat(p[3]):1};
 document.querySelectorAll('body *').forEach(e=>{if(e instanceof SVGElement||e.closest('.ho-nt'))return;const c=getComputedStyle(e);if(c.display==='none'||c.visibility==='hidden'||+c.opacity===0)return;
  const r=e.getBoundingClientRect();if(r.width<vw*.6||r.height>6||r.bottom<0||r.top>vh||r.right<=0||r.left>=vw)return;
  const b=['Top','Bottom'].map(k=>parseFloat(c['border'+k+'Width'])*al(c['border'+k+'Color'])).reduce((a,b)=>a+b,0),ch=r.height-parseFloat(c.borderTopWidth)-parseFloat(c.borderBottomWidth),
   fh=c.backgroundClip==='content-box'?ch:r.height,bg=(al(c.backgroundColor)>0||c.backgroundImage!=='none')&&fh>.01,sh=c.boxShadow!=='none',bf=(c.webkitBackdropFilter||c.backdropFilter||'none')!=='none'&&r.height>0;
  if(b>0||bg||sh||bf)out.push((e.id||e.tagName+'.'+e.className)+' at '+Math.round(r.top)+' pt, '+Math.round(r.height*10)/10+' px'+(b>0?', border':'')+(bg?', fill':'')+(sh?', shadow':'')+(bf?', blur':''));});
 const s=document.getElementById('summary-wrap'),r=s&&s.getBoundingClientRect();return {lines:out,sw:r&&[r.left,r.top,r.right,r.bottom].map(Math.round),open:s&&s.classList.contains('open'),cls:document.documentElement.className}}"""


def _strip_px(a, b, box):
    """How many pixels of the strip `box` differ between two shots by more than 8 levels."""
    a, b = _img(a), _img(b)
    return sum(1 for y in range(max(0, box[1]), min(a.height, box[3])) for x in range(box[0], box[2]) if _d(a.getpixel((x, y)), b.getpixel((x, y))) > 8)


@pytest.mark.parametrize("size", [P, L], ids=["402x874", "874x292"])
@pytest.mark.parametrize("style", STYLES)
def test_nothing_draws_a_rule_across_the_screen_in_any_format(site, style, size):
    async def fn(page):
        out = {}
        for name, q in FORMATS:
            pg = await page("/%s.html?%sstyle=%s" % (name, q + "&" if q else "", style))
            d = await pg.evaluate(LINES)
            # the proof in pixels: the strip where the shut Overview sits, as drawn, and with the Overview taken out of the page
            box = (0, d["sw"][1] - 5, size[0], d["sw"][3] + 5)
            await pg.add_style_tag(content="*,*::before,*::after{animation-play-state:paused!important;transition:none!important}")
            await pg.wait_for_timeout(120)
            a = await pg.screenshot()
            await pg.evaluate("document.getElementById('summary-wrap').style.setProperty('display','none','important')")
            await pg.wait_for_timeout(60)
            d["px"] = _strip_px(a, await pg.screenshot(), box)
            out[name + ("?" + q if q else "")] = d
            await pg.close()
        return out
    out = _session(site, fn, size)
    bad = {k: (d["lines"], d["px"]) for k, d in out.items() if d["lines"] or d["px"] > 40}
    print("1", style, size, {k: (d["sw"], len(d["lines"]), d["px"]) for k, d in out.items()})
    assert not any(d["open"] for d in out.values()), out
    assert all(d["sw"] and d["sw"][2] - d["sw"][0] >= 0 for d in out.values()), out
    assert not bad, f"{style} {size}: a rule across the screen (what paints it, and how many px the shut Overview draws): {bad}"


SW = """()=>{const s=document.getElementById('summary-wrap'),c=getComputedStyle(s),r=s.getBoundingClientRect(),al=k=>{const m=/rgba?\\(([^)]+)\\)/.exec(k||'');const p=m?m[1].split(','):[];return !m?0:p.length>3?parseFloat(p[3]):1};
 return {open:s.classList.contains('open'),h:r.height,top:r.top,clip:c.backgroundClip,fill:al(c.backgroundColor),border:al(c.borderBottomColor)*parseFloat(c.borderBottomWidth),vis:c.visibility}}"""


@pytest.mark.parametrize("style", STYLES)
def test_the_overview_still_opens_as_a_panel_and_shuts_to_nothing(site, style):
    async def fn(page):
        pg = await page("/timeline.html?view=card&style=%s" % style)
        shut0 = await pg.evaluate(SW)
        await pg.evaluate("toggleSummary()")
        await pg.wait_for_timeout(900)
        opened = await pg.evaluate(SW)
        await pg.evaluate("toggleSummary()")
        await pg.wait_for_timeout(900)
        return shut0, opened, await pg.evaluate(SW), (await pg.evaluate(LINES))["lines"]
    shut0, opened, shut, lines = _session(site, fn, P)
    assert not shut0["open"] and shut0["h"] <= 2 and shut0["border"] == 0 and shut0["clip"] == "content-box", shut0
    assert opened["open"] and opened["h"] > 400 and opened["clip"] == "border-box" and opened["fill"] > .5 and opened["vis"] == "visible", f"open, the Overview is its panel: {opened}"
    assert abs(shut["top"] - shut0["top"]) <= 1 and shut["h"] <= 2 and not lines, f"shut again: {shut}, {lines}"


# ── 2: the homepage's bar runs to the top of the screen ──
BAR = 62                                          # the status-bar zone, pt: document y 18 .. 80 of the runway
HOME = """()=>{const de=document.documentElement,tb=document.getElementById('title-bar'),r=tb.getBoundingClientRect(),t=document.getElementById('title-text').getBoundingClientRect();
 return {cls:de.className,y:pageYOffset,bar:[r.top,r.bottom],tab:[t.left,t.right],root:getComputedStyle(de).backgroundColor,theme:document.querySelector('meta[name=theme-color]').content,
  top:(()=>{const o=[];document.querySelectorAll('body *').forEach(e=>{const c=getComputedStyle(e);if(c.position!=='fixed'&&c.position!=='sticky')return;const q=e.getBoundingClientRect();
   if(c.display!=='none'&&q.width>0&&q.height>0&&q.top<=1&&q.bottom>0)o.push(e.id||e.className);});return o})()}}"""


@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("style", STYLES)
def test_upright_the_homepage_bar_runs_up_under_the_clock_and_the_list_does_not_show_there(site, style, theme):
    async def fn(page):
        pg = await page("/home.html?style=%s" % style)
        await pg.evaluate("document.querySelector('#projects-wrap').scrollTop=260")       # tiles under the bar and above it, as in his shot
        await pg.wait_for_timeout(400)
        await pg.add_style_tag(content="*,*::before,*::after{animation-play-state:paused!important}")
        await pg.wait_for_timeout(100)
        d, a = await pg.evaluate(HOME), await pg.screenshot(full_page=True)
        await pg.add_style_tag(content="#projects-wrap>*{visibility:hidden!important}")
        await pg.wait_for_timeout(150)
        return d, a, await pg.screenshot(full_page=True)
    d, a, b = _session(site, fn, P, theme)
    assert "rw" in d["cls"].split() and d["y"] == 80 and d["bar"] == [0, 52] and d["top"] == [], d        # the runway as it was: 80 px down, nothing fixed to the screen's top
    A, B = _img(a), _img(b)
    xs = [x for x in range(4, P[0] - 4, 3)]
    # the list in the status-bar zone: the page with its tiles against the page without them
    through = max(_d(A.getpixel((x, y)), B.getpixel((x, y))) for y in range(80 - BAR, 80) for x in xs)
    # the zone is the bar: against the bar's own ground beside the name tab (6 px into the bar, clear of the clef, the tab and the wordmark)
    free = [x for x in xs if 70 < x < d["tab"][0] - 16 or d["tab"][1] + 16 < x < P[0] - 90]
    zone = max(_d(B.getpixel((x, y)), B.getpixel((x, 86))) for y in range(80 - BAR, 80, 2) for x in free)
    print("2", style, theme, "list through the zone:", through, "| zone vs the bar:", zone, "| root", d["root"], "theme", d["theme"], "| bar px", B.getpixel((100, 86)), "zone px", B.getpixel((100, 50)))
    assert through <= (24 if style == "classic" else 6), f"{style} {theme}: the list shows in the status-bar zone above the bar (up to {through} levels)"
    assert zone <= 14, f"{style} {theme}: the status-bar zone is not the bar's own colour (off by up to {zone} levels)"
    if style != "classic":                        # (Classic's root is its sunset, which Safari's foot keeps: the zone is the page's own pixels, the bar's glass)
        root = _rgb(d["root"])
        assert max(_d(root, B.getpixel((x, 50))) for x in free) <= 12, f"{style} {theme}: Safari's tint {root} is not the bar's {B.getpixel((100, 50))}"
        assert d["theme"].lower() == "#%02x%02x%02x" % root, d


@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("style", STYLES)
def test_on_its_side_safaris_toolbar_colour_is_the_homepage_bars(site, style, theme):
    async def fn(page):
        pg = await page("/home.html?style=%s" % style)
        return await pg.evaluate(HOME), await pg.screenshot()
    d, png = _session(site, fn, L, theme, inset=62)
    assert "rw" not in d["cls"].split() and d["y"] == 0 and d["bar"][0] == 0, d             # no runway: the bar is the top of the page, nothing of it above
    im, root = _img(png), _rgb(d["root"])
    off = max(_d(root, im.getpixel((x, 2))) for x in range(int(d["tab"][0]) - 90, int(d["tab"][0]) - 20, 5))
    print("2L", style, theme, "root", root, "bar px", im.getpixel((int(d["tab"][0]) - 40, 2)), "off", off, "theme", d["theme"])
    assert off <= 12, f"{style} {theme}: on its side Safari's toolbar colour {root} is not the bar's at the top"
    assert d["theme"].lower() == "#%02x%02x%02x" % root, d
