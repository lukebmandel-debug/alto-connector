"""Measures how readable the Memory Atlas's map labels are (Luke, 2026-11-01: "some text here isn't that visible with similar colors to the
background"). Used by tests/test_atlas_label_contrast.py, and runnable alone for a table:  python -m tests.atlas_contrast

HOW A LABEL IS MEASURED (the pixels, not the CSS). The scene is screenshotted three times: the labels' halo alone (text transparent), their letters
alone (magenta, no shadows: the letters' true shape) and the map alone. The ground a letter is read against is the halo-alone picture 1.2 to 1.7 px
out from the letters' edge; its contrast is WCAG's (the label's text colour against each of those pixels). A label is judged by its worst 5%
(p5), so a halo that fails on one side of a letter still fails. The plates (pins, tags, cards) are solid by design and checked by computed colour.
"""
from __future__ import annotations

import base64
import json

COLORS = ["#ffd60a", "#f4f1de", "#0b1d51", "#2a9d8f", "#d62828", "#7b2cbf", "#8ecae6", "#1d2433"]    # pale yellow, cream, navy, teal, red, purple, sky, the text ink itself

PLACES = [  # (node id, act, title, country)
    ("a1", 0, "Answering the Complaint", "Niger"), ("a2", 0, "The Reply (Rule 7(a))", "Niamey, Niger"), ("a3", 0, "Service of Process", "Nigeria"),
    ("b1", 1, "Pennoyer v. Neff", "Brazil"), ("b2", 1, "Minimum contacts", "Peru"), ("b3", 1, "General jurisdiction", "Argentina"),
    ("c1", 2, "Erie Railroad v. Tompkins", "India"), ("c2", 2, "Hanna v. Plumer", "China"), ("c3", 2, "Byrd v. Blue Ridge", "Kazakhstan"),
    ("d1", 3, "Rule 12(b)(6)", "Germany"), ("d2", 3, "Twombly and Iqbal", "Poland"), ("d3", 3, "Summary judgment", "France"),
    ("e1", 4, "Joinder of parties", "Canada"), ("e2", 4, "Class actions", "United States"), ("e3", 4, "Intervention", "Mexico"),
    ("f1", 5, "Preclusion", "Australia"), ("f2", 5, "Res judicata", "Indonesia"), ("f3", 5, "Collateral estoppel", "Japan"),
    ("g1", 6, "Appeals", "Egypt"), ("g2", 6, "Final judgment rule", "South Africa"), ("g3", 6, "Mandamus", "Russia"),
    ("h1", 7, "Discovery", "Saudi Arabia"), ("h2", 7, "Rule 26(b)(1)", "Turkey"), ("h3", 7, "Spoliation", "Sweden"),
]


def page_html():
    from alto.build import world_plan as wp
    from alto.build.builder import build_timeline, load_brief
    nodes = [{"id": i, "act": a, "title": t, "tag": "", "desc": "d"} for i, a, t, _ in PLACES]
    acts = [{"label": f"Unit {a + 1}", "color": COLORS[a]} for a in range(len(COLORS))]
    b = {"title": "Civ Pro", "timeline_id": "civpro", "mode": "palace", "palace_view": "world", "columns": 5, "node_noun": "Concept",
         "period_noun": "Unit", "acts": acts, "world": {"places": {i: wp.resolve(c) for i, _, _, c in PLACES}}}
    return build_timeline(*load_brief({"brief": b, "nodes": nodes}))[0]


# the labels on screen: their boxes and the colour each line is set in
LABELS = r"""(() => { var out = [], vw = innerWidth, vh = innerHeight;
  document.querySelectorAll('#wpal-root .wp-lbl:not(.wp-off)').forEach(L => { var cs = getComputedStyle(L); if (cs.visibility === 'hidden' || +cs.opacity < .9) return;
    L.querySelectorAll('b,i').forEach(e => { var r = e.getBoundingClientRect(); if (!r.width || !e.textContent.trim()) return;
      if (e.tagName === 'I' && getComputedStyle(e).display === 'none') return;
      if (r.left < 14 || r.top < 52 || r.right > vw - 14 || r.bottom > vh - 14) return;       // (a label cut by the window edge, the style frame or under the page title is the page chrome, not the map)
      out.push({t: e.textContent.trim().slice(0, 28), k: e.tagName, x: r.left, y: r.top, w: r.width, h: r.height, c: getComputedStyle(e).color}); }); });
  return out; })()"""

