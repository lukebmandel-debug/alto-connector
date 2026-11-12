"""The phone shell (alto/build/phone_shell.py; chunk 2 of ORG/phone-ui-audit-1111.md): one owner of a phone page's edges.

Static checks always; WebKit checks (headless, offline, silent: no cloud env, no account, nothing tapped) when Playwright is installed.
WebKit emulation has no Safari bars and no safe areas, so the strips' look under the bars and the Dynamic Island stay Simulator rows
(ORG/notes-testing/alto-phone-shell/SIM-RECHECK.md); here the insets are injected to test the landscape move."""
import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from alto.build import phone, phone_shell  # noqa: E402


def test_one_runway_block_for_card_and_whole_view():
    assert "phone-whole.rw body" not in phone.CSS and "phone-whole.rw{" not in phone.CSS
    from alto.build import engine_patches as ep
    new = next(p["new"] for p in ep.PATCHES if p["name"] == "mobile-runway-behind-bars")
    assert new.count('<style id="alto-runway">') == 1
    assert "html:is(.mobile,.phone-whole).rw body:not(#_)" in new and "html:is(.mobile,.phone-whole).rw :is(#page-bg,#page-glass)" in new


def test_shell_is_in_head_of_timeline_and_home():
    import phone_matrix as pm
    from alto.build.builder import build_timeline, load_brief
    from alto.build.pages import build_home
    import json
    d = json.loads((ROOT / "samples" / "contracts_brief.json").read_text(encoding="utf-8"))
    tl = build_timeline(*load_brief(d))[0]
    home = build_home([])
    for html in (tl, home):
        assert html.count('id="alto-shell-js"') == 1
        assert html.index('id="alto-shell-js"') < html.index("<body")
        assert "shell=0" in html
    assert pm  # the matrix tool is importable (the WebKit tests below use it)


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
    pages, plans, art = pm.build_pages()
    s = pm.serve(pages, plans, art)
    yield pm, f"http://127.0.0.1:{s.server_address[1]}"
    s.shutdown()


STATE = """() => { const t=document.getElementById('sh-top'), f=document.getElementById('sh-foot'), de=document.documentElement;
 return {html:getComputedStyle(de).backgroundColor, theme:document.getElementById('meta-theme').content, top:t&&getComputedStyle(t).backgroundColor,
   foot:f&&getComputedStyle(f).backgroundColor, sh:de.classList.contains('sh'), off:de.classList.contains('sh-off'), land:de.classList.contains('sh-landscape'),
   left:getComputedStyle(de).getPropertyValue('--sh-left').trim(),
   l:[...document.querySelectorAll('.sh-l')].map(e=>e.getBoundingClientRect()).filter(q=>q.right>0&&q.left<innerWidth).map(q=>Math.round(q.left)),
   r:[...document.querySelectorAll('.sh-r')].map(e=>e.getBoundingClientRect()).filter(q=>q.right>0&&q.left<innerWidth).map(q=>Math.round(innerWidth-q.right))}; }"""
INSET = "document.addEventListener('DOMContentLoaded',()=>{const s=document.createElement('style');s.textContent='#sh-probe{padding-left:60px!important;padding-right:60px!important}';document.head.appendChild(s);});"


def _load(site, page, query, w=402, h=874, init=None, until=None, js=STATE, shot=False, full=False, late=False):
    """The page's state once `until` (a JS expression) holds, polled every 150 ms for up to 15 s; without one, after a fixed 4.5 s settle."""
    pm, base = site

    async def go():
        async with pm._playwright().async_playwright() as p:
            b = await p.webkit.launch()
            ctx = await b.new_context(viewport={"width": w, "height": h}, is_mobile=True, has_touch=True, user_agent=pm.UA)
            if init:
                await ctx.add_init_script(init)
            pg = await ctx.new_page()
            await pg.goto(f"{base}/{page}.html?{query}", wait_until="load", timeout=45000)
            if until:
                for _ in range(100):
                    if await pg.evaluate(until):
                        break
                    await pg.wait_for_timeout(150)
                else:
                    raise AssertionError(f"never held: {until}")
            else:
                await pg.wait_for_timeout(4500)
            out = await pg.evaluate(js)
            if shot:
                # the final paint may land after `until` holds: take shots until two consecutive ones match (bounded to ~6 s)
                prev = await pg.screenshot(full_page=full)
                for _ in range(40):
                    await pg.wait_for_timeout(150)
                    cur = await pg.screenshot(full_page=full)
                    if cur == prev:
                        break
                    prev = cur
                if late:                 # (the layout as it stands in the settled shot, not as it stood before it)
                    out = await pg.evaluate(js)
                out = (out, prev)
            await b.close()
            return out
    try:
        return asyncio.run(go())
    except Exception as e:
        if "Executable doesn't exist" in str(e):
            pytest.skip(f"no WebKit: {e}")
        raise


