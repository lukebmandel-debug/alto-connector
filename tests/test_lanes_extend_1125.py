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
    assert "window._ALTO_EXTEND_PAGE=1" in h and "ext-view-btn" in h and "lnv-main" in h and "ln-main-pill" not in h and "ln-ext-cue" not in h
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
  const sw = document.getElementById('ln-view'), cue = [...document.querySelectorAll('#lanes-nav .lnv-main.on')].map(b => b.getBoundingClientRect());
  return {on: !!(window._altoLanesExtOn && window._altoLanesExtOn()), k: w.getBoundingClientRect().width / w.offsetWidth, scale: w.style.scale,
    compact: de.classList.contains('ln-compact'), cz: de.classList.contains('ln-cz'), R: f.mode && f.mode.R, u: f.mode && f.mode.u, need: f.need, A: f.A,
    mt: c.scrollHeight - c.clientHeight, top: c.scrollTop, overlaps: ov, n: cards.length,
    sw: sw ? {shown: getComputedStyle(sw).display !== 'none' && +getComputedStyle(sw).opacity > .9, pressed: sw.getAttribute('aria-pressed'), halo: getComputedStyle(sw).boxShadow,
      underScene: sw.parentNode.id === 'tab-rail' && sw.previousElementSibling && sw.previousElementSibling.id === 'bg-toggle'} : null,
    beside: !!document.getElementById('ext-view-btn'),
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
    assert s["sw"]["shown"] and s["sw"]["pressed"] == "true" and s["sw"]["underScene"], s   # the one switch, lit, in the right rail under Scene
    assert not s["cues"] and not pg.evaluate("document.querySelectorAll('.ln-ext-cue').length"), s   # no up / down arrows (Luke 2026-11-26); the line in view: no pill
    ctx.close()
    ctx, pg = _open(site, "tall", expanded=True)                                     # a board whose branches run far past the window
    pg.evaluate("() => { const c = document.getElementById('canvas'); c.scrollTop = c.scrollHeight; }")   # down a long branch: the line leaves the view
    pg.wait_for_timeout(700)
    t = pg.evaluate(ST)
    P = pg.evaluate("""() => { const p = document.querySelector('#lanes-nav .lnv-main'), r = p.getBoundingClientRect(), n = document.getElementById('lanes-nav'), c = document.getElementById('canvas'),
        a = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2), sv = p.querySelector('svg');
      return {first: n.firstElementChild === p, w: r.width, hit: !!(a && a.closest('.lnv-main')), sl: c.scrollLeft, text: p.textContent, label: p.getAttribute('aria-label'), turn: sv.style.transform}; }""")
    # in the step bar, its first button, the line's own name with an arrow to where the line is (above: scrolled down)
    assert t["cues"] and P["first"] and P["hit"] and P["w"] > 60 and P["text"] and "above" in P["label"] and not P["turn"], P
    pg.click("#lanes-nav .lnv-main")                                                 # back: the line centred, no sideways move
    pg.wait_for_timeout(1800)
    back = pg.evaluate("""() => ({off: window._altoLanesMainOff(), sl: document.getElementById('canvas').scrollLeft, pill: document.querySelector('#lanes-nav .lnv-main').classList.contains('on')})""")
    assert abs(back["off"]) < 24 and abs(back["sl"] - P["sl"]) < 1 and not back["pill"], back
    masked = pg.evaluate("() => [...document.querySelectorAll('#world > *')].filter(e => e.style.maskImage || e.style.webkitMaskImage).map(e => e.id)")
    assert not masked, masked                                                        # no fade: the board runs behind the bars to the window's edge (Luke 2026-11-25)
    assert not pg._errs, pg._errs
    ctx.close()


def test_one_switch_compact_is_todays_board_and_expanding_turns_extend_on(site):
    """Luke 2026-11-26: "move the expanded view square toggle to the right sidebar below scene, and eliminate the other extend toggle
    ... If a user exapands a nested branch or hits the expand all toggle we are moving, then extend mode automatically activates." """
    ctx0, pg0 = _open(site, "plain")
    today = pg0.evaluate(ST)
    ctx0.close()
    ctx, pg = _open(site, "on")
    s = pg.evaluate(ST)
    assert not s["on"] and not s["beside"] and s["sw"]["underScene"] and s["sw"]["shown"] and s["sw"]["pressed"] == "false", s
    for k in ("scale", "compact", "cz", "R", "need", "A", "n"):
        assert s[k] == today[k], (k, s[k], today[k])                                 # Compact: the fit, as a page without Extend has it
    assert abs(s["k"] - today["k"]) < .002
    pg.click("#ln-view")                                                             # Expanded (expand all): Extend comes on
    pg.wait_for_timeout(1500)
    t = pg.evaluate(ST)
    assert t["on"] and t["sw"]["pressed"] == "true" and t["mt"] > 200 and not t["scale"], t
    pg.click("#ln-view")
    pg.wait_for_timeout(1500)
    assert not pg.evaluate(ST)["on"]
    pg.evaluate("() => window._altoLanesKids.open('warning', true)")                # one branch opened: Extend comes on
    pg.wait_for_timeout(1200)
    assert pg.evaluate(ST)["on"]
    pg.evaluate("() => window._altoLanesKids.open('warning', false)")               # and goes off when it closes
    pg.wait_for_timeout(1200)
    u = pg.evaluate(ST)
    assert not u["on"] and u["scale"] == today["scale"], u
    assert not pg._errs, pg._errs
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

UNIT = """() => { const W = innerWidth, ml = document.querySelector('#lanes-svg path.ln-main, #lanes-svg .ln-main');
  const lineAt = sx => { const m = ml.getScreenCTM(), L = ml.getTotalLength(); let best = null, bd = 1e9;      // the main line's height on the screen at sx
    for (let i = 0; i <= 400; i++) { const p = ml.getPointAtLength(L * i / 400), x = m.a * p.x + m.c * p.y + m.e; if (Math.abs(x - sx) < bd) { bd = Math.abs(x - sx); best = m.b * p.x + m.d * p.y + m.f; } } return best; };
  const dots = [...document.querySelectorAll('#lanes-svg .ln-dot, #lanes-svg .ln-ring')].map(d => d.getBoundingClientRect()).filter(r => r.width);
  const cards = [...document.querySelectorAll('#world .node-card')].map(c => c.getBoundingClientRect()).filter(r => r.width);
  return [...document.querySelectorAll('#lanes-ulabels .lu-chip')].map(e => { const r = e.getBoundingClientRect(), hit = q => q.left < r.right && r.left < q.right && q.top < r.bottom && r.top < q.bottom;
    return {l: r.left, r: r.right, t: r.top, b: r.bottom, line: lineAt((r.left + r.right) / 2), cy: (r.top + r.bottom) / 2, pin: e.classList.contains('lu-pin'), dots: dots.filter(hit).length, cards: cards.filter(hit).length,
      z: getComputedStyle(e.parentElement).zIndex,
      btn: [...document.querySelectorAll('#key-toggle')].filter(q => getComputedStyle(q).display !== 'none').map(q => q.getBoundingClientRect()).filter(q => q.width && hit(q)).length}; })
    .filter(u => u.r > 0 && u.l < W); }"""


@pytest.mark.parametrize("page", ["on", "plain"])
def test_the_units_label_sits_on_the_main_line_and_stays_in_view_along_it(site, page):
    """Luke 2026-11-26: "i want unit labels embedded in the main timeline, not free floating" (and 2026-11-25: visible at all times)."""
    ctx, pg = _open(site, page, expanded=True)
    pg.evaluate("() => { const o = document.getElementById('ln-offer'); if (o) o.remove(); }")
    us = pg.evaluate(UNIT)
    assert us, us
    for u in us:                                                          # set into the line: centred on it, never over a dot or a card
        assert abs(u["cy"] - u["line"]) <= 2 and not u["dots"] and not u["cards"], u
    for _ in range(3):                                                   # along the line, into the middle of a unit
        pg.keyboard.press("ArrowRight")
        pg.wait_for_timeout(700)
    pg.wait_for_timeout(1000)
    us = pg.evaluate(UNIT)
    lead = min(us, key=lambda u: u["l"])                                  # the label at the left edge
    assert abs(lead["cy"] - lead["line"]) <= 2, lead                     # still on the line
    assert lead["l"] >= 20 - 0.5 and lead["r"] <= 1440, lead              # 20 px in from the left at least: in view
    assert not lead["dots"] and not lead["cards"] and not lead["btn"], lead   # (clear of the key's toggle and the quiet cues)
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


@pytest.mark.parametrize("w,h,phone,q", [(1440, 900, False, ""), (390, 844, True, ""), (844, 390, True, "?view=whole")], ids=["d1440", "p390", "l844"])
def test_the_open_overview_is_dense_enough_that_cards_under_it_are_a_tint(site, w, h, phone, q):
    """B-1126-OVERVIEW-SEETHRU: the open Overview over the board is ~90%+ opaque (cards behind it never read as a second line of text), and a shut one shows no words."""
    ctx, pg = _open(site, "on", w, h, phone=phone, q=q)
    pg.evaluate("() => { const o = document.getElementById('ln-offer'); if (o) o.remove(); }")
    shut = pg.evaluate("() => getComputedStyle(document.getElementById('summary-inner')).visibility")
    assert shut == "hidden", shut
    pg.evaluate("() => toggleSummary()")
    pg.wait_for_timeout(1000)
    d = pg.evaluate("""() => { const w = document.getElementById('summary-wrap'), s = getComputedStyle(w), a = (s.backgroundColor.match(/[\\d.]+/g) || []).map(Number), al = a.length > 3 ? a[3] : 1;
      const l = 1 - Math.pow(1 - al, 1 + (s.backgroundImage.match(/linear-gradient/g) || []).length); return {open: w.classList.contains('open'), vis: getComputedStyle(document.getElementById('summary-inner')).visibility, eff: l}; }""")
    assert d["open"] and d["vis"] == "visible" and d["eff"] >= 0.9, d
    ctx.close()


def test_unit_labels_keep_their_size_and_glide_without_overlapping(site):
    """Luke 2026-11-26: "i don't like that they get squeezed, try to keep them as static elements as they move, and maybe make the
    movement more smooth going with the scroll instead of jumping": each label sticks in its own strip, one size, pushed off by the next."""
    ctx, pg = _open(site, "plain", w=900, h=700)
    R = """() => [...document.querySelectorAll('#lanes-ulabels .lu-chip')].map(e => { const r = e.getBoundingClientRect();
      return [r.left, r.right, r.width, r.height, getComputedStyle(e).position, e.classList.contains('lu-pin')]; })"""
    first = pg.evaluate(R)
    mx = pg.evaluate("() => { const c = document.getElementById('canvas'); return c.scrollWidth - c.clientWidth; }")
    rode = False
    for i in range(13):
        pg.evaluate(f"() => {{ document.getElementById('canvas').scrollLeft = {mx * i / 12}; }}")
        pg.wait_for_timeout(120)
        now = pg.evaluate(R)
        for a, b in zip(first, now):
            assert b[4] == "sticky" and abs(a[2] - b[2]) < .5 and abs(a[3] - b[3]) < .5, (i, a, b)     # never squeezed or re-wrapped
        for a, b in zip(now, now[1:]):
            assert a[1] <= b[0] + .5, (i, a, b)                                                    # pushed off, never on the next
        for c in now:
            if c[5]:
                rode = True
                assert abs(c[0] - 20) < 1.5 or c[1] <= now[now.index(c) + 1][0] - 4, c              # riding 20 px in, or being pushed off
    assert rode
    assert not pg._errs, pg._errs
    ctx.close()


# ── room under the lowest card (Luke 2026-11-26: "i can't see the node hiding behind the toggle, we need to be able to scroll down enough to see it fully") ──

CLEAR = """() => { const vis = e => { if (!e) return null; const r = e.getBoundingClientRect(), cs = getComputedStyle(e);
    return (r.width && r.height && cs.display !== 'none' && cs.visibility !== 'hidden' && +cs.opacity > .05) ? r : null; };
  let lo = -1e9, hi = 1e9; document.querySelectorAll('#world .node').forEach(n => { const r = vis(n) && vis(n.querySelector('.node-card')); if (!r) return;
    lo = Math.max(lo, r.bottom); hi = Math.min(hi, r.top); });
  const nav = vis(document.getElementById('lanes-nav')), mm = vis(document.querySelector('#ln-mm.on')), tb = vis(document.getElementById('title-text'));
  return {lo, hi, clear: Math.min(nav ? nav.top : 1e9, mm ? mm.top : 1e9), head: tb ? tb.bottom : 0}; }"""


@pytest.mark.parametrize("how", ["expanded", "branch"])
def test_the_lowest_and_highest_cards_scroll_fully_clear_of_the_bars(site, how):
    ctx, pg = _open(site, "tall", expanded=(how == "expanded"))
    if how == "branch":                                                               # one branch opened in the Compact view
        pg.evaluate("() => { const k = window._altoLanesKids, f = Object.keys((window._altoLanesGeo || {}).fams || {}); "
                    "const r = [...document.querySelectorAll('#world .ln-chip')].pop(); if (r) r.click(); }")
        pg.wait_for_timeout(1500)
    pg.evaluate("() => { const c = document.getElementById('canvas'); c.scrollTop = c.scrollHeight; }")
    pg.wait_for_timeout(900)
    b = pg.evaluate(CLEAR)
    assert b["lo"] <= b["clear"] - 19, b                                             # the lowest card whole, 20 px over the bar and the minimap
    pg.evaluate("() => { document.getElementById('canvas').scrollTop = 0; }")
    pg.wait_for_timeout(900)
    t = pg.evaluate(CLEAR)
    assert t["hi"] >= t["head"] + 19, t                                              # and the highest one under the top bar
    assert not pg._errs, pg._errs
    ctx.close()


def test_the_lawsuit_button_lets_an_enlarged_branch_card_go_and_comes_back_on_its_parent(site):
    """Luke 2026-11-27: "The lawsuit button doesn't work if a nested branch node is enlarged"."""
    ctx, pg = _open(site, "tall", expanded=True)
    kid = pg.evaluate("() => Object.keys(window._ALTO_LANES.ev).find(i => /-k20$/.test(i))")
    root = kid.rsplit("-k", 1)[0]
    pg.evaluate("(id) => window.enterFocus(id)", kid)                                 # a card deep in a long branch, enlarged
    pg.wait_for_timeout(1500)
    assert pg.evaluate("window._focusedNodeId") == kid
    on = pg.evaluate("() => document.querySelector('#lanes-nav .lnv-main').classList.contains('on')")
    assert on                                                                        # the line is out of view: the button is offered
    pg.click("#lanes-nav .lnv-main")
    pg.wait_for_timeout(2000)
    r = pg.evaluate("""(root) => { const n = document.querySelector('#node-' + root + ' .node-card').getBoundingClientRect();
      return {f: window._focusedNodeId || '', off: window._altoLanesMainOff(), cx: (n.left + n.right) / 2, w: innerWidth, kc: window._altoLanesKids.cursor()}; }""", root)
    assert not r["f"] and not r["kc"], r                                             # the card let go, out of the branch
    assert abs(r["off"]) < 30, r                                                     # back on the line
    assert 0 < r["cx"] < r["w"], r                                                   # on the branch's parent
    assert not pg._errs, pg._errs
    ctx.close()


def test_an_enlarged_card_leaves_nested_cards_no_stronger_than_their_parents_and_no_label_under_it(site):
    """Luke 2026-11-27: "you see the problem with the nested nodes in the background being more visible than their parents?" — and the
    enlarged card stood over a unit's label (text under text)."""
    ctx, pg = _open(site, "tall", expanded=True)
    r = pg.evaluate("() => Object.keys(window._altoLanesGeo.fams)[0]")
    pg.evaluate("(r) => window.enterFocus(window._altoLanesGeo.fams[r][0])", r)
    pg.wait_for_timeout(1400)
    o = pg.evaluate("""() => { const op = e => { let o = 1; for (let q = e; q && q !== document.body; q = q.parentElement) o *= +getComputedStyle(q).opacity; return o; };
      const G = window._altoLanesGeo, f = window._focusedNodeId, bad = [];
      Object.keys(G.fams).forEach(r => { const rc = document.querySelector('#node-' + r + ' .node-card');
        G.fams[r].forEach(k => { if (k === f) return; const kc = document.querySelector('#node-' + k + ' .node-card'); if (r !== f && op(kc) > op(rc) + 1e-3) bad.push(k); }); });
      const kl = document.querySelector('#lanes-svg .ln-kids'), fr = document.querySelector('#world .node.focused .node-card').getBoundingClientRect();
      const under = [...document.querySelectorAll('#world :is(.lu-chip,.lanes-tag,.lanes-box)')].filter(e => { const q = e.getBoundingClientRect();
        return getComputedStyle(e).visibility !== 'hidden' && q.width && q.left < fr.right && fr.left < q.right && q.top < fr.bottom && fr.top < q.bottom; }).length;
      return {bad, lines: kl ? op(kl) : 0, under}; }""")
    assert not o["bad"] and o["lines"] <= 0.15 and o["under"] == 0, o
    assert not pg._errs, pg._errs
    ctx.close()


def test_an_enlarged_card_on_a_landscape_phone_fits_between_the_top_chrome_and_the_step_bar(site):
    """Board 2026-11-27 (l844): an enlarged card's last line ran under the step bar's "2 / 275". It fits the room between the top chrome
    and the step bar, 20 px clear of each, and scrolls inside where its text is longer; let go, it is as it was. The page name's pill is
    solid there too (Classic), so no dimmed card reads through it."""
    ctx, pg = _open(site, "tall", 844, 390, phone=True, q="?view=whole")
    G = """() => { const c = document.querySelector('#world .node.focused .node-card'); if (!c) return null; const r = c.getBoundingClientRect(),
        n = document.getElementById('lanes-nav').getBoundingClientRect(),
        tops = ['#nav > .title', '#nav > svg.brand-mark', '#nav > svg.brand-word'].map(q => document.querySelector(q)).filter(e => e && e.getBoundingClientRect().height)
          .map(e => e.getBoundingClientRect().bottom).filter(b => b < innerHeight / 2);
      const w = c.querySelector(':scope > .ln-fitw'), k = r.height / c.offsetHeight, pb = parseFloat(getComputedStyle(c).paddingBottom) * k;
      return {t: r.top, b: r.bottom, nav: n.top, head: Math.max(0, ...tops), held: !!w, ov: w ? getComputedStyle(w).overflowY : '',
              more: w ? w.scrollHeight > w.clientHeight + 1 : false, wb: w ? w.getBoundingClientRect().bottom : 0, pad: r.bottom - pb}; }"""
    ids = pg.evaluate("() => Object.keys(window._ALTO_LANES.ev).filter(i => !(window._altoLanesKids && window._altoLanesKids.nest(i)))")
    for nid in ids[:3]:
        pg.evaluate("(id) => window.enterFocus(id)", nid)
        pg.wait_for_timeout(1600)
        g = pg.evaluate(G)
        assert g and g["t"] >= g["head"] + 19 and g["b"] <= g["nav"] - 19, (nid, g)     # in the room, 20 px clear of each
        if g["held"]:
            assert g["ov"] == "auto" and g["wb"] <= g["pad"] + 1, (nid, g)              # longer text scrolls inside the card's padding: its foot stays empty
    pg.evaluate("() => window.exitFocus()")
    pg.wait_for_timeout(900)
    assert pg.evaluate("() => !document.querySelector('#world .node-card.ln-fit, #world .ln-fitw') && ![...document.querySelectorAll('#world .node-card')].some(c => c.style.translate || c.style.maxHeight)")
    t = pg.evaluate("() => { const e = document.querySelector('#nav > .title'); return e ? getComputedStyle(e).backgroundColor : null; }")
    if t and pg.evaluate("() => document.documentElement.classList.contains('ln-under')"):
        assert t.startswith("rgb("), t                                                   # the name's pill solid while the board runs under it
    assert not pg._errs, pg._errs
    ctx.close()


def test_an_enlarged_card_on_a_portrait_phone_grows_into_the_room_and_stays_clear_of_the_unit_labels(site):
    """Board 2026-11-27 (p390): the enlarged card kept a set height and cut its description off with the room below unused, and in Retro its ring
    met the unit's label. It grows to hold its text (scrolling only past the room) and keeps 20 px from any unit label or line tag beside it."""
    ctx, pg = _open(site, "tall", 390, 844, phone=True, q="?view=whole")
    G = """() => { const c = document.querySelector('#world .node.focused .node-card'); if (!c) return null; const r = c.getBoundingClientRect(),
        w = c.querySelector(':scope > .ln-fitw'), box = w || c,
        chips = [...document.querySelectorAll('#lanes-ulabels .lu-chip, #world .lanes-tag')].map(e => e.getBoundingClientRect())
          .filter(q => q.height && q.right > r.left && q.left < r.right),
        gap = Math.min(999, ...chips.map(q => q.bottom <= r.top ? r.top - q.bottom : (q.top >= r.bottom ? q.top - r.bottom : -1)));
      const cs = getComputedStyle(c); let ring = 0;
      (cs.boxShadow || '').split(/,(?![^(]*\))/).forEach(sh => { if (/inset/.test(sh)) return; const n = (sh.replace(/rgba?\([^)]*\)|#[0-9a-f]+/gi, '').match(/-?[\d.]+px/g) || []).map(parseFloat);
        if (n.length >= 4 && n[2] === 0) ring = Math.max(ring, n[3] + Math.max(Math.abs(n[0]), Math.abs(n[1]))); });
      if (cs.outlineStyle !== 'none') ring = Math.max(ring, (parseFloat(cs.outlineWidth) || 0) + (parseFloat(cs.outlineOffset) || 0));
      const rg = ring * r.width / c.offsetWidth, labels = [...document.querySelectorAll('#lanes-ulabels .lu-chip')].filter(e => getComputedStyle(e).visibility !== 'hidden').length;
      return {cut: !w && c.scrollHeight > c.clientHeight + 1, held: !!w, gap, h: r.height, l: r.left - rg, r: innerWidth - (r.right + rg), labels}; }"""
    ids = pg.evaluate("() => Object.keys(window._ALTO_LANES.ev).filter(i => !(window._altoLanesKids && window._altoLanesKids.nest(i)))")
    for nid in ids[:3]:
        pg.evaluate("(id) => window.enterFocus(id)", nid)
        pg.wait_for_timeout(1600)
        g = pg.evaluate(G)
        assert g and not g["cut"], (nid, g)                                               # no text clipped at the card's foot
        assert g["gap"] >= 19, (nid, g)                                                   # clear of the unit labels beside it
        assert g["l"] >= 19 and g["r"] >= 19, (nid, g)                                    # its outer ring 20 px from the screen's sides
        assert g["labels"] == 0, (nid, g)                                                 # the units' labels step away while it is enlarged
    pg.evaluate("() => window.exitFocus()")
    pg.wait_for_timeout(900)
    assert pg.evaluate("() => ![...document.querySelectorAll('#world .node-card')].some(c => c.style.height || c.style.translate)")
    assert not pg._errs, pg._errs
    ctx.close()
