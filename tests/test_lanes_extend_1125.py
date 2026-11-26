"""Extend on a horizontal timeline (Luke 2026-11-25, "i'll accept your recs", the mock X5bdNtnEKbRMgjoBmCUtSU).

A page whose owner turned Extend on (brief.extend) skips the fit to the window: no eased gaps, no title-only cards,
no smaller cards, no fitStage scale. One row of cards a side; the board grows up and down instead, the view travels
there (a trackpad, a drag, the quiet cue 20 px in from the left), and the board runs behind the bars to the window's edge. Nested
children stay stacked beyond their parent; Compact | Expanded stays its own switch. The reader's switch beside Search
(glyph up and down) folds it back to today's board, kept per page in this browser. Phones: upright unchanged,
sideways (Whole view) gets it. A page without Extend carries LANES_JS byte for byte."""
import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from alto.build.builder import build_timeline, load_brief  # noqa: E402
from alto.build.lanes import LANES_JS, _EXT_SWAPS, lanes_ext_js  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

try:
    from playwright import sync_api as pw
    import phone_matrix as pm
    pm._playwright()
except Exception:                                   # CI has no Playwright
    pw = None


def _nested(extend):
    """The repo's nested sample, three levels deep (four more children), with or without Extend."""
    d = json.loads((ROOT / "samples" / "lanes_children_brief.json").read_text())
    by = {n["id"]: n for n in d["nodes"]}

    def add(i, p, t):
        n = {k: v for k, v in by[p].items() if k not in ("id", "nest", "title", "desc", "present", "flash")}
        n.update(id=i, nest=p, title=t, desc=t + ".")
        d["nodes"].append(n)
        by[i] = n
    add("warn-bell", "warn-terms", "Ring the bell at dusk")
    add("vote-for", "council-vote", "Seven for the new lamp")
    add("vote-against", "council-vote", "Four against: the cost")
    add("ada-proof", "council-ada", "She reads the 1870 entry aloud")
    if extend:
        d["brief"]["extend"] = True
    return d


def _tall():
    """The nested sample with Extend on and two long stacks of children (like a big event holding a whole unit)."""
    d = _nested(True)
    mains = [n for n in d["nodes"] if not n.get("nest")][:2]
    for m in mains:
        for k in range(24):
            n = {kk: v for kk, v in m.items() if kk not in ("id", "nest", "title", "desc", "present", "flash")}
            n.update(id=f"{m['id']}-k{k}", nest=m["id"], title=f"Entry {k + 1} under {m['title']}", desc="A child entry.")
            d["nodes"].append(n)
    return d


def _page(d):
    return build_timeline(*load_brief(copy.deepcopy(d)))[0]


# ── the page ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name", ["lanes_brief", "lanes_children_brief", "lanes_v2_brief"])
def test_a_page_without_extend_carries_the_lanes_script_untouched(name):
    h = _page(json.loads((ROOT / "samples" / f"{name}.json").read_text()))
    assert LANES_JS in h
    assert "window._altoLanesExtOn=function" not in h and "ln-ext-cue" not in h and "ext-view-btn" not in h


def test_a_page_with_extend_carries_the_variant_switch_and_cues():
    h = _page(_nested(True))
    assert LANES_JS not in h and lanes_ext_js("lighthouse").split("window._ALTO_EXT_KEY=")[0] in h
    for a, b in _EXT_SWAPS:
        assert b in h
    assert "window._ALTO_EXTEND_PAGE=1" in h and "ext-view-btn" in h and "ln-ext-cue" in h
    assert 'M8 4v16M8 4l-3 3M8 4l3 3M16 20V4M16 20l-3-3M16 20l3-3' in h        # the switch's glyph: up and down
    assert "M3 12h18M7 8l-4 4 4 4M17 8l4 4-4 4" not in h                          # (not the outline's sideways one)


def test_the_owner_switch_folds_into_a_horizontal_timelines_brief():
    from alto import edits
    d = _nested(False)
    holder, f, kind = edits._target("pg|extend", d["brief"], {n["id"]: n for n in d["nodes"]}, [])
    assert (f, kind) == ("extend", "pgflag") and holder is d["brief"]


