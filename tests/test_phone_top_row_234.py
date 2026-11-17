"""v1.9.234: the homepage's phone top row (account, search, Scene, info, light/dark) keeps a 20 px gap from the screen edge (was 14),
in Classic, Retro and Holo, light and dark, at 390 and at 320 wide: 44 pt boxes, nothing overlapping, every control still there.
WebKit (headless, offline, silent) when Playwright is installed; a static check always."""
import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))


def test_static_edge_values_are_20():
    t = (ROOT / "alto" / "engine" / "home_template.html").read_text(encoding="utf-8")
    assert "#account-btn{ left:20px !important; }" in t and "#mode-toggle{ right:20px !important;" in t
    assert "#info-btn{ right:72px !important;" in t and "left:72px !important; right:auto !important; transform:none" in t
    r = (ROOT / "alto" / "engine" / "reports_template.html").read_text(encoding="utf-8")
    assert "#account-btn{ left:20px !important; }" in r and "#mode-toggle{ right:20px !important;" in r and "max-width:349px" in r
    assert (ROOT / "engine" / "reports_template.html").read_bytes() == (ROOT / "alto" / "engine" / "reports_template.html").read_bytes()
    assert "right:124px; bottom:auto; left:auto;" in (ROOT / "alto" / "build" / "backgrounds.py").read_text(encoding="utf-8")


JS = """() => { const W = innerWidth, out = {};
  for (const q of ['#account-btn', '#search-btn', '#bg-toggle', '#info-btn', '#mode-toggle']) {
    const e = document.querySelector(q); if (!e) { out[q] = null; continue; }
    const c = getComputedStyle(e), r = e.getBoundingClientRect();
    out[q] = c.display === 'none' || c.visibility === 'hidden' || r.width === 0 ? null : {l: r.left, r: W - r.right, w: r.width, h: r.height, a: r.left, b: r.right}; }
  return out; }"""


@pytest.mark.parametrize("page", ["home", "reports"])
@pytest.mark.parametrize("vw,vh", [(390, 844), (320, 568)])
def test_top_row_edge_gap_20_in_every_style_and_scheme(vw, vh, page):
    import phone_matrix as pm
    try:
        pw = pm._playwright()
    except ImportError:
        pytest.skip("Playwright is not installed")
    pages, plans, art = pm.build_pages()
    from alto.build import pages as _pg
    pages["reports"] = _pg.build_reports([], "")
    s = pm.serve(pages, plans, art)

    async def go():
        res = {}
        async with pw.async_playwright() as p:
            b = await p.webkit.launch()
            for st in ("classic", "retro", "holo"):
                for sc in ("light", "dark"):
                    ctx = await b.new_context(viewport={"width": vw, "height": vh}, is_mobile=True, has_touch=True, user_agent=pm.UA, color_scheme=sc)
                    pg = await ctx.new_page()
                    await pg.goto(f"http://127.0.0.1:{s.server_address[1]}/{page}.html" + ("" if st == "classic" else f"?style={st}"), wait_until="load", timeout=45000)
                    await pg.wait_for_timeout(3500)
                    res[(st, sc)] = await pg.evaluate(JS)
                    await ctx.close()
            await b.close()
        return res
    try:
        res = asyncio.run(go())
    except Exception as e:
        if "Executable doesn't exist" in str(e):
            pytest.skip(f"no WebKit: {e}")
        raise
    finally:
        s.shutdown()
    for key, m in res.items():
        live = {q: v for q, v in m.items() if v}
        assert set(live) >= ({"#account-btn", "#search-btn", "#bg-toggle", "#info-btn"} if page == "home" else {"#account-btn", "#search-btn", "#info-btn"}), (key, "a phone control is gone", m)
        assert round(live["#account-btn"]["l"]) == 20, (key, "account edge gap", live["#account-btn"])
        right = min(v["r"] for v in live.values())
        assert round(right) == 20, (key, "right edge gap", right)
        for q, v in live.items():
            assert round(v["h"]) == 44, (key, q, "44pt tall", v)
            assert round(v["w"]) >= 44, (key, q, "44pt wide", v)
        spans = sorted((v["a"], v["b"], q) for q, v in live.items())
        for (a1, b1, q1), (a2, b2, q2) in zip(spans, spans[1:]):
            assert a2 - b1 >= 6, (key, f"{q1} and {q2} overlap or crowd", spans)


