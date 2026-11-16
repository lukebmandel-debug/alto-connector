"""Every format dims what a filter hides (Luke, 2026-11-01: "In all formats across alto, please ensure that filters dim (or something that works
equally as well artistically given the format) things that don't apply").

One test over (format, style, filter kind). A filter writes `dimmed` (slot chips), `ent-dimmed` (entity chips) or `rel-dimmed` (relation lines) on a node's
`.node-card`; `window._altoShown(id)` (filter_panel.py) is the one answer to "is this node shown?". Each case opens a built page in WebKit, switches the
style, clicks the first chip of one kind and then asks, for every node `_altoShown` says is hidden:
  diff   the node's rectangle looks different (mean luminance change >= 2): the cards of the timeline, lanes, outline, System and Star chart;
  disc   its body is dimmed, not only its label (the median luminance of the middle of its rectangle moves by >= 20): System in Retro (a cream disc) and the
         3D Star chart (a lit sphere);
  plate  as diff, and the card's own plate is faded and its glow gone (Holographic: the whole card fades together, Art alto-art-1101-4600-a);
  body   as diff, and the card's own opacity is <= .2 (the Classic System look: plate, edge, glow and contents fade together, Art alto-art-1102-0800-a);
  dom    its building (the node, or the card's contents) is drawn at <= 50% (the city map's glass buildings, `pal-dim`);
  pins   (Memory Atlas) its pin carries `wp-dim` and is drawn at <= 50%.
The Blueprint / Museum have their own test (tests/test_blueprint_filter_dim.py, branch alto-bp-filter-dim).

Skipped without Playwright and PIL (the repo venv has neither; see the 1.9.62 notes). Local pages only: nothing here touches the network, Firebase or any
ALTO_* setting."""
import copy
import http.server
import io
import json
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import palace_assets, world_plan as wp  # noqa: E402
from alto.build.builder import build_timeline, load_brief  # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None
try:
    from PIL import Image, ImageChops
except ImportError:
    Image = None

SAMPLES = ROOT / "samples"
IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"   # (the page decides "phone" by this and the width)
SLOT = [{"id": "court", "label": "Filter by Court", "source": "axis1"}]


def _sample(name, **brief):
    d = json.loads((SAMPLES / f"{name}.json").read_text(encoding="utf-8"))
    d["brief"].update(brief)
    return d


def _html(d):
    b, n, c = load_brief(copy.deepcopy(d))
    return build_timeline(b, n, c)[0]


def _timeline():
    return _html(_sample("contracts_brief", filters=SLOT))


def _lanes():
    return _html(_sample("lanes_brief"))


def _outline():
    return _html(_sample("outline_brief"))


def _system():
    d = _sample("contracts_brief", layout="solar", hub_look="stars", filters=SLOT)
    d["brief"]["mode"] = "outline"
    return _html(d)


def _entities():
    return _sample("contracts_brief")["brief"]["entities"]


def _city():
    from tests import test_palace_chrome as pc
    d = pc.bundle()
    d["brief"].update(entities=_entities(), entity_axis_label="Doctrines", entity_axis_singular="Doctrine")
    for i, n in enumerate(d["nodes"]):
        n["entity_ids"] = [_entities()[i % 3]["id"]]
    return _html(d)


def _atlas():
    from tests.test_world_palace import NODES, brief
    b = brief(world={"places": {"erie": wp.resolve("Peru")}}, entities=_entities(), entity_axis_label="Doctrines", entity_axis_singular="Doctrine",
              relations=[{"key": "spine", "label": "leads to"}, {"key": "cites", "label": "cites", "color": "#a78bfa"}])
    nodes = copy.deepcopy(NODES)
    for i, n in enumerate(nodes):
        n["entity_ids"] = [_entities()[i % 3]["id"]]
    return _html({"brief": b, "nodes": nodes, "connections": [["pj2", "hanna", "cites"], ["pj", "erie", "spine"]]})


def style(s):
    return f"window._altoStyle.set('{s}')"


def sstyle(s):
    return f"window._altoSolarStyles.set('{s}')"


def atlas_globe():
    return ("(()=>{var b=[...document.querySelectorAll('#wpal-root button, #wpal-root .wp-btn')]"
            ".find(x=>/globe/i.test(x.textContent+x.title+(x.getAttribute('aria-label')||'')));if(b)b.click();})()")


