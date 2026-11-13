"""Phone prev / next bar, option B (Luke 2026-11-12, Art sheet 1112-navbar): the card view's strip and the detail page's strip are ONE glass pill at the foot, between FIND and MENU,
and the unit colour stays only as the progress hairline. Measured in WebKit on upright phones (headless, offline, silent; no cloud env):

  * the pill sits between the two corner controls (FIND, MENU / NOTES) with no overlap, on the card view and on a detail page, in Classic, Retro and Holo, light and dark;
  * the header is clear: Classic paints no unit colour on it or on a strip at the top;
  * "Back to" sits above the pill and never over it;
  * every touch target in the pill is at least 44 pt;
  * the pill stays still across a swipe: the same box, the same height, on every card of a timeline (Luke: "the text shouldn't jump and the background shouldn't jump");
  * ONE height for a timeline: exactly 52 pt if any of its names wraps at this width, else 44; one past two lines is cut with an ellipsis and a press-and-hold shows it whole (and does not turn the page);
  * the hairline along its foot fills by the card's place in the timeline, in the unit's colour (Classic);
  * the names are one type in every style: mixed case, no tracking;
  * on a detail page the pill's ground is solid (Retro, Holo) or the page's own ground with the blur (Classic); the card view keeps the glass;
  * "Back to Overview" is the "Back to" pill of each style under the header, not a band, and the page's text starts well under it;
  * on its side the names stay in the title row (card view and detail page) with no ground of their own, over nothing in the header.
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

R = "const R=e=>{if(!e)return null;const r=e.getBoundingClientRect();return {l:r.left,t:r.top,r:r.right,b:r.bottom,w:r.width,h:r.height}},$=i=>document.getElementById(i);"
STY = {"classic": "", "retro": "&style=retro", "holo": "&style=holo"}


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
    for name in ("timeline", "short"):
        brief = json.loads((ROOT / "samples" / "contracts_brief.json").read_text(encoding="utf-8"))
        if name == "short":            # the same timeline with one-word names: none wraps
            for n in brief["nodes"]:
                n["title"] = n["title"].split()[0]
        html = build_timeline(*load_brief(brief))[0]
        i = html.rfind("</body>")
        html = html[:i] + pm.LOADER % json.dumps(man) + html[i:]
        j = html.find('<script id="alto-shell-js">')
        pages[name] = html[:j] + pm.SEED + html[j:] if j >= 0 else html
    s = pm.serve(pages, {}, {})
    yield pm, f"http://127.0.0.1:{s.server_address[1]}"
    s.shutdown()


def _run(site, fn, style="classic", theme="light", w=402, h=874, land=False, page="timeline"):
    pm, base = site

    async def go():
        async with pm._playwright().async_playwright() as p:
            b = await p.webkit.launch()
            ctx = await b.new_context(viewport={"width": w, "height": h}, is_mobile=True, has_touch=True, user_agent=pm.UA)
            await ctx.add_init_script("try{localStorage.setItem('alto-theme-v1',%r)}catch(e){}" % theme)
            pg = await ctx.new_page()
            try:
                await pg.goto(f"{base}/{page}.html?view=card" + STY[style], wait_until="load", timeout=45000)
                await pg.wait_for_timeout(2600 if style != "classic" else 1500)
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


TE = """const te=(tg,type,x,y)=>{const a={identifier:1,target:tg,clientX:x,clientY:y,pageX:x,pageY:y,screenX:x,screenY:y};const e=new Event(type,{bubbles:true,cancelable:true});
  Object.defineProperty(e,'touches',{value:type==='touchend'?[]:[a]});Object.defineProperty(e,'targetTouches',{value:type==='touchend'?[]:[a]});Object.defineProperty(e,'changedTouches',{value:[a]});tg.dispatchEvent(e);};"""
GEO = "()=>{" + R + """return {bar:R($('timeline-label-bar')), prev:R($('tlb-prev')), next:R($('tlb-next')), find:R($('pmin-find')), menu:R($('hamburger-tab')), nav:R($('nav')),
  navBg:getComputedStyle($('nav'),'::before').backgroundColor, navBg2:getComputedStyle($('nav')).backgroundColor, pos:getComputedStyle($('timeline-label-bar')).position, vh:innerHeight, vw:innerWidth}}"""
DET = "()=>{" + R + """const n=$('node-nav-bar'),d=$('detail-page');return {bar:R(n), vis:n.classList.contains('visible'), prev:R($('nav-prev-label')), next:R($('nav-next-label')), find:R($('search-toggle')), notes:R($('notes-toggle')),
  bg:getComputedStyle(n).backgroundColor, bi:getComputedStyle(n).backgroundImage, bf:getComputedStyle(n).webkitBackdropFilter||getComputedStyle(n).backdropFilter,
  type:['nav-prev-label','nav-next-label'].map(i=>{const c=getComputedStyle($(i));return [c.textTransform,c.letterSpacing,c.fontFamily.split(',')[0]]}),
  back:R($('alto-back-prev')), backHidden:$('alto-back-prev')&&$('alto-back-prev').hasAttribute('hidden'), page:R(d), nav:R($('nav')), navBg:getComputedStyle($('nav'),'::before').backgroundColor, vh:innerHeight}}"""


def _apart(a, b, what):
    assert a["r"] <= b["l"] + 0.5 or b["r"] <= a["l"] + 0.5 or a["b"] <= b["t"] + 0.5 or b["b"] <= a["t"] + 0.5, f"{what}: {a} overlaps {b}"


@pytest.mark.parametrize("style,theme", [("classic", "light"), ("classic", "dark"), ("retro", "dark"), ("holo", "dark")])
@pytest.mark.parametrize("w,h", [(402, 874), (375, 812)])
def test_the_card_views_pill_sits_between_find_and_menu(site, style, theme, w, h):
    async def fn(pg):
        await pg.evaluate("document.getElementById('tlb-next').click()")
        await pg.wait_for_timeout(800)
        return await pg.evaluate(GEO)
    g = _run(site, fn, style, theme, w, h)
    b, f, m = g["bar"], g["find"], g["menu"]
    assert b["t"] > g["vh"] * .8 and abs(b["b"] - f["b"]) < 1.5, f"the pill is at the foot, on the controls' line: {b} {f}"
    assert b["l"] >= f["r"] + 6 and b["r"] <= m["l"] - 6, f"between FIND and MENU: {b} {f} {m}"
    _apart(b, f, "pill / FIND")
    _apart(b, m, "pill / MENU")
    assert abs(b["h"] - 52) < 0.05, f"exactly 52 pt in a timeline with a name that wraps (Carlill v. Carbolic Smoke Ball), in every style: {b['h']}"
    for k in ("prev", "next"):
        assert g[k]["h"] >= 43.5 and g[k]["w"] >= 44, f"touch target {k}: {g[k]}"
    assert b["w"] > 150 and g["pos"] == "fixed"
    if style == "classic":
        assert g["navBg"] in ("rgba(0, 0, 0, 0)", "transparent") and g["navBg2"] in ("rgba(0, 0, 0, 0)", "transparent"), f"the header carries no unit colour: {g['navBg']} {g['navBg2']}"


@pytest.mark.parametrize("style,theme", [("classic", "light"), ("retro", "dark"), ("holo", "dark")])
def test_a_detail_pages_pill_sits_between_find_and_notes_and_back_to_stays_above_it(site, style, theme):
    async def fn(pg):
        await pg.evaluate("showDetail('node', NODE_ORDER[1])")
        await pg.wait_for_timeout(900)
        d0 = await pg.evaluate(DET)
        await pg.evaluate("document.querySelector('#detail-content').dispatchEvent(new Event('mousedown',{bubbles:true}));showDetail('node', NODE_ORDER[3])")
        await pg.wait_for_timeout(900)
        return d0, await pg.evaluate(DET)
    d0, d = _run(site, fn, style, theme)
    for x in (d0, d):
        b = x["bar"]
        assert x["vis"] and b["t"] > x["vh"] * .8, f"the strip is the pill at the foot: {b}"
        _apart(b, x["find"], "pill / FIND")
        _apart(b, x["notes"], "pill / NOTES")
        assert b["l"] >= x["find"]["r"] + 6 and b["r"] <= x["notes"]["l"] - 6
        assert x["prev"]["h"] >= 43.5 and x["next"]["h"] >= 43.5 and x["prev"]["w"] >= 44
        assert abs(x["page"]["t"] - x["nav"]["b"]) < 1.5, f"the page starts under the 52 pt header: {x['page']['t']} {x['nav']['b']}"
    assert not d["backHidden"] and d["back"], "a hop from a page shows Back to"
    assert d["back"]["b"] <= d["bar"]["t"] - 4, f"Back to above the pill: {d['back']} {d['bar']}"
    assert d["back"]["l"] >= 0 and d["back"]["r"] <= 402
    for x in (d0, d):
        assert all(t[0] == "none" and t[1] in ("normal", "0px") and t[2].strip('"') == "Georgia" for t in x["type"]), f"one type in every style, mixed case, no tracking: {x['type']}"
        assert abs(x["bar"]["h"] - 52) < 0.05, f"the same 52 pt as the card view's: {x['bar']['h']}"
    if style == "classic":
        assert d["navBg"] not in ("rgba(0, 0, 0, 0)", "transparent"), "on a detail page the header takes the page's ground"
        assert d["bi"].count("gradient") == 3 and "blur" in d["bf"], f"Classic: the page's own ground three times over (.62 -> .94) with the blur: {d['bi']} {d['bf']}"
    else:
        assert d["bg"].startswith("rgb(") and "gradient" not in d["bi"], f"Retro and Holo: a solid ground, no text reads through: {d['bg']}"


BOX = "(()=>{const b=[...document.querySelectorAll('#timeline-label-bar,#node-nav-bar')].find(e=>e.offsetHeight),r=b.getBoundingClientRect(),t=[...b.querySelectorAll('.nb-t,.wrap-pill')].map(e=>{const q=e.getBoundingClientRect();return [q.height,q.top+q.height/2]});" \
      "return {box:[r.left,r.top,r.width,r.height],lines:t,names:b.textContent,p:b.style.getPropertyValue('--nb-p'),u:getComputedStyle(b).getPropertyValue('--nb-u').replace(/\\s/g,''),unit:b.style.getPropertyValue('--nb-unit').replace(/\\s/g,'')}})()"


def test_the_pill_stays_still_across_a_swipe(site):
    """Two finger swipes across detail pages whose names go from one line to two: the pill's box (place AND height) is the same in every frame and after each."""
    async def fn(pg):
        await pg.evaluate("showDetail('node', NODE_ORDER[0])")
        await pg.wait_for_timeout(900)
        a = await pg.evaluate(BOX)
        out = []
        for _ in range(2):
            await pg.evaluate("""async()=>{""" + TE + """const d=document.getElementById('detail-page'),raf=()=>new Promise(r=>requestAnimationFrame(r)),rec=()=>{const r=document.getElementById('node-nav-bar').getBoundingClientRect();window.__s.push([r.left,r.top,r.width,r.height]);};
              window.__s=[];te(d,'touchstart',260,500);await raf();for(let n=1;n<=12;n++){te(d,'touchmove',260-n*14,500);await raf();rec();}te(d,'touchend',92,500);setTimeout(rec,700);}""")
            await pg.wait_for_timeout(1400)
            out.append((await pg.evaluate("window.__s"), await pg.evaluate(BOX)))
        return a, out
    a, out = _run(site, fn)
    names = [a["names"]] + [z["names"] for _s, z in out]
    assert len(set(names)) == 3, f"each swipe turned the page: {names}"
    assert {len(z["lines"]) and max(l[0] for l in z["lines"]) > 20 for z in [a] + [z for _s, z in out]} == {True, False}, "the swipes pass one-line and two-line names"
    for s, z in out:
        assert len(s) >= 12
        for r in s + [z["box"]]:
            assert all(abs(r[k] - a["box"][k]) < 0.05 for k in range(4)), f"the pill moved or changed height on a swipe: {r} vs {a['box']}"


