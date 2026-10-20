"""Hub & spoke, Luke's round 8 (after using 1.9.110 in Safari): an enlarged body's own come up
beside it, every body has a label, the zoomed-out chart stays readable, no markup shows as text,
a detail page has no chart chrome, and the way back from it is called the system.

Browser checks run in Chromium and WebKit (Playwright; skipped without them). Positions are read
in #world layout px (style.left/top) where geometry matters, as in test_solar_draw.py."""
import copy
import sys
from pathlib import Path

import pytest

from alto.build.builder import build_timeline, load_brief

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_solar_draw import _open, browser, solar_doc  # noqa: E402,F401

ROOT = Path(__file__).resolve().parent.parent
TORTS = [[[2, 2, 2], [2, 0, 2]], [[0, 0, 2, 2, 2], [3, 2, 3, 2, 2], [0, 0, 2], [], []]]     # the shape of Luke's Torts
CIVPRO = [[[2, 1], [0, 2, 0], [1], [2, 0]], [[1, 1], [2], [0, 0, 1]], [[2, 2], [1], [0]], [[1, 0, 2], [2], [1, 1]],
          [[0, 2], [1, 1, 0], [2]], [[1], [2, 2], [0, 1]], [[2, 0, 1], [1]], [[0], [1, 2], [2, 0]], [[1, 1], [0, 2], [1]]]
WIDE = [[[0] * 8 for _ in range(12)]]                     # one sun, 12 planets of 8 moons
NOTES = ('<span class="ns-item"><a class="note-link" href="#" onclick="showDetail(\'node\',\'u1-p2\');return false;">'
         'Torts Notes 8/25/26</a></span><span class="ns-item">Smith &amp; Jones &lt;1999&gt;</span>')


def _html(units, style="orbit", tweak=None):
    d = solar_doc(units, style)
    if tweak:
        tweak(d)
    html, _ = build_timeline(*load_brief(copy.deepcopy(d)))
    return html


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    d = tmp_path_factory.mktemp("round8")

    def notes(doc):
        for n in doc["nodes"]:
            if n["id"] == "u1-p1":
                n["sections"] = [{"h": "Source notes", "t": NOTES}, {"h": "Rule", "t": "<p>Intent &amp; contact.</p>"}]
            if n["id"] == "u1-p1-m2":
                n["title"] = "Duress & Undue Influence"
    out = {}
    for name, units, style, tw in (("hub", TORTS, "spoke", notes), ("stars", TORTS, "orbit", notes),
                                   ("civpro", CIVPRO, "orbit", None), ("wide", WIDE, "spoke", None)):
        f = d / f"{name}.html"
        f.write_text(_html(units, style, tw), encoding="utf-8")
        out[name] = f
    return out


def _pg(browser, f, reduced=True, wait=1400):
    pg, errs = _open(browser, f, reduced=reduced, wait=wait)
    pg.mouse.move(2, 940)
    return pg, errs


FLANK = r"""(id) => { var G=window._altoSolarGeo(), F=G.bodies[id], n=document.getElementById('node-'+id), c=document.getElementById('canvas');
  var R=parseFloat(n.style.getPropertyValue('--sD'))*1.7/2, out={R:R, cw:c.clientWidth, ch:c.clientHeight, fx:F.x, fy:F.y, kids:{}, spokes:0};
  out.spokes=[].filter.call(document.querySelectorAll('#sol-flank-svg line'), function(l){ return +l.getAttribute('opacity')>.9; }).length;
  document.querySelectorAll('#world .node.sol-flank').forEach(function(k){ var i=k.id.slice(5), b=G.bodies[i], lb=k.querySelector('.sol-lbl');
    out.kids[i]={x:b.x, y:b.y, d:b.d, p:b.p, op:getComputedStyle(k.querySelector('.node-card')).opacity, lbl:lb.getAttribute('data-l'),
      lop:getComputedStyle(lb).opacity, ldisp:getComputedStyle(lb).display}; });
  return out; }"""