PEACH = ("rgb(255, 201, 138)", "#ffc59e")


@pytest.mark.parametrize("page,query,want", [("timeline", "view=card&style=retro", "rgb(0, 0, 0)"),
                                             ("timeline", "view=whole&style=holo", "rgb(233, 247, 250)"),
                                             ("home", "style=retro", "rgb(0, 0, 0)")])
def test_edges_take_the_pages_own_ground(site, page, query, want):
    m = _load(site, page, query)
    assert m["sh"] and m["html"] == want == m["top"] == m["foot"], m
    assert m["theme"] not in PEACH


def test_classic_is_left_as_it_was(site):
    m = _load(site, "timeline", "view=card")
    assert m["sh"] and m["top"] is None and m["html"] == PEACH[0] and m["theme"] == PEACH[1], m


def test_shell_0_keeps_the_old_path(site):
    m = _load(site, "timeline", "view=card&style=retro&shell=0")
    assert m["off"] and not m["sh"] and m["top"] is None and m["theme"] in PEACH, m


SETTLED = "document.readyState==='complete' && document.documentElement.classList.contains('sh') && document.documentElement.style.getPropertyValue('--sh-left')!==''"
MOVED = SETTLED + " && document.querySelectorAll('.sh-l').length>0 && document.querySelectorAll('.sh-r').length>0"


EDGE_PIECES = """() => { const q=s=>document.querySelector(s), R=e=>e&&e.getBoundingClientRect();
 const a=['#nav .brand-mark','#nav svg.brand-word','#pmin-find','#hamburger-tab'].map(s=>R(q(s))).filter(r=>r&&r.width>2);
 return {n:a.length, minL:Math.min(...a.map(r=>r.left)), minR:Math.min(...a.map(r=>innerWidth-r.right)), land:document.documentElement.classList.contains('sh-landscape')}; }"""


def test_landscape_corner_chrome_clears_the_island(site):
    # (chunk 5: the header row and the two corner controls place themselves by the insets, 14 pt past them, so nothing is left within the island's reach for the shell's own nudge (.sh-l / .sh-r);
    # what is asked is unchanged: the clef, the wordmark and the two corner controls are all past the inset)
    m = _load(site, "timeline", "view=card", 874, 402, init=INSET, until=SETTLED, js=EDGE_PIECES)
    assert m["land"] and m["n"] == 4 and m["minL"] >= 60 and m["minR"] >= 60, m
    p = _load(site, "timeline", "view=card", 402, 874, init=INSET, until=SETTLED + " && document.documentElement.classList.contains('sh-portrait')")
    assert not p["land"] and not p["l"] and not p["r"], p        # portrait: nothing moves


# ── chunk 2b: the three tint/edge rows the iPhone Simulator failed (ORG/sim-main/sim1111c/report.md S4, S8, S9) ──

ROOT_BG = """() => { const c=getComputedStyle(document.documentElement), pb=getComputedStyle(document.getElementById('page-bg'));
 return {img:c.backgroundImage, size:c.backgroundSize, repeat:c.backgroundRepeat, pb:pb.backgroundImage, board:(window._altoShell||{}).board}; }"""


def test_classic_whole_view_root_continues_the_board(site):
    """S4: Classic's whole view — the root (what Safari shows behind its bars and at the side strips) is the board's own picture, frosted like it, laid at the
    board's box, not the root's differently scaled sunset."""
    m = _load(site, "outline-long", "view=whole", js=ROOT_BG, until=SETTLED)
    assert m["board"] == 1, m
    assert m["img"].startswith("linear-gradient(rgba(250, 251, 255, 0.35)") and m["img"].endswith(m["pb"]), m
    assert m["size"].startswith("100% 1094px") and m["repeat"].startswith("no-repeat"), m