@pytest.mark.parametrize("page,want", [("timeline", 52), ("short", 44)])
@pytest.mark.parametrize("style,theme,w,h", [("classic", "light", 402, 874), ("classic", "light", 375, 812), ("retro", "dark", 402, 874), ("holo", "dark", 402, 874)])
def test_one_pill_height_for_a_whole_timeline_and_the_hairline_fills_by_position(site, page, want, style, theme, w, h):
    """Every card of the card view, then every detail page: one box. 52 pt exactly where a name of the timeline wraps, 44 where none does; a one-line name is on the same line on every card."""
    async def fn(pg):
        n = await pg.evaluate("NODE_ORDER.length")
        card, det = [], []
        for i in range(n):
            await pg.evaluate("document.getElementById('tlb-next').click()")
            await pg.wait_for_timeout(350)
            card.append((await pg.evaluate("NODE_ORDER.indexOf(window._featuredNodeId)"), await pg.evaluate(BOX)))
        for i in range(n):
            await pg.evaluate("i=>showDetail('node', NODE_ORDER[i])", i)
            await pg.wait_for_timeout(350)
            det.append((i, await pg.evaluate(BOX)))
        return n, card, det, await pg.evaluate("document.documentElement.style.getPropertyValue('--nb-h')")
    n, card, det, nbh = _run(site, fn, style, theme, w, h, page=page)
    first = card[0][1]["box"]
    assert abs(first[3] - want) < 0.05, f"{want} pt: {first}"
    assert nbh == f"{want}px", f"--nb-h tells Back to: {nbh}"
    two = False
    for i, z in card + det:
        assert all(abs(z["box"][k] - first[k]) < 0.05 for k in range(4)), f"one box on every card and page: {z['box']} vs {first}"
        assert abs(float(z["p"]) - (i + 1) / n) < 0.001, f"the hairline fills by position: card {i} of {n}: {z['p']!r}"
        if style == "classic":
            assert z["unit"].startswith("rgb(") and z["u"] == z["unit"], f"in the unit's colour, read on the bar itself: {z['u']!r} {z['unit']!r}"
        for hgt, mid in z["lines"]:
            two = two or hgt > 20
            if hgt < 20:
                assert abs(mid - (first[1] + (want - 1) / 2)) < 4, f"a one-line name sits on the same line on every card: {mid} in {first}"
    assert two == (want == 52), "a name wraps in this timeline exactly when the pill is 52 pt"