@pytest.mark.parametrize("look", ["hub", "stars"])
def test_an_enlarged_body_has_its_children_beside_it(browser, built, look):
    pg, errs = _pg(browser, built[look])
    kids = pg.evaluate("() => Object.keys(window._ALTO_SOLAR.nodes).filter(function(i){ return window._ALTO_SOLAR.nodes[i].parent==='u2-p2'; })")
    assert len(kids) == 5
    pg.evaluate("() => window.enterFocus('u2-p2')")
    pg.wait_for_timeout(900)
    st = pg.evaluate(FLANK, "u2-p2")
    assert sorted(st["kids"]) == sorted(kids), st
    sides = {-1: 0, 1: 0}
    for i, k in st["kids"].items():
        assert k["p"] == "u2-p2" and float(k["op"]) > .99 and float(k["lop"]) > .99 and k["ldisp"] != "none", (i, k)
        dx, dy = k["x"] - st["fx"], k["y"] - st["fy"]
        assert abs(dx) - k["d"] / 2 >= st["R"] + 20, (i, k, st["R"])                     # clear of the disc
        assert abs(dx) + k["d"] / 2 <= st["cw"] / 2 - 115 + 1, (i, k)                    # 115 px from the window's edge
        assert abs(dy) + k["d"] / 2 <= st["ch"] / 2 - 40, (i, k)                         # under the bars, over the bottom row
        sides[1 if dx > 0 else -1] += 1
    assert sides == {-1: 3, 1: 2}, sides                                                 # alternately left and right
    assert st["spokes"] == 5
    xs = sorted((k["x"], k["y"]) for k in st["kids"].values())
    for a in range(len(xs)):
        for b in range(a + 1, len(xs)):
            assert abs(xs[a][0] - xs[b][0]) > 30 or abs(xs[a][1] - xs[b][1]) > 40, xs  # never on top of one another
    assert not errs, errs
    pg.context.close()


def test_a_body_beside_the_disc_is_enlarged_where_it_stands_and_esc_brings_all_home(browser, built):
    pg, errs = _pg(browser, built["hub"])
    home = pg.evaluate("() => window._altoSolarGeo().bodies")
    pg.evaluate("() => window.enterFocus('u2-p2')")
    pg.wait_for_timeout(900)
    st = pg.evaluate(FLANK, "u2-p2")
    m = "u2-p2-m1"
    xy = pg.evaluate("(i) => { var r=document.querySelector('#node-'+i+' .node-card').getBoundingClientRect(); return [r.left+r.width/2, r.top+r.height/2]; }", m)
    pg.mouse.click(xy[0], xy[1])
    pg.wait_for_timeout(1000)
    assert pg.evaluate("() => window._focusedNodeId") == m
    now = pg.evaluate("() => window._altoSolarGeo().bodies")
    assert abs(now[m]["x"] - st["kids"][m]["x"]) < 2 and abs(now[m]["y"] - st["kids"][m]["y"]) < 2      # where it stood
    st2 = pg.evaluate(FLANK, m)
    assert sorted(st2["kids"]) == ["u2-p2-m1-s1", "u2-p2-m1-s2", "u2-p2-m1-s3"], st2                    # its own, not its siblings
    # arrows: right from the disc goes to one of its own on the right
    pg.keyboard.press("ArrowRight")
    pg.wait_for_timeout(900)
    f = pg.evaluate("() => window._focusedNodeId")
    assert f in st2["kids"] and st2["kids"][f]["x"] > st2["fx"], (f, st2)
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(900)
    end = pg.evaluate("() => window._altoSolarGeo().bodies")
    assert not pg.evaluate("() => document.querySelectorAll('#world .node.sol-flank').length")
    moved = [i for i in home if abs(end[i]["x"] - home[i]["x"]) > 1.5 or abs(end[i]["y"] - home[i]["y"]) > 1.5]
    assert not moved, moved                                                              # everything home (no orbit: reduced motion)
    assert not errs, errs
    pg.context.close()