def test_classic_card_view_root_is_untouched(site):
    m = _load(site, "outline-long", "view=card", js=ROOT_BG, until=SETTLED)
    assert not m["board"] and m["img"] == m["pb"] and "rgba(250, 251, 255" not in m["img"], m


def test_holo_home_landscape_takes_the_ground(site):
    """S8: the homepage in landscape is its desktop layout (no runway), so the shell never ran there and theme-color stayed Classic's peach."""
    m = _load(site, "home", "style=holo", 874, 402, until=SETTLED + " && document.documentElement.classList.contains('alto-holo') && (window._altoShell||{}).top")
    assert m["theme"] == "#e9f7fa" and m["html"] == "rgb(233, 247, 250)", m
    assert m["top"] is None and m["foot"] is None, m          # no runway there: no strips


EDGES = """() => { const R=e=>{const q=e.getBoundingClientRect(); return [Math.round(q.left), Math.round(innerWidth-q.right), Math.round(q.top), Math.round(q.bottom)];};
 const one=s=>{const e=document.querySelector(s); return e?R(e):null;}, cv=document.getElementById('canvas');
 return {chip:one('#world .phase-label-float'), num:one('#world .phase-numeral'), sw:cv&&cv.scrollWidth, cw:cv&&cv.clientWidth,
   clef:one('#title-bar .brand-mark'), word:one('#title-bar .brand-word'), slab:one('.project-slab'),
   bg:one('#bg-toggle'), acct:one('#account-btn'), search:one('#search-btn'), info:one('#info-btn'), doc:document.documentElement.scrollWidth, w:innerWidth}; }"""


def test_landscape_whole_view_unit_chips_clear_the_island(site):
    """S9: the whole view's unit chip and its numeral ran 14 px from the screen's edges, under the Dynamic Island; the board now sits between the insets,
    refitted, with nothing to scroll sideways."""
    m = _load(site, "outline-long", "view=whole", 874, 402, init=INSET, js=EDGES,
              until=SETTLED + " && document.querySelector('#world .phase-label-float') && document.getElementById('canvas').scrollWidth<=document.getElementById('canvas').clientWidth+1"
                              " && document.querySelector('#world .phase-label-float').getBoundingClientRect().left>=60"
                              # the shell moves the numeral ~150 ms after the chip: wait for it to hold one position across two polls, then to clear the inset
                              " && (() => { const n = document.querySelector('#world .phase-numeral'); if (!n) return false; const q = n.getBoundingClientRect(), k = q.left + '|' + q.right;"
                              " const same = window.__numLast === k; window.__numLast = k; return same && innerWidth - q.right >= 60; })()")
    assert m["chip"][0] >= 60 and m["num"][1] >= 60, m
    assert m["sw"] <= m["cw"] + 1, m
    p = _load(site, "outline-long", "view=whole", 402, 874, init=INSET, js=EDGES, until=SETTLED + " && !!document.querySelector('#world .phase-label-float')")
    assert p["chip"][0] < 60 and p["cw"] >= 400, p              # portrait: the board keeps the full width


def test_landscape_home_clears_the_island(site):
    """S9: the homepage in landscape — the clef was 20 px from the left, the picture tile on the right edge, the list's slabs 16 px in."""
    m = _load(site, "home", "style=holo", 874, 402, init=INSET, js=EDGES, until=SETTLED + " && document.documentElement.classList.contains('sh-landscape')")
    for k in ("clef", "acct", "slab"):
        assert m[k][0] >= 60, (k, m)
    for k in ("word", "bg", "info", "search", "slab"):
        assert m[k][1] >= 60, (k, m)
    assert m["search"][1] >= m["info"][1] + 30, m              # the bottom-right pair keep their spacing (both moved)
    assert m["doc"] <= m["w"], m


# ── sim1111f (a ?dbg=1 overlay in the real iPhone 18 Pro Simulator): two causes WebKit emulation hid ──
# S4: the board the reader sees is #glass-slab (the units' colour bands at .7, its backdrop saturated) over the glass; the side bands round the board and the
#     runway above / below it showed #page-bg's sunset, so the shell paints those bands with the board's own colour, row by row.
# S8: Mobile Safari (iOS 27) ignores theme-color and tints its landscape toolbar from the root's background colour AS IT STANDS AT FIRST LAYOUT (and again
#     only on a turn): a test page that set the Holo ground in <head> came out pale blue, one that set theme-color there stayed peach. So the shell sets the root
#     colour in <head>, before layout, from what this page last painted or from the chosen look's known ground.