def test_a_long_name_wraps_to_two_lines_and_a_longer_one_is_cut_but_can_be_held_to_read(site):
    async def fn(pg):
        await pg.evaluate("document.getElementById('tlb-next').click()")
        await pg.wait_for_timeout(800)
        g0 = await pg.evaluate(GEO)
        # (a name from outside the timeline's own, a character's or a theme's: the pill takes 52 pt from then on)
        await pg.evaluate("(()=>{document.getElementById('tlb-next').textContent='Carlill v. Carbolic Smoke Ball and Another';})()")
        await pg.wait_for_timeout(300)
        g1 = await pg.evaluate(GEO + "")
        h1 = await pg.evaluate("document.documentElement.style.getPropertyValue('--nb-h')")
        await pg.evaluate("(()=>{document.getElementById('tlb-next').textContent=" + json.dumps("Carlill v. Carbolic Smoke Ball and the extraordinarily long name of a case that nobody could ever fit on two lines of a pill") + ";})()")
        await pg.wait_for_timeout(300)
        cut = await pg.evaluate("(()=>{const s=document.querySelector('#tlb-next .nb-t');return [s.scrollHeight>s.clientHeight+1, getComputedStyle(s).webkitLineClamp, document.getElementById('tlb-next').title]})()")
        g2 = await pg.evaluate(GEO)
        # a press-and-hold with a finger: the whole name appears, and letting go does not turn the page
        before = await pg.evaluate("window._featuredNodeId")
        await pg.evaluate("()=>{" + TE + "const l=document.getElementById('tlb-next'),r=l.getBoundingClientRect();te(l,'touchstart',r.left+20,r.top+20);}")
        await pg.wait_for_timeout(800)
        shown = await pg.evaluate("(()=>{const f=document.getElementById('nb-full');return f?f.textContent:null})()")
        await pg.evaluate("()=>{" + TE + "const l=document.getElementById('tlb-next'),r=l.getBoundingClientRect();te(l,'touchend',r.left+20,r.top+20);l.click();}")
        await pg.wait_for_timeout(500)
        gone = await pg.evaluate("!document.getElementById('nb-full')")
        after = await pg.evaluate("window._featuredNodeId")
        await pg.evaluate("document.getElementById('tlb-prev').click()")
        await pg.wait_for_timeout(500)
        return g0, g1, g2, h1, cut, shown, gone, before, after, await pg.evaluate(GEO)
    g0, g1, g2, h1, cut, shown, gone, before, after, g3 = _run(site, fn, page="short")
    assert abs(g0["bar"]["h"] - 44) < 0.05 and abs(g1["bar"]["h"] - 52) < 0.05 and abs(g2["bar"]["h"] - 52) < 0.05, f"44 with one-line names, exactly 52 with a wrapped one, and no more with a cut one: {g0['bar']['h']} {g1['bar']['h']} {g2['bar']['h']}"
    assert abs(g3["bar"]["h"] - 52) < 0.05, f"and it does not shrink back on the next card: {g3['bar']['h']}"
    assert abs(g1["bar"]["b"] - g0["bar"]["b"]) < 0.5, "the same foot"
    assert h1 == "52px", f"--nb-h tells Back to: {h1}"
    assert cut[0] and cut[1] == "2" and "extraordinarily" in cut[2], f"cut with an ellipsis after two lines, the full name kept: {cut}"
    assert shown and "extraordinarily long name" in shown and "pill" in shown, f"press-and-hold shows the name: {shown}"
    assert gone and before == after, f"letting go hides it and does not move the page: {before} {after}"