def test_place_nodes_takes_extend_alone_on_a_horizontal_timeline(monkeypatch):
    from alto import mcp_server as ms
    d = _nested(False)
    saved = {}

    class St:
        def put_timeline(self, u, t, doc):
            saved["doc"] = doc
    monkeypatch.setattr(ms, "_timeline_or_error", lambda t: (copy.deepcopy(d), None))
    monkeypatch.setattr(ms, "get_store", lambda: St())
    monkeypatch.setattr(ms, "uid", lambda: "u1")
    f = getattr(ms.place_nodes, "__wrapped__", ms.place_nodes)
    while hasattr(f, "__wrapped__"):
        f = f.__wrapped__
    r = f("lighthouse", extend=True)
    assert r.get("ok") and saved["doc"]["brief"]["extend"] is True
    r = f("lighthouse", extend=False)
    assert r.get("ok") and "extend" not in saved["doc"]["brief"]
    assert f("lighthouse", placements={"arrive": {"x": 1}}).get("error") == "needs_outline"


# ── in a real browser (WebKit) ───────────────────────────────────────────────

ST = """() => { const c = document.getElementById('canvas'), w = document.getElementById('world'), f = window._altoLanesFit || {}, de = document.documentElement;
  const R = [], cards = [...document.querySelectorAll('#world .node')].filter(n => getComputedStyle(n).display !== 'none' && n.querySelector('.node-card'));
  cards.forEach(n => R.push(n.querySelector('.node-card').getBoundingClientRect()));
  let ov = 0; for (let i = 0; i < R.length; i++) for (let j = i + 1; j < R.length; j++) { const a = R[i], b = R[j];
    if (a.left < b.right - 2 && b.left < a.right - 2 && a.top < b.bottom - 2 && b.top < a.bottom - 2) ov++; }
  const sw = document.getElementById('ext-view-btn'), cue = [...document.querySelectorAll('.ln-ext-cue')].filter(b => !b.hidden).map(b => b.getBoundingClientRect());
  return {on: !!(window._altoLanesExtOn && window._altoLanesExtOn()), k: w.getBoundingClientRect().width / w.offsetWidth, scale: w.style.scale,
    compact: de.classList.contains('ln-compact'), cz: de.classList.contains('ln-cz'), R: f.mode && f.mode.R, u: f.mode && f.mode.u, need: f.need, A: f.A,
    mt: c.scrollHeight - c.clientHeight, top: c.scrollTop, overlaps: ov, n: cards.length,
    sw: sw ? {shown: sw.style.display !== 'none', pressed: sw.getAttribute('aria-pressed'), halo: getComputedStyle(sw).boxShadow} : null,
    cues: cue.map(r => [Math.round(r.left), Math.round(r.top), Math.round(r.width)]), off: de.classList.contains('alto-ext-off')}; }"""
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) "
      "Version/18.0 Mobile/15E148 Safari/604.1")


@pytest.fixture(scope="module")
def site():
    if pw is None:
        pytest.skip("no Playwright")
    s = pm.serve({"on": _page(_nested(True)), "plain": _page(_nested(False)), "tall": _page(_tall())}, {}, {})
    with pw.sync_playwright() as p:
        try:
            b = p.webkit.launch()
        except Exception as e:
            pytest.skip(f"no WebKit: {e}")
        yield b, f"http://127.0.0.1:{s.server_address[1]}"
        b.close()
    s.shutdown()


def _open(site, name, w=1440, h=900, phone=False, q="", expanded=False):
    b, base = site
    kw = dict(viewport={"width": w, "height": h})
    if phone:
        kw.update(is_mobile=True, has_touch=True, user_agent=UA, device_scale_factor=2)
    ctx = b.new_context(**kw)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(f"{base}/{name}.html{q}", wait_until="load")
    pg.wait_for_timeout(3000)
    if expanded:
        pg.evaluate("() => window._altoLanesKids.view('expanded')")
        pg.wait_for_timeout(1500)
    pg._errs = errs
    return ctx, pg


def test_on_the_board_keeps_its_full_spacing_and_grows_up_and_down(site):
    ctx, pg = _open(site, "on", expanded=True)
    s = pg.evaluate(ST)
    assert s["on"] and not s["scale"] and not s["compact"] and not s["cz"], s        # no fitStage scale, whole cards, full size
    assert s["R"] == 1 and s["u"] == 1, s                                            # one row a side, the gaps at their roomiest
    assert s["mt"] > 200 and s["overlaps"] == 0, s                                   # taller than the window: it scrolls; nothing on top of anything
    assert s["sw"]["shown"] and s["sw"]["pressed"] == "true", s                      # the switch, lit
    assert s["cues"] and s["cues"][0][0] == 20, s                                    # the quiet cue, 20 px in, on the side with more
    pg.click(".ln-ext-cue:not([hidden])")
    pg.wait_for_timeout(1500)
    t = pg.evaluate(ST)
    assert t["top"] > 150, t                                                         # it went down
    masked = pg.evaluate("() => [...document.querySelectorAll('#world > *')].filter(e => e.style.maskImage || e.style.webkitMaskImage).map(e => e.id)")
    assert not masked, masked                                                        # no fade: the board runs behind the bars to the window's edge (Luke 2026-11-25)
    assert not pg._errs, pg._errs
    ctx.close()