# Where to compare, read from the layout (11 Nov: the fixed points x=30 / x=72, y=100 landed on a unit's chip once the 44 pt header row moved the chip band up): for each row, a
# point in the middle of the band #sh-bl and the nearest point beside it that is bare board: the hit there is the board itself (#canvas, #world, a unit's colour band), and no card,
# chip, unit bar or button drawn in the board has its box within 3 px of it. Rows with no such point within 14 px of the band (a unit bar runs the board's whole width) are left out.
BESIDE = """(() => { var B=document.getElementById('sh-bl').getBoundingClientRect(), cv=document.getElementById('canvas'), ok=function(e){ return !!e&&(/^(canvas|world|glass-slab|river-svg)$/.test(e.id)||(e.classList&&e.classList.contains('phase-band'))); },
  boxes=[], out=[]; cv.querySelectorAll('*').forEach(function(e){ if(ok(e)||e.ownerSVGElement) return; var b=e.getBoundingClientRect(), cs=getComputedStyle(e); if(b.width<1||b.height<1||cs.visibility==='hidden'||cs.display==='none'||+cs.opacity===0) return; boxes.push(b); });
  for(var y=20;y<innerHeight-10;y+=10){ for(var x=Math.ceil(B.right)+2;x<=B.right+14;x+=2){ if(!ok(document.elementFromPoint(x,y))) continue;
      if(boxes.some(function(b){ return x>=b.left-3&&x<=b.right+3&&y>=b.top-3&&y<=b.bottom+3; })) continue; out.push([y,(B.left+B.right)/2,x]); break; } }
  return out; })()"""


@pytest.mark.parametrize("w,h,init", [(402, 714, None), (874, 292, INSET)], ids=["portrait", "landscape-island"])
def test_classic_whole_view_side_bands_continue_the_board(site, w, h, init):
    import io
    from PIL import Image
    until = SETTLED + " && (window._altoShell||{}).board===1 && !!document.getElementById('sh-bl')" + (" && document.documentElement.classList.contains('sh-landscape')" if init else "")
    rows, png = _load(site, "outline-long", "view=whole&ix=0", w, h, init=init, until=until, js=BESIDE, shot=True, late=True)      # (ix=0: the board itself, not the unit index over it, phone_index.py)
    assert len(rows) >= (h - 30) // 10 // 2, rows          # bare board beside the band on at least half the rows: the comparison is not an empty one
    im = Image.open(io.BytesIO(png)).convert("RGB")
    k = im.size[0] / w
    bad = []
    for y, xa, xb in rows:
        a, b = im.getpixel((int(xa * k), int(y * k))), im.getpixel((int(xb * k), int(y * k)))
        if max(abs(a[i] - b[i]) for i in range(3)) > 30:
            bad.append((y, xb, a, b))
    assert not bad, bad          # (was the sunset beside the blue board: (216, 215, 224) against (117, 175, 245) at the top)


def test_the_chosen_looks_root_colour_is_there_before_first_layout(site):
    from alto.build.pages import HOME_BG_KEY
    sk = HOME_BG_KEY[:-3] + "-style" if HOME_BG_KEY.endswith("-bg") else HOME_BG_KEY + "-style"
    init = ("try{localStorage.setItem(%r,'holo');localStorage.removeItem('alto-sh-root');}catch(e){}"
            "document.addEventListener('DOMContentLoaded',function(){window.__dcl=getComputedStyle(document.documentElement).backgroundColor;},{once:true});") % sk
    m = _load(site, "home", "", 874, 292, init=init, until="document.readyState==='complete'", js="window.__dcl")
    assert m == "rgb(233, 247, 250)", m              # (a stored Holo look: already so on the homepage, which turns Holo on in <head>; a guard)
    m = _load(site, "home", "", 402, 714, init=init.replace("'holo'", "'retro'"), until="document.readyState==='complete'", js="window.__dcl")
    assert m == "rgb(0, 0, 0)", m