@pytest.mark.parametrize("style,theme", [("classic", "light"), ("classic", "dark"), ("retro", "dark"), ("holo", "light"), ("holo", "dark")])
def test_back_to_overview_is_the_back_to_pill_under_the_header_and_the_page_starts_well_under_it(site, style, theme):
    async def fn(pg):
        await pg.evaluate("showDetail('node', NODE_ORDER[1])")
        await pg.wait_for_timeout(900)
        await pg.evaluate("document.querySelector('#detail-content').dispatchEvent(new Event('mousedown',{bubbles:true}));showDetail('node', NODE_ORDER[3])")
        await pg.wait_for_timeout(900)
        q = "()=>{" + R + """const L=i=>{const e=$(i),c=getComputedStyle(e);return {r:R(e),bg:c.backgroundColor,col:c.color,rad:c.borderTopLeftRadius,sh:c.boxShadow,font:c.fontSize+' '+c.fontFamily,ls:c.letterSpacing}};
          const d=$('detail-page'),f=d.querySelector('#detail-content *');return {bto:L('back-to-overview-bar'),bp:L('alto-back-prev'),nav:R($('nav')),page:R(d),first:f.getBoundingClientRect().top,hit:document.elementFromPoint(innerWidth/2,R($('back-to-overview-bar')).t-3).id,vw:innerWidth}}"""
        p0 = await pg.evaluate("document.getElementById('detail-page').querySelector('#detail-content *').getBoundingClientRect().top")
        # (the engine shows the bar and sets the page's top inline when a page is opened from the Overview)
        await pg.evaluate("(()=>{document.getElementById('back-to-overview-bar').classList.add('visible');document.getElementById('detail-page').style.top='138px'})()")
        await pg.wait_for_timeout(500)
        return p0, await pg.evaluate(q)
    p0, g = _run(site, fn, style, theme)
    o, b = g["bto"], g["bp"]
    assert o["r"]["w"] < g["vw"] - 100 and abs((o["r"]["l"] + o["r"]["r"]) / 2 - g["vw"] / 2) < 1, f"a pill in the middle, not a band from edge to edge: {o['r']}"
    assert 4 <= o["r"]["t"] - g["nav"]["b"] <= 8, f"just under the header: {o['r']} {g['nav']}"
    for k in ("bg", "col", "rad", "sh", "font", "ls"):
        assert o[k] == b[k], f"the look of this style's Back to pill ({k}): {o[k]!r} vs {b[k]!r}"
    assert abs(o["r"]["h"] - b["r"]["h"]) < 0.5
    assert g["hit"] == "back-to-overview-bar", "a 44 pt touch target around it"
    assert abs(g["page"]["t"] - g["nav"]["b"]) < 1.5, f"the page keeps its place under the header (one ground, no band of the scene): {g['page']}"
    assert g["first"] - o["r"]["b"] >= 40 and abs((g["first"] - o["r"]["b"]) - (p0 - g["nav"]["b"])) < 6, f"its text starts as far under the pill as it did under the header: {g['first']} {o['r']} (was {p0})"


