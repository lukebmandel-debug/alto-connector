"""Phone fit (Luke 2026-11-06, L-1106-230038 / L-1106-230647): the Retro frame hugs the screen's true bottom on a phone, the page's background layers cover the screen
(and the runway above and below it) in portrait and landscape, before and after a scroll, and a long unit title wraps inside its header on a phone outline instead of
falling out of it. WebKit, an iPhone user agent, served from 127.0.0.1 like test_atlas_flags.py (a WebKit page.close() can hang: pages are never closed on their own and
the browser's close gets 15 s by an alarm). Not the real Safari: the Simulator steps are in ORG/notes-testing/alto-phone-fit/sim-steps.md."""
import http.server
import json
import signal
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import palace_assets, retro  # noqa: E402
from alto.build.builder import build_timeline, load_brief  # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None

UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"
LONG = ["UNIT ONE — PERSONAL JURISDICTION, SERVICE OF PROCESS AND NOTICE UNDER RULE 4 AND THE LONG-ARM STATUTES",
        "UNIT TWO — THE DUTY OF REASONABLE CARE, BREACH, ACTUAL CAUSE, PROXIMATE CAUSE AND THE LIMITS OF LIABILITY IN NEGLIGENCE",
        "UNIT THREE — Remedies and the extraordinarily long list of every equitable and legal measure a court may award, restitution, reformation, rescission, specific performance, injunctions, declaratory relief and the rest"]


def _page(long_titles, sample="outline"):
    d = json.load(open(ROOT / "samples" / f"{sample}_brief.json"))
    if long_titles:
        for a, t in zip(d["brief"]["acts"], LONG):
            a["label"] = t
            a["short"] = t.title()
    return build_timeline(*load_brief(d))[0]


