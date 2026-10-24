"""The horizontal timeline's spacing (lanes.py, Luke 2026-10-23): "Its a problem that you have to scroll up
or down to see them all, they should all be within the bounds of the page. You left out major characters that
had nav bar chips ... you should be able to figure out the spacing based on time."

So: every character with a chip in the nav bar has a line (the brief's lines, plus one for each chip it never
named); the whole board — every card, every line — fits between the bars at the top and the rail at the bottom
on a desktop window and on a phone held sideways (the phone's whole view), with nothing to scroll up or down;
and across is story time: an event later in the story is never left of an earlier one, a long gap is wider than
a short one, and close events still never overlap. Geometry is checked in Chromium and WebKit."""
import copy
import functools
import http.server
import socketserver
import threading

import pytest

from alto.build import phone
from alto.build.builder import build_timeline, load_brief
from alto.build.lanes import lanes_payload

CHARS = [("ada", "Ada"), ("ben", "Ben Ortiz"), ("cy", "CY"), ("dora", "Dora"), ("eli", "Eli"),
         ("fay", "Fay Lin"), ("gus", "Gus"), ("hal", "Hal")]


def _doc():
    """Eight characters with chips; the brief names lines for only three of them (one by a label that is
    the entity's alias). Thirty events over three units, dated by story day — some on the same day, one
    long jump — plus a two-event flashback and one character's own event off the page."""
    b = {"title": "Fit", "timeline_id": "fit", "subject": "Fit", "mode": "lanes", "main_line": "The page",
         "node_noun": "scene", "entity_axis_label": "Characters", "entity_axis_singular": "Character",
         "acts": [{"label": "ONE — START", "short": "One", "color": "#4a9eff"},
                  {"label": "TWO — MIDDLE", "short": "Two", "color": "#e8a87c"},
                  {"label": "THREE — END", "short": "Three", "color": "#a78bfa"}],
         "relations": [{"key": "spine", "label": "leads to"}],
         "lines": [{"id": "l-ada", "label": "Ada", "side": "above"}, {"id": "l-ben", "label": "Ortiz", "side": "below"},
                   {"id": "cy", "label": "Cy", "side": "above"}],
         "flashbacks": [{"id": "before", "label": "Years before"}],
         "entities": [{"id": i, "name": n, "role": "", "color": ""} for i, n in CHARS]}
    b["entities"][1]["aliases"] = ["Ortiz"]
    nodes, day = [], 0
    days = [1, 1, 2, 3, 3, 3, 5, 6, 8, 9, 10, 10, 11, 14, 15, 15, 16, 30, 31, 31, 32, 34, 35, 36, 36, 37, 40, 41, 42, 44]
    for k, day in enumerate(days):
        who = [CHARS[(k + j) % 8][0] for j in range(1 + k % 4)]
        n = {"id": f"e{k:02d}", "act": k * 3 // len(days), "tag": "Scene", "title": f"Scene {k + 1} of the story",
             "desc": f"What happens in scene {k + 1}, in the material's words, long enough to wrap onto a few lines.",
             "when": f"Day {day}", "entity_ids": who}
        nodes.append(n)
        if k == 12:                                            # the story looks back, then resumes
            nodes.append({"id": "f1", "act": n["act"], "tag": "Memory", "title": "The old house", "desc": "Then.",
                          "when": "Day -400", "flash": "before", "entity_ids": ["ada", "gus"]})
            nodes.append({"id": "f2", "act": n["act"], "tag": "Memory", "title": "The fire", "desc": "Then.",
                          "when": "Day -380", "flash": "before", "entity_ids": ["gus"]})
    nodes.append({"id": "own", "act": 1, "line": "cy", "tag": "Aside", "title": "Cy alone", "desc": "Off the page.",
                  "when": "Day 12", "entity_ids": []})
    return {"brief": b, "nodes": nodes, "connections": []}


def test_every_character_with_a_chip_has_a_line():
    d = _doc()
    b, nodes, *_ = load_brief(copy.deepcopy(d))
    L = lanes_payload(b, nodes)
    ids = [ln["id"] for ln in L["lines"]]
    # the brief's lines first (matched by id, by name, by alias), then one for every chip it never named
    assert ids == ["l-ada", "l-ben", "cy", "dora", "eli", "fay", "gus", "hal"], ids
    assert [ln["label"] for ln in L["lines"]][3:] == ["Dora", "Eli", "Fay Lin", "Gus", "Hal"]
    sides = [ln["side"] for ln in L["lines"]]
    assert abs(sides.count("above") - sides.count("below")) <= 1, sides
    by = {ln["id"]: ln for ln in L["lines"]}
    of = {"ada": "l-ada", "ben": "l-ben", "cy": "cy", "dora": "dora", "eli": "eli", "fay": "fay", "gus": "gus", "hal": "hal"}
    for e, lid in of.items():                                  # on the page wherever the event carries its chip
        want = [n["id"] for n in d["nodes"] if e in n["entity_ids"] and not n.get("line")]
        assert by[lid]["presence"] == [i for i in L["order"] if i in want], lid
    assert L["ev"]["e00"]["present"] == [] and L["ev"]["e00"]["ent"] == ["l-ada"]   # authored `present` stays as authored
    # a chip no event links gets no line
    d2 = copy.deepcopy(d)
    d2["brief"]["entities"].append({"id": "zed", "name": "Zed", "role": "", "color": ""})
    b2, n2, *_ = load_brief(d2)
    assert "zed" not in [ln["id"] for ln in lanes_payload(b2, n2)["lines"]]