def test_the_pill_fades_after_three_and_a_half_seconds_and_the_first_tap_on_it_still_acts(site):
    async def fn(pg):
        await pg.evaluate("document.getElementById('tlb-next').click()")
        await pg.wait_for_timeout(400)
        await pg.evaluate("window._altoPhoneMinApi.wake()")
        await pg.wait_for_timeout(2500)
        lit = await pg.evaluate("getComputedStyle(document.getElementById('timeline-label-bar')).opacity")
        await pg.wait_for_timeout(2200)
        idle = await pg.evaluate("[document.documentElement.classList.contains('pmin-idle'), getComputedStyle(document.getElementById('timeline-label-bar')).opacity]")
        r = await pg.evaluate("(()=>{const r=document.getElementById('tlb-next').getBoundingClientRect();return [r.left+r.width/2,r.top+r.height/2,window._featuredNodeId]})()")
        await pg.touchscreen.tap(r[0], r[1])
        await pg.wait_for_timeout(900)
        return lit, idle, r[2], await pg.evaluate("window._featuredNodeId"), await pg.evaluate("getComputedStyle(document.getElementById('timeline-label-bar')).opacity")
    lit, idle, before, after, woke = _run(site, fn)
    assert float(lit) > 0.9, f"lit for 3.5 s after a touch: {lit}"
    assert idle[0] and float(idle[1]) < 0.05, f"faded with the corner controls: {idle}"
    assert after != before and float(woke) > 0.9, f"the first tap on the faded pill turns the card and wakes it: {before} -> {after}, {woke}"