def test_the_flank_glides_on_the_focus_clock_and_edit_mode_has_none(browser, built):
    pg, errs = _pg(browser, built["hub"], reduced=False)
    pg.evaluate("() => window._altoSolarMotion.set(false)")
    pg.evaluate("() => window.enterFocus('u1-p1')")
    pg.wait_for_timeout(120)
    mid = pg.evaluate(FLANK, "u1-p1")
    pg.wait_for_timeout(900)
    end = pg.evaluate(FLANK, "u1-p1")
    home = pg.evaluate("() => window._altoSolarGeo().bodies")
    k = "u1-p1-m1"
    assert mid["kids"][k]["x"] != end["kids"][k]["x"], (mid["kids"][k], end["kids"][k])  # it travels there, not a jump
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(900)
    pg.evaluate("() => document.documentElement.classList.add('alto-editing')")
    pg.wait_for_timeout(200)
    pg.evaluate("() => window.enterFocus('u1-p1')")
    pg.wait_for_timeout(700)
    assert pg.evaluate("() => document.querySelectorAll('#world .node.sol-flank').length") == 0
    assert home[k]["x"] is not None
    assert not errs, errs
    pg.context.close()


def test_choosing_one_beside_the_disc_on_a_star_chart_lets_the_others_go_home_and_flies(browser, built):
    pg, errs = _pg(browser, built["stars"], reduced=False)
    pg.evaluate("() => window.enterFocus('u2-p2')")
    pg.wait_for_timeout(900)
    assert pg.evaluate("() => document.querySelectorAll('#world .node.sol-flank').length") == 5
    pg.evaluate("() => window.enterFocus('u2-p2-m3')")
    pg.wait_for_timeout(500)
    assert pg.evaluate("() => document.querySelectorAll('#world .node.sol-flank').length") == 0
    assert pg.evaluate("() => !!window._altoSolarFlight && !!window._altoSolarFlight()")                # flying, as before
    pg.wait_for_timeout(8500)
    assert pg.evaluate("() => window._focusedNodeId") == "u2-p2-m3"
    assert pg.evaluate("() => document.querySelectorAll('#world .node.sol-flank').length") == 3           # its satellites
    assert not errs, errs
    pg.context.close()


LABELS = r"""() => { var out={bodies:0, missing:[], shown:[], z:parseFloat(getComputedStyle(document.documentElement).zoom)||1};
  var G=window._altoSolarGeo();
  Object.keys(G.bodies).forEach(function(id){ var n=document.getElementById('node-'+id), lb=n && n.querySelector(':scope > .sol-lbl'); out.bodies++;
    var t=n.querySelector('.node-title'); if(!lb || lb.getAttribute('data-l')!==(t ? t.textContent.replace(/\s+/g,' ').trim() : '')){ out.missing.push(id); return; }
    var cs=getComputedStyle(lb); if(cs.display==='none' || +cs.opacity<.5 || cs.visibility==='hidden') return;
    var r=lb.getBoundingClientRect(), m=new DOMMatrix(cs.transform==='none' ? undefined : cs.transform);
    out.shown.push({id:id, role:G.bodies[id].role, l:r.left, t:r.top, r:r.right, b:r.bottom, fs:parseFloat(cs.fontSize), skew:Math.abs(m.b)+Math.abs(m.c)}); });
  return out; }"""


def _overlaps(shown, tol=0.5):
    bad = []
    for i, a in enumerate(shown):
        for b in shown[i + 1:]:
            if a["l"] < b["r"] - tol and b["l"] < a["r"] - tol and a["t"] < b["b"] - tol and b["t"] < a["b"] - tol:
                bad.append((a["id"], b["id"]))
    return bad


