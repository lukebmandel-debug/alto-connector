"""Opening fit on a phone (chunk 4 of ORG/phone-ui-audit-1111.md): lanes rows F1 and F2. WebKit, headless, offline, silent; skipped without Playwright.
(F3, the System's opening fit, needs the 3D bodies WebKit emulation does not draw: a Simulator row. F4 to F6, the Atlas, belong to #19 E8.)"""
import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

JS = """() => { const R=e=>{const r=e.getBoundingClientRect();return [r.left,r.top,r.right,r.bottom].map(Math.round)}, W=innerWidth, H=innerHeight;
  const cards=[...document.querySelectorAll('#world .node .node-card')].map(R).filter(r=>r[2]>0&&r[0]<W&&r[3]>0&&r[1]<H);
  const n=document.getElementById('lanes-nav'), bs=[...n.querySelectorAll(':scope>button')];
  return {W:W, cards:cards, cur:window._altoLanesCurrent&&_altoLanesCurrent(), first:((window._altoLanesTravel()||{}).ids||[])[0]||null, curCard:(function(){var c=window._altoLanesCurrent&&_altoLanesCurrent(),e=c&&document.querySelector('#node-'+c+' .node-card');return e?R(e):null;})(), nav:R(n), btn:bs.map(R),
    hit:bs.map(b=>{const a=getComputedStyle(b,'::after'); return a.content!=='none'&&a.position==='absolute' ? b.getBoundingClientRect().width-2*parseFloat(a.left) : b.getBoundingClientRect().width;}),
    mid:R(n.querySelector('.lnv-mid'))}; }"""


def _lanes(w, h, query=""):
    import phone_matrix as pm
    try:
        pw = pm._playwright()
    except ImportError:
        pytest.skip("Playwright is not installed")
    pages, plans, art = pm.build_pages()
    s = pm.serve(pages, plans, art)

    async def go():
        async with pw.async_playwright() as p:
            b = await p.webkit.launch()
            ctx = await b.new_context(viewport={"width": w, "height": h}, is_mobile=True, has_touch=True, user_agent=pm.UA)
            pg = await ctx.new_page()
            await pg.goto(f"http://127.0.0.1:{s.server_address[1]}/lanes.html?{query}", wait_until="load", timeout=45000)
            for _ in range(60):
                if await pg.evaluate("!!document.getElementById('lanes-nav') && !!(window._altoLanesTravel && _altoLanesTravel())"):
                    break
                await pg.wait_for_timeout(150)
            await pg.wait_for_timeout(1200 if not query else 3500)
            out = await pg.evaluate(JS)
            await b.close()
            return out
    try:
        return asyncio.run(go())
    except Exception as e:
        if "Executable doesn't exist" in str(e):
            pytest.skip(f"no WebKit: {e}")
        raise
    finally:
        s.shutdown()


@pytest.mark.parametrize("w,h,query", [(402, 874, ""), (375, 812, ""), (402, 874, "style=retro")], ids=["p402", "p375", "p402-retro"])
def test_lanes_opens_on_the_first_event_with_its_card_on_screen(w, h, query):
    m = _lanes(w, h, query)
    assert m["cur"] and m["curCard"] and (m["first"] is None or m["cur"] == m["first"]), m       # resting on the first event, as one tap on Next would leave it
    c = m["curCard"]
    assert c[0] >= 8 and c[2] <= w - 8, m                              # F1: was x 185 to 475 on a 402 pt screen


@pytest.mark.parametrize("w,h", [(402, 874), (375, 812), (874, 292)], ids=["p402", "p375", "l874"])
def test_lanes_step_bar_is_whole_and_touchable(w, h):
    m = _lanes(w, h)
    nav = m["nav"]
    assert nav[0] >= 56 and nav[2] <= w - 56, m                        # clear of the corner tiles
    assert nav[2] - nav[0] <= 360, m                                   # a bar, not a rail the width of a phone on its side
    for b, hit in zip(m["btn"], m["hit"]):
        assert b[2] - b[0] == 28, m                                    # F2: drawn as designed (they were squeezed to 16 px) ...
        assert b[0] >= nav[0] and b[2] <= nav[2], m                    # ... inside the bar (Next ran off a 375 pt screen) ...
        assert hit >= 44, m                                            # ... and 44 pt to touch
    assert m["mid"][2] - m["mid"][0] >= 110, m
