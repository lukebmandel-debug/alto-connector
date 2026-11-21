"""v1.9.273: Holo's S1 glass on the top bar's group labels, chips and x, the sub-chip rows and every format's bottom controls (Luke L-1116-110714, L-1118-001345 / B-1118-GLASSCHROME).

Holo only: Classic and Retro are untouched. The glass is the shared S1 plate (the declarations S1_CSS writes), pills stay pills (never a circle on a wide control), a ring shows for keyboard
focus only, a phone's controls keep their size, and the top bar's pieces never overlap. The computed-style checks run in headless WebKit (offline, silent) when Playwright is installed."""
import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

# page -> the controls that must wear the glass
GLASS = {
    "timeline": ["#title-text", "#nav .nav-btn", "#nav .nav-group-label", "#ct-chips", "#search-btn", "#info-btn", "#account-btn", ".alto-edit-pill"],
    "outline-long": ["#nav .nav-btn", "#nav .nav-group-label", "#ct-chips"],
    "system": ["#nav .nav-btn", "#nav .nav-group-label", "#sol-ctl .sol-seg", "#sol-ctl #sol-motion", "#sol-ctl .sol-opt", "#nvo-a"],
    "lanes": ["#nav .nav-btn", "#lanes-nav", "#key-toggle"],
    "city": ["#pal-ctl .pc-pill", "#pal-ctl .pc-city", "#pal-ctl .pc-dirb"],
    "atlas": ["#wpal-root .wp-bar:not(.wp-pick)"],
    "blueprint": ["#bldg-root .bl-btn"],
}
PHONE = ["timeline", "system", "lanes", "city", "atlas"]


def test_static_glass_is_the_shared_s1_plate_and_holo_scoped():
    from alto.build import holo, retro
    for part in (holo.S1_BG, holo.S1_RIM, holo.S1_RIM_HOVER, holo.S1_BLUR.replace(" !important", "").split(";")[0]):
        assert part.replace(" !important", "") in holo.S1_CSS.replace(" !important", ""), part   # the same declaration S1_CSS writes, not a fork
    assert holo.S1_BG in holo.G273_CSS and holo.S1_RIM in holo.G273_CSS and holo.S1_BLUR in holo.G273_CSS
    css = holo.css()
    for sel in ("#nav .nav-btn", "#nav .nav-group-label", "#ct-chips", "#sol-ctl .sol-seg", "#lanes-nav", "#pal-ctl .pc-pill", "#bldg-root .bl-btn"):
        assert f"html.alto-holo {sel}" in css, sel
    assert "#title-bar #title-text" in holo.G273_CSS    # the title tab is a pill now; the clef and wordmark are not touched
    assert "alto-wordmark" not in holo.G273_CSS and "#desk-logo" not in holo.G273_CSS
    assert "G273" not in retro.css() and "saturate(1.5)" not in retro.css().replace("saturate(1.25)","")
    import re
    for rule in filter(None, holo.G273_CSS.split("\n")):
        head = rule.split("{")[0]
        if head.startswith("@media"):
            head = rule.split("{", 1)[1].split("{")[0]
        assert all(part.startswith("X") for part in re.split(r",(?=X)", head)), head[:80]      # X = html.alto-holo: every selector is Holo's
        assert not re.search(r",(?!X)(?![^(]*\))", head), head[:80]


JS_STYLE = """(sels) => sels.map(q => { const els = [...document.querySelectorAll(q)].filter(e => { const r = e.getBoundingClientRect(); const c = getComputedStyle(e); return r.width > 4 && r.height > 4 && c.display !== 'none' && c.visibility !== 'hidden'; });
  if (!els.length) return [q, null];
  const e = els[0], c = getComputedStyle(e), r = e.getBoundingClientRect();
  return [q, {glass: /gradient/.test(c.backgroundImage), blur: /blur/.test(c.backdropFilter || c.webkitBackdropFilter || ''), rad: c.borderRadius, w: r.width, h: r.height}]; })"""
JS_FOCUS = """() => { const b = document.querySelector('#nav .nav-btn') || document.querySelector('#search-btn'); if (!b) return null;
  b.focus({focusVisible: false}); const a = getComputedStyle(b).outlineStyle; return [a, b.matches(':focus-visible')]; }"""
JS_SIZES = """(sels) => sels.map(q => [q, [...document.querySelectorAll(q)].filter(e => { const r = e.getBoundingClientRect(); const c = getComputedStyle(e); return r.width > 4 && r.height > 4 && c.display !== 'none' && c.visibility !== 'hidden'; })
  .slice(0, 6).map(e => { const r = e.getBoundingClientRect(); return [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)]; })])"""
