"""Touch sizes (alto/build/phone_touch.py; chunk 7 of ORG/phone-ui-audit-1111.md, rows H2 / F2): the small controls take 44 pt to touch on a phone and
look exactly as they did. Static check always; WebKit (headless, offline, silent) when Playwright is installed."""
import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from alto.build import phone_shell, phone_touch  # noqa: E402


def test_css_is_touch_only_and_in_the_shell_head():
    assert phone_touch.CSS.startswith("@media (pointer:coarse){") and phone_touch.CSS.endswith("}")
    assert 'id="alto-touch"' in phone_shell.head_block()
    assert "width" not in phone_touch.CSS and "height" not in phone_touch.CSS and "padding" not in phone_touch.CSS      # nothing that changes a drawn size


HIT = """() => { const out={}; for(const q of %s){ const e=document.querySelector(q); if(!e) { out[q]=null; continue; } const r=e.getBoundingClientRect();
  let w=r.width, h=r.height; for(const p of ['::after','::before']){ const a=getComputedStyle(e,p); if(a.content==='none'||a.position!=='absolute') continue;
    const t=parseFloat(a.top), l=parseFloat(a.left); if(t<0||l<0){ w=Math.max(w, r.width-2*Math.min(0,l)); h=Math.max(h, r.height-2*Math.min(0,t)); } }
  out[q]={draw:[Math.round(r.width),Math.round(r.height)], hit:[Math.round(w),Math.round(h)]}; } return out; }"""


def _hits(page, query, sels, w=402, h=874):
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
            await pg.goto(f"http://127.0.0.1:{s.server_address[1]}/{page}.html?{query}", wait_until="load", timeout=45000)
            await pg.wait_for_timeout(4000)
            out = await pg.evaluate(HIT % repr(sels))
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


@pytest.mark.parametrize("page,query,sels,draw", [
    ("home", "", ["#account-btn", "#mode-toggle", "#bg-toggle", "#info-icon", ".slab-share"], {"#account-btn": [34, 34], ".slab-share": [30, 30]}),
    ("timeline", "view=card", [".csym-btn", ".esym-btn", "#af-btn"], {".csym-btn": [34, 34], "#af-btn": [34, 34]}),
])
def test_small_controls_take_44pt_and_keep_their_drawn_size(page, query, sels, draw):
    m = _hits(page, query, sels)
    for q in sels:
        assert m[q], (q, m)
        assert min(m[q]["hit"]) >= 44, (q, m[q])
    for q, d in draw.items():
        assert m[q]["draw"] == d, (q, m[q])
