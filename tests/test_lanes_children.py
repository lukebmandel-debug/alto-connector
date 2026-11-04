"""Child nodes on the horizontal timeline (node.nest, lanes.py): an event nested under another of the same
line. Only ever on the user's yes (Edit mode "Nest under…", or a request to Claude / Bass): no switch, never
by itself. Compact view: tucked behind the parent ("▾ n inside"), Down opens and lands on the first child, Up
returns. Expanded view: always shown, outline-style beyond the parent on the far side of the line. The data and
the edits run everywhere; the drawing is checked in a real browser (WebKit here; skipped without Playwright)."""
import copy
import json
from pathlib import Path

import pytest

from alto.build.brief import BriefError, validate_brief, validate_nodes
from alto.build.builder import build_timeline, load_brief
from alto.build.lanes import LANES_CSS, LANES_JS, _nest_of, tidy
from tests.test_lanes import _payload, _rebuilds, _store

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "samples" / "lanes_children_brief.json"


def _d():
    return json.loads(SAMPLE.read_text())


def _check(d):
    b, nodes, _ = load_brief(copy.deepcopy(d))
    return validate_brief(b) + validate_nodes(b, nodes)


def _node(d, i):
    return next(n for n in d["nodes"] if n["id"] == i)


# ── the data ─────────────────────────────────────────────────────────────────

def test_the_sample_validates_and_the_payload_carries_each_parent():
    d = _d()
    assert not [w for w in _check(d) if "nest" in w]
    ev = _payload(d)["ev"]
    assert {k: v["p"] for k, v in ev.items() if v.get("p")} == {
        "warn-terms": "warning", "warn-lamp": "warn-terms", "warn-rock": "warn-terms",
        "council-vote": "council", "council-ada": "council", "log-1870": "logbooks"}
    assert all("p" not in v for k, v in ev.items() if k in ("arrive", "warning", "council"))


@pytest.mark.parametrize("mutate,msg", [
    (lambda d: _node(d, "warn-terms").update(nest="warn-terms"), "nest is itself"),
    (lambda d: (_node(d, "warning").pop("present"), _node(d, "warning").update(nest="warn-lamp")), "loops back"),
    (lambda d: _node(d, "log-1870").update(nest="warning"), "different line"),
    (lambda d: _node(d, "warn-terms").update(present=["ada"]), "no `present`"),
    (lambda d: _node(d, "warn-terms").update(flash="storm"), "no `present`"),
    (lambda d: _node(d, "warn-terms").update(nest=7), "id of the event"),
])
def test_a_child_that_crosses_the_line_or_loops_is_refused(mutate, msg):
    d = _d()
    mutate(d)
    with pytest.raises(BriefError, match=msg):
        _check(d)


def test_a_parent_that_is_not_an_event_yet_is_a_warning_and_the_child_stands_alone():
    d = _d()
    _node(d, "warn-terms")["nest"] = "not-yet"
    assert any("not-yet" in w and "not an event yet" in w for w in _check(d))
    assert "p" not in _payload(d)["ev"]["warn-terms"]


def test_nest_needs_the_horizontal_timeline():
    d = json.loads((ROOT / "samples" / "contracts_brief.json").read_text())
    d["nodes"][0]["nest"] = d["nodes"][1]["id"]
    b, nodes, _ = load_brief(d)
    with pytest.raises(BriefError, match="need mode 'lanes'"):
        validate_nodes(b, nodes)


def test_a_loop_or_a_cross_line_nest_draws_as_an_event_of_its_own():
    class N:
        def __init__(self, i, nest="", line=""):
            self.id, self.nest, self.line = i, nest, line
    by = {x.id: x for x in (N("a", "b"), N("b", "a"), N("c", "a", "l2"), N("d", "a"))}
    assert _nest_of(by["a"], by) == "" and _nest_of(by["c"], by) == ""
    assert _nest_of(by["d"], by) == ""        # its parent's chain loops


