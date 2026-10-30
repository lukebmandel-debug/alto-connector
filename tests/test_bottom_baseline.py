"""One bottom line for the desktop controls along the foot (Luke, 2026-10-30, his Terrarium horizontal timeline in Safari:
"correct me if i'm wrong, are the toggles on the bottom right higher than the account toggle?"). The account toggle, the
right-hand row (search, info, light/dark, the edit toggle), the System's and the Memory Palace's own controls and the
horizontal timeline's step bar share one centre line (--alto-row-b), in every format, Classic and Retro, in Chromium and
WebKit. Skipped when Playwright is not installed."""
import json
from pathlib import Path

import pytest

pw = pytest.importorskip("playwright.sync_api")

from alto.build import retro  # noqa: E402
from alto.build.builder import build_timeline, load_brief  # noqa: E402
from tests.test_world_palace import loaded as palace_brief  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FORMATS = {"timeline": ("contracts_brief", {}), "outline": ("outline_brief", {}), "lanes": ("lanes_brief", {}),
           "system": ("outline_brief", {"layout": "solar", "hub_look": "hub"}), "stars": ("outline_brief", {"layout": "solar"}),
           "palace": None, "atlas": None}
ROW = ["account-btn", "search-btn", "info-btn", "mode-toggle", "alto-edit-pill", "sol-ctl", "pal-ctl", "lanes-nav"]


@pytest.fixture(scope="module")
def pages(tmp_path_factory):
    t = tmp_path_factory.mktemp("row")
    for name, spec in FORMATS.items():
        if spec is None:
            b, nodes, conns = palace_brief(palace_view="city" if name == "palace" else "world")
        else:
            d = json.loads((ROOT / "samples" / f"{spec[0]}.json").read_text(encoding="utf-8"))
            d["brief"].update(spec[1])
            b, nodes, conns = load_brief(d)
        (t / f"{name}.html").write_text(build_timeline(b, nodes, conns)[0], encoding="utf-8")
    return t


@pytest.fixture(scope="module", params=["webkit", "chromium"])
def browser(request):
    with pw.sync_playwright() as p:
        try:
            b = getattr(p, request.param).launch()
        except Exception as e:
            pytest.skip(f"no {request.param}: {e}")
        yield b
        b.close()


MIDS = """(ids)=>{const o={}; for(const id of ids){const e=document.getElementById(id); if(!e||!e.offsetWidth) continue;
  const r=e.getBoundingClientRect(); if(r.bottom<innerHeight-120) continue; o[id]=(r.top+r.bottom)/2;} return o;}"""


@pytest.mark.parametrize("look", ["classic", "retro"])
@pytest.mark.parametrize("fmt", list(FORMATS))
def test_the_foot_controls_share_one_centre_line(browser, pages, fmt, look):
    pg = browser.new_context(viewport={"width": 1400, "height": 900}).new_page()
    pg.goto((pages / f"{fmt}.html").as_uri())
    pg.wait_for_timeout(1500)
    if look == "retro":
        pg.add_script_tag(content=retro.ASSET)
        pg.evaluate("window._altoRetro.on()")
        pg.wait_for_timeout(500)
    m = pg.evaluate(MIDS, ROW)
    pg.close()
    assert "account-btn" in m and "search-btn" in m, m
    a = m["account-btn"]
    off = {k: round(v - a, 2) for k, v in m.items() if abs(v - a) > 1}
    assert not off, f"{fmt} {look}: off the account toggle's centre line (px): {off}"