@pytest.mark.parametrize("look", ["hub", "stars"])
@pytest.mark.parametrize("dark", [False, True])
def test_every_body_has_an_upright_label_and_none_overlap(browser, built, look, dark):
    pg, errs = _pg(browser, built[look])
    if dark:
        pg.evaluate("() => { if(!document.documentElement.classList.contains('dark') && window.toggleMode) toggleMode(); }")
        pg.wait_for_timeout(300)
    pg.evaluate("() => window._altoSolarZoom(0.32)")             # the Torts shape in view (labels keep their size)
    pg.wait_for_timeout(400)
    st = pg.evaluate(LABELS)
    assert st["bodies"] == len(pg.evaluate("() => Object.keys(window._ALTO_SOLAR.nodes)")) and not st["missing"], st["missing"]
    assert not _overlaps(st["shown"]), _overlaps(st["shown"])
    assert all(s["skew"] < 1e-6 for s in st["shown"])                                  # upright
    roles = {s["role"] for s in st["shown"]}
    assert {"sun", "planet"} <= roles, roles
    assert sum(1 for s in st["shown"] if s["role"] == "planet") >= 6, st["shown"]
    # at full size, every planet / moon label that shows is 11-12 px (constant), and the chart keeps them clear
    pg.evaluate("() => window._altoSolarZoom(1)")
    pg.wait_for_timeout(400)
    st = pg.evaluate(LABELS)
    assert not _overlaps(st["shown"]), _overlaps(st["shown"])
    assert all(10.5 <= s["fs"] <= 12.5 for s in st["shown"] if s["role"] != "sun"), st["shown"]
    assert not errs, errs
    pg.context.close()


@pytest.mark.parametrize("chart", ["civpro", "wide"])
def test_fully_zoomed_out_the_chart_reads(browser, built, chart):
    pg, errs = _pg(browser, built[chart])
    pg.evaluate("() => window._altoSolarZoom(0.0001)")
    pg.wait_for_timeout(500)
    s = pg.evaluate("() => window._altoSolarZoom()")
    fit = pg.evaluate("""() => { var c=document.getElementById('canvas'), w=document.getElementById('world');
      return Math.min((c.clientWidth-60)/w.offsetWidth, (c.clientHeight-60)/w.offsetHeight); }""")
    assert abs(s - 0.85 * fit) < 1e-3, (s, fit)                                        # all of it, filling 85% of the window
    st = pg.evaluate(LABELS)
    suns = [x for x in st["shown"] if x["role"] == "sun"]
    nsuns = len(pg.evaluate("() => window._ALTO_SOLAR.systems"))
    assert len(suns) == nsuns, (len(suns), nsuns)
    assert all(x["fs"] * st["z"] >= 11 for x in suns), suns                            # >= 11 px on screen
    assert all(x["fs"] * st["z"] >= 11 for x in st["shown"] if x["role"] == "planet")
    assert not [x for x in st["shown"] if x["role"] == "sat"]
    assert not _overlaps(st["shown"]), _overlaps(st["shown"])
    # every body is at least a dot of a few px; the rings stay at least a hairline
    small = pg.evaluate("""() => { var s=window._altoSolarZoom(), bad=[]; document.querySelectorAll('#world .node[data-solar]').forEach(function(n){
        var d=parseFloat(getComputedStyle(n).getPropertyValue('--dn')), dot=n.querySelector('.sol-dot'), cs=getComputedStyle(dot);
        if(d*s<4 && (+cs.opacity<.99 || parseFloat(cs.width)<3.9)) bad.push(n.id); }); return bad; }""")
    assert not small, small
    assert pg.evaluate("() => getComputedStyle(document.querySelector('#solar-svg .sol-ring')).vectorEffect") == "non-scaling-stroke"
    assert not errs, errs
    pg.context.close()


MARKUP = r"""() => { var bad=[], re=/<span|<\/?a[ >]|&lt;|&gt;|&amp;|&quot;/;
  function chk(where, s){ if(s && re.test(s)) bad.push([where, s.slice(0, 120)]); }
  var n=document.getElementById('node-u1-p1');
  chk('disc', n.querySelector('.sol-body').innerText);
  document.querySelectorAll('#world .node[data-solar]').forEach(function(k){
    ['title', 'aria-label'].forEach(function(a){ k.querySelectorAll('['+a+']').forEach(function(e){ chk(k.id+' '+a, e.getAttribute(a)); }); });
    var lb=k.querySelector('.sol-lbl'); if(lb) chk(k.id+' label', lb.getAttribute('data-l'));
    if(k.classList.contains('sol-flank')) chk(k.id+' flank', k.innerText);
  });
  document.querySelectorAll('.sol-unit').forEach(function(c){ chk('chip', c.innerText); });
  return {bad:bad, secs:n.querySelectorAll('.sol-sec').length, links:n.querySelectorAll('.sol-sec .alto-link').length,
          prov:n.querySelectorAll('.sol-sec h6 .sec-prov').length, text:n.querySelector('.sol-body').innerText}; }"""


