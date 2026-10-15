"""The Mind Palace's Index pages as a building's lobby (palace_doors.py): each group is a department behind a glass
door (a button: aria-expanded / aria-controls) that swings open and unfolds its rows; palace-only (every other
timeline's index glue is byte-identical). Browser tests skip without Playwright's browsers; nothing here touches the
network or any ALTO_* setting."""
import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from alto.build import detail_extras as dx, palace_doors as pd  # noqa: E402
from alto.build.builder import build_timeline, load_brief  # noqa: E402
import test_palace as tp  # noqa: E402

OUTLINE = json.loads((ROOT / "samples" / "outline_brief.json").read_text(encoding="utf-8"))


def _axes(label, key_prefix, n, hide=True):
    return {"label": label, "singular": label.rstrip("s"), "hide_nav": hide,
            "values": [{"id": f"{key_prefix}{i}", "name": f"{label} entry {i}",
                        "sections": [{"h": "Holding", "t": f"What {label} {i} holds."}]} for i in range(n)]}


def palace_bundle():
    """test_palace's synthetic city with two big Index lists, their entries spread over the units
    (one unit holds a single entry)."""
    d = tp.bundle(with_city=False)
    d["brief"]["axes"] = [_axes("Cases", "c", 6), _axes("Federal Rules", "r", 3)]
    d["brief"]["entities"] = []
    for n in d["nodes"]:
        n["entity_ids"] = []
    at = {"alpha": ["c0", "c1"], "beta": ["c2"], "gamma": ["c3", "c4"], "delta": ["c5"]}
    rules = {"alpha": ["r0"], "delta": ["r1", "r2"]}
    for n in d["nodes"]:
        n["axis1_values"] = at.get(n["id"], [])
        n["axis2_values"] = rules.get(n["id"], [])
    return d


@pytest.fixture(scope="module")
def html():
    out, _ = build_timeline(*load_brief(copy.deepcopy(palace_bundle())))
    return out


# ── palace only ─────────────────────────────────────────────────────────────
def test_the_patched_glue_is_palace_only_and_keeps_the_original_pieces():
    g = pd.axis_index_glue()
    assert g != dx.AXIS_INDEX_GLUE and "window._palDoors" in g
    assert "window._palDoors" not in dx.AXIS_INDEX_GLUE                    # the shared glue is untouched
    assert "function row(eid, via)" in g and "updateNodeNavBar(null, null)" in g


def test_a_non_palace_build_is_byte_identical_to_the_shared_glue():
    d = copy.deepcopy(OUTLINE)
    out, _ = build_timeline(*load_brief(d))
    assert dx.AXIS_INDEX_GLUE in out
    assert "_palDoors" not in out and "pd-door" not in out and "pd-dept" not in out


def test_a_palace_build_carries_the_lobby(html):
    assert "window._palDoors=" in html and ".pd-door" in html and pd.axis_index_glue() in html
    assert dx.AXIS_INDEX_GLUE not in html


# ── in a browser ────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def browser():
    pw = pytest.importorskip("playwright.sync_api")
    with pw.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:
            pytest.skip(f"no chromium: {e}")
        yield b
        b.close()


@pytest.fixture(scope="module")
def page_file(tmp_path_factory, html):
    f = tmp_path_factory.mktemp("paldoors") / "page.html"
    f.write_text(html, encoding="utf-8")
    return f


def _open(browser, f, kind, w=1400, h=900, **kw):
    pg = browser.new_context(viewport={"width": w, "height": h}, **kw).new_page()
    pg.errs = []
    pg.on("pageerror", lambda e: pg.errs.append(str(e)))
    pg.goto(f.as_uri() + ("?mobile" if kw.get("is_mobile") else ""))
    pg.wait_for_timeout(1500)
    pg.evaluate(f"window.showAxisIndex({json.dumps(kind)})")
    pg.wait_for_timeout(300)
    return pg