def test_classic_whole_views_root_is_the_boards_blue_before_first_layout(site):
    """S4 landscape: Safari tints its toolbar from the root colour at first layout; Classic's whole view had its sunset's last stop (peach) there."""
    init = ("try{localStorage.removeItem('alto-sh-root');}catch(e){}"
            "document.addEventListener('DOMContentLoaded',function(){window.__dcl=getComputedStyle(document.documentElement).backgroundColor;},{once:true});")
    m = _load(site, "outline-long", "view=whole", 874, 292, init=init, until="document.readyState==='complete'", js="window.__dcl")
    assert m not in ("rgb(255, 201, 138)", "rgb(255, 197, 158)"), m
    import re
    r, g, b = [int(float(v)) for v in re.findall(r"[\d.]+", m)[:3]]
    assert b > r + 40 and b > 200, m                 # a blue, the board's top
    # and once painted, the page remembers its own colour for the next first layout
    init2 = "document.addEventListener('DOMContentLoaded',function(){window.__dcl=getComputedStyle(document.documentElement).backgroundColor;},{once:true});"
    m2 = _load(site, "outline-long", "view=whole", 874, 292, init=init2, until="document.readyState==='complete' && (window._altoShell||{}).board===1",
               js="[window.__dcl, getComputedStyle(document.documentElement).backgroundColor, localStorage.getItem('alto-sh-root')]")
    assert m2[2] and "outline-long" in m2[2], m2


# ── fable, 11 Nov (Luke: "it wants to reintroduce color bars at top and bottom, which we worked so hard to eliminate") ──
# A full-page WebKit shot shows the runway itself: the 80 px above and the 140 px below the screen box, which Safari shows under its bars. On c73ce161 those
# strips were flat or sampled paint: lanes Classic had the sunset over a blue board (a step of ~100 levels), the System the sunset (Classic) or grey (Holo)
# over black space (~220 / ~85), Holo's grid stopped at the screen box, the Classic whole view was 6 to 10 off, and the closed MENU drawer's shadow lay
# 30 px wide down the right edge. Now a strip is the ground itself carried on (the slab's own gradient and filter; a ground's own repeating layers), so the
# rows either side of each seam must match.
# (view=whole opens on the unit index, phone_index.py; &ix=0 is the board under it: both are checked)
SEAMS = [("lanes", ""), ("lanes", "style=holo"), ("system", ""), ("system", "style=holo"), ("outline-long", "view=whole"), ("outline-long", "view=whole&style=holo"),
         ("outline-long", "view=whole&ix=0"), ("outline-long", "view=whole&ix=0&style=holo"), ("timeline", "view=whole&ix=0"),
         ("timeline", "view=whole"), ("timeline", "view=card&style=holo"), ("timeline", "view=card&style=retro"), ("timeline", "view=card")]


@pytest.mark.parametrize("page,query", SEAMS, ids=[f"{p}-{q or 'classic'}" for p, q in SEAMS])
def test_runway_strips_continue_the_ground(site, page, query):
    import io
    from PIL import Image
    until = SETTLED + " && document.documentElement.classList.contains('sh')" + (" && document.documentElement.classList.contains('alto-%s')" % query.split("style=")[1] if "style=" in query else "")
    _m, png = _load(site, page, query, until=until, js="1", shot=True, full=True)
    im = Image.open(io.BytesIO(png)).convert("RGB")
    assert im.size[1] in (1094, 2188), im.size                  # the screen box plus the runway (80 above, 140 below)
    k = im.size[1] / 1094
    xs = [int(402 * k * t) for t in (.08, .2, .35, .5, .65, .8, .92)]

    def step(y):      # median over 7 columns of the colour step between the row 2 px outside the screen box and the row 1 px inside it
        d = sorted(max(abs(a - b) for a, b in zip(im.getpixel((x, int((y - 2) * k))), im.getpixel((x, int((y + 1) * k))))) for x in xs)
        return d[3]
    top, foot = step(80), -1
    d = sorted(max(abs(a - b) for a, b in zip(im.getpixel((x, int((80 + 874 + 2) * k))), im.getpixel((x, int((80 + 874 - 2) * k))))) for x in xs)
    foot = d[3]
    assert top <= 12 and foot <= 12, (page, query, top, foot)
    # the right edge of the runway: no shadow band from the closed MENU drawer (was 30 to 50 levels darker than 30 px in)
    a, b = im.getpixel((int(400 * k), int(30 * k))), im.getpixel((int(340 * k), int(30 * k)))
    assert max(abs(a[i] - b[i]) for i in range(3)) <= 14, (page, query, a, b)


