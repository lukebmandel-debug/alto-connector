"""The horizontal timeline's drawing (lanes.py LANES_JS / LANES_CSS, v2): the main
line is the page; a character's solid line dips onto it, ringed, wherever the
character is on the page; a flashback is a detour of the main line itself down
to a labelled past track. Static checks on what the page carries, and geometry
checks in a real browser (Chromium and WebKit; skipped without Playwright)."""
import copy
import json
import re
from pathlib import Path

import pytest

from alto.build.builder import build_timeline, load_brief
from alto.build.lanes import LANES_CSS, LANES_JS, parse_when

ROOT = Path(__file__).resolve().parent.parent
LEGACY = json.loads((ROOT / "samples" / "lanes_brief.json").read_text())


def _node(i, act, title, when, present=(), line="", flash=""):
    n = {"id": i, "act": act, "line": line, "when": when, "tag": "Scene", "title": title,
         "desc": f"{title}: the material's words.", "entity_ids": []}
    if present:
        n["present"] = list(present)
    if flash:
        n["flash"] = flash
    return n


def _v2_doc():
    b = copy.deepcopy(LEGACY["brief"])
    b.update(title="Flashbacks", timeline_id="flashbacks", main_line="The page", relations=[{"key": "spine", "label": "leads to"}],
             lines=[{"id": "mara", "label": "Mara", "side": "above"}, {"id": "tom", "label": "Tom", "side": "below"},
                    {"id": "ilse", "label": "Ilse", "side": "above"}],
             flashbacks=[{"id": "child", "label": "Mara's childhood"}, {"id": "war", "label": "The war years"}])
    b["entities"] = [{"id": x, "name": x.title(), "role": "", "color": "#888888"} for x in ("mara", "tom", "ilse")]
    nodes = [
        _node("f1", 0, "A house by the sea", "1987", ["mara"], flash="child"),       # the story opens in a flashback
        _node("f2", 0, "The boat burns", "1990", ["mara", "tom"], flash="child"),
        _node("p1", 0, "Mara comes home", "2019-03", ["mara"]),
        _node("p2", 0, "Tom at the harbour", "2019-05", ["tom", "mara"]),
        _node("p3", 1, "The box of letters", "2019-08", ["mara", "ilse"]),
        _node("w1", 1, "Tom enlists", "1999", ["tom"], flash="war"),
        _node("w2", 1, "Letters home", "2000-06", ["tom", "ilse"], flash="war"),
        _node("w3", 1, "The crossing", "2001", ["tom"], flash="war"),
        _node("p4", 1, "Ilse tells the rest", "2019-09", ["ilse", "mara"]),
        _node("t1", 2, "Tom's own reckoning", "2019-10", line="tom"),
        _node("p5", 2, "The last of the letters", "2019-12", ["mara", "tom", "ilse"]),
    ]
    return {"brief": b, "nodes": nodes, "connections": []}


def _v2_data(d):
    """window._ALTO_LANES v2 as docs/lanes-v2-contract.md defines it — used only
    while this branch's lanes_data still sends v1 (before the lanes-data merge)."""
    b, ns = d["brief"], d["nodes"]
    order = [n["id"] for n in sorted(ns, key=lambda n: (n["act"], ns.index(n)))]
    pal = ["#e07a5f", "#3d9a8b", "#8a6fd1", "#d4a017", "#4a90d9", "#c2577a"]
    lines = [{"id": l["id"], "label": l["label"], "color": l.get("color") or pal[i % 6],
              "side": l.get("side") or ("above", "below")[i % 2], "from": l.get("from") or "", "to": l.get("to") or ""}
             for i, l in enumerate(b["lines"])]
    ev = {n["id"]: {"l": n.get("line") or "main", "w": n.get("when") or "", "t": parse_when(n.get("when")),
                    "present": n.get("present") or [], "flash": n.get("flash") or ""} for n in ns}
    mains = [i for i in order if ev[i]["l"] == "main"]
    for k, i in enumerate(order):
        ev[i]["i"] = k
    for ln in lines:
        ln["events"] = [i for i in order if ev[i]["l"] == ln["id"]]
        ln["presence"] = [i for i in mains if ln["id"] in ev[i]["present"] or i in (ln["from"], ln["to"])]
        on = [i for i in order if i in set(ln["events"]) | set(ln["presence"])]
        ln["span"] = [on[0], on[-1]] if on else []
    fbs = []
    for f in b.get("flashbacks") or []:
        ids = [i for i in mains if ev[i]["flash"] == f["id"]]
        a, z = (mains.index(ids[0]), mains.index(ids[-1])) if ids else (0, -1)
        fbs.append({"id": f["id"], "label": f["label"], "nodes": ids, "prev": mains[a - 1] if ids and a else "",
                    "next": mains[z + 1] if ids and z + 1 < len(mains) else ""})
    return {"v": 2, "main": b.get("main_line") or "", "order": order, "lines": lines, "ev": ev, "flashbacks": fbs}