# the plates: a pin's number against its plate, a tag's and a card's text against their fill (over white and over black, the worst of the map beneath)
PLATES = r"""(() => { var cv = document.createElement('canvas').getContext('2d'), out = [];
  function rgba(s){ cv.clearRect(0,0,1,1); cv.fillStyle = '#000'; cv.fillStyle = s; cv.fillRect(0,0,1,1); var d = cv.getImageData(0,0,1,1).data; return [d[0], d[1], d[2], d[3] / 255]; }
  function over(f, b){ return [0,1,2].map(i => f[i] * f[3] + b[i] * (1 - f[3])); }
  function lum(c){ return c.map(v => { v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); }).reduce((a, v, i) => a + v * [.2126, .7152, .0722][i], 0); }
  function cr(a, b){ var x = lum(a), y = lum(b); return (Math.max(x, y) + .05) / (Math.min(x, y) + .05); }
  function ground(e){ var layers = []; for(var n = e; n && n.nodeType === 1; n = n.parentElement){ var c = rgba(getComputedStyle(n).backgroundColor); if(c[3] > 0) layers.push(c); if(c[3] >= .999) break; } return layers; }
  function plate(sel, what){ document.querySelectorAll(sel).forEach(e => { var cs = getComputedStyle(e), r = e.getBoundingClientRect(); if(!r.width || cs.visibility === 'hidden' || +cs.opacity < .5) return;
      var L = ground(e), tx = rgba(cs.color);
      var worst = Math.min.apply(null, [[255,255,255],[0,0,0]].map(g => { var bg = g; for(var i = L.length - 1; i >= 0; i--) bg = over(L[i], bg); return cr(over(tx, bg), bg); }));
      out.push({what: what, t: (e.textContent || '').trim().slice(0, 24), cr: worst}); }); }
  plate('#wpal-root .wp-pin', 'pin'); plate('#wpal-root .wp-hk', 'badge'); plate('#wpal-root .wp-tag', 'tag'); plate('#wpal-root .wp-tag b', 'tag number'); plate('#wpal-root .wp-card .n', 'card kicker'); plate('#wpal-root .wp-list button b', 'list number');
  return out; })()"""