def test_the_page_never_puts_a_child_on_the_line():
    assert "function placeKids" in LANES_JS and "isKid(id)" in LANES_JS
    assert ".ln-kid-shut{display:none" in LANES_CSS
    # phones keep the engine's card view: nothing of this runs there
    assert "function kidsOn(){ return !de.classList.contains('mobile') && !de.classList.contains('phone-whole'); }" in LANES_JS


# ── manual edit mode: n|id|nest folds into the brief ─────────────────────────

def test_nest_and_un_nest_fold_into_the_draft():
    from alto.edits import fold
    st = _store(_d())
    st.edits = {"v": 1, "ops": {
        "n|council-vote|nest": {"b": "council", "v": "", "t": 1},
        "n|arrive|nest": {"b": "", "v": "warning", "t": 2}}}
    r = fold(st, "u", "t1")
    assert not r["conflicts"] and not r.get("error"), r
    by = {n["id"]: n for n in st.nodes}
    assert "nest" not in by["council-vote"] and by["arrive"]["nest"] == "warning"
    _rebuilds(st)


def test_a_nest_the_page_could_not_have_made_is_a_conflict():
    from alto.edits import fold
    st = _store(_d())
    st.edits = {"v": 1, "ops": {"n|warning|nest": {"b": "", "v": "warn-lamp", "t": 1}}}      # under its own child: a loop
    assert fold(st, "u", "t1")["conflicts"] == ["n|warning|nest"]
    st = _store(_d())
    st.edits = {"v": 1, "ops": {"n|logbooks|nest": {"b": "", "v": "warning", "t": 1}}}        # another line
    assert fold(st, "u", "t1")["conflicts"] == ["n|logbooks|nest"]
    st = _store(_d())
    st.edits = {"v": 1, "ops": {"n|warn-lamp|nest": {"b": "council", "v": "", "t": 1}}}       # changed since
    assert fold(st, "u", "t1")["conflicts"] == ["n|warn-lamp|nest"]
    st = _store(_d())
    st.edits = {"v": 1, "ops": {"n|warn-lamp|nest": {"b": "warn-terms", "v": "warn-terms", "t": 1}}}
    r = fold(st, "u", "t1")
    assert not r["conflicts"] and not r.get("error")


def test_a_nested_card_taken_to_another_line_or_a_parent_deleted_un_nests_its_children():
    from alto.edits import fold
    st = _store(_d())
    st.edits = {"v": 1, "ops": {"n|council|line": {"b": "", "v": "ben", "t": 1}}}
    r = fold(st, "u", "t1")
    assert not r["conflicts"], r
    by = {n["id"]: n for n in st.nodes}
    assert by["council"]["line"] == "ben" and "nest" not in by["council-vote"] and "nest" not in by["council-ada"]
    assert by["warn-terms"]["nest"] == "warning"                   # untouched
    d = _d()
    nodes = [n for n in d["nodes"] if n["id"] != "warning"]
    changed = tidy(d["brief"], nodes)
    assert "warn-terms" in changed and "nest" not in _node({"nodes": nodes}, "warn-terms")
    assert _node({"nodes": nodes}, "warn-lamp")["nest"] == "warn-terms"      # the rest of the family keeps its shape


def test_a_nest_edit_drops_nothing_it_was_not_asked_to():
    from alto.edits import fold
    st = _store(_d())
    st.edits = {"v": 1, "ops": {"n|arrive|present": {"b": ["ada"], "v": [], "t": 1}, "n|arrive|nest": {"b": "", "v": "warning", "t": 2}}}
    r = fold(st, "u", "t1")
    assert not r["conflicts"], r
    n = next(x for x in st.nodes if x["id"] == "arrive")
    assert n["nest"] == "warning" and not n.get("present")


# ── the chat's way in: add_nodes carries `nest`, and only the user's yes puts it there ──