def _page(d):
    d = copy.deepcopy(d)
    try:
        html, _ = build_timeline(*load_brief(d))
        if re.search(r'window\._ALTO_LANES=\{"v":2', html):
            return html
    except TypeError:                       # this branch's Node / Brief have no present / flash / flashbacks yet
        pass
    L = _v2_data(d)
    d["brief"].pop("flashbacks", None)
    for n in d["nodes"]:
        n.pop("present", None)
        n.pop("flash", None)
    html, _ = build_timeline(*load_brief(d))
    return re.sub(r"window\._ALTO_LANES=\{.*?\};\n",
                  lambda m: "window._ALTO_LANES=" + json.dumps(L, separators=(",", ":")) + ";\n", html, count=1)


# ── what the page carries ────────────────────────────────────────────────────

def test_the_only_dashes_left_are_the_materials_own_arcs():
    """Characters and flashbacks are solid now; the one dashed thing is an arc
    (a link the material draws between events), and the key's swatch of it."""
    css = re.sub(r"/\*.*?\*/", "", LANES_CSS, flags=re.S)
    css_dashes = [l for l in css.splitlines() if "dasharray" in l]
    assert len(css_dashes) == 1 and ".ln-rel" in css_dashes[0]
    assert "ln-fb" not in LANES_CSS and "ln-fb" not in LANES_JS and "'11 9'" not in LANES_JS
    js_dashes = re.findall(r"sw\([^)]*?,'([^']+)'", LANES_JS)
    assert js_dashes == ["7 5"], js_dashes                  # the key: only the arc's swatch is dashed
    # the unit dividers are not dashed either (dashes are kept for meaning)
    assert "dashed" not in css


def test_the_page_carries_dips_rings_and_detours():
    html = _page(_v2_doc())
    for s in ("ln-ring", "ln-past-band", "lanes-past", "function levelsPath", "presence:geo.presence", "detours:runs.map",
              "what is on the page, in the order the story tells it", "A detour down: a flashback",
              "A dip onto the main line, ringed"):
        assert s in html, s


# ── in a browser ─────────────────────────────────────────────────────────────

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None
PHONE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")


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


def _open(browser, html, tmp_path, phone=False):
    f = tmp_path / "lanes.html"
    f.write_text(html, encoding="utf-8")
    if phone:
        ctx = browser.new_context(viewport={"width": 390, "height": 844}, user_agent=PHONE_UA, has_touch=True)
    else:
        ctx = browser.new_context(viewport={"width": 1600, "height": 1000})
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(f.as_uri())
    pg.wait_for_timeout(1200)
    return pg, errs