def test_off_is_todays_board_and_the_readers_choice_survives_a_reload(site):
    ctx0, pg0 = _open(site, "plain", expanded=True)
    today = pg0.evaluate(ST)
    ctx0.close()
    ctx, pg = _open(site, "on", expanded=True)
    pg.click("#ext-view-btn")
    pg.wait_for_timeout(1500)
    s = pg.evaluate(ST)
    assert s["off"] and not s["on"] and s["sw"]["pressed"] == "false", s
    for k in ("scale", "compact", "cz", "R", "need", "A", "n"):
        assert s[k] == today[k], (k, s[k], today[k])                                 # the fit, as a page without Extend has it
    assert abs(s["k"] - today["k"]) < .002
    pg.reload(wait_until="load")
    pg.wait_for_timeout(3000)
    assert pg.evaluate(ST)["off"]                                                    # kept for this page in this browser
    pg.click("#ext-view-btn")
    pg.wait_for_timeout(1200)
    assert pg.evaluate(ST)["on"]
    ctx.close()


def test_nested_children_stay_stacked_beyond_their_parent(site):
    ctx, pg = _open(site, "on", expanded=True)
    g = pg.evaluate("""() => { const r = i => document.querySelector('#node-' + i + ' .node-card').getBoundingClientRect();
      const P = r('warning'), T = r('warn-terms'), K = ['warn-lamp', 'warn-rock', 'warn-bell'].map(r), C = r('council'), V = r('council-vote');
      return {P: [P.left, P.top, P.bottom], T: [T.left, T.top, T.bottom], K: K.map(k => [k.left, k.top, k.bottom]), C: [C.top, C.bottom], V: [V.left, V.top]}; }""")
    assert g["T"][2] <= g["P"][1] + 1                                                 # above the line: the child above its parent
    assert all(k[2] <= g["T"][1] + 1 for k in g["K"])                                # its own children above it
    assert len({round(k[0]) for k in g["K"]}) == 1                                   # in one column (stacked, not fanned)
    assert g["V"][1] >= g["C"][1] - 1                                                # below the line: the child below its parent
    ctx.close()


def test_phones_upright_unchanged_sideways_extended(site):
    ctx0, pg0 = _open(site, "plain", 390, 844, phone=True, q="?view=whole")
    up0 = pg0.evaluate(ST)
    ctx0.close()
    ctx, pg = _open(site, "on", 390, 844, phone=True, q="?view=whole")
    up = pg.evaluate(ST)
    assert not up["on"] and not up["cues"], up
    for k in ("scale", "compact", "cz", "R", "need", "A"):
        assert up[k] == up0[k], (k, up[k], up0[k])
    ctx.close()
    ctx, pg = _open(site, "on", 844, 390, phone=True, q="?view=whole")
    s = pg.evaluate(ST)
    if pg.evaluate("() => document.documentElement.classList.contains('phone-whole')"):
        assert s["on"] and not s["cz"] and not s["compact"], s                       # sideways: whole cards, full size
        row = pg.evaluate("() => { const r = document.getElementById('ext-drawer-row'); return r ? getComputedStyle(r).display : null; }")
        assert row is None or row != "none"
    assert not pg._errs, pg._errs
    ctx.close()


# ── the unit labels stay in view (Luke 2026-11-25: "unit labels in expanded horizontal timeline need to be visible at all times") ──

UNIT = """() => { const W = innerWidth, H = innerHeight;
  return [...document.querySelectorAll('#world .lanes-unit')].map(u => { const r = u.getBoundingClientRect(), c = u.querySelector('.lu-chip').getBoundingClientRect();
    return {ul: r.left, ur: r.right, l: c.left, r: c.right, t: c.top, b: c.bottom, pin: u.querySelector('.lu-chip').classList.contains('lu-pin')}; })
    .filter(u => u.ur > 0 && u.ul < W); }"""


