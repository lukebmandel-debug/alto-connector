"""A horizontal timeline's ink-saver print, re-flowed like an outline's (Luke 2026-11-26: "please fix horizontal timeline print ink
saver to be like it is for outline"): white sheets of compact columns, each unit a heading with its events under it in page order,
every card nested in an event indented under that event, nothing cut at a sheet's edge, as many sheets as asked for. WebKit,
on a made-up board the size of civ-pro-litigation (275 cards, 7 units, 20 events, Extend on)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import lanes_print_fixture as lf  # noqa: E402
from alto.build.builder import build_timeline, load_brief  # noqa: E402

try:
    from playwright import sync_api as pw
    import phone_matrix as pm
    pm._playwright()
except Exception:                                   # CI has no Playwright
    pw = None

SHEETS = """() => { const out = [], L = window._altoInkLast || {};
  document.querySelectorAll('.ink-tile').forEach((t, ti) => { const tr = t.getBoundingClientRect();
    t.querySelectorAll('.ink-card').forEach(c => { const r = c.getBoundingClientRect();
      out.push({t: ti, x0: r.left - tr.left, y0: r.top - tr.top, x1: r.right - tr.left, y1: r.bottom - tr.top, w: tr.width, h: tr.height,
                unit: c.classList.contains('ink-unit'), title: (c.querySelector('.node-title') || {}).textContent || ''}); }); });
  return {cards: out, n: NODES.length, flow: !!L.flow, sheets: L.sheets, tiles: document.querySelectorAll('.ink-tile').length}; }"""


@pytest.fixture(scope="module")
def page():
    if pw is None:
        pytest.skip("no Playwright")
    d = lf.brief()
    s = pm.serve({"l": build_timeline(*load_brief(d))[0]}, {}, {})
    with pw.sync_playwright() as p:
        try:
            b = p.webkit.launch()
        except Exception as e:
            pytest.skip(f"no WebKit: {e}")
        pg = b.new_context(viewport={"width": 1440, "height": 900}).new_page()
        pg.goto(f"http://127.0.0.1:{s.server_address[1]}/l.html", wait_until="load")
        pg.wait_for_timeout(3500)
        yield pg, d
        b.close()
    s.shutdown()


def _stage(pg, n):
    pg.evaluate("window._altoInkUnstage()")                                   # (each print is staged from the screen, as a real one is)
    pg.evaluate("document.documentElement.classList.remove('printing','print-ink')")
    pg.emulate_media(media="screen")
    assert pg.evaluate(f"(() => {{ window._altoInkSheets = {n}; return window._altoInkStage(); }})()") is True
    pg.evaluate("document.documentElement.classList.add('printing','print-ink')")
    pg.emulate_media(media="print")
    return pg.evaluate(SHEETS)


@pytest.mark.parametrize("n", [0, 2, 4])
def test_every_card_once_inside_its_sheet_none_touching_on_the_sheets_asked_for(page, n):
    pg, d = page
    r = _stage(pg, n)
    cards = [c for c in r["cards"] if not c["unit"]]
    assert r["flow"] and len(cards) == r["n"] == 275 and r["tiles"] == r["sheets"], {k: r[k] for k in ("flow", "n", "sheets", "tiles")}
    if n:
        assert r["sheets"] <= n
    for c in r["cards"]:
        assert c["x0"] >= -0.5 and c["y0"] >= -0.5 and c["x1"] <= c["w"] + 0.5 and c["y1"] <= c["h"] + 0.5, c   # nothing past a sheet's edge
    by = {}
    for c in r["cards"]:
        by.setdefault(c["t"], []).append(c)
    for cs in by.values():
        for i, a in enumerate(cs):
            for b in cs[i + 1:]:
                assert a["x1"] <= b["x0"] + 0.5 or b["x1"] <= a["x0"] + 0.5 or a["y1"] <= b["y0"] + 0.5 or b["y1"] <= a["y0"] + 0.5, (a["title"], b["title"])


def test_units_head_their_events_in_page_order_and_nested_cards_sit_under_their_event(page):
    pg, d = page
    _stage(pg, 0)
    seq = pg.evaluate("""() => [...document.querySelectorAll('#alto-ink-host .ink-card')].map(c => ({unit: c.classList.contains('ink-unit'),
        x: c.getBoundingClientRect().left - c.closest('.ink-tile').getBoundingClientRect().left - c.closest('.ink-in').getBoundingClientRect().left + c.closest('.ink-tile').getBoundingClientRect().left,
        t: (c.querySelector('.node-title') || {}).textContent.trim()}))""")
    units = [c["t"] for c in seq if c["unit"]]
    assert units == [a["short"] for a in d["brief"]["acts"]], units                               # every unit's label, in order
    title = {n["id"]: n["title"] for n in d["nodes"]}
    order = [c["t"] for c in seq if not c["unit"]]
    events = [title[n["id"]] for n in d["nodes"] if not n.get("nest")]
    assert [t for t in order if t in events] == events                                           # the events in page order
    pos = {t: i for i, t in enumerate(order)}
    for n in d["nodes"]:
        if n.get("nest"):
            assert pos[title[n["id"]]] > pos[title[n["nest"]]], n["id"]                          # under its parent
    # each event follows its own unit's heading
    cur, unit_of = None, {}
    for c in seq:
        if c["unit"]:
            cur = c["t"]
        elif c["t"] in events:
            unit_of[c["t"]] = cur
    for n in d["nodes"]:
        if not n.get("nest"):
            assert unit_of[title[n["id"]]] == d["brief"]["acts"][n["act"]]["short"]