def test_the_dead_filter_bar_offsets_are_gone():
    from alto.build import phone_minimal
    css = phone_minimal._nb_port()
    assert "filter-active" not in css and "mobile-filter-bar" not in css and "130px" not in css


@pytest.mark.parametrize("style,theme", [("classic", "light"), ("retro", "light"), ("retro", "dark"), ("holo", "light"), ("holo", "dark")])
def test_on_its_side_a_detail_pages_names_have_no_ground_and_cover_nothing_in_the_header(site, style, theme):
    async def fn(pg):
        await pg.add_style_tag(content="#sh-probe{padding-left:62px!important;padding-right:62px!important}")
        await pg.evaluate("showDetail('node', NODE_ORDER[2])")
        await pg.wait_for_timeout(900)
        return await pg.evaluate("()=>{" + R + """const c=e=>getComputedStyle(e),n=$('node-nav-bar'),clear=x=>x==='rgba(0, 0, 0, 0)'||x==='transparent',t=s=>R(document.querySelector(s));
          return {bar:[c(n).backgroundColor,c(n).backgroundImage,c(n).borderBottomWidth,c(n).boxShadow,c(n).webkitBackdropFilter||c(n).backdropFilter,c(n,'::before').backgroundColor,c(n,'::after').backgroundColor],
            labs:['nav-prev-label','nav-next-label'].map(i=>[c($(i)).backgroundColor,c($(i)).boxShadow,c($(i)).textTransform,c($(i)).letterSpacing]),
            text:['nav-prev-label','nav-next-label'].map(i=>R($(i).querySelector('.nb-t,.wrap-pill')||$(i))),
            head:[t('#nav .brand-mark'),t('#nav .title'),t('#nav>svg:not(.brand-mark)'),R($('back-btn'))].filter(Boolean), rule:c($('nav')).borderBottomWidth, h:R(n).h}}""")
    g = _run(site, fn, style, theme, w=874, h=292)
    clear = ("rgba(0, 0, 0, 0)", "transparent")
    b = g["bar"]
    assert b[0] in clear and b[1] == "none" and b[2] == "0px" and b[3] == "none" and b[4] in ("none", "") and b[5] in clear and b[6] in clear, f"the row has no ground and no border: {b}"
    for lab in g["labs"]:
        assert lab[0] in clear and lab[1] == "none" and lab[2] == "none" and lab[3] in ("normal", "0px"), f"a name has no plate, and the one type: {lab}"
    assert len(g["head"]) >= 3 and g["h"] <= 44.5
    for tx in g["text"]:
        assert tx["h"] < 20, f"one line in the title row: {tx}"
        for hd in g["head"]:
            _apart(tx, hd, "a name / the clef, title, Alto or the back button")


