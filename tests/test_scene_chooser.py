"""The Scene / Background picker, Luke 2026-11-18 ("glitch with scene chooser", Safari, Holographic home): the card text behind the panel ghosted through
it, the Holographic tiles were pale and five were nearly blank, and the page's side tab peeked out beside the panel.
Each style at a computer width and a phone width, in WebKit and (when installed) Chromium: nothing of the page reads through the open panel, every
tile has loaded and is a real picture (pixel variance), and the side tab is out of sight while the panel is open."""
import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_scene_panel as sp                        # noqa: E402
from test_scene_panel import site                    # noqa: E402,F401  (the fixture)

try:
    import playwright.sync_api as pw
    from PIL import Image, ImageStat
except ImportError:
    pw = None


@pytest.fixture(scope="module", params=["webkit", "chromium"])
def br(request):
    if pw is None:
        pytest.skip("Playwright/PIL is not installed")
    with pw.sync_playwright() as p:
        try:
            b = getattr(p, request.param).launch()
        except Exception as e:
            pytest.skip(f"no {request.param}: {e}")
        yield b
        b.close()


CASES = [(s, w, d) for s in ("classic", "retro", "holo") for w in (1440, 390) for d in ((False, True) if s == "holo" else (s != "classic",))]


def _open(br, site, style, w, dark):
    pg, ctx, errs = sp._go(br, site, "home", w, style=style, dark=dark, height=900 if w > 500 else 844)
    sp._open_panel(pg)
    pg.wait_for_timeout(400)
    return pg, ctx


def _img(png):
    return Image.open(io.BytesIO(png)).convert("RGB")


@pytest.mark.parametrize("style,w,dark", CASES)
def test_nothing_of_the_page_reads_through_the_open_panel(br, site, style, w, dark):
    pg, ctx = _open(br, site, style, w, dark)
    try:
        box = pg.evaluate("(()=>{const r=document.getElementById('bg-panel').getBoundingClientRect();"
                          "const L=Math.max(0,r.left)+14,T=Math.max(0,r.top)+14;return {x:L,y:T,width:Math.min(innerWidth,r.right)-L-14,height:Math.min(innerHeight,r.bottom)-T-14}})()")
        a = _img(pg.screenshot(clip=box))
        # the same panel over a loud, different page: everything else is hidden and the ground is magenta
        pg.add_style_tag(content="html,body{background:#ff00ff !important} body *:not(#bg-panel):not(#bg-panel *){visibility:hidden !important}"
                                 "#page-bg,#glass-slab,canvas,video{display:none !important}")
        pg.wait_for_timeout(300)
        b = _img(pg.screenshot(clip=box))
        import os
        if os.environ.get('DBG'): a.save(os.environ['DBG']+f'/a-{style}-{w}.png'); b.save(os.environ['DBG']+f'/b-{style}-{w}.png')
        from PIL import ImageChops
        diff = max(max(ex) for ex in ImageChops.difference(a, b).getextrema())
        assert diff <= 3, f"the page reads through the panel (max channel difference {diff})"
        alpha = pg.evaluate("getComputedStyle(document.getElementById('bg-panel')).backgroundColor")
        assert alpha.startswith("rgb(") or alpha.endswith(", 1)"), alpha
    finally:
        ctx.close()


@pytest.mark.parametrize("style,w,dark", CASES)
def test_every_scene_tile_has_loaded_and_is_a_real_picture(br, site, style, w, dark):
    pg, ctx = _open(br, site, style, w, dark)
    try:
        n = pg.evaluate("document.querySelectorAll('#bg-panel .bg-tile[data-bg]').length")
        assert n > 8
        seen = 0
        bad = []
        for i in range(n):
            t = pg.query_selector_all("#bg-panel .bg-tile[data-bg]")[i]
            if not t.is_visible():
                continue                                        # (a style hides the sections it does not offer)
            t.scroll_into_view_if_needed(timeout=5000)
            pg.wait_for_timeout(60)
            tid = t.get_attribute("data-bg")
            seen += 1
            if tid in ("c:", None) or tid.startswith("u:"):
                continue
            if t.query_selector("img"):
                for _ in range(40):
                    if t.evaluate("e=>{const i=e.querySelector('img');return i.complete&&i.naturalWidth>0}"):
                        break
                    pg.wait_for_timeout(100)
                else:
                    bad.append((tid, "image never loaded"))
                    continue
            im = _img(t.screenshot())
            W, H = im.size
            top = im.crop((0, 0, W, int(H * .6)))              # (the name strip at the foot is text on a shade)
            st = ImageStat.Stat(top.convert("L"))
            sd, mean = st.stddev[0], st.mean[0]
            if tid.startswith("h-"):
                if mean > 150:
                    bad.append((tid, f"pale: mean luminance {mean:.0f}"))
                if sd < 3:
                    bad.append((tid, f"near-uniform: sd {sd:.1f}"))
            elif tid and not tid.startswith(("c-", "x-")) and sd < 3:
                bad.append((tid, f"near-uniform: sd {sd:.1f}"))
        assert (seen >= 3 or style == "retro") and not bad, (seen, bad)     # (Retro shows the style picker only: no tiles)
    finally:
        ctx.close()


@pytest.mark.parametrize("style,w,dark", CASES)
def test_no_side_tab_is_visible_over_the_open_panel(br, site, style, w, dark):
    pg, ctx = _open(br, site, style, w, dark)
    try:
        v = pg.evaluate("""(()=>{const t=document.getElementById('bg-toggle'); if(!t) return 'none';
          const c=getComputedStyle(t), r=t.getBoundingClientRect(); return (c.display==='none'||c.visibility==='hidden'||+c.opacity===0||!r.width) ? 'hidden' : 'visible'})()""")
        assert v in ("hidden", "none"), v
    finally:
        ctx.close()


@pytest.mark.parametrize("style,w,dark", CASES)
def test_the_last_row_is_fully_visible_at_the_foot_of_the_scroll(br, site, style, w, dark):
    pg, ctx = _open(br, site, style, w, dark)
    try:
        r = pg.evaluate("""(()=>{const b=document.querySelector('#bg-panel .bg-body'); b.scrollTop=b.scrollHeight;
          const bb=b.getBoundingClientRect(); let low=0;
          b.querySelectorAll('.bg-tile,.bg-name,.bg-h,.bg-auto,p,div').forEach(e=>{const r=e.getBoundingClientRect(); if(r.width&&r.height&&getComputedStyle(e).visibility!=='hidden') low=Math.max(low,r.bottom)});
          return {gap:bb.bottom-low}})()""")
        assert r["gap"] >= 8, f"the last row sits {r['gap']:.1f}px from the scroll edge"
    finally:
        ctx.close()


@pytest.mark.parametrize("w", [1440, 390])
def test_a_holographic_tile_is_its_dark_scene_even_in_the_instant_the_theme_class_is_off(br, site, w):
    """Luke's pale tiles: a tile drawn while the page's dark class was off took the light half of its scene (a pale gradient). Holographic is dark-only."""
    pg, ctx = _open(br, site, "holo", w, True)
    try:
        r = pg.evaluate("""async()=>{const t=[...document.querySelectorAll('#bg-panel .bg-tile[data-bg^=h-]')], root=document.documentElement;
          const before=t.map(e=>e.style.background); root.classList.remove('dark');
          await new Promise(r=>queueMicrotask(r));            // (after the pickers' own observers have run, before Holographic puts the class back)
          const during=t.map(e=>e.style.background); return {n:t.length, same:before.every((b,i)=>b===during[i])}}""")
        assert r["n"] >= 11 and r["same"], r
    finally:
        ctx.close()