@pytest.mark.parametrize("kind,n_entries", [("env", 6), ("theme", 3)])
def test_each_index_builds_as_a_lobby_of_doors(browser, page_file, kind, n_entries):
    pg = _open(browser, page_file, kind)
    got = pg.evaluate("""()=>({ doors:Array.from(document.querySelectorAll('#detail-content .pd-door')).map(b=>({
        exp:b.getAttribute('aria-expanded'), ctl:b.getAttribute('aria-controls'), tag:b.tagName, plaque:b.querySelector('.pd-plaque').textContent.trim(),
        name:b.querySelector('.pd-name').textContent, panel:!!document.getElementById(b.getAttribute('aria-controls')),
        hidden:getComputedStyle(document.getElementById(b.getAttribute('aria-controls'))).visibility})),
      rows:document.querySelectorAll('#detail-content .doc-row').length, hdr:!!document.querySelector('#detail-content .detail-header .pd-facade svg'),
      name:document.querySelector('#detail-content .detail-name').textContent})""")
    assert got["doors"] and all(d["tag"] == "BUTTON" and d["exp"] == "false" and d["panel"] and d["hidden"] == "hidden" for d in got["doors"])
    assert sum(int(d["plaque"].split()[0]) for d in got["doors"]) == n_entries == got["rows"]
    assert any(d["plaque"].startswith("1 ") and not d["plaque"].endswith("s") for d in got["doors"])   # a single entry is still a door
    assert got["hdr"] and not pg.errs
    pg.close()


def test_clicking_a_door_opens_its_department_and_closing_closes_it(browser, page_file):
    pg = _open(browser, page_file, "env")
    b = pg.locator("#detail-content .pd-door").first
    b.click()
    pg.wait_for_timeout(900)
    assert b.get_attribute("aria-expanded") == "true"
    dept = pg.locator("#detail-content .pd-dept").first
    assert "open" in dept.get_attribute("class")
    assert pg.evaluate("getComputedStyle(document.getElementById(arguments[0])).visibility".replace("arguments[0]", json.dumps(b.get_attribute('aria-controls')))) == "visible"
    assert pg.locator("#detail-content .pd-dept.open .doc-row-t").first.is_visible()
    assert pg.locator("#detail-content .pd-dept.open .alto-link[data-sd-type='node']").count() >= 1   # 'Appears in' links stay
    b.focus(); pg.keyboard.press("Enter"); pg.wait_for_timeout(900)                                  # a button: Enter closes it
    assert b.get_attribute("aria-expanded") == "false"
    pg.keyboard.press("Space"); pg.wait_for_timeout(900)
    assert b.get_attribute("aria-expanded") == "true"
    assert not pg.errs
    pg.close()


def test_open_all_and_a_deep_link_to_a_row(browser, page_file):
    pg = _open(browser, page_file, "env")
    pg.click(".pd-all"); pg.wait_for_timeout(700)
    assert pg.locator(".pd-dept.open").count() == pg.locator(".pd-dept").count()
    assert pg.inner_text(".pd-all") == "Close all"
    pg.click(".pd-all"); pg.wait_for_timeout(700)
    assert pg.locator(".pd-dept.open").count() == 0
    pg.evaluate("window.showAxisIndex('env', 'c4')"); pg.wait_for_timeout(1200)                       # a row opens its department
    assert pg.evaluate("document.querySelector('.doc-row-t[data-sd-id=c4]').closest('.pd-dept').classList.contains('open')")
    assert pg.locator(".pd-dept.open").count() == 1
    pg.close()


def test_on_a_phone_doors_are_two_up_and_only_one_stays_open(browser, page_file):
    pg = _open(browser, page_file, "env", w=390, h=844, device_scale_factor=2, is_mobile=True, has_touch=True)
    cols = pg.evaluate("getComputedStyle(document.querySelector('.pd-lobby')).gridTemplateColumns.split(' ').length")
    assert cols == 2
    assert not pg.locator(".pd-all").is_visible()
    doors = pg.locator("#detail-content .pd-door")
    doors.nth(0).tap(); pg.wait_for_timeout(700)
    doors.nth(1).tap(); pg.wait_for_timeout(700)
    assert pg.locator(".pd-dept.open").count() == 1 and doors.nth(1).get_attribute("aria-expanded") == "true"
    assert doors.nth(0).get_attribute("aria-expanded") == "false"
    assert pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
    pg.close()


def test_reduced_motion_crossfades_instead_of_swinging(browser, page_file):
    ctx = browser.new_context(viewport={"width": 1400, "height": 900}, reduced_motion="reduce")
    pg = ctx.new_page()
    pg.goto(page_file.as_uri()); pg.wait_for_timeout(1500)
    pg.evaluate("window.showAxisIndex('env')"); pg.wait_for_timeout(300)
    pg.click(".pd-door"); pg.wait_for_timeout(300)
    assert pg.evaluate("getComputedStyle(document.querySelector('.pd-dept.open .pd-leaf')).opacity") == "0"
    assert pg.evaluate("getComputedStyle(document.querySelector('.pd-dept.open .pd-leaf')).transform") in ("none", "matrix(1, 0, 0, 1, 0, 0)")
    pg.close()