ANALYSE = r"""async ([C, D, E, boxes]) => {
  function load(u){ return new Promise(r => { var i = new Image(); i.onload = () => r(i); i.src = u; }); }
  var ic = await load(C), id = await load(D), ie = await load(E), W = ic.width, H = ic.height, S = W / innerWidth0;
  function px(img){ var c = document.createElement('canvas'); c.width = W; c.height = H; var x = c.getContext('2d', {willReadFrequently: true}); x.drawImage(img, 0, 0); return x.getImageData(0, 0, W, H).data; }
  var dc = px(ic), dd = px(id), de = px(ie), cv = document.createElement('canvas').getContext('2d');
  function rgb(s){ cv.fillStyle = '#000'; cv.fillStyle = s; cv.fillRect(0,0,1,1); var d = cv.getImageData(0,0,1,1).data; return [d[0], d[1], d[2]]; }
  function lum(c){ var l = 0; for(var i = 0; i < 3; i++){ var v = c[i] / 255; l += (v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4)) * [.2126, .7152, .0722][i]; } return l; }
  function cr(a, b){ var x = lum(a), y = lum(b); return (Math.max(x, y) + .05) / (Math.min(x, y) + .05); }
  var res = [];
  boxes.forEach(bx => { var tc = rgb(bx.c), pad = 6, x0 = Math.max(0, Math.floor((bx.x - pad) * S)), y0 = Math.max(0, Math.floor((bx.y - pad) * S)),
      x1 = Math.min(W, Math.ceil((bx.x + bx.w + pad) * S)), y1 = Math.min(H, Math.ceil((bx.y + bx.h + pad) * S)), w = x1 - x0, h = y1 - y0, ink = new Uint8Array(w * h), n = 0;
    // the letters' own shape: where the label painted in magenta (no shadows) and the map beneath did not already look so
    for(var y = 0; y < h; y++) for(var x = 0; x < w; x++){ var o = ((y0 + y) * W + x0 + x) * 4;
      var near = Math.max(Math.abs(dd[o] - 255), Math.abs(dd[o+1]), Math.abs(dd[o+2] - 255)), ch = Math.abs(dd[o] - de[o]) + Math.abs(dd[o+1] - de[o+1]) + Math.abs(dd[o+2] - de[o+2]);
      if(near < 150 && ch > 50){ ink[y * w + x] = 1; n++; } }
    if(n < 6){ res.push({t: bx.t, k: bx.k, ink: n}); return; }
    // the ground the letters are read against: the shadows alone (text transparent), 1.2 to 1.7 px out from the letters' edge, scored against the text colour
    var d = Math.max(2, Math.round(2 * S)), crs = [], wp = null, lo = Math.pow(1.2 * S, 2), hi = Math.pow(1.7 * S, 2);
    for(var y = d; y < h - d; y++) for(var x = d; x < w - d; x++){ if(ink[y * w + x]) continue;
      var best = 1e9;
      for(var dy = -d; dy <= d; dy++) for(var dx = -d; dx <= d; dx++){ if(ink[(y + dy) * w + x + dx]){ var q = dx * dx + dy * dy; if(q < best) best = q; } }
      if(best <= lo || best > hi) continue;                  // the ring 1.2 to 1.7 css px out from the letters' edge
      var o = ((y0 + y) * W + x0 + x) * 4, cc = cr(tc, [dc[o], dc[o+1], dc[o+2]]); crs.push(cc); if(!wp || cc < wp[0]) wp = [cc, (x0 + x) / S, (y0 + y) / S, dc[o], dc[o+1], dc[o+2]]; }
    crs.sort((a, b) => a - b);
    res.push({t: bx.t, k: bx.k, ink: n, min: crs[0], p5: crs[Math.floor(crs.length * .05)], med: crs[crs.length >> 1], n: crs.length, wp: wp}); });
  return res; }"""


def _shot(page, css=None) -> str:
    if css:
        page.evaluate("(c) => { var s = document.createElement('style'); s.id = '_lblShot'; s.textContent = c; document.head.appendChild(s); }", css)
    png = page.screenshot(type="png")
    if css:
        page.evaluate("document.getElementById('_lblShot').remove()")
    return "data:image/png;base64," + base64.b64encode(png).decode()


SIG = r"""(() => [...document.querySelectorAll('#wpal-root .wp-lbl')].map(l => { var r = l.getBoundingClientRect(), c = getComputedStyle(l);
  return [l.classList.contains('wp-off') ? 0 : 1, (+c.opacity).toFixed(2), r.left.toFixed(1), r.top.toFixed(1)].join(','); }).join('|'))()"""


def settled(page, tries=30):
    """Waits until no label is moving or fading (the map decides its names once a gesture settles, and they fade in over .22 s)."""
    prev = None
    for _ in range(tries):
        cur = page.evaluate(SIG)
        if cur == prev and not any(0 < float(x.split(",")[1]) < 1 for x in cur.split("|") if x):
            return True
        prev = cur
        page.wait_for_timeout(350)
    return False


def measure(page, scratch):
    """Labels' contrast on screen now. `scratch` is a blank page of the same browser, used to read the screenshots."""
    settled(page)
    boxes = page.evaluate(LABELS)
    if not boxes:
        return [], page.evaluate(PLATES)
    c = _shot(page, "#wpal-root .wp-lbl,#wpal-root .wp-lbl *{color:transparent !important;text-decoration-color:transparent !important}")      # the halo alone
    d = _shot(page, "#wpal-root .wp-lbl,#wpal-root .wp-lbl *{color:#f0f !important;text-shadow:none !important;text-decoration:none !important}")  # the letters alone
    e = _shot(page, "#wpal-root .wp-lbl{visibility:hidden !important}")                                                                           # the map alone
    scratch.set_content("<script>var innerWidth0=%d</script>" % page.evaluate("innerWidth"))
    return scratch.evaluate(ANALYSE, [c, d, e, boxes]), page.evaluate(PLATES)


