"""Home label row B (12 Nov): under HOME one centred row, a Private | Shared switch and the sort chip, drawn like the corner toggles.
With nothing shared there is a plain "Private" chip, not a one-item switch. The corner toggles stay where they were.

Browser (WebKit; skipped without Playwright): Classic, Retro and Holographic, light and dark, a computer at 1000 and 1440 wide, a phone upright and
sideways. The row sits under the HOME bar, is centred, overlaps neither the corner toggles nor the first project box, and its touch targets are 44 pt on a phone."""
import http.server
import socketserver
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import holo, pages, retro            # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None


def test_row_b_replaces_the_two_group_labels_and_keeps_the_corner_toggles():
    h = pages.build_home([])
    assert "#home-row{" in h and ".home-section-label{ display:none; }" in h
    assert "const VIEW_KEY = 'alto-home-view-v1'" in h
    assert "c.className = 'hr-chip hr-plain'" in h and "'Private' : 'Shared'" in h
    assert "wrap.insertBefore(homeRow, wrap.firstChild)" in h
    # the home search still finds shared items while the Private view is up: both groups are always built
    assert "_searchExtra('shared', found)" in h and "classList.toggle('hr-off'" in h
    assert "html.info-open #search-btn, html.info-open #bin-btn{ transform:translateX(-324px); }" in h   # the corner row is untouched


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    if pw is None:
        pytest.skip("Playwright is not installed")
    d = tmp_path_factory.mktemp("hlsite")
    (d / "h.html").write_text(pages.build_home([]), encoding="utf-8")
    (d / "holo").mkdir()
    (d / "retro").mkdir()
    name, text = holo.holo_asset()
    (d / "holo" / name).write_text(text, encoding="utf-8")
    name, text = retro.retro_asset()
    (d / "retro" / name).write_text(text, encoding="utf-8")

    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(d), **k)

        def log_message(self, *a):
            pass
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), H)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


@pytest.fixture(scope="module")
def browser():
    if pw is None:
        pytest.skip("Playwright is not installed")
    with pw.sync_playwright() as p:
        try:
            b = p.webkit.launch()
        except Exception as e:
            pytest.skip(f"no webkit: {e}")
        yield b
        b.close()


def _pages(n=3):
    return [{"key": "k%d" % i, "project": "Project %d" % (i % 3), "title": "T%d" % i, "heading": "T%d" % i, "tid": "t%d" % i,
             "added": 1.7e12 - i, "viewedAt": 1.7e12 - i, "fmt": "timeline", "units": [{"label": "U", "color": "#7c5cff"}]} for i in range(n)]


def _shared():
    return [{"key": "s1", "title": "Torts outline", "heading": "Torts outline", "fmt": "outline", "units": []}]


RECTS = """()=>{const o={};const add=(k,e)=>{if(!e)return;const s=getComputedStyle(e);if(s.display==='none'||s.visibility==='hidden')return;
  const r=e.getBoundingClientRect();if(r.width)o[k]={l:r.left,t:r.top,r:r.right,b:r.bottom,w:r.width,h:r.height}};
  add('row',document.getElementById('home-row'));add('title',document.getElementById('title-bar'));
  add('slab',document.querySelector('.slab-group:not(.hr-off) .project-slab'));
  for(const id of ['search-btn','bin-btn','info-btn','mode-toggle','bg-toggle','m-search','account-btn'])add(id,document.getElementById(id));
  document.querySelectorAll('#home-row button').forEach((b,i)=>add('btn'+i,b));
  return o}"""


def _hit(a, b):
    return a["l"] < b["r"] - 0.5 and b["l"] < a["r"] - 0.5 and a["t"] < b["b"] - 0.5 and b["t"] < a["b"] - 0.5


def _open(browser, site, style, dark, size, shared):
    pg = browser.new_page(viewport={"width": size[0], "height": size[1]})
    pg.add_init_script("try{localStorage.setItem('alto-bg-home-v1-style','%s');localStorage.removeItem('alto-home-view-v1')}catch(e){}" % style)
    pg.goto(f"{site}/h.html")
    pg.wait_for_timeout(800)
    pg.evaluate("d=>document.documentElement.classList.toggle('dark', d)", dark)
    import json
    pg.evaluate("p=>{drawPrivate(p)}", _pages())
    if shared:
        pg.evaluate("s=>{drawShared(s)}", _shared())
    pg.wait_for_timeout(400)
    return pg


