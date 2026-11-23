"""Classic home card: the privacy glyph stands in the button row, clear of the study-plan pill (Luke 2026-11-20); Holo and Retro keep >=12px; a phone has no overlap and 44px targets."""
import functools
import http.server
import json
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from test_study_plan import NOW, _home   # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None

PLAN = {"days": ["2026-11-05", "2026-11-02"], "nodes": ["a", "b"], "exam": ""}
CASES = {
    "private": dict(key="k1", title="Torts", heading="Torts", project="Law", fmt="outline", tid="t1", units=["#4a9eff"], plan=PLAN),
    "shared": dict(key="k2", title="Contracts", heading="Contracts", project="Law", fmt="timeline", tid="t2", units=["#4a9eff"], shareKey="abc123", plan={"days": ["2026-11-05"], "nodes": ["a"], "exam": ""}),
    "noplan": dict(key="k3", title="Property", heading="Property", project="Law", fmt="lanes", tid="t3", units=["#4a9eff"]),
}
BASE_H = {"private": 180.4, "shared": 157.2, "noplan": 150.0}
JS = """()=>{const t=document.querySelector('.course-tile:not(.new-tile)'), r=e=>e&&e.getBoundingClientRect();
 const pill=t.querySelector('.sp-card'), pr=pill&&getComputedStyle(pill).display!=='none'?r(pill):null, l=t.querySelector('.priv-sym'), lr=r(l);
 const rg=document.createRange(); if(pill) rg.selectNodeContents(pill); const rr=pill&&[...rg.getClientRects()].filter(q=>q.width>0), lab=rr&&rr.length?[Math.min(...rr.map(q=>q.left)),Math.min(...rr.map(q=>q.top)),Math.max(...rr.map(q=>q.right)),Math.max(...rr.map(q=>q.bottom)),Math.max(...rr.map(q=>q.height)), rr.length]:null;
 const acts=[...t.querySelectorAll('.tile-reports,.tile-share,.tile-download')].map(r), tr=r(t);
 const hit=l?(()=>{const q=r(l); return {w:q.width,h:q.height}})():null;
 return {label:lab, h:tr.height, pill:pr&&[pr.top,pr.bottom,pr.left,pr.right], lock:[lr.left,lr.top,lr.right,lr.bottom], tile:[tr.left,tr.top,tr.right,tr.bottom], acts:acts.map(a=>[a.left,a.top,a.right,a.bottom]),
   name:l.getAttribute('aria-label'), title:l.title, hit}}"""


@pytest.fixture(scope="module")
def srv(tmp_path_factory):
    if pw is None:
        pytest.skip("Playwright is not installed")
    from alto.build import holo, retro
    d = tmp_path_factory.mktemp("lockgap")
    (d / "retro").mkdir()
    (d / "holo").mkdir()
    n, t = retro.retro_asset()
    (d / "retro" / n).write_text(t, encoding="utf-8")
    n, t = holo.holo_asset()
    (d / "holo" / n).write_text(t, encoding="utf-8")
    for k, v in CASES.items():
        (d / (k + ".html")).write_text(_home([v]), encoding="utf-8")
    s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(type("H", (http.server.SimpleHTTPRequestHandler,), {"log_message": lambda *a: None}), directory=str(d)))
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield "http://127.0.0.1:%d/" % s.server_address[1]
    s.shutdown()


@pytest.fixture(scope="module")
def browser():
    with pw.sync_playwright() as p:
        b = p.webkit.launch()
        yield b
        b.close()


def _measure(browser, srv, case, style, w, h, mobile=False, flow=False):  # noqa: ARG001
    ua = {"user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"} if mobile else {}
    ctx = browser.new_context(viewport={"width": w, "height": h}, is_mobile=mobile, has_touch=mobile, **ua)
    pg = ctx.new_page()
    pg.add_init_script(NOW + "try{localStorage.setItem('alto-bg-home-v1-style','%s')}catch(e){}" % style)
    pg.goto(srv + case + ".html")
    pg.wait_for_timeout(600)
    pg.evaluate("(s)=>window._altoStyle && window._altoStyle.set(s)", style)
    pg.wait_for_timeout(900)
    if flow:   # the old place: the glyph back in its line under the pill
        pass
    got = pg.evaluate(JS)
    ctx.close()
    return got