def test_holo_private_and_sort_wear_the_s1_glass_on_a_phone_only():
    """v1.9.234 (Luke L-1116-104958): phone Holo PRIVATE chip and Sort chip are round glass, 44pt tall; a computer's stay square."""
    import phone_matrix as pm
    try:
        pw = pm._playwright()
    except ImportError:
        pytest.skip("Playwright is not installed")
    pages, plans, art = pm.build_pages()
    s = pm.serve(pages, plans, art)
    J = "() => [...document.querySelectorAll('#home-row .hr-chip,#home-row .home-sort')].filter(e => e.getBoundingClientRect().width > 8 && e.getAttribute('aria-hidden') !== 'true').map(e => { const c = getComputedStyle(e); return {r: parseFloat(c.borderTopLeftRadius), h: Math.round(e.getBoundingClientRect().height), g: c.boxShadow.indexOf('inset') >= 0 && c.backdropFilter.indexOf('blur') >= 0 || c.webkitBackdropFilter.indexOf('blur') >= 0}; })"

    async def go():
        out = {}
        async with pw.async_playwright() as p:
            b = await p.webkit.launch()
            for name, w, h, mob in (("phone", 390, 844, True), ("desk", 1280, 800, False)):
                ctx = await b.new_context(viewport={"width": w, "height": h}, is_mobile=mob, has_touch=mob, user_agent=pm.UA if mob else None)
                pg = await ctx.new_page()
                await pg.add_init_script("try{localStorage.setItem('alto-bg-home-v1-style','holo');localStorage.removeItem('alto-home-view-v1');}catch(e){}")
                await pg.goto(f"http://127.0.0.1:{s.server_address[1]}/home.html", wait_until="load", timeout=45000)
                await pg.wait_for_timeout(1500)
                await pg.evaluate("p => { drawPrivate(p) }", [{"key": "k%d" % i, "project": "Project %d" % (i // 4), "title": "Tile %d" % i, "heading": "Tile %d" % i, "tid": "t%d" % i, "added": 1.7e12 - i, "viewedAt": 1.7e12 - i, "fmt": "timeline", "units": [{"label": "U", "color": "#7c5cff"}]} for i in range(8)])
                await pg.wait_for_timeout(1500)
                out[name] = await pg.evaluate(J)
                await ctx.close()
            await b.close()
        return out
    try:
        res = asyncio.run(go())
    except Exception as e:
        if "Executable doesn't exist" in str(e):
            pytest.skip(f"no WebKit: {e}")
        raise
    finally:
        s.shutdown()
    assert res["phone"], "the home row has its chips on a phone"
    for c in res["phone"]:
        assert c["r"] >= 20 and c["h"] == 44 and c["g"], c
    assert all(c["r"] < 10 for c in res["desk"]), ("a computer keeps its square chips", res["desk"])


INFO_JS = """(B) => { const W = innerWidth, H = innerHeight, i = document.getElementById('info-btn');
  return (res => { const pc = document.getElementById('info-content'), ib = i.getBoundingClientRect(), pr = pc.getBoundingClientRect();
    const wide = pr.width > 60, P = wide ? pr : ib, el = wide && ib.width < 60 ? pc : i, c = getComputedStyle(el), r = P;
    const hits = []; document.querySelectorAll(B).forEach(e => { const s = getComputedStyle(e), q = e.getBoundingClientRect(); if (s.display === 'none' || s.visibility === 'hidden' || +s.opacity === 0 || q.width < 4) return;
      const g = W > 640 ? 8 : 0;   // on a computer a button keeps 8px clear of the panel
      if (!(q.left < r.right + g && q.right > r.left - g && q.top < r.bottom + g && q.bottom > r.top - g)) return;
      const inside = q.left >= r.left && q.right <= r.right && q.top >= r.top && q.bottom <= r.bottom, chip = !!e.closest('#home-row');
      if (!(chip && inside && W <= 640)) hits.push((e.id || e.className) + ':' + [q.left, q.top, q.right, q.bottom].map(Math.round)); });   // a chip may sit wholly under the phone's solid plate; nothing may be half-cut
    return res({exp: i.classList.contains('expanded'), l: r.left, t: r.top, r: W - r.right, b: H - r.bottom, w: r.width, h: r.height, rad: parseFloat(c.borderTopLeftRadius) || 0, alpha: (/rgba?\(([^)]*)\)/.exec(getComputedStyle(el).backgroundColor) || [0, ''])[1].split(',').length > 3 ? parseFloat(getComputedStyle(el).backgroundColor.split(',')[3]) : 1, hits}); })(x => x); }"""
CORNERS = "#info-icon,#home-row .hr-chip,#home-row .home-sort,#search-btn,#bin-btn,#mode-toggle,#account-btn,#bg-toggle,#download-all,#drawer-scene-btn,#key-toggle,#sx-toggle"


@pytest.mark.parametrize("vw,vh,mob", [(1440, 900, False), (1024, 768, False), (390, 844, True), (320, 568, True)])
def test_open_info_guide_is_a_rounded_rectangle_20px_in_and_clear_of_the_buttons(vw, vh, mob):
    """v1.9.234 (Luke L-1116-110333): the open info guide was a circle in Holo (the S1 plate's 999px carried over), cutting its text; in every style, light and dark,
    it is a rounded rectangle at least 20px (19 for rounding) from every window edge and touches no corner button."""
    import phone_matrix as pm
    try:
        pw = pm._playwright()
    except ImportError:
        pytest.skip("Playwright is not installed")
    pages, plans, art = pm.build_pages()
    s = pm.serve(pages, plans, art)

    async def go():
        res = {}
        async with pw.async_playwright() as p:
            b = await p.webkit.launch()
            for st in ("classic", "retro", "holo"):
                for sc in (("light", "dark") if st == "classic" else ("dark",)):
                    ctx = await b.new_context(viewport={"width": vw, "height": vh}, is_mobile=mob, has_touch=mob, user_agent=pm.UA if mob else None, color_scheme=sc)
                    pg = await ctx.new_page()
                    await pg.goto(f"http://127.0.0.1:{s.server_address[1]}/home.html" + ("" if st == "classic" else f"?style={st}"), wait_until="load", timeout=45000)
                    await pg.wait_for_timeout(3000)
                    await pg.evaluate("p => { drawPrivate(p) }", [{"key": "k%d" % i, "project": "Project %d" % (i // 4), "title": "Tile %d" % i, "heading": "Tile %d" % i, "tid": "t%d" % i, "added": 1.7e12 - i, "viewedAt": 1.7e12 - i, "fmt": "timeline", "units": [{"label": "U", "color": "#7c5cff"}]} for i in range(8)])
                    await pg.wait_for_timeout(800)
                    await pg.click("#info-btn")
                    await pg.wait_for_timeout(900)
                    res[(st, sc)] = await pg.evaluate(INFO_JS, CORNERS)
                    await ctx.close()
            await b.close()
        return res
    try:
        res = asyncio.run(go())
    except Exception as e:
        if "Executable doesn't exist" in str(e):
            pytest.skip(f"no WebKit: {e}")
        raise
    finally:
        s.shutdown()
    for key, m in res.items():
        assert m["exp"], (key, "the guide opened")
        assert min(m["l"], m["t"], m["r"], m["b"]) >= 19, (key, "20px from every edge", m)
        assert m["w"] > 150 and m["h"] > 150, (key, "it is the open panel", m)
        assert m["rad"] < min(m["w"], m["h"]) / 4, (key, "a rounded rectangle, not a circle", m)
        assert not m["hits"], (key, "a control sits on the guide", m)
        if vw <= 640:
            assert m["w"] >= vw - 41 and m["alpha"] >= 0.95, (key, "phone: full width and a solid plate", m)