# geometry, all in svg / world layout px (never screen px): rings on their anchors,
# each character's path through its rings, no line through a card, the detour
GEOMETRY = r"""() => {
  var G=window._altoLanesGeo, P=WORLD_PAD_TOP, svg=document.getElementById('lanes-svg'), out={bad:[], rings:0, anchors:0};
  if(!G || !svg) return {bad:['no geometry']};
  svg.querySelectorAll('path.ln-br, path.ln-main').forEach(function(p){
    var d=getComputedStyle(p).strokeDasharray; if(d && d!=='none') out.bad.push('dashed line '+p.parentNode.getAttribute('data-ln')+' '+d); });
  var cards=[]; Object.keys(G.x).forEach(function(id){ var c=document.querySelector('#node-'+id+' .node-card'); if(!c) return;
    var w=c.offsetWidth, h=G.h[id]||120; cards.push({id:id, x0:G.x[id]-w/2+3, x1:G.x[id]+w/2-3, y0:G.y[id]-h/2+P+3, y1:G.y[id]+h/2+P-3}); });
  function pts(p){ var L=p.getTotalLength(), a=[]; for(var s=0;s<=L;s+=3){ var q=p.getPointAtLength(s); a.push([q.x,q.y]); } return a; }
  G.lines.forEach(function(l){
    var g=svg.querySelector('g[data-ln="'+l.id+'"] path.'+(l.id==='main'?'ln-main':'ln-br')); if(!g){ if(l.id==='main' || l.drawn) out.bad.push('no path '+l.id); return; }
    var a=pts(g);
    a.forEach(function(q){ cards.forEach(function(c){ if(q[0]>c.x0 && q[0]<c.x1 && q[1]>c.y0 && q[1]<c.y1) out.bad.push(l.id+' runs through card '+c.id+' at '+q.map(Math.round)); }); });
    if(l.id==='main') return;
    (G.presence[l.id]||[]).forEach(function(s){ out.anchors++;
      var best=1e9; a.forEach(function(q){ var dd=Math.hypot(q[0]-s.x, q[1]-(s.y+P)); if(dd<best) best=dd; });
      if(best>2) out.bad.push(l.id+' misses its anchor at '+s.id+' by '+best.toFixed(1));
      var at=G.at[s.id], want=at.y; if(at.line==='main' && Math.abs(s.y-want)>.5) out.bad.push(l.id+' anchor '+s.id+' off the main line');
    });
  });
  svg.querySelectorAll('circle.ln-ring').forEach(function(c){ out.rings++; });
  out.detours=G.detours.map(function(r){
    var m=svg.querySelector('g[data-ln=main] path.ln-main'), L=m.getTotalLength(), mid=(r.f0+r.f1)/2, y=null, lo=0, hi=L;
    for(var k=0;k<60;k++){ var md=(lo+hi)/2, q=m.getPointAtLength(md); if(q.x<mid) lo=md; else hi=md; }
    y=m.getPointAtLength(lo).y;
    var t=document.querySelector('.lanes-past[data-fb="'+r.id+'"]');
    return {id:r.id, pastY:y-P, y:r.y, mainY:G.mainY, label:t?t.textContent:'', range:r.range, n:r.nodes.length};
  });
  out.mainAtStart=(function(){ var m=svg.querySelector('g[data-ln=main] path.ln-main'); return m.getPointAtLength(0).y-P; })();
  return out;
}"""


def test_v2_lines_dip_onto_the_page_and_flashbacks_detour(browser, tmp_path):
    pg, errs = _open(browser, _page(_v2_doc()), tmp_path)
    r = pg.evaluate(GEOMETRY)
    assert not errs, errs
    assert r["bad"] == [], r["bad"][:8]
    # every presence (17 in the doc) is a ring on the line where the character meets the page
    assert r["anchors"] == 17 and r["rings"] == 17, r
    ds = {d["id"]: d for d in r["detours"]}
    assert set(ds) == {"child", "war"} and ds["child"]["n"] == 2 and ds["war"]["n"] == 3
    for d in ds.values():
        assert abs(d["pastY"] - d["y"]) < 1 and d["y"] > d["mainY"] + 30      # the main line itself is down on the past track
    assert "Mara's childhood" in ds["child"]["label"] and "1987–1990" in ds["child"]["label"]
    assert "The war years" in ds["war"]["label"] and "1999–2001" in ds["war"]["label"]
    assert abs(r["mainAtStart"] - ds["child"]["mainY"]) < 1                    # opens in the present, then dips
    # hovering a character's label lights its line and the cards where it is on the page
    pg.hover('.lanes-tag[data-ln-tag="ilse"]')
    pg.wait_for_timeout(500)
    on = pg.evaluate("() => [].map.call(document.querySelectorAll('.node.ln-on'), function(n){ return n.id; }).sort()")
    assert on == ["node-p3", "node-p4", "node-p5", "node-w2"], on