STYLES = ["classic-light", "classic-dark", "retro", "holo-light", "holo-dark"]


def set_style(page, name):
    page.evaluate("""(name) => { var r = document.documentElement, st = name.split('-')[0];
        window._altoStyle.set(st);
        if(st !== 'retro') r.classList.toggle('dark', name.endsWith('-dark')); }""", name)
    page.wait_for_timeout(1200)


SCENES = [
    ("world", "AltoWorld.tourMode(false); AltoWorld.world()"),
    ("tour-world", "AltoWorld.tourMode(true); AltoWorld.world()"),
    ("unit-1", "AltoWorld.tourMode(false); AltoWorld.unit(0, {instant: true})"),
    ("unit-6", "AltoWorld.unit(5, {instant: true})"),
    ("country", "AltoWorld.select('b2', {instant: true})"),
    ("country+", "AltoWorld.select('c1', {instant: true})"),
    ("tour-unit", "AltoWorld.tourMode(true); AltoWorld.unit(2, {instant: true})"),
]
LEAN = ("world", "tour-unit", "country", "unit-6")      # the four that show the most labels over the most colours


def run_all(browser, origin, styles=STYLES, zooms=(0, 1, 3), scenes=LEAN, verbose=False):
    ctx = browser.new_context(viewport={"width": 1280, "height": 800}, device_scale_factor=1)
    scratch = ctx.new_page()
    page = ctx.new_page()
    page.goto(origin + "/index.html")
    page.wait_for_function("window.AltoWorld && document.querySelector('#wpal-root .wp-pin')", timeout=20000)
    out = []
    for st in styles:
        set_style(page, st)
        for name, js in [x for x in SCENES if x[0] in scenes]:
            page.evaluate(js)
            for z in zooms:
                if z == 0:
                    page.wait_for_timeout(1000)
                else:
                    for _ in range(z):
                        page.evaluate("(() => { var b = [].find.call(document.querySelectorAll('#wpal-root .wp-ctl .wp-btn'), x => x.getAttribute('aria-label') === 'Zoom in'); b.click(); })()")
                        page.wait_for_timeout(200)
                    page.wait_for_timeout(1100)
                labs, plates = measure(page, scratch)
                out.append({"style": st, "scene": name, "zoom": z, "labels": labs, "plates": plates})
                if verbose:
                    ok = [l for l in labs if "p5" in l]
                    print(st, name, z, "labels", len(ok), "worst p5", min([l["p5"] for l in ok], default=None))
            page.evaluate("AltoWorld.tourMode(false)")
    ctx.close()
    return out


if __name__ == "__main__":
    import http.server
    import sys
    import threading
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from alto.build import palace_assets
    import playwright.sync_api as pw
    html = page_html()

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            path = self.path.split("?")[0]
            hit = (("text/html", html) if path in ("/", "/index.html") else ("text/javascript", "") if path == "/alto-cloud.js" else palace_assets.find(path))
            body = (hit[1] if hit else "no").encode("utf-8")
            self.send_response(200 if hit else 404)
            self.send_header("Content-Type", hit[0] if hit else "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    with pw.sync_playwright() as p:
        b = p.webkit.launch()
        only = sys.argv[2].split(",") if len(sys.argv) > 2 and sys.argv[2] else STYLES
        sc = tuple(sys.argv[3].split(",")) if len(sys.argv) > 3 and sys.argv[3] else LEAN
        res = run_all(b, f"http://127.0.0.1:{srv.server_address[1]}", styles=only, scenes=sc, verbose=True)
        b.close()
    Path(sys.argv[1] if len(sys.argv) > 1 else "contrast.json").write_text(json.dumps(res, indent=1))