@pytest.mark.parametrize("page", ["on", "plain"])
def test_the_units_label_stays_in_view_down_and_along_the_board(site, page):
    ctx, pg = _open(site, page, expanded=True)
    pg.evaluate("() => { const o = document.getElementById('ln-offer'); if (o) o.remove(); }")
    for _ in range(3):                                                   # along the line, into the middle of a unit
        pg.keyboard.press("ArrowRight")
        pg.wait_for_timeout(700)
    pg.wait_for_timeout(1000)
    if page == "on":
        pg.evaluate("() => window._altoLanesVy(5000)")                    # and all the way down
        pg.wait_for_timeout(1800)
    us = pg.evaluate(UNIT)
    lead = min(us, key=lambda u: u["ul"])                                 # the unit at the left edge
    assert lead["t"] >= 104 and lead["b"] <= 900 - 62, lead              # below the bars at the top, in the window
    assert lead["l"] >= 20 and lead["r"] <= 1440, lead                    # 20 px in from the left at least
    assert lead["l"] >= lead["ul"] - 1 and lead["r"] <= lead["ur"] + 1, lead   # never out of its own unit
    if page == "on":
        assert lead["pin"] and lead["l"] >= 66 - 1, lead                  # riding the top, clear of the quiet cue
    assert not pg._errs, pg._errs
    ctx.close()



# ── going behind the bars "like normal" (Luke 2026-11-25; Board B-1125-UNITPIN-HOLD): no fade, and no card text ever shows
#    through the title, a chip or a button — each one the board passes under has its own solid or frosted backing ──

CHROME = r"""() => {
  const de = document.documentElement, W = innerWidth, H = innerHeight;
  // card text lines at rest: every text-bearing element inside a visible card
  const txt = [];
  document.querySelectorAll('#world .node-card').forEach(c => { if (getComputedStyle(c.closest('.node')).display === 'none') return;
    c.querySelectorAll('.node-title,.node-desc,.node-tag,.lanes-when,.node-footer,.ref-chip,[class*=chip]').forEach(e => { const r = e.getBoundingClientRect(); if (r.width && r.height && r.bottom > 0 && r.top < H && r.right > 0 && r.left < W) txt.push(r); }); });
  // the page's fixed chrome: everything position:fixed (or inside it) that is not the board
  const cv = document.getElementById('canvas'), out = [];
  const all = [...document.body.querySelectorAll('*')].filter(e => !cv.contains(e) || e.classList.contains('lu-pin'));
  all.forEach(e => {
    const c = getComputedStyle(e); if (c.display === 'none' || c.visibility === 'hidden' || parseFloat(c.opacity) < .05) return;
    const r = e.getBoundingClientRect(); if (!r.width || !r.height || r.width > W * .9 && r.height > H * .5) return;   // (full-window layers: the backdrop, panels)
    if (r.bottom < 0 || r.top > H || r.right < 0 || r.left > W) return;
    // does this element paint something (text or a box) of its own?
    const ownText = [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim()), box = e.tagName === 'BUTTON' || e.tagName === 'svg' || ownText;
    if (!box) return;
    const hit = txt.some(t => t.left < r.right && r.left < t.right && t.top < r.bottom && r.top < t.bottom); if (!hit) return;
    // its backing: the first ancestor-or-self with a background or backdrop
    let x = e, bg = null;
    while (x && x !== document.body) { const s = getComputedStyle(x), a = (s.backgroundColor.match(/[\d.]+/g) || []).map(Number), al = s.backgroundColor === 'transparent' ? 0 : a.length > 3 ? a[3] : (a.length ? 1 : 0), bf = (s.backdropFilter && s.backdropFilter !== 'none' ? s.backdropFilter : s.webkitBackdropFilter) || 'none';
      if (al > 0.05 || bf !== 'none' || s.backgroundImage !== 'none') { bg = {el: (x.id || x.className.toString()).slice(0, 30), alpha: al, blur: bf, img: s.backgroundImage !== 'none'}; break; } x = x.parentElement; }
    out.push({el: (e.id || e.className.toString() || e.tagName).slice(0, 30), text: (e.textContent || '').trim().slice(0, 24), r: [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)], bg});
  });
  return {style: de.className.match(/alto-(retro|holo)/) ? de.className.match(/alto-(retro|holo)/)[0] : 'classic', n: out.length, bare: out.filter(o => !o.bg), weak: out.filter(o => o.bg && !(o.bg.alpha >= .9 || o.bg.img || (o.bg.blur !== 'none' && o.bg.alpha >= .3))), all: out.slice(0, 12)};
}"""