def test_add_nodes_accepts_nest_and_refuses_a_child_across_the_line(tmp_path):
    from alto import mcp_server as srv
    from alto.store.local import LocalStore
    srv.set_store(LocalStore(tmp_path))
    try:
        d = _d()
        pid = srv.create_project("Stories", "a novel", "writing")["project_id"]
        base = [n for n in d["nodes"] if not n.get("nest")]
        tid = srv.create_timeline(pid, d["brief"])["timeline_id"]
        srv.record_materials_consent(tid, [{"name": "notes.pdf", "kind": "notes"}], True)
        assert "error" not in srv.add_nodes(tid, base)
        kid = _node(d, "warn-terms")
        r = srv.add_nodes(tid, [kid])
        assert "error" not in r, r
        bad = dict(_node(d, "log-1870"), nest="warning")
        r = srv.add_nodes(tid, [bad])
        assert r["error"] == "invalid_nodes" and "different line" in r["message"], r
        assert "ONLY when the user said yes" in srv.add_nodes.__doc__
    finally:
        srv.set_store(None)


def test_the_guide_says_to_offer_never_to_default():
    g = (ROOT / "alto" / "interview_guide.md").read_text()
    i = g.index("**Child nodes (`nest`)**")
    seg = g[i:i + 1600]
    for s in ("an offer, never a default", "same date", "clearly derived", "only on the user's yes", "never written for the purpose"):
        assert s in seg, s


# ── in a browser ─────────────────────────────────────────────────────────────

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None


@pytest.fixture(params=["chromium", "webkit"])
def browser(request):
    if pw is None:
        pytest.skip("Playwright is not installed")
    with pw.sync_playwright() as p:
        try:
            b = getattr(p, request.param).launch()
        except Exception as e:
            try:
                if request.param != "chromium":
                    raise e
                b = p.chromium.launch(channel="chrome")
            except Exception:
                pytest.skip(f"no {request.param}: {e}")
        yield b
        b.close()


FAKE = """(function(){ var store=null;
 var C={enabled:true, known:true, user:{uid:'u1'}, getEdits:function(){ return Promise.resolve(store); },
  putEdits:function(t,d){ store=JSON.parse(JSON.stringify(d)); return Promise.resolve(); }, watchEdits:function(){ return function(){}; }};
 Object.defineProperty(window,'AltoCloud',{get:function(){return C;}, set:function(){}, configurable:true}); })();"""


def _open(browser, d, tmp_path, name="lc.html", viewport=(1600, 1000), phone=False, edit=False, settle=2600):
    html, _ = build_timeline(*load_brief(copy.deepcopy(d)))
    f = tmp_path / name
    f.write_text(html, encoding="utf-8")
    if phone:
        ctx = browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True,
                                  user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
                                             "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
    else:
        ctx = browser.new_context(viewport={"width": viewport[0], "height": viewport[1]})
    if edit:
        ctx.add_init_script(FAKE)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: "/phone/" in str(e) or errs.append(str(e)))
    if edit:                       # manual edit mode only runs on an http(s) page: serve the built page from a fake origin
        body = html.encode("utf-8")
        pg.route("http://alto.test/**", lambda r: r.fulfill(status=200, content_type="text/html", body=body)
                 if r.request.url.endswith(".html") else r.fulfill(status=200, content_type="text/javascript", body=""))
        pg.goto("http://alto.test/lc.html")
    else:
        pg.goto(f.as_uri())
    pg.wait_for_timeout(settle)
    return pg, errs


FAMS = {"warning": ["warn-terms", "warn-lamp", "warn-rock"], "council": ["council-vote", "council-ada"], "logbooks": ["log-1870"]}


