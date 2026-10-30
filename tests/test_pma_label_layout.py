"""Every framed work's museum label keeps its rows apart: title (one or two lines), artist, year and the credit or card row all fit inside the plate,
whatever the title's length (the 2-line title + credit row used to overprint on the year row)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.building_fpv_support import open_view  # noqa: E402
from tests.test_building_fpv_render import engine  # noqa: E402,F401  (the Chromium + WebKit fixture)


JS = """(W) => { const S = AltoBuildingFPV._debug(), g = document.createElement('canvas').getContext('2d'), F = 'Georgia,"Times New Roman",serif', out = [];
  for (const wk of W) for (const n of [null, {n: '3.8', t: 'Concept 23'}]) { const L = S.flay(g, 256, 128, wk, n, F);
    out.push({t: wk.t, n: !!n, lines: L.tl.length, bot: L.bot, lim: 128 - L.pad * .35, f2: L.f2, ya: L.ya, yd: L.yd, ye: L.ye, fs: L.fs}); }
  return out; }"""


def test_every_framed_label_fits_its_plate(engine):
    from alto.buildings import pma
    from tests.test_building_pma_render import _html
    which, b, srv = engine
    plan = pma.plan()
    works = [dict(t=s["work"]["title"], a=s["work"].get("artist"), d=s["work"].get("date"), lic=s["work"].get("lic"), cl=s["work"].get("cl"))
             for s in plan["sl"] if s.get("fr")]
    page, errors = open_view(b, srv, _html(), plan)
    try:
        rows = page.evaluate(JS, works)
    finally:
        page.close()
    assert len(rows) == 2 * len(works) and len(works) == 69
    bad = [r for r in rows if r["bot"] > r["lim"] + 1e-6]
    assert not bad, bad[:5]
    two = [r for r in rows if r["lines"] == 2 and not r["n"]]
    assert two, "the set has two-line titles"
    for r in rows:
        assert r["f2"] >= 10 and r["yd"] - r["ya"] >= r["f2"] * 1.1 - 1e-6, r                           # readable, and the year row clear of the artist row
        if r["ye"]:
            assert r["ye"] - r["yd"] >= r["f2"] * 1.0, r                                                   # the credit/card row clear of the year row
    assert errors == []
