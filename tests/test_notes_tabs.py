"""Luke 2026-11-13, "freewrite is a little cut off" (Holo, desktop Safari, the Highlights & Notes panel): the panel's two tabs (Notes & highlights | Freewrite,
#fw-seg, freewrite.py) ran 6 px wider than their bar in Holo (Retro's wide lettering), so Freewrite's right edge was clipped. Now each tab stays inside the bar and the bar
inside the panel's inner padding (12 px each side, 9 allowed for the panel's border and rounding), in Classic, Retro and Holo, at 1440 / 1280 and a narrow panel, and on a phone upright and on its side; a tab wraps to
two lines rather than clipping, and Freewrite never wraps mid-word or ellipsizes. WebKit, headless, offline, silent; no cloud env, no account."""
import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

from test_phone_sim1112a import _pw  # noqa: E402

STYLES = ("classic", "retro", "holo")
# (width, height, phone, forced panel width px or 0)
SIZES = [(1440, 900, 0, 0), (1280, 800, 0, 0), (1280, 800, 0, 280), (1280, 800, 0, 224), (1024, 768, 0, 0), (402, 874, 1, 0), (874, 402, 1, 0), (320, 568, 1, 0), (568, 320, 1, 0)]
# the real minimums, measured on every device (1024 and under: the notes panel is 224 px; a phone's is the whole screen, 320 the narrowest)
M = """()=>{const p=document.getElementById('notes-panel'),s=document.getElementById('fw-seg'),pr=p.getBoundingClientRect(),sr=s.getBoundingClientRect(),
 bs=[...s.children].map(b=>{const r=b.getBoundingClientRect(),c=getComputedStyle(b);return {h:r.height,l:r.left,r:r.right,sw:b.scrollWidth,cw:b.clientWidth,ell:c.textOverflow}});
 return {pl:pr.left,pr:pr.right,sl:sr.left,sr:sr.right,bs}}"""


@pytest.fixture(scope="module")
def site():
    pm = _pw()
    pages, plans, art = pm.build_pages()
    s = pm.serve(pages, plans, art)
    yield pm, f"http://127.0.0.1:{s.server_address[1]}"
    s.shutdown()


@pytest.mark.parametrize("style", STYLES)
def test_the_notes_tabs_stay_inside_the_panels_inner_padding(site, style):
    pm, base = site

    async def go():
        out = {}
        async with pm._playwright().async_playwright() as p:
            b = await p.webkit.launch()
            for w, h, mob, pw_ in SIZES:
                ctx = await b.new_context(viewport={"width": w, "height": h}, is_mobile=bool(mob), has_touch=bool(mob), user_agent=pm.UA if mob else None)
                pg = await ctx.new_page()
                await pg.goto(f"{base}/outline-long.html?view=card&style={style}", wait_until="load", timeout=45000)
                await pg.wait_for_timeout(1500)
                await pg.evaluate("window.toggleNotes&&window.toggleNotes()")
                await pg.wait_for_timeout(600)
                if pw_:
                    await pg.evaluate("w=>{const p=document.getElementById('notes-panel');p.style.setProperty('width',w+'px','important');p.style.setProperty('transition','none','important')}", pw_)
                    await pg.wait_for_timeout(200)
                out[(w, h, pw_)] = await pg.evaluate(M)
                await ctx.close()
            await b.close()
        return out
    try:
        out = asyncio.run(go())
    except Exception as e:
        if "Executable doesn't exist" in str(e):
            pytest.skip(f"no WebKit: {e}")
        raise
    for k, m in out.items():
        assert m["sl"] >= m["pl"] + 9 and m["sr"] <= m["pr"] - 9, (style, k, m)       # the bar sits in the panel's 12 px inner padding
        for t in m["bs"]:
            assert t["l"] >= m["sl"] - 0.6 and t["r"] <= m["sr"] + 0.6, (style, k, "a tab runs past its bar", m)
            assert k[2] or t["h"] < (26 if k[0] > 700 and k[0] != 874 else 40), (style, k, "a tab wrapped: both tabs sit on one line from the 224 px floor up", m)
            assert t["ell"] != "ellipsis" and t["sw"] <= t["cw"] + 1, (style, k, "a tab's text is clipped", m)