@pytest.mark.parametrize("detail", [False, True])
def test_on_its_side_the_names_stay_in_the_title_row(site, detail):
    async def fn(pg):
        await pg.add_style_tag(content="#sh-probe{padding-left:62px!important;padding-right:62px!important}")
        if detail:
            await pg.evaluate("showDetail('node', NODE_ORDER[1])")
        await pg.wait_for_timeout(900)
        pn, nn = ("nav-prev-label", "nav-next-label") if detail else ("tlb-prev", "tlb-next")
        return await pg.evaluate("()=>{" + R + f"return {{bar:R($('node-nav-bar')), tlb:R($('timeline-label-bar')), nav:R($('nav')), page:R($('detail-page')), p:R($('{pn}')), n:R($('{nn}'))}}}}")
    g = _run(site, fn, w=874, h=292)
    b = g["bar"] if detail else g["tlb"]
    assert b["t"] < 1 and b["h"] <= 44.5, f"the names are in the 44 pt title row: {b}"
    assert g["p"]["h"] >= 43.5 and g["n"]["h"] >= 43.5
    if detail:
        assert abs(g["page"]["t"] - 44) < 1.5, f"the page starts under the row: {g['page']}"


BACKTO = "()=>{" + R + """const b=$('alto-back-prev'),n=$('node-nav-bar'),dp=$('detail-page'),cs=getComputedStyle(b),
  tw=document.createTreeWalker($('detail-content'),NodeFilter.SHOW_TEXT),rb=R(b),lines=[];let t;
  while(t=tw.nextNode()){if(!t.textContent.trim())continue;const rg=document.createRange();rg.selectNodeContents(t);for(const q of rg.getClientRects())if(q.width>1&&q.height>1)lines.push([q.left,q.top,q.right,q.bottom])}
  const hit=lines.filter(q=>q[0]<rb.r&&q[2]>rb.l&&q[1]<rb.b&&q[3]>rb.t).length;
  return {pill:rb,nav:R(n),hidden:b.hasAttribute('hidden'),inPage:b.parentNode===dp,col:cs.color,bg:cs.backgroundColor,op:cs.opacity,hit,before:getComputedStyle(b,'::before').content}}"""


def _lum(c):
    v = [float(x) for x in c[c.index("(") + 1:c.index(")")].split(",")[:3]]
    f = lambda u: (u / 255 / 12.92) if u / 255 <= .03928 else (((u / 255) + .055) / 1.055) ** 2.4
    return .2126 * f(v[0]) + .7152 * f(v[1]) + .0722 * f(v[2])


def _contrast(a, b):
    la, lb = _lum(a), _lum(b)
    return (max(la, lb) + .05) / (min(la, lb) + .05)


@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
@pytest.mark.parametrize("theme", ["light", "dark"])
def test_back_to_overlaps_no_page_text_and_no_nav_pill_and_reads(site, style, theme):
    async def fn(pg):
        await pg.evaluate("showDetail('node', NODE_ORDER[1])")
        await pg.wait_for_timeout(900)
        await pg.evaluate("document.querySelector('#detail-content').dispatchEvent(new Event('mousedown',{bubbles:true}));showDetail('node', NODE_ORDER[3])")
        await pg.wait_for_timeout(900)
        res = []
        for y in (0, 120, 400, 800):   # the page scrolled: Back to goes away with the content, never over a line
            await pg.evaluate("y=>{document.getElementById('detail-page').scrollTop=y}", y)
            await pg.wait_for_timeout(150)
            res.append(await pg.evaluate(BACKTO))
        return res
    for d in _run(site, fn, style, theme):
        assert not d["hidden"] and d["inPage"], "a hop from a page shows Back to, inside the page's own top margin"
        _apart(d["pill"], d["nav"], "Back to / nav pill")
        assert d["hit"] == 0, f"Back to overlaps {d['hit']} lines of page text"
        assert d["before"] in ("none", "normal"), "nothing is painted behind it: no band"
        assert float(d["op"]) == 1
        assert d["bg"].startswith("rgb(") or d["bg"].endswith(", 1)"), f"an opaque ground: {d['bg']}"
        assert _contrast(d["col"], d["bg"]) >= 4.5, f"Back to text reads (4.5+): {d['col']} on {d['bg']}"