def test_compact_tucks_the_children_behind_the_parent_and_the_line_is_untouched(browser, tmp_path):
    d = _d()
    pg, errs = _open(browser, d, tmp_path)
    r = pg.evaluate("""()=>{
      var G=window._altoLanesGeo, chips={}; document.querySelectorAll('.ln-chip').forEach(function(c){ chips[c.getAttribute('data-root')]=c.textContent; });
      var shut=[].slice.call(document.querySelectorAll('.node.ln-kid-shut')).map(function(n){ return n.id.slice(5)+':'+getComputedStyle(n).display; });
      var lines=G.lines.map(function(l){ return [l.id, Math.round(l.y)]; });
      return {fams:G.fams, chips:chips, shut:shut, onLine:Object.keys(G.x).filter(function(i){ return /^(warn-|council-|log-)/.test(i); }),
        lines:lines, x:G.x, H:G.H, view:document.getElementById('ln-view').getAttribute('aria-pressed'),
        tuck:getComputedStyle(document.getElementById('node-warning'),'::before').content, stops:window._altoLanesTravel && 1}
    }""")
    assert r["fams"] == FAMS
    assert r["chips"] == {"warning": "▾ 3 inside", "council": "▾ 2 inside", "logbooks": "▾ 1 inside"}
    assert sorted(r["shut"]) == sorted(f"{k}:none" for v in FAMS.values() for k in v)
    assert r["onLine"] == [], "a child is never an event of the line (no dot, no stem, no step)"
    assert r["view"] == "false" and r["tuck"] not in ("none", "normal", ""), r["tuck"]
    # the same board without the children at all: every event and every line where it was
    bare = copy.deepcopy(d)
    gone = {k for v in FAMS.values() for k in v}
    bare["nodes"] = [n for n in bare["nodes"] if n["id"] not in gone]
    pg2, _ = _open(browser, bare, tmp_path, "bare.html")
    r2 = pg2.evaluate("()=>({lines:window._altoLanesGeo.lines.map(function(l){ return [l.id, Math.round(l.y)]; }), x:window._altoLanesGeo.x, H:window._altoLanesGeo.H})")
    assert r["lines"] == r2["lines"] and r["H"] == r2["H"]
    assert {k: round(v) for k, v in r["x"].items()} == {k: round(v) for k, v in r2["x"].items()}
    assert not errs, errs


def test_the_chip_and_down_open_a_family_and_up_closes_it_again(browser, tmp_path):
    pg, errs = _open(browser, _d(), tmp_path)
    kids = "()=>[].slice.call(document.querySelectorAll('.node.ln-kid-shut')).length"
    assert pg.evaluate(kids) == 6
    pg.click(".ln-chip[data-root=council]")
    pg.wait_for_timeout(500)
    assert pg.evaluate(kids) == 4
    assert pg.evaluate("()=>document.querySelector('.ln-chip[data-root=council]').textContent") == "▴ hide"
    assert not pg.evaluate("()=>window._focusedNodeId"), "the chip does not enlarge the card"
    pg.click(".ln-chip[data-root=council]")
    pg.wait_for_timeout(500)
    assert pg.evaluate(kids) == 6
    assert not errs, errs


def test_down_opens_the_events_children_up_goes_back_and_left_right_carry_on(browser, tmp_path):
    pg, errs = _open(browser, _d(), tmp_path)
    kids = "()=>[].slice.call(document.querySelectorAll('.node.ln-kid-shut')).length"
    pg.mouse.move(800, 990)
    pg.keyboard.press("ArrowRight")
    pg.wait_for_timeout(1500)
    assert pg.evaluate("()=>window._altoLanesCurrent()") == "warning"
    pg.keyboard.press("ArrowDown")
    pg.wait_for_timeout(700)
    assert pg.evaluate("()=>window._altoLanesKids.cursor()") == "warn-terms" and pg.evaluate(kids) == 3
    pg.keyboard.press("ArrowDown")
    pg.keyboard.press("ArrowDown")
    assert pg.evaluate("()=>window._altoLanesKids.cursor()") == "warn-rock"
    pg.keyboard.press("ArrowUp")                         # Up goes out to the parent: warn-rock sits under warn-terms
    assert pg.evaluate("()=>window._altoLanesKids.cursor()") == "warn-terms"
    pg.keyboard.press("ArrowUp")
    assert pg.evaluate("()=>window._altoLanesKids.cursor()") == "" and pg.evaluate("()=>window._altoLanesCurrent()") == "warning"
    pg.keyboard.press("ArrowDown")
    pg.wait_for_timeout(400)
    assert pg.evaluate("()=>window._altoLanesKids.cursor()") == "warn-terms"
    pg.keyboard.press("ArrowRight")                      # on along the line from the parent
    pg.wait_for_timeout(1500)
    assert pg.evaluate("()=>window._altoLanesKids.cursor()") == "" and pg.evaluate("()=>window._altoLanesCurrent()") == "great-storm"
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(500)
    assert pg.evaluate(kids) == 6
    assert not errs, errs


