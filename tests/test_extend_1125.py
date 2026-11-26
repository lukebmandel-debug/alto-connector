"""Extend on an outline (Luke 2026-11-25; changed 2026-11-26).

- The owner turns Extend on per page (brief.extend: place_nodes(extend=…) or the editing bar's switch, the edit
  `pg|extend`): one setting for the whole outline.
- 2026-11-26 (Luke: "that doesn't mean reformat everything, to look this crazy, it should look largely the same as normal,
  just able to continue off on either side when necessary"; "extend mode should not be unit-specific, it messes with lines
  that span units, make it the whole outline"): Extend never lays the outline out again. The page is the normal tree, and its
  whole board grows past the window's edges where cards stand beyond them, as one surface: no unit scrolls on its own,
  no reader's switch (on and off would look the same), and lines between units are drawn as on any page.
- outline_plan(extend=True) (the row-subtrees layout) stays in the engine; no page uses it."""
import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "tools"))

import torts_fixture as tf  # noqa: E402
from alto.build import layout as L  # noqa: E402
from alto.build.brief import BriefError  # noqa: E402
from alto.build.builder import load_brief  # noqa: E402


def _plans(d):
    b, nodes, _ = load_brief(copy.deepcopy(d))
    return [L.plan_js(L.outline_plan(nodes, len(b.acts), b.placement, b.tree_lines, b.outcomes, e)) for e in (False, True)]


def test_extend_off_is_the_layout_without_extend_and_on_widens_instead_of_stacking():
    off, on = _plans(tf.negligence_brief(extend=False))
    assert "wide" not in off and on.get("wide", 0) > 0
    # off: the Negligence branches squeezed onto the page; on: full-width cards, side by side, past it
    assert max(off["x"].values()) <= 1700 and max(on["x"].values()) > 1700
    assert all(w >= 190 for w in on["w"].values())
    # a page with nothing wider than the window gets the same plan either way (the sample outline)
    d = json.loads((ROOT / "samples" / "outline_brief.json").read_text(encoding="utf-8"))
    a, b = _plans(d)
    assert a == {k: v for k, v in b.items() if k not in ("wide", "open")}


def test_outcomes_beside_stay_finite_with_extend():
    d = tf.negligence_brief()
    d["brief"]["outcomes"] = "beside"
    b, nodes, _ = load_brief(d)
    p = L.outline_plan(nodes, len(b.acts), b.placement, b.tree_lines, b.outcomes, True)
    assert 0 < p["wide"] < 6000, p["wide"]


def test_extend_must_be_true_or_false():
    d = tf.negligence_brief()
    d["brief"]["extend"] = "yes"
    from alto.build.brief import validate_brief
    with pytest.raises(BriefError):
        b, nodes, _ = load_brief(d)
        validate_brief(b)


def _cross(ext, shift=None):
    d = tf.negligence_brief(extend=ext)
    d["brief"]["relations"] = [{"key": "compare", "label": "Compare with"}]
    d["connections"] = [["duty", "strict-animals", "compare"]]              # a line from unit one into unit two
    if shift:
        d["brief"]["placement"]["damages"] = {"shift": shift}
    return tf.page(data=d)


def _plan_of(h):
    return h.split("window._ALTO_TREE_PLAN=", 1)[1].split(";", 1)[0]


def test_extend_keeps_the_normal_plan_and_carries_no_second_plan_or_readers_switch():
    on, off = _cross(True), _cross(False)
    assert _plan_of(on) == _plan_of(off)                                    # the same tree, card for card
    assert "_ALTO_EXTEND_PAGE=1" in on and "_ALTO_EXTEND_PAGE=1" not in off
    assert "_ALTO_TREE_PLAN_OFF=" not in on and "alto-extview-" not in on and "window._altoUnits=" not in on


def test_the_owners_switch_folds_into_the_brief():
    from alto.edits import _target
    brief = {"mode": "outline"}
    holder, f, kind = _target("pg|extend", brief, {}, [])
    assert (f, kind) == ("extend", "pgflag") and holder is brief
    assert _target("pg|extend", {"mode": "palace"}, {}, []) is None      # (a horizontal timeline takes it too: test_lanes_extend_1125)