# (id, builder, setup JS, chip kind, metric, marks)
CASES = [
    ("timeline-classic-slot", _timeline, None, "slot", "diff", ()),
    ("timeline-retro-slot", _timeline, style("retro"), "slot", "diff", ()),
    ("timeline-holo-slot", _timeline, style("holo"), "slot", "plate", ()),
    ("timeline-classic-entity", _timeline, None, "entity", "diff", ()),
    ("timeline-classic-lines", _timeline, None, "lines", "diff", ()),
    ("lanes-classic-lines", _lanes, None, "lines", "diff", ()),
    ("lanes-retro-lines", _lanes, style("retro"), "lines", "diff", ()),
    ("lanes-holo-lines", _lanes, style("holo"), "lines", "plate", ()),
    ("outline-classic-lines", _outline, None, "lines", "diff", ()),
    ("outline-retro-lines", _outline, style("retro"), "lines", "diff", ()),
    ("outline-holo-lines", _outline, style("holo"), "lines", "plate", ()),
    ("city-classic-entity", _city, None, "entity", "dom", ()),
    ("city-retro-entity", _city, style("retro"), "entity", "dom", ()),
    ("system-system-slot", _system, sstyle("system"), "slot", "body", ()),
    ("system-chart-slot", _system, sstyle("chart"), "slot", "diff", ()),
    ("system-retro-slot", _system, sstyle("retro"), "slot", "disc", ()),
    ("system-holo-slot", _system, sstyle("holo"), "slot", "plate", ()),
    ("system-3d-slot", _system, sstyle("3d"), "slot", "disc", ()),
    ("atlas-flat-entity", _atlas, None, "entity", "pins", ()),
    ("atlas-flat-lines", _atlas, None, "lines", "pins", ()),
    ("atlas-globe-entity", _atlas, atlas_globe(), "entity", "pins", ()),
    ("atlas-globe-lines", _atlas, atlas_globe(), "lines", "pins", ()),
]


class _Server:
    def __init__(self, html):
        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                path = self.path.split("?")[0]
                code, ct, body = 404, "text/plain", b"no"
                if path in ("/", "/index.html"):
                    code, ct, body = 200, "text/html; charset=utf-8", html.encode()
                elif path == "/alto-cloud.js":
                    code, ct, body = 200, "text/javascript", b""
                else:
                    hit = palace_assets.find(path)
                    if hit:
                        code, ct, body = 200, hit[0], (hit[1].encode() if isinstance(hit[1], str) else hit[1])
                self.send_response(code)
                self.send_header("Content-Type", ct)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.origin = "http://127.0.0.1:%d" % self.srv.server_port

    def close(self):
        self.srv.shutdown()


@pytest.fixture(scope="module")
def browser():
    if pw is None or Image is None:
        pytest.skip("Playwright and PIL are needed")
    with pw.sync_playwright() as p:
        try:
            b = p.webkit.launch()
        except Exception as e:
            pytest.skip(f"no webkit: {e}")
        yield b
        b.close()


_PAGES = {}


def _page_html(builder):
    if builder not in _PAGES:
        _PAGES[builder] = builder()
    return _PAGES[builder]


def _lum(png):
    return Image.open(io.BytesIO(png)).convert("L")