def test_expanded_shows_every_child_outline_style_on_the_far_side_and_nothing_overlaps(browser, tmp_path):
    pg, errs = _open(browser, _d(), tmp_path)
    c = pg.evaluate("()=>({mainY:window._altoLanesGeo.mainY, lines:window._altoLanesGeo.lines.map(function(l){ return Math.round(l.y-window._altoLanesGeo.mainY); })})")
    pg.click("#ln-view")
    pg.wait_for_timeout(900)
    r = pg.evaluate("""()=>{
      var G=window._altoLanesGeo, P=WORLD_PAD_TOP, out={bad:[], n:0};
      var box=function(id){ var e=document.querySelector('#node-'+id+' .node-card'), r=e.getBoundingClientRect(); return {x0:r.left,x1:r.right,y0:r.top,y1:r.bottom,cx:(r.left+r.right)/2,cy:(r.top+r.bottom)/2}; };
      Object.keys(G.fams).forEach(function(root){
        var rb=box(root);
        var ry=G.y[root]-G.mainY, sd=ry>0?1:-1;
        G.fams[root].forEach(function(k){ out.n++;
          var n=document.getElementById('node-'+k), cs=getComputedStyle(n);
          if(cs.display==='none') out.bad.push(k+' hidden');
          var ky=G.kids[k].y-G.mainY;
          if(Math.sign(ky)!==sd) out.bad.push(k+' crosses the line');
          if(Math.abs(ky)<=Math.abs(ry)) out.bad.push(k+' is not beyond its parent');
          var kb=box(k); if(kb.x0<rb.x0-1) out.bad.push(k+' starts left of its parent');
        });
      });
      var ids=[].slice.call(document.querySelectorAll('#world .node')).filter(function(n){ return getComputedStyle(n).display!=='none' && n.querySelector('.node-card'); }).map(function(n){ return n.id.slice(5); });
      for(var i=0;i<ids.length;i++) for(var j=i+1;j<ids.length;j++){ var a=box(ids[i]), b=box(ids[j]);
        if(a.x0<b.x1-2 && b.x0<a.x1-2 && a.y0<b.y1-2 && b.y0<a.y1-2) out.bad.push('overlap '+ids[i]+' / '+ids[j]); }
      out.chips=document.querySelectorAll('.ln-chip').length; out.lines=G.lines.map(function(l){ return Math.round(l.y-G.mainY); });
      out.pressed=document.getElementById('ln-view').getAttribute('aria-pressed'); out.shut=document.querySelectorAll('.ln-kid-shut').length;
      out.paths=document.querySelectorAll('#lanes-svg .ln-kidline').length;
      return out;
    }""")
    assert r["bad"] == [], r["bad"]
    assert r["n"] == 6 and r["shut"] == 0 and r["chips"] == 0 and r["paths"] == 6 and r["pressed"] == "true"
    assert r["lines"] == c["lines"], "the cap is on the lines: the lines sit where they did"
    pg.click("#ln-view")
    pg.wait_for_timeout(700)
    assert pg.evaluate("()=>document.querySelectorAll('.ln-kid-shut').length") == 6
    assert not errs, errs