JS_TOP = """() => { const sel = '#title-text,#nav .nav-btn,#nav .nav-group-label,#ct-chips,#desk-logo,.alto-wordmark,#wordmark';
  const els = [...document.querySelectorAll(sel)].filter(e => { const r = e.getBoundingClientRect(); const c = getComputedStyle(e); return r.width > 2 && r.height > 2 && c.display !== 'none' && c.visibility !== 'hidden'; })
    .map(e => { const r = e.getBoundingClientRect(); return [e.id || e.className, r.left, r.top, r.right, r.bottom]; });
  const hits = []; for (let i = 0; i < els.length; i++) for (let j = i + 1; j < els.length; j++) { const a = els[i], b = els[j];
    if (a[1] < b[3] - 1 && a[3] > b[1] + 1 && a[2] < b[4] - 1 && a[4] > b[2] + 1) hits.push([a[0], b[0]]); }
  return {n: els.length, hits}; }"""


def _run(vw, vh, mob, names, js, arg=None, wait=3500, style="holo", patch=None):
    import phone_matrix as pm
    try:
        pw = pm._playwright()
    except ImportError:
        pytest.skip("Playwright is not installed")
    if patch:
        patch()
    pages, plans, art = pm.build_pages()
    s = pm.serve(pages, plans, art)

    async def go():
        res = {}
        async with pw.async_playwright() as p:
            b = await p.webkit.launch()
            for n in names:
                ctx = await b.new_context(viewport={"width": vw, "height": vh}, is_mobile=mob, has_touch=mob, user_agent=pm.UA if mob else None)
                pg = await ctx.new_page()
                await pg.goto(f"http://127.0.0.1:{s.server_address[1]}/{n}.html?style={style}", wait_until="load", timeout=45000)
                await pg.wait_for_timeout(wait)
                res[n] = await pg.evaluate(js, arg) if arg is not None else await pg.evaluate(js)
                await ctx.close()
            await b.close()
        return res
    try:
        return asyncio.run(go())
    except Exception as e:
        if "Executable doesn't exist" in str(e):
            pytest.skip(f"no WebKit: {e}")
        raise
    finally:
        s.shutdown()


def test_every_holo_control_wears_the_glass_and_pills_stay_pills():
    seen = 0
    for n, sels in GLASS.items():
        for q, v in _run(1440, 900, False, [n], JS_STYLE, sels)[n]:
            if v is None:
                continue
            seen += 1
            assert v["glass"] and v["blur"], (n, q, "no S1 glass", v)
            assert v["rad"] != "50%", (n, q, "a circle", v)
            if v["w"] > v["h"] * 1.4:
                assert v["rad"] not in ("50%", "0px"), (n, q, "wide control is not a pill", v)
    assert seen >= 18


@pytest.mark.parametrize("style", ["classic", "retro"])
def test_other_styles_are_unchanged(style):
    sels = ["#nav .nav-btn", "#nav .nav-group-label", "#ct-chips"]
    for q, v in _run(1440, 900, False, ["timeline"], JS_STYLE, sels, style=style)["timeline"]:
        if v is not None:
            assert not (v["glass"] and v["blur"]), (style, q, "Holo glass leaked", v)


def test_focus_ring_only_for_keyboard_focus():
    r = _run(1440, 900, False, ["timeline"], JS_FOCUS)["timeline"]
    assert r and r[0] == "none" and r[1] is False, r    # a script/mouse focus draws no ring
    from alto.build import holo
    assert "html.alto-holo #nav .nav-btn:focus-visible" in holo.css() and "#ct-chips:focus-visible" in holo.css()
    assert ":focus:not(:focus-visible)" in holo.G273_CSS


def test_phone_controls_keep_their_size():
    from alto.build import holo
    sels = sorted({s for p in PHONE for s in GLASS[p]})
    after = _run(390, 844, True, PHONE, JS_SIZES, sels)
    saved = holo.G273_CSS
    try:
        before = _run(390, 844, True, PHONE, JS_SIZES, sels, patch=lambda: setattr(holo, "G273_CSS", ""))
    finally:
        holo.G273_CSS = saved
    n = 0
    for p in PHONE:
        for (q, a), (_q, b) in zip(after[p], before[p]):
            assert [x[2:] for x in a] == [x[2:] for x in b], (p, q, "a phone control changed size", a, b)    # glass paints; it never resizes a 44pt target
            n += len(a)
    assert n >= 2


@pytest.mark.parametrize("vw,vh,mob", [(1440, 900, False), (2000, 1100, False), (390, 844, True)])
def test_top_bar_pieces_never_overlap(vw, vh, mob):
    r = _run(vw, vh, mob, ["timeline", "outline-long", "system"], JS_TOP)
    for n, v in r.items():
        assert not v["hits"], (n, v)
        assert v["n"] > 0 or mob     # (a phone's header is its own one-card strip: nothing of the desktop's bar is there to overlap)