# ── in a browser ─────────────────────────────────────────────────────────────

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None
IPHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 "
          "(KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1")


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


@pytest.fixture
def site(tmp_path):
    """The page served over http with the phone's hosted script beside it, so a phone gets its whole view."""
    name, body = phone.phone_asset()
    (tmp_path / "phone").mkdir()
    (tmp_path / "phone" / name).write_text(body, encoding="utf-8")
    (tmp_path / "fit.html").write_text(build_timeline(*load_brief(_doc()))[0], encoding="utf-8")
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(tmp_path))
    h.log_message = lambda *a: None
    srv = socketserver.TCPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/fit.html"
    srv.shutdown()
    srv.server_close()


DEVICES = {"desktop": dict(viewport={"width": 1440, "height": 900}),
           "laptop": dict(viewport={"width": 1280, "height": 720}),
           "phone-landscape": dict(viewport={"width": 844, "height": 390}, user_agent=IPHONE, has_touch=True)}

# everything in screen px: the band no chrome covers, every card and line inside it, no card on another
FITS = r"""() => {
  var c=document.getElementById('canvas'), r=c.getBoundingClientRect(), top=r.top, bot=r.bottom, q, out={bad:[], lines:[], cards:0};
  var vis=function(e){ if(!e) return null; var b=e.getBoundingClientRect(); return (b.width && b.height && getComputedStyle(e).display!=='none') ? b : null; };
  if((q=vis(document.getElementById('key-toggle')))) top=Math.max(top, q.bottom);
  ['lanes-nav','ph-bar'].forEach(function(id){ if((q=vis(document.getElementById(id))) && q.top>r.top+40) bot=Math.min(bot, q.top); });
  var boxes=[];
  document.querySelectorAll('#world .node[id^="node-"] .node-card').forEach(function(e){ var b=e.getBoundingClientRect(); if(!b.height) return;
    out.cards++; boxes.push([e.parentNode.id, b]);
    if(b.top<top-1 || b.bottom>bot+1) out.bad.push('card '+e.parentNode.id+' '+Math.round(b.top)+'..'+Math.round(b.bottom)+' outside '+Math.round(top)+'..'+Math.round(bot)); });
  document.querySelectorAll('#lanes-svg g[data-ln] path.ln-br, #lanes-svg g[data-ln] path.ln-main').forEach(function(p){ var b=p.getBoundingClientRect();
    if(p.classList.contains('ln-br')) out.lines.push(p.parentNode.getAttribute('data-ln'));
    if(b.height && (b.top<top-1 || b.bottom>bot+1)) out.bad.push('line '+p.parentNode.getAttribute('data-ln')+' '+Math.round(b.top)+'..'+Math.round(b.bottom)); });
  document.querySelectorAll('.lanes-tag').forEach(function(t){ var b=vis(t); if(b && (b.top<top-1 || b.bottom>bot+1)) out.bad.push('label '+t.textContent); });
  for(var i=0;i<boxes.length;i++) for(var j=i+1;j<boxes.length;j++){ var a=boxes[i][1], b=boxes[j][1];
    if(a.left<b.right-2 && b.left<a.right-2 && a.top<b.bottom-2 && b.top<a.bottom-2) out.bad.push('cards overlap '+boxes[i][0]+' '+boxes[j][0]); }
  out.scroll=[c.scrollHeight, c.clientHeight];
  out.x=window._altoLanesGeo.x; out.whole=document.documentElement.classList.contains('phone-whole');
  return out; }"""


@pytest.mark.parametrize("device", list(DEVICES))
def test_the_whole_board_fits_the_window_in_story_order(browser, site, device):
    ctx = browser.new_context(**DEVICES[device])
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(site + ("?view=whole" if device.startswith("phone") else ""))
    pg.wait_for_timeout(2600)                                  # the rail / the phone's bar arrive, the board refits once
    r = pg.evaluate(FITS)
    ctx.close()
    assert not [e for e in errs if "ResizeObserver" not in e], errs
    if device.startswith("phone"):
        assert r["whole"], "the phone's whole view did not load"
    assert r["cards"] == 33
    assert r["bad"] == [], r["bad"][:10]
    assert r["scroll"][0] <= r["scroll"][1] + 1, r["scroll"]                 # nothing to scroll up or down to
    # every character with a chip has its line
    assert sorted(set(r["lines"])) == sorted(["l-ada", "l-ben", "cy", "dora", "eli", "fay", "gus", "hal"]), r["lines"]
    # across is story time: in the present, later is never left of earlier, and strictly right when later
    x, d = r["x"], _doc()
    pres = [(int(n["when"].split()[1]), k, n["id"]) for k, n in enumerate(d["nodes"]) if not n.get("flash")]
    pres.sort()
    for (ta, _, a), (tb, _, b) in zip(pres, pres[1:]):
        assert x[b] >= x[a] - 0.5, (a, b, x[a], x[b])
        if tb > ta:
            assert x[b] > x[a] + 1, (a, b, x[a], x[b])
    # a jump of two weeks (Day 16 → Day 30) is wider than a step of one day (Day 30 → Day 31)
    assert x["e17"] - x["e16"] > 1.5 * (x["e18"] - x["e17"]), (x["e16"], x["e17"], x["e18"])
    # the flashback's events sit inside its detour, between the present events either side of it
    assert x["e12"] < x["f1"] < x["f2"] < x["e13"]
