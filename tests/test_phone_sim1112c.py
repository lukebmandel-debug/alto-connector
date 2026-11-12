"""sim1112c (the real-iPhone check of rel-223 054e8a09): two items left, both on Classic's homepage after a turn.

  T3  opened on its side and turned upright: Safari's status-bar zone (the top 62 pt) was a flat band of the root's colour (peach ffc989, brown 6a421f in the dark
      theme) over a page that was, from 64 pt down, the upright page pixel for pixel. A page opened upright shows its gradient there, and upright -> side -> upright
      had no band. What the two pages do not share: the one opened on its side had its header and its two ground layers fixed to the screen's top from its first
      layout on; the turn's first upright layout still had them there (html.rw came with the media query's change event, after that layout); and theme-color still
      said the sideways page's header glass. Now: nothing is fixed to the top of a page opened on its side until it is touched or scrolls, html.rw goes on at
      orientationchange (before the window has its new size), and theme-color is the upright page's.
  T1  opened upright and turned on its side: the list stood 78 pt higher than on a page opened on its side, until the reader scrolled. Safari puts the page back
      where it was as its turn ends: 80 px down a runway the sideways page does not have. The page is held at its top while the turn lasts.

WebKit, the phone's own boxes and the phone's own turn: orientationchange, a resize at +78 ms (the new width, the old bars) and one at +418 ms. What Safari itself
paints behind its bars cannot be seen here: the tests hold what the page gives it. Each fails on 054e8a09.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

from test_phone_sim1112a import site, _img, _d, _rgb, R  # noqa: E402,F401  (the fixture and the helpers)
from test_phone_sim1112b import _session, P, L  # noqa: E402

BAR = 62                                         # the status-bar zone, pt
UP1, SIDE1 = (402, 764), (874, 402)              # the turn's first resize: the new width, the last way up's bars
# an iPhone's own answers: which way up, and its screen (always the upright box)
PHONE = ("try{Object.defineProperty(window,'orientation',{configurable:true,writable:true,value:innerWidth>innerHeight?90:0});Object.defineProperty(screen,'width',{configurable:true,get:function(){return 402}});"
         "Object.defineProperty(screen,'height',{configurable:true,get:function(){return 874}});}catch(e){}"
         "document.addEventListener('DOMContentLoaded',function(){window.__dclTop=(%s)();},{once:true});")
# what is fixed (or sticky) to the screen's top edge: what Safari paints its top bar flat for
TOPFIX = ("function(){var o=[];[].forEach.call(document.querySelectorAll('body *'),function(e){var c=getComputedStyle(e);if(c.position!=='fixed'&&c.position!=='sticky')return;"
          "var r=e.getBoundingClientRect();if(c.display!=='none'&&r.width>0&&r.height>0&&r.top<=1&&r.bottom>0)o.push(e.id||e.className);});return o;}")
STATE = "()=>{" + R + """const de=document.documentElement, cs=e=>getComputedStyle(e);
 return {rw:de.classList.contains('rw'), cls:de.className.split(/\\s+/).filter(c=>c!=='sh-fx').sort().join(' '), root:cs(de).backgroundColor, theme:document.querySelector('meta[name=theme-color]').content,
  y:pageYOffset, top:(%s)(), dclTop:window.__dclTop, bar:R($('title-bar')), tab:R($('title-text')), list:R(document.querySelector('#projects-wrap .project, #projects-wrap > *')),
  barPos:cs($('title-bar')).position, vw:innerWidth, vh:innerHeight}}""" % TOPFIX
TOUCH = "()=>{const e=new Event('touchstart',{bubbles:true,cancelable:true});e.touches=[{clientX:300,clientY:200}];document.body.dispatchEvent(e);}"


def _theme(t):
    return PHONE % TOPFIX + "try{localStorage.setItem('alto-theme-v1',%r)}catch(e){}" % t


async def _turn(pg, to, put_back=None):
    """The phone's turn. Returns the page's state on orientationchange itself (the window still the last way up's) and at the first resize."""
    await pg.evaluate("o=>{Object.defineProperty(window,'orientation',{configurable:true,writable:true,value:o});window.dispatchEvent(new Event('orientationchange'));}", 90 if to == L else 0)
    at0 = await pg.evaluate(STATE)
    await pg.wait_for_timeout(78)
    mid = SIDE1 if to == L else UP1
    await pg.set_viewport_size({"width": mid[0], "height": mid[1]})
    at1 = await pg.evaluate(STATE)
    await pg.wait_for_timeout(340)
    await pg.set_viewport_size({"width": to[0], "height": to[1]})
    if put_back is not None:                                       # Safari, as its turn ends: the page back where it was
        for ms in put_back:
            await pg.wait_for_timeout(ms)
            await pg.evaluate("window.scrollTo(0,78)")
    return at0, at1


def _top_px(a, b, w=P[0]):
    a, b = _img(a), _img(b)
    return max(_d(a.getpixel((x, y))[:3], b.getpixel((x, y))[:3]) for y in range(0, BAR + 2) for x in range(0, w, 3))


def _same_page(d, fresh, what):
    for k in ("rw", "cls", "root", "theme", "y", "top", "barPos", "vw", "vh"):
        assert d[k] == fresh[k], f"{what}: {k} is {d[k]!r}; a page opened upright has {fresh[k]!r}"
    for k in ("bar", "tab"):
        assert max(abs(x - y) for x, y in zip(d[k], fresh[k])) <= 1, f"{what}: {k} {d[k]} vs {fresh[k]}"
    assert max(abs(x - y) for x, y in zip(d["list"][:3], fresh["list"][:3])) <= 1, f"{what}: the list {d['list']} vs {fresh['list']}"


# ── T3: opened on its side, turned upright ──
@pytest.mark.parametrize("theme", ["light", "dark"])
def test_classic_home_opened_on_its_side_and_turned_upright_gives_safari_the_upright_page(site, theme):
    async def fn(page):
        f = await page("/home.html", P)
        fresh, fpng = await f.evaluate(STATE), await f.screenshot()
        pg = await page("/home.html", L)
        side = await pg.evaluate(STATE)
        at0, at1 = await _turn(pg, P)
        await pg.wait_for_timeout(1500)
        return fresh, fpng, side, at0, at1, await pg.evaluate(STATE), await pg.screenshot()
    fresh, fpng, side, at0, at1, d, png = _session(site, fn, size=L, init=_theme(theme))
    assert fresh["rw"] and fresh["y"] == 80 and fresh["top"] == [] and fresh["dclTop"] == [], fresh
    # on its side: nothing fixed to the screen's top, at the first layout and after the load
    assert side["dclTop"] == [] and side["top"] == [], f"opened on its side, fixed to the screen's top: at the first layout {side['dclTop']}, loaded {side['top']}"
    # on orientationchange, the window still 874 wide: the runway's class, 80 px down it, and the upright page's root colour
    assert at0["vw"] == L[0] and at0["rw"] and at0["y"] == 80 and at0["top"] == [], f"on orientationchange: {at0}"
    assert at0["root"] == fresh["root"], f"the root as the screen turns is {at0['root']}; a page opened upright has {fresh['root']}"
    assert at0["theme"] == fresh["theme"], f"theme-color as the screen turns is {at0['theme']}; a page opened upright has {fresh['theme']}"
    # the first resize (402 wide, the sideways page's bars): the runway page already
    assert at1["vw"] == P[0] and at1["rw"] and at1["y"] == 80 and at1["top"] == [] and at1["root"] == fresh["root"] and at1["barPos"] == "absolute", f"at the first resize: {at1}"
    _same_page(d, fresh, "turned upright")
    px = _top_px(png, fpng)
    assert px <= 2, f"the top {BAR} pt of the turned page are not the pixels of a page opened upright (off by up to {px} levels)"
    print("T3", theme, "side dclTop", side["dclTop"], "| at0 rw/y/root/theme", at0["rw"], at0["y"], at0["root"], at0["theme"], "| turned theme", d["theme"], "fresh", fresh["theme"], "| top px diff", px)


def test_classic_home_upright_then_on_its_side_then_upright_is_still_the_upright_page(site):
    async def fn(page):
        f = await page("/home.html", P)
        fresh, fpng = await f.evaluate(STATE), await f.screenshot()
        pg = await page("/home.html", P)
        await _turn(pg, L, put_back=(40, 500))
        await pg.wait_for_timeout(1900)
        side = await pg.evaluate(STATE)
        at0, at1 = await _turn(pg, P)
        await pg.wait_for_timeout(1500)
        return fresh, fpng, side, at0, at1, await pg.evaluate(STATE), await pg.screenshot()
    fresh, fpng, side, at0, at1, d, png = _session(site, fn, init=_theme("light"))
    assert not side["rw"] and side["y"] == 0, side
    assert at0["rw"] and at0["y"] == 80 and at0["root"] == fresh["root"] and at0["theme"] == fresh["theme"], at0
    assert at1["rw"] and at1["y"] == 80 and at1["top"] == [], at1
    _same_page(d, fresh, "upright, on its side, upright")
    assert _top_px(png, fpng) <= 2


def test_classic_home_on_its_side_keeps_its_header_on_screen_once_touched_or_scrolled(site):
    """Until then the header and the two ground layers lie at the page's top: the same pixels. A touch or a scroll fixes them to the screen, as they were."""
    async def fn(page):
        pg = await page("/home.html", L)
        a, before = await pg.evaluate(STATE), await pg.screenshot()
        await pg.evaluate(TOUCH)
        b, after = await pg.evaluate(STATE), await pg.screenshot()
        await pg.evaluate("window.scrollTo(0,300)")
        await pg.wait_for_timeout(300)
        c = await pg.evaluate(STATE)
        cpos = await pg.evaluate("['page-bg','page-glass','title-bar'].map(i=>{const e=document.getElementById(i),r=e.getBoundingClientRect();return [getComputedStyle(e).position,Math.round(r.top),Math.round(r.height)]})")
        p2 = await page("/home.html", L)                           # no touch: a scroll alone
        await p2.evaluate("window.scrollTo(0,300)")
        await p2.wait_for_timeout(300)
        return a, before, b, after, c, cpos, await p2.evaluate(STATE)
    a, before, b, after, c, cpos, s = _session(site, fn, size=L, init=_theme("light"))
    assert a["top"] == [] and a["barPos"] == "absolute", a
    assert b["barPos"] == "fixed" and sorted(b["top"]) == ["page-bg", "page-glass", "title-bar"], b
    x, y = _img(before), _img(after)
    assert max(_d(x.getpixel((i, j))[:3], y.getpixel((i, j))[:3]) for j in range(0, L[1], 2) for i in range(0, L[0], 3)) <= 1, "fixing the header to the screen moved a pixel"
    assert c["y"] == 300 and c["bar"][1] == 0 and all(q == ["fixed", 0, q[2]] and q[2] > 40 for q in cpos), f"scrolled, the header and the ground stay on screen: {c['bar']} {cpos}"
    assert s["y"] == 300 and s["barPos"] == "fixed" and s["bar"][1] == 0, f"a scroll with no touch: {s}"


# ── T1: opened upright, turned on its side ──
@pytest.mark.parametrize("put_back", [(40,), (40, 500), (700,)], ids=["as-the-turn-ends", "twice", "late"])
def test_classic_home_turned_on_its_side_rests_at_its_top_like_a_page_opened_on_its_side(site, put_back):
    async def fn(page):
        fresh = await (await page("/home.html", L)).evaluate(STATE)
        pg = await page("/home.html", P)
        up = await pg.evaluate(STATE)
        await _turn(pg, L, put_back=put_back)
        await pg.wait_for_timeout(1900 - sum(put_back))
        d = await pg.evaluate(STATE)
        # the hold is over: the reader's own scroll is the reader's
        await pg.evaluate("window.scrollTo(0,200)")
        await pg.wait_for_timeout(1300)
        return fresh, up, d, await pg.evaluate("pageYOffset")
    fresh, up, d, later = _session(site, fn, init=_theme("light"))
    assert up["rw"] and up["y"] == 80, up
    print("T1", put_back, "turned: y", d["y"], "list top", d["list"][1], "| opened on its side: y", fresh["y"], "list top", fresh["list"][1])
    assert not d["rw"] and d["y"] == 0, f"turned on its side the page is {d['y']} px down; a page opened on its side is at its top"
    assert max(abs(a - b) for a, b in zip(d["list"], fresh["list"])) <= 1, f"the list {d['list']} is not where a page opened on its side has it {fresh['list']}"
    assert max(abs(a - b) for a, b in zip(d["bar"], fresh["bar"])) <= 1, (d["bar"], fresh["bar"])
    assert later == 200, f"after the turn a scroll is the reader's: {later}"


def test_a_finger_on_the_screen_ends_the_hold(site):
    async def fn(page):
        pg = await page("/home.html", P)
        await _turn(pg, L)
        await pg.wait_for_timeout(60)
        await pg.evaluate(TOUCH)
        await pg.evaluate("window.scrollTo(0,150)")
        await pg.wait_for_timeout(1200)
        return await pg.evaluate("pageYOffset")
    assert _session(site, fn, init=_theme("light")) == 150