@pytest.fixture(scope="module")
def origin():
    pages = {"plain": _page(False), "long": _page(True), "lanes": _page(True, "lanes")}

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            path, _, q = self.path.partition("?")
            if path in ("/", "/index.html", "/long", "/lanes"):
                hit = ("text/html", pages["long" if path == "/long" else "lanes" if path == "/lanes" else "plain"])
            elif path == "/alto-cloud.js":
                hit = ("text/javascript", "")
            else:
                hit = palace_assets.find(path)
            body = (hit[1] if hit else "no").encode("utf-8")
            self.send_response(200 if hit else 404)
            self.send_header("Content-Type", hit[0] if hit else "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


@pytest.fixture(scope="module")
def browser():
    if pw is None:
        pytest.skip("Playwright is not installed")
    p = pw.sync_playwright().start()
    try:
        b = p.webkit.launch()
    except Exception as e:
        p.stop()
        pytest.skip(f"no webkit: {e}")
    yield b
    signal.signal(signal.SIGALRM, lambda *a: (_ for _ in ()).throw(TimeoutError("browser close hung")))
    signal.alarm(15)
    try:
        b.close()
        p.stop()
    except Exception:
        pass
    finally:
        signal.alarm(0)


def _open(browser, base, style, size, path="/", whole=True):
    ctx = browser.new_context(viewport={"width": size[0], "height": size[1]}, device_scale_factor=3, is_mobile=True, has_touch=True, user_agent=UA)
    page = ctx.new_page()
    page.goto(base + path + ("?view=whole" if whole else "?view=card"))
    page.wait_for_function("window._altoBg && document.documentElement.classList.contains('rw')", timeout=30000)
    if style != "classic":
        page.evaluate("k => { localStorage.setItem(k.replace(/-bg$/, '-style'), %r); }" % style, page.evaluate("_altoBg.key"))
        page.reload()
        page.wait_for_function("document.documentElement.classList.contains('alto-%s')" % style, timeout=30000)
    page.wait_for_timeout(1200)
    return page


RECTS = """() => { const R = s => { const e = document.querySelector(s); if (!e) return null; const r = e.getBoundingClientRect(); return {l: r.left, t: r.top, r: r.right, b: r.bottom}; };
  return {vw: innerWidth, vh: innerHeight, bg: R('#page-bg'), glass: R('#page-glass'), body: R('body'), frame: R('#sk-frame'), cls: document.documentElement.className}; }"""


@pytest.mark.parametrize("size", [(390, 844), (844, 390)])
@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
def test_the_background_layers_cover_the_screen_and_the_runway_in_both_orientations_and_after_a_scroll(browser, origin, style, size):
    page = _open(browser, origin, style, size)
    for scrolled in (False, True):
        if scrolled:
            page.evaluate("window.scrollTo(0, 60)")
            page.wait_for_timeout(300)
        r = page.evaluate(RECTS)
        for k in ("bg", "glass"):
            b = r[k]
            assert b and b["l"] <= 0 and b["r"] >= r["vw"] and b["t"] <= -80 + 1 and b["b"] >= r["vh"] + 140 - 1, (k, scrolled, r)    # (the 80 px above and the 140 px below the screen box, the runway)
        assert r["body"]["b"] - r["body"]["t"] >= r["vh"] - 1, r


@pytest.mark.parametrize("size", [(390, 844), (844, 390)])
def test_the_retro_page_has_no_frame_only_the_rule_under_the_title(browser, origin, size):
    """Art option D (Luke 2026-11-12): no gold lines, chamfers or corner diagonals, no foot measured against the screen; one plain faded line, no diamond, lowered to clear the title."""
    page = _open(browser, origin, "retro", size)
    r = page.evaluate("""() => { const f = document.getElementById('sk-frame'), b = f && f.querySelector('b'), c = f && getComputedStyle(f);
      return {kids: f ? f.children.length : -1, i: f ? f.querySelectorAll('i').length : -1, bg: c && c.backgroundImage, ext: f ? f.style.getPropertyValue('--fz-ext') : 'x',
              top: b && b.getBoundingClientRect().top, after: b && getComputedStyle(b, '::after').content, fzp: !!document.getElementById('sk-fzp')}; }""")
    assert r["kids"] == 1 and r["i"] == 0 and r["bg"] == "none" and r["ext"] == "" and not r["fzp"] and r["after"] in ("none", "normal"), r          # (no diamond)
    assert abs(r["top"] - (38 if size[0] > size[1] else 40)) < 1.5, r


WHOLE_CHIPS = """() => { const R = e => e.getBoundingClientRect(), z = parseFloat(getComputedStyle(document.getElementById('world')).zoom) || 1;
  const chips = [].slice.call(document.querySelectorAll('#world .phase-label-float')), bars = [].slice.call(document.querySelectorAll('#world .unit-bar')),
        cards = [].slice.call(document.querySelectorAll('#world .node-card')), hits = [];
  const ov = (a, b) => a.left < b.right - .5 && a.right > b.left + .5 && a.top < b.bottom - .5 && a.bottom > b.top + .5;
  chips.concat(bars).forEach(c => cards.forEach(n => { if (ov(R(c), R(n))) hits.push([(c.textContent || c.className).slice(0, 14), n.parentElement.id]); }));
  const rows = bars.map(b => { const br = R(b), nx = cards.map(R).filter(r => r.top > br.bottom - 1).sort((x, y) => x.top - y.top)[0]; return nx ? (nx.top - br.bottom) / z : null; });
  const rl = document.getElementById('summary-wrap'), c0 = chips[0];
  return {hits, rows, hx: window._altoHX || [], ruleGap: rl && c0 ? R(c0).top - R(rl).bottom : null, scrolled: document.getElementById('canvas').scrollTop, chips: chips.map(e => { const c = getComputedStyle(e), sp = e.firstElementChild || e, sr = R(sp), er = R(e), br = R(bars[chips.indexOf(e)]);
    return {t: e.textContent.trim().slice(0, 24), fs: parseFloat(c.fontSize), ell: c.textOverflow, clip: sr.bottom > er.bottom + .5 || sr.top < er.top - .5 || sr.right > er.right + .5 || sr.left < er.left - .5,
            inbar: er.top >= br.top - .5 && er.bottom <= br.bottom + .5}; })}; }"""


@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
@pytest.mark.parametrize("size", [(390, 844), (844, 390)])
def test_a_long_unit_title_wraps_and_grows_its_header_and_the_rows_below_move_down(browser, origin, style, size):
    """Luke 2026-11-06 L-1106-230647: nothing is clipped or ellipsised; a header that needs more room GROWS (window._altoHX) and the engine lays every row below it out again,
    so no chip or unit tube touches a card, each unit keeps its clear gap under its tube, and the type stays at 10.5 px or more."""
    page = _open(browser, origin, style, size, path="/long")
    page.wait_for_timeout(1500)
    r = page.evaluate(WHOLE_CHIPS)
    assert r["chips"], "no unit headers"
    assert r["hits"] == [], r["hits"]                                                        # (no chip or tube over a card)
    assert r["scrolled"] > 0 or r["ruleGap"] >= 6, r                                         # (the first unit's header starts under the header rule, not across it)
    assert max(r["hx"] or [0]) > 0, r                                                        # (the longest title did grow its header, it was not squeezed)
    for x in r["chips"]:
        assert not x["clip"] and x["inbar"], x                                               # (every word inside the chip, the chip inside its tube)
        assert x["fs"] >= 10.5 and x["ell"] != "ellipsis", x
    assert all(g is None or g >= 60 for g in r["rows"]), r["rows"]                           # (the same clear gap under every tube as before: the rows moved, the gap did not shrink)


def test_a_short_title_changes_nothing_in_the_whole_view(browser, origin):
    page = _open(browser, origin, "classic", (390, 844), path="/")
    page.wait_for_timeout(1200)
    r = page.evaluate(WHOLE_CHIPS)
    assert r["hits"] == [] and max(r["hx"] or [0]) == 0 and (r["scrolled"] > 0 or r["ruleGap"] >= 6), r                                    # (no growth where nothing needs it)


def _retro_src():
    return [("/%s/%s" % (f, n)) for f, n, _t in palace_assets.assets() if f == "retro"][0]


def _home_page():
    """The homepage with the hosted Retro script loaded (the Simulator pages' loader), for a phone."""
    from alto.build.pages import build_home
    html = build_home([{"name": "Law school %d" % p, "pid": "p%d" % p, "courses": [{"title": "Civil Procedure %d.%d" % (p, c), "href": "outline.html", "sub": "%d units" % (c + 3),
                       "courseId": "c%d%d" % (p, c), "units": []} for c in range(6)]} for p in range(3)])
    src = [("/%s/%s" % (f, n)) for f, n, _t in palace_assets.assets() if f == "retro"][0]
    i = html.rfind("</body>")
    return html[:i] + "<script>var x=document.createElement('script');x.src=%r;x.onload=function(){setTimeout(function(){window._altoRetro&&window._altoRetro.on();},500);};document.head.appendChild(x);</script>" % src + html[i:]


def test_the_retro_home_page_has_a_rule_under_the_tab_and_the_top_row_has_a_solid_backing(browser, origin):
    """Sim 1107c S6: on the homepage the frame's foot sat ~100 pt above the screen's and cards showed through the top row. Page 790 tall on an 844 screen (Safari's bar up)."""
    import http.server as hs
    page_html = _home_page()

    class H(hs.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            path = self.path.partition("?")[0]
            hit = ("text/html", page_html) if path in ("/", "/home.html") else (("text/javascript", "") if path == "/alto-cloud.js" else palace_assets.find(path))
            body = (hit[1] if hit else "no").encode("utf-8")
            self.send_response(200 if hit else 404)
            self.send_header("Content-Type", hit[0] if hit else "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    srv = hs.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        ctx = browser.new_context(viewport={"width": 390, "height": 790}, device_scale_factor=3, is_mobile=True, has_touch=True, user_agent=UA)
        ctx.add_init_script("Object.defineProperty(screen,'height',{get:()=>844,configurable:true});")
        page = ctx.new_page()
        page.goto("http://127.0.0.1:%d/home.html" % srv.server_address[1])
        page.wait_for_function("document.querySelector('#sk-frame')", timeout=30000)
        page.wait_for_timeout(900)
        r = page.evaluate("""() => { const f = document.getElementById('sk-frame'), rb = f.querySelector('b').getBoundingClientRect(), b = getComputedStyle(document.documentElement, '::before');
          return {kids: f.children.length, top: rb.top, w: rb.width, vw: innerWidth, pos: b.position, bg: b.backgroundColor, bi: b.backgroundImage, h: parseFloat(b.height), z: b.zIndex}; }""")
        assert r["kids"] == 1 and abs(r["top"] - 54) < 1.5 and abs(r["w"] - 0.88 * r["vw"]) < 2, r                      # (Art option D: no frame, a plain rule under the HOME tab)
        assert r["pos"] == "fixed" and (r["bg"] in ("rgb(0, 0, 0)", "rgba(0, 0, 0, 1)") or "linear-gradient" in r["bi"]) and r["h"] >= 104 and int(r["z"]) < 300, r   # (solid black under the top row; 1.9.220 draws it as a black gradient that fades in the last 12 px, kept)
    finally:
        srv.shutdown()


@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
def test_a_sideways_phone_home_has_two_wide_columns_and_clear_side_gutters(browser, origin, style):
    """Luke 2026-11-12: sideways, Home's buttons stand in side gutters and the tiles stay wide (2 columns, 230 px or more), in every style."""
    html = _home_page() if style != "classic" else _home_page().split("<script>var x=document.createElement")[0] + "</body></html>"
    if style == "holo":
        src = [("/%s/%s" % (f, n)) for f, n, _t in palace_assets.assets() if f == "holo"][0]
        html = html.replace(_retro_src(), src).replace("_altoRetro", "_altoHolo")
    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            p = self.path.partition("?")[0]
            hit = ("text/html", html) if p == "/home.html" else (("text/javascript", "") if p == "/alto-cloud.js" else palace_assets.find(p))
            body = (hit[1] if hit else "no").encode("utf-8")
            self.send_response(200 if hit else 404)
            self.send_header("Content-Type", hit[0] if hit else "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        ctx = browser.new_context(viewport={"width": 874, "height": 292}, device_scale_factor=2, is_mobile=True, has_touch=True, user_agent=UA)
        page = ctx.new_page()
        page.goto("http://127.0.0.1:%d/home.html" % srv.server_address[1])
        if style != "classic":
            page.wait_for_function("document.documentElement.classList.contains('alto-%s')" % style, timeout=30000)
        page.wait_for_timeout(1500)
        r = page.evaluate("""() => { const t = [].slice.call(document.querySelectorAll('.course-tile:not(.new-tile)')).map(e => e.getBoundingClientRect()), s = document.querySelector('.project-slab').getBoundingClientRect();
          return {n: t.length, w: Math.min.apply(null, t.map(r => r.width)), cols: new Set(t.map(r => Math.round(r.left))).size, sl: s.left, sr: s.right, vw: innerWidth}; }""")
        assert r["n"] >= 2 and r["w"] >= 230 and r["cols"] == 2, r
        assert r["sl"] >= 90 and r["vw"] - r["sr"] >= 100, r                         # (the slab stands clear of the left buttons and the right buttons)
    finally:
        srv.shutdown()


def test_the_lanes_unit_chip_wraps_instead_of_running_on(browser, origin):
    page = _open(browser, origin, "classic", (390, 844), path="/lanes")
    page.wait_for_timeout(1500)
    r = page.evaluate("() => [].map.call(document.querySelectorAll('#world .lu-chip'), e => getComputedStyle(e).whiteSpace)")
    assert r and all(w == "normal" for w in r), r


@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
@pytest.mark.parametrize("size", [(390, 844), (844, 390)])
def test_a_long_unit_title_is_never_cut_on_a_one_card_phone_outline(browser, origin, style, size):
    """The card page's unit header (.node-unit, over each card; in the card when the chrome is in the way): wraps, no ellipsis, nothing clipped."""
    page = _open(browser, origin, style, size, path="/long", whole=False)
    page.wait_for_timeout(1200)
    r = page.evaluate("""() => [].map.call(document.querySelectorAll('#world .node-unit'), e => { const c = getComputedStyle(e);
      return {t: e.textContent.slice(0, 24), sw: e.scrollWidth, cw: e.clientWidth, sh: e.scrollHeight, ch: e.clientHeight, ws: c.whiteSpace, ell: c.textOverflow, fs: parseFloat(c.fontSize)}; })""")
    assert r
    for x in r:
        assert x["ws"] != "nowrap" and x["ell"] != "ellipsis" and x["sw"] <= x["cw"] + 1 and x["sh"] <= x["ch"] + 1 and x["fs"] >= 10, x


ATLAS_LONG_TITLE = "Civil Procedure, Evidence and the Federal Rules of Civil Procedure"


@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
def test_the_atlas_header_group_hangs_under_a_long_title_and_every_chip_shows_its_whole_text(browser, style):
    """#23, Sim 1107c / B6: on a phone's Atlas page the Tour / country / zoom group sat ON the title and the wordmark (Holo read "NITED STATES", the Tour chip empty).
    390x844, a long timeline title and a long country (Congo). The group is under the title bar, inside the screen, its chips hold their text, and the Tour label is not
    drawn in the page's own ground colour."""
    from tests.test_world_palace import built
    html = built(world={"country": "COD"}, title=ATLAS_LONG_TITLE)[0]

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            path = self.path.partition("?")[0]
            hit = ("text/html", html) if path in ("/", "/index.html") else (("text/javascript", "") if path == "/alto-cloud.js" else palace_assets.find(path))
            body = (hit[1] if hit else "no").encode("utf-8")
            self.send_response(200 if hit else 404)
            self.send_header("Content-Type", hit[0] if hit else "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        ctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=3, has_touch=True)
        page = ctx.new_page()
        page.goto("http://127.0.0.1:%d/index.html" % srv.server_address[1])
        page.wait_for_function("window.AltoWorld && document.querySelector('#wpal-root')", timeout=30000)
        if style != "classic":
            src = [("/%s/%s" % (f, n)) for f, n, _t in palace_assets.assets() if f == style][0]
            page.evaluate("src => new Promise(r => { var x = document.createElement('script'); x.src = src; x.onload = r; document.head.appendChild(x); })", src)
            page.wait_for_timeout(500)
            page.evaluate("window._alto%s && window._alto%s.on()" % (style.capitalize(), style.capitalize()))
        page.wait_for_timeout(2500)
        r = page.evaluate("""() => { const R = e => e.getBoundingClientRect(), ctl = document.querySelector('#wpal-root .wp-ctl'), tb = document.getElementById('title-bar'),
            c = R(ctl), probe = document.createElement('i'); document.body.appendChild(probe); probe.style.color = 'var(--ho-bg)';
          const tt = ctl.querySelector('.wp-tt'), ground = getComputedStyle(probe).color;
          return {c: [c.left, c.top, c.right, c.bottom], tbBottom: R(tb).bottom, vw: innerWidth,
            btns: [].map.call(ctl.querySelectorAll('.wp-btn'), b => ({t: b.textContent.trim().slice(0, 30), sw: b.scrollWidth, cw: b.clientWidth, l: R(b).left, r: R(b).right, t0: R(b).top, b0: R(b).bottom})),
            ttColor: getComputedStyle(tt).color, ground, ctlBg: getComputedStyle(ctl).backgroundColor}; }""")
        assert r["c"][1] >= r["tbBottom"] - 0.5 and r["c"][0] >= 0 and r["c"][2] <= r["vw"], r                 # (under the title bar, inside the screen)
        for b in r["btns"]:
            assert b["sw"] <= b["cw"] + 1 and b["l"] >= r["c"][0] - 0.5 and b["r"] <= r["c"][2] + 0.5 and b["t0"] >= r["c"][1] - 0.5 and b["b0"] <= r["c"][3] + 0.5, b   # (text whole, chip inside its group)
        assert style != "holo" or r["ttColor"] != r["ground"], r                                              # (the Tour label is not the ground's own colour)
    finally:
        srv.shutdown()


WORDS = """() => { const bad = [], fs = [];
  document.querySelectorAll('#world .node:not(.focused) .node-title').forEach(e => { if (!e.offsetHeight) return; fs.push(parseFloat(getComputedStyle(e).fontSize));
    const w = document.createTreeWalker(e, NodeFilter.SHOW_TEXT); let t;
    while ((t = w.nextNode())) { const re = /[^\\s\\u2010-\\u2014-]+/g; let m; while ((m = re.exec(t.data))) { const r = document.createRange(); r.setStart(t, m.index); r.setEnd(t, m.index + m[0].length);
      if (r.getClientRects().length > 1) bad.push(m[0]); } } });
  return {bad, min: Math.min.apply(null, fs), n: fs.length}; }"""


@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
@pytest.mark.parametrize("size", [(390, 844), (844, 390)])
def test_whole_view_card_titles_break_only_at_spaces_never_inside_a_word(browser, origin, style, size):
    """Luke 2026-11-06/07 (Sim 1107d: REVOCATIO N, OPTION CONTRACT S): Safari does not hyphenate capitals, so a word wider than its card used to split letters. Hyphenation is switched off here
    (what Safari does to capitals) and a narrow card (the engine's own width cut) is forced: the type shrinks to fit, never below 10.5 px, and no word spans two lines."""
    page = _open(browser, origin, style, size, path="/long")
    page.add_style_tag(content="#world .node-title{hyphens:none !important;-webkit-hyphens:none !important;} #world .node-card{width:96px !important;}")
    page.evaluate("window._altoPhone.chips()")
    page.wait_for_timeout(600)
    r = page.evaluate(WORDS)
    assert r["n"] > 5 and r["bad"] == [], r
    assert r["min"] >= 10.5, r
    assert page.evaluate("[...document.querySelectorAll('#world .node:not(.focused) .node-title')].some(e => e.offsetHeight && e.getAttribute('style') && e.getAttribute('style').includes('--ph-t'))"), "nothing needed shrinking: the test card is not narrow enough"


HEAD = """() => { const R = s => { const e = document.querySelector(s); if (!e) return null; const r = e.getBoundingClientRect(); return r.height ? {l: r.left, t: r.top, r: r.right, b: r.bottom} : null; };
  const cards = [].map.call(document.querySelectorAll('#world .node-card'), e => e.getBoundingClientRect()).filter(r => r.height > 0).sort((a, b) => a.top - b.top);
  return {vw: innerWidth, rule: R('#summary-wrap'), chip: R('#world .phase-label-float'), card: cards[0] ? {t: cards[0].top, b: cards[0].bottom} : null, scroll: document.getElementById('canvas').scrollTop}; }"""


@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
def test_turning_the_phone_lays_the_first_unit_out_again_under_the_header_rule(browser, origin, style):
    """Sim 1107d S2: portrait -> landscape kept the portrait offsets and scroll, so the first unit chip sat in the header band (over the clef and the Alto wordmark) and the rule cut the first card.
    After a turn (either way) the chip and the first card start under the rule and the chip is on the screen."""
    for first, second in (((390, 844), (844, 390)), ((844, 390), (390, 844))):
        page = _open(browser, origin, style, first, path="/long")
        page.wait_for_timeout(800)
        page.set_viewport_size({"width": second[0], "height": second[1]})
        page.wait_for_timeout(2500)
        r = page.evaluate(HEAD)
        assert r["chip"] and r["rule"], r
        assert r["chip"]["t"] >= r["rule"]["b"] - 1, r                                       # (the chip is under the header band: nothing of it by the clef or the wordmark)
        assert r["card"]["t"] >= r["rule"]["b"] - 1, r                                       # (the rule does not cut the first card)
        assert r["chip"]["l"] >= -1 and r["chip"]["r"] <= r["vw"] + 1, r