def test_the_parents_filter_dims_its_children_and_a_hit_inside_a_tucked_parent_opens_it(browser, tmp_path):
    pg, errs = _open(browser, _d(), tmp_path)
    pg.click(".ln-chip[data-root=warning]")
    pg.wait_for_timeout(500)
    r = pg.evaluate("""()=>{
      var c=document.querySelector('#node-warning .node-card'); c.classList.add('ent-dimmed'); return new Promise(function(ok){ setTimeout(function(){
        ok({kids:FAM.map(function(k){ return document.querySelector('#node-'+k+' .node-card').classList.contains('ln-kid-dim'); }),
            other:document.querySelector('#node-warn-terms .node-card').classList.contains('ln-kid-dim')});
      }, 200); });
    }""".replace("FAM", json.dumps(FAMS["warning"])))
    assert r["kids"] == [True, True, True]
    pg.evaluate("document.querySelector('#node-warning .node-card').classList.remove('ent-dimmed')")
    pg.wait_for_timeout(200)
    assert pg.evaluate("()=>document.querySelectorAll('.ln-kid-dim').length") == 0
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(500)
    # search: the engine's own landing enlarges the card by its id; a child tucked behind its parent opens first
    assert pg.evaluate("()=>document.getElementById('node-council-vote').classList.contains('ln-kid-shut')")
    pg.evaluate("window._altoSearch.land('council-vote')")
    pg.wait_for_timeout(900)
    assert not pg.evaluate("()=>document.getElementById('node-council-vote').classList.contains('ln-kid-shut')")
    assert pg.evaluate("()=>window._focusedNodeId") == "council-vote"
    assert not errs, errs


def test_print_shows_the_children_in_the_expanded_view_and_puts_the_screen_back(browser, tmp_path):
    pg, errs = _open(browser, _d(), tmp_path)
    shut = "()=>document.querySelectorAll('.node.ln-kid-shut').length"
    assert pg.evaluate(shut) == 6
    pg.evaluate("window.dispatchEvent(new Event('beforeprint'))")
    pg.wait_for_timeout(600)
    assert pg.evaluate(shut) == 0 and pg.evaluate("()=>document.querySelectorAll('.ln-chip').length") == 0
    pg.evaluate("window.dispatchEvent(new Event('afterprint'))")
    pg.wait_for_timeout(600)
    assert pg.evaluate(shut) == 6
    assert not errs, errs


def test_edit_mode_shows_every_child_and_offers_nest_under(browser, tmp_path):
    pg, errs = _open(browser, _d(), tmp_path, edit=True)
    assert pg.evaluate("!!(window._altoManual && window._altoManual.canEdit && window._altoManual.canEdit())")
    pg.evaluate("window._altoManual.enter()")
    pg.wait_for_timeout(900)
    assert pg.evaluate("()=>document.querySelectorAll('.node.ln-kid-shut').length") == 0
    pg.evaluate("window._altoManual.change('n|arrive|nest', 'warning')")
    pg.wait_for_timeout(700)
    r = pg.evaluate("()=>({fams:window._altoLanesGeo.fams, on:Object.keys(window._altoLanesGeo.x).indexOf('arrive')})")
    assert r["fams"]["warning"][0] == "arrive" or "arrive" in r["fams"]["warning"], r
    assert r["on"] == -1, "a nested card leaves the line"
    pg.evaluate("window._altoManual.undo()")
    pg.wait_for_timeout(700)
    assert "arrive" in pg.evaluate("()=>Object.keys(window._altoLanesGeo.x)")
    pg.evaluate("window._altoManual.exit()")
    assert not errs, errs


def test_a_phone_keeps_the_engines_card_view(browser, tmp_path):
    pg, errs = _open(browser, _d(), tmp_path, phone=True)
    r = pg.evaluate("()=>({chips:document.querySelectorAll('.ln-chip').length, view:!!document.getElementById('ln-view'), shut:document.querySelectorAll('.ln-kid-shut').length, lanes:document.documentElement.classList.contains('alto-lanes')})")
    assert r == {"chips": 0, "view": False, "shut": 0, "lanes": False}, r
    assert not errs, errs


def test_edit_mode_menu_offers_nest_under_and_taking_it_out():
    import alto.build.manual_edit as me
    src = Path(me.__file__).read_text()
    for t in ("'Nest under…'", "'Take it out of “'", "'n|' + id + '|nest'", "Only entries on the same line"):
        assert t in src, t
