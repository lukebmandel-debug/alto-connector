"""Board B-1119-SHOTS246-GO (1.9.252): text on text. On the city map (Memory Map) and the Blueprint, in every style at d1440 and p390, no district or room
label box meets a number tag, a chip or a column dot. (The district names sat under the number tags on the board; the Blueprint's room names were
placed before the chips settled and measured in the Classic face, so Retro's capitals and letter-spacing ran into chips and columns.) Chromium and WebKit."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from test_palace_title_visible import browser, pages, _serve, READY, UA, PLAN, bs  # noqa: E402,F401

MEAS = """() => {
 const rc = e => { const r = e.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom, e.textContent.trim().slice(0,30)]; };
 const labs = [...document.querySelectorAll('#bldg-root .bl-lab, #palace-svg text.pl-dist, #pal-map text.pl-dist, text.pl-dist')].filter(e => { const r=e.getBoundingClientRect(); const c=getComputedStyle(e); return r.width>0 && c.display!=='none' && c.visibility!=='hidden' && +c.opacity>.3 && e.style.display!=='none'; });
 const tags = [...document.querySelectorAll('#bldg-root .bl-mk > *, .pl-chip, .pl-nbtag, #world .node .node-card, #world .node .num, #world .node .nb3d, #world .node-num')].filter(e => { const r=e.getBoundingClientRect(); return r.width>0 && r.width<=90 && r.height<=34 && getComputedStyle(e).display!=='none' && !e.classList.contains('bl-off'); });
 const cols = [...document.querySelectorAll('#bldg-root .bl-col, .pl-pin, .pl-stt, .pl-ring')].filter(e => e.getBoundingClientRect().width>0);
 const hit = (a,b) => a[0]<b[2]&&a[2]>b[0]&&a[1]<b[3]&&a[3]>b[1];
 const bad = [];
 labs.forEach(l => { const a = rc(l); [['tag',tags],['col',cols]].forEach(([k,L]) => L.forEach(t => { const b=rc(t); if (hit(a,b)) bad.push([k, a[4], t.className && t.className.baseVal!==undefined ? t.className.baseVal : t.className, a.slice(0,4).map(Math.round), b.slice(0,4).map(Math.round)]); })); });
 return {labs: labs.length, tags: tags.length, cols: cols.length, bad};
}"""


@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
@pytest.mark.parametrize("size", ["d1440", "p390"])
@pytest.mark.parametrize("kind", ["city", "blueprint"])
def test_no_label_sits_on_a_chip_a_number_tag_or_a_column_dot(browser, pages, kind, size, style):
    srv = _serve(pages[kind], dict([bs.hosted_json(PLAN)]) if kind == "blueprint" else None)
    o = f"http://127.0.0.1:{srv.server_address[1]}"
    vp, mob = ({"width": 1440, "height": 900}, False) if size == "d1440" else ({"width": 390, "height": 844}, True)
    cx = browser.new_context(viewport=vp, **({"is_mobile": True, "has_touch": True, "user_agent": UA} if mob else {}))
    page = cx.new_page()
    try:
        page.goto(o + "/index.html")
        page.wait_for_function(READY[kind], timeout=20000)
        if style != "classic":
            page.evaluate("(s) => (window._altoStyle || window._altoStyleC).set(s)", style)
            page.reload()
            page.wait_for_function(READY[kind], timeout=20000)
        page.wait_for_timeout(2500)
        r = page.evaluate(MEAS)
        assert not r["bad"], r
        if size == "d1440":
            assert r["labs"] >= 3, r                      # (the names are still there: nothing was dropped to make it pass)
    finally:
        cx.close()
        srv.shutdown()