def test_place_nodes_turns_extend_on_and_off(tmp_path):
    from alto import mcp_server as srv
    from alto.store.local import LocalStore
    srv.set_store(LocalStore(tmp_path))
    try:
        d = tf.negligence_brief(extend=False)
        pid = srv.create_project("Law School", "1L year", "studying")["project_id"]
        tid = srv.create_timeline(pid, d["brief"])["timeline_id"]
        srv.record_materials_consent(tid, [{"name": "notes.pdf", "kind": "notes"}], True)
        srv.set_entities(tid, d["brief"].get("entities") or [])
        assert "error" not in srv.add_nodes(tid, d["nodes"])
        r = srv.place_nodes(tid, extend=True)
        assert r["ok"], r
        assert srv.get_timeline(tid)["brief"].get("extend") is True
        r = srv.place_nodes(tid, extend=False)
        assert r["ok"] and "extend" not in srv.get_timeline(tid)["brief"]
    finally:
        srv.set_store(None)


# ── in the browser ───────────────────────────────────────────────────────────

try:
    import phone_matrix as pm
    _pw = pm._playwright()
except Exception:                                   # CI has no Playwright
    _pw = None
needs_pw = pytest.mark.skipif(_pw is None, reason="no Playwright")

GEO = """() => { const q = i => { const r = document.querySelector('#node-' + i + ' .node-card').getBoundingClientRect(); return [Math.round(r.left), Math.round(r.top)]; };
  const e = document.querySelector('#river-svg [data-edge="duty|strict-animals"]');
  return {cards: ['negligence', 'duty', 'breach', 'damages', 'strict', 'strict-animals'].map(q), line: e && e.getAttribute('d'), units: (window._altoUnits || []).length,
    wide: document.documentElement.classList.contains('alto-xwide'), sw: document.getElementById('canvas').scrollWidth, cw: document.getElementById('canvas').clientWidth,
    sw2: !!document.getElementById('ext-view-btn') && getComputedStyle(document.getElementById('ext-view-btn')).display !== 'none'}; }"""


def _run(pages, steps, vp=(1440, 900), query="", mobile=False):
    import asyncio
    s = pm.serve(pages, {}, {})

    async def go():
        out = {}
        async with _pw.async_playwright() as p:
            b = await p.webkit.launch()
            for name in pages:
                kw = {"viewport": {"width": vp[0], "height": vp[1]}, "color_scheme": "light"}
                if mobile:
                    kw.update(is_mobile=True, has_touch=True, device_scale_factor=2,
                              user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1")
                ctx = await b.new_context(**kw)
                pg = await ctx.new_page()
                await pg.goto(f"http://127.0.0.1:{s.server_address[1]}/{name}.html{query}", wait_until="load", timeout=45000)
                await pg.wait_for_timeout(3500)
                out[name] = await steps(pg)
                await ctx.close()
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


@needs_pw
def test_on_the_page_extend_looks_like_normal_and_a_line_between_units_is_the_same():
    async def steps(pg):
        return await pg.evaluate(GEO)
    r = _run({"on": _cross(True), "off": _cross(False)}, steps, query="?style=classic")
    assert r["on"]["cards"] == r["off"]["cards"], r                           # every card where the normal tree has it
    assert r["on"]["line"] and r["on"]["line"] == r["off"]["line"], r         # the line from unit one into unit two, unchanged
    assert r["on"]["units"] == 0 and not r["on"]["sw2"], r["on"]              # no unit scrolls on its own; no reader's switch


@needs_pw
def test_a_card_past_the_edge_opens_the_whole_board_with_extend_on_or_off():
    # (reverses interview question 4: Luke 2026-11-25, Torts, "I could not drag a node beyond the canvass with extend mode on or off")
    async def steps(pg):
        return await pg.evaluate(GEO)
    r = _run({"on": _cross(True, [1600, 0]), "off": _cross(False, [1600, 0])}, steps, query="?style=classic")
    for k in ("on", "off"):
        assert r[k]["wide"] and r[k]["sw"] > r[k]["cw"] and r[k]["units"] == 0, (k, r[k])   # one board, wider than the window, out to the card
    assert r["on"]["cards"] == r["off"]["cards"] and r["on"]["line"] == r["off"]["line"]


@needs_pw
@pytest.mark.parametrize("vp", [(390, 844), (844, 390)])
def test_phones_whole_view_is_the_normal_tree_and_has_no_extend_row(vp):
    async def steps(pg):
        return await pg.evaluate("() => [!!document.getElementById('ext-drawer-row'), (window._altoUnits || []).length]")
    r = _run({"on": _cross(True), "off": _cross(False)}, steps, vp=vp, query="?view=whole", mobile=True)
    assert r["on"] == r["off"] == [False, 0], r
