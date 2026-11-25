"""Extend, done properly (Luke 2026-11-25; interview ORG/notes-ceo/extend-interview-1125.md).

- The owner turns Extend on per page (brief.extend: place_nodes(extend=…) or the editing bar's switch, the edit
  `pg|extend`). Off, the page is laid out exactly as it was before Extend.
- On, each unit's rows keep their cards' width and a unit wider than the window scrolls sideways on its own
  (row-subtrees); the page also carries the plan without Extend, for the reader's switch.
- The reader's switch sits in the bottom row just left of Search, in the look of its neighbours, and only on a page
  whose owner turned Extend on; it never takes an editing button's place. Phones: a MENU row in the Whole view.
- Without Extend, a card placed past the page's edge comes back inside it."""
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


def test_the_page_carries_both_plans_and_the_switch_only_when_the_owner_turned_extend_on():
    on = tf.page(data=tf.negligence_brief())
    off = tf.page(data=tf.negligence_brief(extend=False))
    assert "_ALTO_TREE_PLAN_OFF=" in on and "_ALTO_EXTEND_PAGE=1" in on and "alto-extview-" in on
    assert "_ALTO_TREE_PLAN_OFF=" not in off and "_ALTO_EXTEND_PAGE=1" not in off
    assert "html:not(.mobile).alto-ext-off #node-" in on           # each plan's card widths hold in its own view
    assert ".alto-ext-off" not in off.split("<style", 1)[0]


def test_the_owners_switch_folds_into_the_brief():
    from alto.edits import _target
    brief = {"mode": "outline"}
    holder, f, kind = _target("pg|extend", brief, {}, [])
    assert (f, kind) == ("extend", "pgflag") and holder is brief
    assert _target("pg|extend", {"mode": "lanes"}, {}, []) is None


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

SWITCH = """() => { const b = document.getElementById('ext-view-btn'), s = document.getElementById('search-btn'),
    i = document.getElementById('info-btn');
  if(!b) return null; const r = b.getBoundingClientRect(), q = s.getBoundingClientRect(), n = i.getBoundingClientRect();
  const hits = [...document.querySelectorAll('#search-btn,#info-btn,#mode-toggle,#alto-edit-pill,#account-btn,#tab-rail')]
    .map(e => e.getBoundingClientRect()).filter(o => o.width && r.left < o.right && o.left < r.right && r.top < o.bottom && o.top < r.bottom).length;
  return {shown: getComputedStyle(b).display !== 'none', l: r.left, r: r.right, t: r.top, w: r.width, h: r.height,
          sl: q.left, st: q.top, sw: q.width, gap: q.left - r.right, gap2: n.left - q.right, hits: hits, edge: innerWidth - r.right}; }"""


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
@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
def test_the_readers_switch_sits_left_of_search_as_one_of_the_row(style):
    async def steps(pg):
        return await pg.evaluate(SWITCH)
    res = _run({"on": tf.page(data=tf.negligence_brief()), "off": tf.page(data=tf.negligence_brief(extend=False))},
               steps, query=f"?style={style}")
    assert res["off"] is None                                                 # not on a page without Extend
    r = res["on"]
    assert r["shown"] and r["hits"] == 0, r                                   # takes no button's place
    assert abs(r["w"] - r["sw"]) < 1 and abs(r["t"] - r["st"]) < 1, r        # the row's size and line
    assert abs(r["gap"] - r["gap2"]) < 1.5, r                                # the row's own spacing


@needs_pw
def test_switching_off_folds_each_unit_into_the_window_and_is_remembered():
    async def steps(pg):
        out = {"u0": await pg.evaluate("() => (window._altoUnits||[]).length")}
        await pg.click("#ext-view-btn")
        await pg.wait_for_timeout(1500)
        out["off"] = await pg.evaluate("""() => ({u: (window._altoUnits||[]).length, cls: document.documentElement.classList.contains('alto-ext-off'),
            right: Math.max(...[...document.querySelectorAll('#world .node[id^=node-]')].map(e => e.getBoundingClientRect().right)), vw: innerWidth,
            sw: document.getElementById('canvas').scrollWidth - document.getElementById('canvas').clientWidth,
            pressed: document.getElementById('ext-view-btn').getAttribute('aria-pressed')})""")
        await pg.reload(wait_until="load")
        await pg.wait_for_timeout(3500)
        out["again"] = await pg.evaluate("() => [document.documentElement.classList.contains('alto-ext-off'), (window._altoUnits||[]).length]")
        return out
    r = _run({"on": tf.page(data=tf.negligence_brief())}, steps, query="?style=classic")["on"]
    assert r["u0"] == 2
    o = r["off"]
    assert o["u"] == 0 and o["cls"] and o["pressed"] == "false", o
    assert o["right"] <= o["vw"] and o["sw"] <= 2, o                          # everything on the page, no sideways scroll
    assert r["again"] == [True, 0]