def _median(img):
    v = sorted(img.getdata())
    return v[len(v) // 2]


NODES_JS = """() => [...document.querySelectorAll('#world .node')].map(n => { const r = n.getBoundingClientRect();
  var cd = n.querySelector('.node-card'), cs = cd && getComputedStyle(cd), bg = cs ? (cs.backgroundColor.match(/[\\d.]+/g) || []) : [];
  return {cop: cs ? parseFloat(cs.opacity) : 1, sh: cs ? cs.boxShadow : 'none', ba: bg.length > 3 ? parseFloat(bg[3]) : 1, id: n.id.slice(5), nop: parseFloat(getComputedStyle(n).opacity), x: r.x, y: r.y, w: r.width, h: r.height, shown: window._altoShown ? !!window._altoShown(n.id.slice(5)) : true,
          op: (n.querySelector('.node-card') && n.querySelector('.node-card').firstElementChild) ? parseFloat(getComputedStyle(n.querySelector('.node-card').firstElementChild).opacity) : 1}; })"""
CLICK_JS = """(k) => { const e = [...document.querySelectorAll('.ef-chip[data-fs]')].find(x => x.dataset.fs.startsWith(k)); if (!e) return false; e.click(); return true; }"""
PINS_JS = """() => [...document.querySelectorAll('#wpal-root .wp-pin')].map(p => ({dim: p.classList.contains('wp-dim'), op: parseFloat(getComputedStyle(p).opacity)}))"""


@pytest.mark.parametrize("case", [pytest.param(c, id=c[0], marks=c[5]) for c in CASES])
def test_a_filter_dims_what_it_hides(browser, case):
    _id, builder, setup, kind, metric, _marks = case
    srv = _Server(_page_html(builder))
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    try:
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(srv.origin + "/index.html", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)
        if setup:
            page.evaluate(setup)
            page.wait_for_timeout(3000)
        before = _lum(page.screenshot())
        assert page.evaluate(CLICK_JS, kind), f"the page has no {kind} chip"
        page.wait_for_timeout(3000)
        after = _lum(page.screenshot())
        assert not errors, errors
        if metric == "pins":
            pins = page.evaluate(PINS_JS)
            hidden = [p for p in pins if p["dim"]]
            assert hidden, "no pin fades under the filter"
            assert all(p["op"] <= 0.5 for p in hidden), hidden
            return
        nodes = page.evaluate(NODES_JS)
        hidden = [n for n in nodes if not n["shown"]]
        assert hidden, "the filter hides nothing"
        W, H = before.size
        measured = 0
        for n in hidden:
            x0, y0, x1, y1 = max(0, int(n["x"])), max(0, int(n["y"])), min(W, int(n["x"] + n["w"])), min(H, int(n["y"] + n["h"]))
            if x1 - x0 < 8 or y1 - y0 < 8:
                continue
            measured += 1
            a, b = before.crop((x0, y0, x1, y1)), after.crop((x0, y0, x1, y1))
            if metric == "dom":
                assert min(n["op"], n["nop"]) <= 0.5, n
            elif metric in ("diff", "plate", "body"):
                if metric == "body":
                    assert n["cop"] <= 0.2, f"{n['id']}: the whole body is not faded ({n['cop']})"
                if metric == "plate":
                    assert n["sh"] == "none" and n["ba"] <= 0.2, f"{n['id']}: the plate is not faded ({n['ba']}, {n['sh'][:40]})"
                d = ImageChops.difference(a, b)
                assert sum(d.getdata()) / (d.size[0] * d.size[1]) >= 2.0, f"{n['id']} looks the same under the filter"
            else:
                qx, qy = a.size[0] // 4, a.size[1] // 4
                box = (qx, qy, a.size[0] - qx, a.size[1] - qy)
                assert abs(_median(a.crop(box)) - _median(b.crop(box))) >= 20, f"{n['id']}'s body is not dimmed (only its label is)"
        assert measured, "no hidden node is on screen to look at"
    finally:
        ctx.close()
        srv.close()


@pytest.mark.parametrize("name", ["atlas-relation-pins", "holo-card", "system-classic"])
def test_the_dim_is_on_on_phones_too(browser, name):
    """Luke's yes L-1101-231956: dimming on Holographic, Retro, System and Atlas covers phones (390x844, iPhone UA, Card view). A relation-line filter fades the Atlas's
    pins and a Holographic card a filter hides fades whole (plate 15%, 1px edge at 30%). The Card-view slot filter stays as it is (it hides by data, never dims)."""
    srv = _Server(_atlas() if name == "atlas-relation-pins" else _system() if name == "system-classic" else _timeline())
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, user_agent=IPHONE)
    try:
        page = ctx.new_page()
        page.goto(srv.origin + "/index.html" + ("?view=whole" if name == "system-classic" else ""), wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)
        if name == "system-classic":
            page.evaluate(sstyle("system"))
            page.wait_for_timeout(2500)
            assert page.evaluate(CLICK_JS, "entity")
            page.wait_for_timeout(2500)
            ops = page.evaluate("""() => [...document.querySelectorAll('#world .node')].filter(n => !window._altoShown(n.id.slice(5))).map(n => parseFloat(getComputedStyle(n.querySelector('.node-card')).opacity))""")
            assert ops and all(o <= 0.2 for o in ops), ops
        elif name == "atlas-relation-pins":
            assert page.evaluate("document.querySelectorAll('#wpal-root .wp-pin').length") > 0
            assert page.evaluate(CLICK_JS, "lines")
            page.wait_for_timeout(2500)
            assert page.evaluate("document.querySelectorAll('#wpal-root .wp-pin.wp-dim').length") > 0
        else:
            page.evaluate(style("holo"))
            page.wait_for_timeout(2500)
            assert page.evaluate(CLICK_JS, "entity")
            page.wait_for_timeout(2500)
            hidden = page.evaluate("""() => [...document.querySelectorAll('#world .node')].filter(n => !window._altoShown(n.id.slice(5))).map(n => getComputedStyle(n.querySelector('.node-card')).borderTopColor)""")
            assert hidden and all("0.3)" in c for c in hidden), hidden
    finally:
        ctx.close()
        srv.close()