def _undated_doc(gaps):
    d = _v2_doc()
    d["brief"].pop("flashbacks"); 
    d["nodes"] = [n for n in d["nodes"] if not n.get("flash") and n["line"] == ""]
    for n in d["nodes"]:
        n["when"] = ""
        n.pop("flash", None)
    for nid, g in gaps.items():
        next(n for n in d["nodes"] if n["id"] == nid)["gap"] = g
    return d


def test_the_pace_of_the_story_sets_how_close_events_sit(browser, tmp_path):
    ids = [n["id"] for n in _undated_doc({})["nodes"]]
    X = "() => { const G = window._altoLanesGeo; return G.x; }"
    pg, errs = _open(browser, _page(_undated_doc({})), tmp_path)
    plain = pg.evaluate(X)
    steps = [plain[b] - plain[a] for a, b in zip(ids, ids[1:])]
    assert max(steps) - min(steps) < 1.5 and 120 < steps[0] < 260              # undated and unmarked: one ordinary, fairly close step
    pg2, errs2 = _open(browser, _page(_undated_doc({ids[1]: "hours", ids[2]: "years"})), tmp_path)
    x = pg2.evaluate(X)
    quick, jump, even = x[ids[1]] - x[ids[0]], x[ids[2]] - x[ids[1]], x[ids[3]] - x[ids[2]]
    assert quick < 0.6 * steps[0] and jump > 2 * steps[0] and abs(even - steps[0]) < 1.5, (quick, jump, even, steps[0])
    assert not [e for e in errs + errs2 if "ResizeObserver" not in e]       # (WebKit's loop notice is benign here)


def test_the_main_line_is_the_heaviest_thing_on_the_board(browser, tmp_path):
    pg, errs = _open(browser, _page(_v2_doc()), tmp_path)
    w = pg.evaluate("""() => { const sw = c => parseFloat(getComputedStyle(document.querySelector(c)).strokeWidth);
      return {main: sw('#lanes-svg .ln-main'), halo: sw('#lanes-svg .ln-main-halo'), chars: sw('#lanes-svg .ln-br')}; }""")
    assert w["main"] >= 2.5 * w["chars"] and w["halo"] > w["main"], w
    assert not errs


def test_a_legacy_timeline_still_draws_its_branches_as_dips(browser, tmp_path):
    pg, errs = _open(browser, build_timeline(*load_brief(copy.deepcopy(LEGACY)))[0], tmp_path)
    r = pg.evaluate(GEOMETRY)
    assert not errs, errs
    assert r["bad"] == [], r["bad"][:8]
    pres = pg.evaluate("() => { var P=window._altoLanesGeo.presence, o={}; Object.keys(P).forEach(function(k){ o[k]=P[k].map(function(s){ return s.id; }); }); return o; }")
    assert pres == {"tomas": ["letter", "council"], "ilse": ["letter", "council"], "flashback": ["memory"]}, pres
    assert r["detours"] == []


def test_a_phone_keeps_the_card_view(browser, tmp_path):
    pg, errs = _open(browser, _page(_v2_doc()), tmp_path, phone=True)
    assert not errs, errs
    r = pg.evaluate("""() => ({mobile: document.documentElement.classList.contains('mobile'),
        svg: (function(s){ return !s || getComputedStyle(s).display==='none'; })(document.getElementById('lanes-svg')),
        past: [].every.call(document.querySelectorAll('.lanes-past'), function(e){ return getComputedStyle(e).display==='none'; }),
        chip: (document.querySelector('#node-f1 .lanes-when')||{}).textContent || ''})""")
    assert r["mobile"] and r["svg"] and r["past"], r
    assert r["chip"].startswith("1987") and "Mara's childhood" in r["chip"], r