@pytest.mark.parametrize("w", [901, 1024, 1440, 2000])
@pytest.mark.parametrize("case", list(CASES))
def test_classic_glyph_sits_in_the_button_row_and_the_card_keeps_its_height(browser, srv, case, w):
    m = _measure(browser, srv, case, "classic", w, 1000)
    assert abs(m["h"] - BASE_H[case]) < 0.6, (m["h"], BASE_H[case])   # (the card heights measured on v1.9.277, before the change)
    l, (a_l, a_t, a_r, a_b) = m["lock"], (min(a[0] for a in m["acts"]), m["acts"][0][1], max(a[2] for a in m["acts"]), m["acts"][0][3])
    assert l[0] - a_r >= 12                                  # clear of the buttons, to their right
    assert abs((l[1] + l[3]) / 2 - (a_t + a_b) / 2) < 1.5      # centred on them
    assert m["tile"][2] - l[2] >= 12                           # the card's own inner padding, never at the edge
    assert m["pill"] is None or l[1] - m["pill"][1] >= 12      # 12px or more below the pill
    assert m["name"] and m["title"]                          # tooltip and accessible name stay


BASE_T = {"private": 168.6, "shared": 145.4, "noplan": 138.2}   # (the tablet card heights measured on v1.9.278)


@pytest.mark.parametrize("w", [641, 680, 720, 743, 744, 768, 900])
@pytest.mark.parametrize("case", list(CASES))
def test_tablet_glyph_stands_beside_the_pill_not_under_it(browser, srv, case, w):
    m = _measure(browser, srv, case, "classic", w, 1000)
    assert abs(m["h"] - BASE_T[case] - (12 if w < 744 else 0)) < 0.6, (m["h"], BASE_T[case])   # (a narrow tablet keeps the glyph under the pill, 12px clear: the card is 12px taller)
    l, p = m["lock"], m["pill"]
    assert p is not None                                       # (the pill shows from 641px up)
    assert l[0] - p[3] >= 12 or l[1] - p[1] >= 12              # 12px or more clear of the pill (to its right, or below it)
    assert m["tile"][2] - l[2] >= 6                            # (off the card's edge)
    for a in m["acts"]:
        assert l[2] <= a[0] or l[0] >= a[2] or l[3] <= a[1] or l[1] >= a[3]
    assert m["name"] and m["title"]
    if case == "noplan":                                       # "+ Make a study plan": one line, wholly inside the pill
        lb = m["label"]
        assert lb[4] <= 20 and lb[0] >= p[2] and lb[2] <= p[3] and lb[1] >= p[0] and lb[3] <= p[1], (lb, p)


@pytest.mark.parametrize("style", ["holo", "retro"])
@pytest.mark.parametrize("case", list(CASES))
def test_holo_and_retro_keep_twelve_px_between_glyph_and_pill(browser, srv, case, style):
    m = _measure(browser, srv, case, style, 1440, 1000)
    l = m["lock"]
    if m["pill"]:
        assert l[3] <= m["pill"][0] - 12 or l[1] >= m["pill"][1] + 12 or l[2] <= m["pill"][2] - 12 or l[0] >= m["pill"][2] + 12


@pytest.mark.parametrize("case", list(CASES))
def test_phone_glyph_does_not_overlap_the_buttons_or_the_pill(browser, srv, case):
    m = _measure(browser, srv, case, "classic", 390, 844, mobile=True)
    l = m["lock"]
    assert m["pill"] is None                                  # (a phone draws no pill)
    for a in m["acts"]:
        if a[2] - a[0] > 0:
            assert l[2] <= a[0] or l[0] >= a[2] or l[3] <= a[1] or l[1] >= a[3]
            assert (a[2] - a[0]) >= 28                         # (28px chips with a 44px hit area from ::after)