@pytest.mark.parametrize("style,w,h,phone", [("classic", 1440, 900, False), ("retro", 1440, 900, False), ("holo", 1440, 900, False),
                                              ("classic", 844, 390, True), ("retro", 844, 390, True)],
                         ids=["d1440-classic", "d1440-retro", "d1440-holo", "l844-classic", "l844-retro"])
def test_nothing_over_the_board_lets_card_text_show_through(site, style, w, h, phone):
    b, base = site
    kw = dict(viewport={"width": w, "height": h})
    if phone:
        kw.update(is_mobile=True, has_touch=True, user_agent=UA, device_scale_factor=2)
    ctx = b.new_context(**kw)
    if style != "classic":
        ctx.add_init_script("localStorage.setItem('alto-hl-lanes-children-style', '%s')" % style)
    pg = ctx.new_page()
    pg.goto(f"{base}/on.html" + ("?view=whole" if phone else ""), wait_until="load")
    pg.wait_for_timeout(3500)
    pg.evaluate("() => { window._altoLanesKids.view('expanded'); const o = document.getElementById('ln-offer'); if (o) o.remove(); }")
    pg.wait_for_timeout(1500)
    seen = 0
    for dy in (260, 260, 300, 400):                                       # the board run up under the bars step by step, each time at rest
        pg.evaluate("(d) => window._altoLanesVy(d)", dy)
        pg.wait_for_timeout(1600)
        d = pg.evaluate(CHROME)
        assert d["style"] == ("classic" if style == "classic" else "alto-" + style), d["style"]
        assert not d["bare"] and not d["weak"], (dy, d["bare"], d["weak"])
        seen += d["n"]
    assert seen > 0                                                       # (the board did run under them)
    if not phone:                                                         # the brand marks in the top corners keep a backing too
        marks = pg.evaluate("""() => document.documentElement.classList.contains('ln-under') ? [...document.querySelectorAll('#title-bar > svg.brand-mark, #title-bar > svg.brand-word')]
          .map(e => { const s = getComputedStyle(e); return [s.backgroundColor, s.backdropFilter || s.webkitBackdropFilter || 'none']; }) : null""")
        assert marks, marks
        assert all(bg not in ("rgba(0, 0, 0, 0)", "transparent") for bg, _ in marks), marks
    masked = pg.evaluate("() => [...document.querySelectorAll('#world > *')].filter(e => e.style.maskImage || e.style.webkitMaskImage).length")
    assert masked == 0                                                    # and no fade
    ctx.close()


ROOM = """() => { const t = 104 + 8, b = innerHeight - 62 - 8; let n = 0;
  document.querySelectorAll('#world .node .node-card').forEach(c => { const r = c.getBoundingClientRect(), id = c.closest('.node').id.slice(5);
    if (!window._altoLanesKids.nest(id) && r.height && r.bottom > t && r.top < b && r.right > 0 && r.left < innerWidth) n++; });     // (the main line's own cards)
  const c = document.getElementById('canvas'); return {n, mt: c.scrollHeight - c.clientHeight, top: c.scrollTop}; }"""


def test_a_tall_board_opens_expanded_on_its_main_line_not_its_top_edge(site):
    """Luke's civ-pro events board (2026-11-26): an event holding a whole unit made the Expanded board taller than the window,
    and it opened on its empty top edge. It now opens (and turns Expanded) resting on the main line."""
    ctx, pg = _open(site, "tall", expanded=True)
    r = pg.evaluate(ROOM)
    assert r["mt"] > 1800, r                                              # (a board well taller than the window)
    assert r["n"] >= 2, r                                                 # turned Expanded: the main line's cards in the room, not the top edge
    pg.reload(wait_until="load")
    pg.wait_for_timeout(3500)
    assert pg.evaluate("() => window._altoLanesKids.view()") == "expanded"
    r = pg.evaluate(ROOM)
    assert r["n"] >= 2, r                                                 # opened Expanded: the same
    pg.evaluate("(d) => window._altoLanesVy(d)", -5000)                  # a height the hand chose stays the hand's
    pg.wait_for_timeout(1500)
    assert pg.evaluate(ROOM)["top"] < 5, r
    assert not pg._errs, pg._errs
    ctx.close()