@pytest.mark.parametrize("look", ["hub", "stars"])
def test_no_markup_shows_as_text(browser, built, look):
    pg, errs = _pg(browser, built[look])
    pg.evaluate("() => window.enterFocus('u1-p1')")
    pg.wait_for_timeout(900)
    st = pg.evaluate(MARKUP)
    assert not st["bad"], st["bad"]
    assert st["secs"] == 2 and st["links"] == 1, st                                   # the notes' markup, rendered
    assert "Smith & Jones <1999>" in st["text"] and "Torts Notes 8/25/26" in st["text"], st["text"]
    lbl = pg.evaluate("() => document.querySelector('#node-u1-p1-m2 .sol-lbl').getAttribute('data-l')")
    assert lbl == "Duress & Undue Influence", lbl
    assert not errs, errs
    pg.context.close()


def test_a_section_heading_with_its_provenance_renders_as_the_detail_page_does(browser, tmp_path):
    def prov(doc):
        for n in doc["nodes"]:
            if n["id"] == "u1-p1":
                n["sections"] = [{"h": "Overview", "t": "<p>The rule.</p>", "prov": "notes"}]
    f = tmp_path / "prov.html"
    f.write_text(_html([[[0]]], "spoke", prov), encoding="utf-8")
    pg, errs = _pg(browser, f)
    pg.evaluate("() => window.enterFocus('u1-p1')")
    pg.wait_for_timeout(800)
    h = pg.evaluate("() => { var h=document.querySelector('#node-u1-p1 .sol-sec h6'); return h ? [h.innerText, h.innerHTML] : null; }")
    assert h and "<span" not in h[0] and "&lt;" not in h[0], h
    assert not errs, errs
    pg.context.close()


def test_a_detail_page_shows_no_chart_chrome_and_goes_back_to_the_system(browser, built):
    pg, errs = _pg(browser, built["hub"])
    vis = "() => getComputedStyle(document.getElementById('sol-ctl')).display"
    assert pg.evaluate(vis) != "none"
    pg.evaluate("() => showDetail('node','u1-p1')")
    pg.wait_for_timeout(600)
    assert pg.evaluate(vis) == "none"
    b = pg.evaluate("() => { var b=document.getElementById('desk-back'); return [b.textContent.trim(), b.title, b.getAttribute('aria-label'), document.querySelector('.db-name').textContent]; }")
    assert b == ["System", "Back to the system", "Back to the system", "System"], b
    pg.evaluate("() => showTimeline()")
    pg.wait_for_timeout(600)
    assert pg.evaluate(vis) != "none"
    assert not errs, errs
    pg.context.close()


def test_an_outline_tree_page_keeps_its_wording(browser, tmp_path):
    d = solar_doc([[[0]], [[0]]])
    d["brief"].pop("layout")
    d["brief"].pop("hub_look")
    html, _ = build_timeline(*load_brief(copy.deepcopy(d)))
    f = tmp_path / "tree.html"
    f.write_text(html, encoding="utf-8")
    pg, errs = _pg(browser, f)
    pg.evaluate("() => showDetail('node','u1-p1')")
    pg.wait_for_timeout(500)
    b = pg.evaluate("() => [document.getElementById('desk-back').textContent.trim(), document.querySelector('.db-name').textContent]")
    assert b == ["Outline", "Timeline"], b
    pg.context.close()


def test_the_guide_calls_the_main_view_the_system():
    g = (ROOT / "alto" / "interview_guide.md").read_text(encoding="utf-8")
    assert "**← System**" in g and "beside it" in g

