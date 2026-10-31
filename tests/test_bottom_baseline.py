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
ROW = ["account-btn", "search-btn", "key-toggle", "info-btn", "mode-toggle", "alto-edit-pill", "sol-ctl", "pal-ctl", "lanes-nav"]


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


KEYED = {"lanes": None, "city": None}


@pytest.fixture(scope="module")
def keyed(tmp_path_factory):
    import copy
    from tests.test_palace_chrome import bundle
    t = tmp_path_factory.mktemp("key")
    d = json.loads((ROOT / "samples" / "lanes_brief.json").read_text(encoding="utf-8"))
    (t / "lanes.html").write_text(build_timeline(*load_brief(d))[0], encoding="utf-8")
    (t / "city.html").write_text(build_timeline(*load_brief(copy.deepcopy(bundle())))[0], encoding="utf-8")
    return t


KEY = """()=>{const r=id=>document.getElementById(id).getBoundingClientRect(), s=r('search-btn'), k=r('key-toggle'), i=r('info-btn'),
  p=document.querySelector('.key-pop'), pr=p.getBoundingClientRect(), c=getComputedStyle(p);
  return {order:s.right<k.left && k.right<i.left, gaps:[k.left-s.right, i.left-k.right], mid:[(k.top+k.bottom)/2,(i.top+i.bottom)/2],
    above:pr.bottom<=k.top, right:[pr.right,k.right], bg:c.backgroundColor, blur:c.backdropFilter||c.webkitBackdropFilter||'none'};}"""


@pytest.mark.parametrize("look", ["classic", "dark", "retro"])
@pytest.mark.parametrize("page", list(KEYED))
def test_the_key_sits_in_the_row_between_info_and_search_and_its_panel_is_opaque(browser, keyed, page, look):
    """Luke picked Art's option A (2026-10-30): the key's toggle in the bottom-right row, one spot on every page; the key
    opens above it on a plate no card text shows through."""
    pg = browser.new_context(viewport={"width": 1400, "height": 900}).new_page()
    pg.goto((keyed / f"{page}.html").as_uri())
    pg.wait_for_timeout(1500)
    if look == "dark":
        pg.evaluate("document.getElementById('mode-toggle').click()")
    elif look == "retro":
        pg.add_script_tag(content=retro.ASSET)
        pg.evaluate("window._altoRetro.on()")
    pg.wait_for_timeout(400)
    pg.evaluate("document.getElementById('key-toggle').click()")
    pg.wait_for_timeout(400)
    r = pg.evaluate(KEY)
    pg.close()
    assert r["order"], r
    assert abs(r["gaps"][0] - r["gaps"][1]) < 0.6, r
    assert abs(r["mid"][0] - r["mid"][1]) < 1, r
    assert r["above"] and abs(r["right"][0] - r["right"][1]) < 0.6, r
    alpha = 1.0 if r["bg"].startswith("rgb(") else float(r["bg"].rstrip(")").split(",")[-1])
    assert alpha >= 0.97 and r["blur"] == "none", r