@needs_pw
def test_without_extend_a_card_past_the_edge_comes_back_inside():
    d = tf.negligence_brief(extend=False)
    d["brief"]["placement"]["damages"] = {"shift": [1600, 0]}
    d2 = tf.negligence_brief()
    d2["brief"]["placement"]["damages"] = {"shift": [1600, 0]}

    async def steps(pg):
        return await pg.evaluate("""() => { const w = document.getElementById('world'), k = w.getBoundingClientRect().width / w.offsetWidth;
            const e = document.getElementById('node-damages'); return [parseFloat(e.style.left), (window._altoUnits||[]).map(u => u.max)]; }""")
    r = _run({"off": tf.page(data=d), "on": tf.page(data=d2)}, steps, query="?style=classic")
    assert r["off"][0] <= 1680 - 190 / 2, r["off"]                             # pulled back onto the page, 20 px clear (a 190 px card)
    assert r["on"][0] > 1700 and r["on"][1][0] > 0, r["on"]                    # with Extend: its row reaches it


@needs_pw
def test_phones_whole_view_has_the_switch_in_the_menu_and_card_view_has_none():
    async def steps(pg):
        await pg.evaluate("() => window.openNavDrawer && openNavDrawer()")
        await pg.wait_for_timeout(700)
        return await pg.evaluate("""() => { const r = document.getElementById('ext-drawer-row'), b = document.getElementById('ext-view-btn');
            return {row: r ? [getComputedStyle(r).display, r.getBoundingClientRect().height, r.textContent] : null,
                    btn: b ? getComputedStyle(b).display : null, sw: document.documentElement.scrollWidth, iw: innerWidth}; }""")
    page = tf.page(data=tf.negligence_brief())
    whole = _run({"w": page}, steps, vp=(390, 844), query="?style=classic&view=whole", mobile=True)["w"]
    assert whole["row"][0] != "none" and whole["row"][1] >= 44 and "Extend" in whole["row"][2], whole
    assert whole["sw"] == whole["iw"]
    card = _run({"c": page}, steps, vp=(390, 844), query="?style=classic", mobile=True)["c"]
    assert card["btn"] in (None, "none") and (card["row"] is None or card["row"][0] == "none"), card
    assert card["sw"] == card["iw"]


@needs_pw
@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
def test_no_halo_a_quiet_cue_and_the_row_end_fades_before_the_rail(style):
    # Luke 2026-11-25: "i don't think we need the halo effect, find another way to indicate extend mode is on"
    async def steps(pg):
        return await pg.evaluate("""() => { const u = window._altoUnits[0], rail = document.getElementById('tab-rail').getBoundingClientRect().left;
          const glow = [...document.querySelectorAll('#world *')].filter(e => { const s = getComputedStyle(e), r = e.getBoundingClientRect();
            return r.height > 300 && r.width < 120 && (s.backdropFilter || s.webkitBackdropFilter || 'none') !== 'none' && !e.closest('.node'); }).length;
          const R = u.R.getBoundingClientRect(), masks = [...document.querySelectorAll('#world .node-card')].filter(c => (c.style.maskImage || c.style.webkitMaskImage)).length;
          const cut = [...document.querySelectorAll('#world .node-card')].filter(c => c.style.clipPath).length;
          const lit = getComputedStyle(document.getElementById('ext-view-btn')).boxShadow.indexOf('inset') >= 0;
          return {glow, right: [R.left, R.right, getComputedStyle(u.R).opacity], rail, masks, cut, lit, old: document.querySelectorAll('.alto-edge').length}; }""")
    r = _run({"on": tf.page(data=tf.negligence_brief())}, steps, query=f"?style={style}")["on"]
    assert r["glow"] == 0 and r["old"] == 0, r                                # no glowing panel
    assert float(r["right"][2]) > 0.5 and r["right"][1] <= r["rail"] - 20, r  # the arrow says there is more, clear of the rail
    assert r["masks"] >= 1 and r["masks"] >= r["cut"] and r["lit"], r       # a card at the end fades out before any clip; the switch is lit