@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
@pytest.mark.parametrize("dark", [False, True])
@pytest.mark.parametrize("size", [(1000, 700), (1440, 800), (402, 874), (874, 292)], ids=["narrow1000", "wide1440", "phone-up", "phone-side"])
def test_the_row_sits_under_home_centred_clear_of_the_toggles(browser, site, style, dark, size):
    pg = _open(browser, site, style, dark, size, shared=True)
    try:
        r = pg.evaluate(RECTS)
        row = r["row"]
        assert abs((row["l"] + row["r"]) / 2 - size[0] / 2) <= 6, ("centred", row)
        assert row["t"] >= r["title"]["b"] - 1, ("under HOME", row, r["title"])
        buttons = [v for k, v in r.items() if k.startswith("btn")]
        assert len(buttons) == 3                                         # Private, Shared, the sort chip
        for k, v in r.items():
            if k in ("row", "title", "slab") or k.startswith("btn"):
                continue
            for b in buttons:
                assert not _hit(b, v), ("overlaps the corner toggle", k, b, v)
        assert not any(_hit(a, b) for i, a in enumerate(buttons) for b in buttons[i + 1:])
        if size[0] <= 640 or size[1] <= 500:                              # a phone: finger-sized
            assert all(b["h"] >= 43.5 for b in buttons), buttons
        if size[0] <= 640:
            assert row["l"] >= 0 and row["r"] <= size[0] and not pg.evaluate("document.documentElement.scrollWidth > innerWidth"), "no side stacking"
            assert max(b["t"] for b in buttons) - min(b["t"] for b in buttons) < 2, "one line"
        if size[1] > 500 or size[0] > 640:
            assert "slab" not in r or not _hit(row, r["slab"]) or row["b"] <= r["slab"]["t"] + 20, (row, r["slab"])
    finally:
        pg.close()


@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
def test_the_switch_swaps_the_groups_and_the_sort_goes_with_private(browser, site, style):
    pg = _open(browser, site, style, False, (1440, 800), shared=True)
    try:
        vis = "()=>[...document.querySelectorAll('.slab-group')].filter(g=>getComputedStyle(g).display!=='none').map(g=>g.className.split(' ')[1])"
        assert pg.evaluate(vis) == ["private-group"]
        assert pg.locator("#home-row .home-sort").count() == 1
        pg.locator("#home-row [role=radio]", has_text="Shared").click()
        assert pg.evaluate(vis) == ["shared-group"]
        assert pg.locator("#home-row .home-sort").is_hidden()            # kept as a hidden spacer
        assert pg.locator("#home-row .hr-sortw.hr-ghost button[aria-hidden=true][tabindex='-1']").count() == 1
        assert pg.evaluate("localStorage.getItem('alto-home-view-v1')") == "shared"
        pg.locator("#home-row [role=radio]", has_text="Private").click()
        assert pg.evaluate(vis) == ["private-group"]
        pg.locator("#home-row .home-sort").click()
        assert pg.locator(".home-sort-pop").is_visible()
    finally:
        pg.close()


@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
@pytest.mark.parametrize("size", [(1440, 800), (402, 874)], ids=["wide1440", "phone-up"])
def test_a_plain_private_chip_when_nothing_is_shared(browser, site, style, size):
    pg = _open(browser, site, style, False, size, shared=False)
    try:
        assert pg.locator("#home-row [role=radio]").count() == 0          # not a one-item switch
        chip = pg.locator("#home-row .hr-plain")
        assert chip.count() == 1 and chip.inner_text().strip().lower() == "private"
        r = pg.evaluate(RECTS)
        assert abs((r["row"]["l"] + r["row"]["r"]) / 2 - size[0] / 2) <= 6
        assert pg.locator("#home-row .home-sort").count() == 1
    finally:
        pg.close()


@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
@pytest.mark.parametrize("size", [(1440, 800), (375, 812), (402, 874)], ids=["wide1440", "phone375", "phone-up"])
def test_the_switch_does_not_move_between_private_and_shared(browser, site, style, size):
    pg = _open(browser, site, style, False, size, shared=True)
    try:
        left = "()=>document.querySelector('#home-row .hr-switch').getBoundingClientRect().left"
        a = pg.evaluate(left)
        pg.locator("#home-row [role=radio]", has_text="Shared").click()
        b = pg.evaluate(left)
        assert abs(a - b) < 0.5, (a, b)
        assert pg.evaluate("document.querySelectorAll('#home-row .hr-chip').length") == 3
        row = pg.evaluate("()=>{const r=document.getElementById('home-row').getBoundingClientRect();return [r.left,r.right]}")
        assert row[0] >= 0 and row[1] <= size[0]
    finally:
        pg.close()