def test_closed_drawer_casts_no_shadow_and_an_open_one_does(site):
    m = _load(site, "timeline", "view=card", until=SETTLED, js="""() => { const d=document.getElementById('nav-drawer'), a=getComputedStyle(d).boxShadow;
      d.classList.add('open'); const b=getComputedStyle(d).boxShadow; d.classList.remove('open'); return [a,b]; }""")
    assert m[0] == "none" and m[1] != "none", m


def test_slab_strips_are_the_slab_itself(site):
    """The Classic whole view's strips carry the slab's own gradient and backdrop filter (not sampled colours), and stop where the slab stops (a short timeline)."""
    js = """() => { const sl=getComputedStyle(document.getElementById('glass-slab')), g=i=>{const e=document.getElementById(i); return e&&{bg:e.style.backgroundImage, bf:e.style.webkitBackdropFilter||e.style.backdropFilter, h:e.getBoundingClientRect().height}; };
      return {slab:sl.backgroundImage, t:g('sh-bt'), b:g('sh-bb'), l:g('sh-bl')}; }"""
    until = SETTLED + " && (window._altoShell||{}).board===1 && !!document.getElementById('sh-bt')"
    m = _load(site, "outline-long", "view=whole&ix=0", until=until, js=js)          # (ix=0: the board, not the unit index)
    assert m["t"]["bg"].startswith(m["slab"][:60]) and "saturate" in m["t"]["bf"] and m["b"] and m["l"], m
    m = _load(site, "timeline", "view=whole&ix=0", until=until, js=js)          # the sample timeline's board ends mid-screen: no slab strip under the foot
    assert m["t"] and not m["b"] and m["l"]["h"] < 800, m


def test_the_stored_look_colours_the_root_inside_head(site):
    """S8 (sim1111g): the peach toolbar on Holo home in landscape was the harness seeding the style key at the end of <body>, in a new Private tab each time.
    With the key there before the page loads (as it is for a reader who chose the look), the shell's own <head> script sets the root colour."""
    from alto.build.pages import HOME_BG_KEY
    sk = HOME_BG_KEY[:-3] + "-style" if HOME_BG_KEY.endswith("-bg") else HOME_BG_KEY + "-style"
    init = "try{localStorage.setItem(%r,'holo');localStorage.removeItem('alto-sh-root');}catch(e){}" % sk
    m = _load(site, "home", "", 874, 292, init=init, until="document.readyState==='complete'", js="(window._altoShell||{}).early")
    assert m == "#e9f7fa", m


# (ix=0: the board; the unit index over it has its own band check, tests/test_phone_whole_c2.py)
LAND = [("lanes", ""), ("lanes", "style=holo"), ("outline-long", "view=whole&ix=0"), ("outline-long", "view=whole&ix=0&style=holo"), ("system", "style=holo")]


@pytest.mark.parametrize("page,query", LAND, ids=[f"{p}-{q or 'classic'}" for p, q in LAND])
def test_landscape_island_bands_and_runway_continue_the_ground(site, page, query):
    """874 x 292 (Mobile Safari's real landscape box) with 60 px insets: the bands beside the inset canvas and the runway above / below are the ground carried on.
    (lanes Classic had the sunset in the left band; Holo a flat, grid-less band each side; the System a starless one.)"""
    import io
    from PIL import Image
    until = SETTLED + " && document.documentElement.classList.contains('sh-landscape')" + (" && document.documentElement.classList.contains('alto-%s')" % query.split("style=")[1] if "style=" in query else "")
    _m, png = _load(site, page, query, 874, 292, init=INSET, until=until, js="1", shot=True, full=True)
    im = Image.open(io.BytesIO(png)).convert("RGB")
    k = im.size[1] / (292 + 220)

    def mean(x, y, w=16, h=16):
        c = im.crop((int(x * k), int(y * k), int((x + w) * k), int((y + h) * k))).resize((1, 1), Image.BOX).getpixel((0, 0))
        return c
    bad = []
    for name, a, b in [("left band", mean(30, 300), mean(66, 300)), ("right band", mean(874 - 46, 300), mean(874 - 82, 300)),
                       ("top runway", mean(600, 56), mean(600, 84)), ("foot runway", mean(600, 80 + 292 + 4), mean(600, 80 + 292 - 20))]:
        if max(abs(a[i] - b[i]) for i in range(3)) > 14:
            bad.append((name, a, b))
    assert not bad, (page, query, bad)
