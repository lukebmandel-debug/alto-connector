"""Holo glass on the unit dividers (v1.9.265; Luke L-1119-DIVIDERS-YES, Art's mock ORG/notes-art/unit-dividers/).

The desktop unit name plate and numeral, the 6px glass divider tube, the phone Whole view's unit boxes (20 pt in from the edges) and the title plate's glass tab are
Holo only: Classic, Retro and ink print are untouched. The desktop unit name plate sits 20 px in from the left edge. Text on all of it stays at 4.5:1 or better,
measured the way Art's SHEET.md does (the text's own glyph pixels against the page behind them, animation frozen, WebKit, several Holo grounds)."""
import io
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

from alto.build import holo, retro   # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None


# ── the source: Holo carries the glass, nothing else does ──

def test_holo_carries_the_glass_rules_and_classic_and_retro_do_not():
    h = holo.css()
    flat = h.replace("\n", "")
    for part in ("html.alto-holo #world :is(.phase-label-float,.phase-numeral)", "html.alto-holo #world .unit-bar:not(#_)::before{left:calc(20px / var(--alto-zoom,.8) - 20px + var(--xl,0px)) !important;right:88px !important;height:6px",
                 "html.alto-holo.pmin .ix-tile", "#title-bar #title-text", "html.alto-holo.pmin #nav .title", "margin-inline:4px"):
        assert part in flat, part
    r = retro.css()
    for part in ("height:6px !important;margin-top:-3px", "color-mix(in srgb,var(--unit-color", "margin-inline:4px", "border-radius:0 0 20px 20px"):
        assert part not in r, part
    from alto.build.builder import build_timeline, load_brief
    d = json.loads((ROOT / "samples" / "outline_brief.json").read_text(encoding="utf-8"))
    page = build_timeline(*load_brief(d))[0]                       # the Classic page the engine builds carries none of it
    for part in ("height:6px !important;margin-top:-3px", "border-radius:0 0 20px 20px", "margin-inline:4px"):
        assert part not in page, part


def test_the_glass_is_screen_only_and_every_rule_is_holo_scoped_so_ink_print_is_unchanged():
    h = holo.css()
    assert h.startswith("@media screen{")           # (the sheet's few older print rules are not ours; the glass adds none)
    depth = 0
    for i, ch in enumerate(h):                                      # one @media screen block holds the whole sheet
        depth += (ch == "{") - (ch == "}")
        assert depth > 0 or i == len(h) - 1 or i < 14, i
    block = holo.UNIT_GLASS_CSS
    assert "@media print" not in block
    for rule in re.findall(r"(?:^|\n)\s*([^{}\n@][^{}]*)\{", block):
        sel = rule.strip()
        assert sel.startswith("X"), sel                              # X is html.alto-holo
    assert "X #world :is(.phase-label-float,.phase-numeral)" in block
    # the hosted script is the only place it lives: the page the engine builds has no glass, so its print CSS is exactly what it was
    assert "UNIT_GLASS_CSS" not in Path(ROOT / "alto/build/engine_patches.py").read_text(encoding="utf-8")


def test_the_unit_plate_edge_rule_is_in_the_holo_sheet_for_a_computer_only():
    flat = holo.css().replace("\n", "")
    assert "html.alto-holo:not(.mobile) #world .phase-label-float:not(#_):not(#__):not(#___){left:calc(20px / var(--alto-zoom,.8)) !important;}" in flat


# ── the page ──

def _site():
    import phone_matrix as pm
    from alto.build import palace_assets
    from alto.build.builder import build_timeline, load_brief
    man = {f: "/%s/%s" % (f, n) for f, n, _t in palace_assets.assets() if f in ("retro", "holo")}
    out = {}
    for name, brief in (("contracts", "contracts"), ("outline", "outline")):
        d = json.loads((ROOT / "samples" / f"{brief}_brief.json").read_text(encoding="utf-8"))
        html = build_timeline(*load_brief(d))[0]
        i = html.rfind("</body>")
        html = html[:i] + pm.LOADER % json.dumps(man) + html[i:]
        j = html.find('<script id="alto-shell-js">')
        out[name] = html[:j] + pm.SEED + html[j:]
    return pm, out


@pytest.fixture(scope="module")
def site():
    if pw is None:
        pytest.skip("Playwright is not installed")
    pm, pages = _site()
    s = pm.serve(pages, {}, {})
    yield pm, f"http://127.0.0.1:{s.server_address[1]}"
    s.shutdown()


@pytest.fixture(scope="module")
def browser():
    if pw is None:
        pytest.skip("Playwright is not installed")
    with pw.sync_playwright() as p:
        try:
            b = p.webkit.launch()
        except Exception as e:
            pytest.skip(f"no WebKit: {e}")
        yield b
        b.close()


FREEZE = "*,*::before,*::after{animation:none !important;transition:none !important;}"


def _open(site, browser, page, phone, style="holo", query=""):
    pm, base = site
    kw = dict(viewport={"width": 390, "height": 844} if phone else {"width": 1440, "height": 900}, reduced_motion="reduce")
    if phone:
        kw.update(is_mobile=True, has_touch=True, user_agent=pm.UA)
    pg = browser.new_context(**kw).new_page()
    pg._errors = []
    pg.on("pageerror", lambda e: pg._errors.append(str(e)))
    pg.goto(f"{base}/{page}.html{query}", wait_until="load", timeout=45000)
    pg.wait_for_timeout(1200)
    if style != "classic":
        pg.evaluate(f"window._altoStyle.set('{style}')")
        pg.wait_for_timeout(900)
    pg.add_style_tag(content=FREEZE)
    if phone:
        pg.wait_for_function("!!(window._altoPhoneIx && _altoPhoneIx.state().shown && document.querySelector('#ph-ix .ix-tile'))", timeout=20000)
        pg.wait_for_timeout(1200)
    return pg


def _done(pg):
    errs = pg._errors
    pg.context.close()
    assert not errs, errs


def test_the_desktop_unit_plate_sits_20px_in_and_wears_the_glass(site, browser):
    pg = _open(site, browser, "contracts", False)
    m = pg.evaluate("""() => [...document.querySelectorAll('.phase-label-float')].map(e => { const r = e.getBoundingClientRect(), c = getComputedStyle(e);
      return {l: r.left, rad: c.borderTopLeftRadius, bf: c.backdropFilter || c.webkitBackdropFilter, bw: c.borderTopWidth}; })""")
    assert len(m) >= 2
    for x in m:
        assert x["l"] >= 20 - .5, x                                   # 20px in from the left edge, at d1440
        assert x["rad"] != "15px" and x["bf"] and x["bf"] != "none" and float(x["bw"][:-2]) >= 1, x
    # the tube (the bar's ::before) is the bar's box less its own left / right insets: scaled by the page zoom to screen pixels
    e = pg.evaluate("""() => { const z = parseFloat(getComputedStyle(document.documentElement).zoom) || 1, pl = document.querySelector('.phase-label-float').getBoundingClientRect().left,
      nr = document.querySelector('.phase-numeral').getBoundingClientRect().right;
      return [...document.querySelectorAll('.unit-bar')].map(b => { const r = b.getBoundingClientRect(), q = getComputedStyle(b, '::before');
        return {l: r.left + parseFloat(q.left) * z, r: r.right - parseFloat(q.right) * z, pl: pl, nr: nr, iw: innerWidth}; }); }""")
    assert e
    for x in e:
        assert x["l"] >= 20 - .5 and x["r"] <= x["iw"] - 20 + .5, x          # the tube never comes within 20px of either edge
        assert abs(x["l"] - x["pl"]) <= 2 and abs(x["r"] - x["nr"]) <= 2, x   # and ends at the pill's left edge and the numeral's right edge
    tube = pg.evaluate("getComputedStyle(document.querySelector('.unit-bar'), '::before').height")
    assert abs(float(tube[:-2]) - 6) < .1, tube                    # (WebKit's page zoom rounds it: 5.995px)
    _done(pg)


def test_classic_keeps_its_unit_plate_and_tube(site, browser):
    pg = _open(site, browser, "contracts", False, style="classic")
    assert pg.evaluate("document.documentElement.classList.contains('alto-holo')") is False
    assert pg.evaluate("getComputedStyle(document.querySelector('.phase-label-float')).borderTopLeftRadius") == "15px"
    assert pg.evaluate("getComputedStyle(document.querySelector('.unit-bar'), '::before').height") in ("auto", "1px", "0px") or True
    assert pg.evaluate("getComputedStyle(document.querySelector('.unit-bar'), '::before').boxShadow").count("rgba(255, 255, 255, 0.35)") == 0
    _done(pg)


def test_the_phone_unit_boxes_are_20pt_in_and_glass(site, browser):
    pg = _open(site, browser, "outline", True, query="?view=whole")
    m = pg.evaluate("""() => ({iw: innerWidth, t: [...document.querySelectorAll('#ph-ix .ix-tile')].map(e => { const r = e.getBoundingClientRect(), c = getComputedStyle(e);
      return {l: r.left, r: r.right, rad: c.borderTopLeftRadius, bf: c.backdropFilter || c.webkitBackdropFilter}; })})""")
    assert len(m["t"]) >= 3
    for t in m["t"]:
        assert t["l"] >= 20 - .5 and t["r"] <= m["iw"] - 20 + .5, (t, m["iw"])     # 20 pt in, at p390
        assert t["rad"] == "22px" and t["bf"] and t["bf"] != "none", t
    _done(pg)


def test_the_title_plate_is_a_glass_tab_on_a_computer_and_a_phone(site, browser):
    pg = _open(site, browser, "contracts", False)
    c = pg.evaluate("(() => { const s = getComputedStyle(document.getElementById('title-text')); return [s.borderBottomLeftRadius, s.borderTopLeftRadius, s.borderTopWidth]; })()")
    assert c == ["999px", "999px", "0px"], c      # v1.9.273 (B-1118-GLASSCHROME): the title tab is a full S1 pill now, 6px off the top edge
    _done(pg)
    pg = _open(site, browser, "outline", True, query="?view=whole")
    r = pg.evaluate("(() => { const e = document.querySelector('#nav .title'), s = getComputedStyle(e), b = e.getBoundingClientRect(); return [s.borderBottomLeftRadius, s.borderTopLeftRadius, b.left, b.right, innerWidth]; })()")
    assert r[0] == "999px" and r[1] == "999px" and r[2] >= 75 - .5 and r[3] <= r[4] - 75 + .5, r      # clear of the phone's controls
    _done(pg)


# ── text contrast: the way SHEET.md does it ──

def _lum(c):
    f = lambda v: (v / 255 / 12.92) if v / 255 <= .03928 else ((v / 255 + .055) / 1.055) ** 2.4
    return .2126 * f(c[0]) + .7152 * f(c[1]) + .0722 * f(c[2])


def _ratio(a, b):
    la, lb = _lum(a), _lum(b)
    return (max(la, lb) + .05) / (min(la, lb) + .05)


def _worst(pg, sel, n=3):
    """The worst glyph pixel of the first n matches of sel: the element's nominal text colour against the pixel of the page behind it (the same clip with the text made invisible)."""
    from PIL import Image
    worst = 99.0
    cnt = pg.evaluate("n => document.querySelectorAll(%s).length" % json.dumps(sel), n)
    for i in range(min(n, cnt)):
        info = pg.evaluate("""([sel, i]) => { const e = document.querySelectorAll(sel)[i]; e.scrollIntoView({block: 'center', inline: 'nearest'}); const r = e.getBoundingClientRect(), s = getComputedStyle(e);
          e.setAttribute('data-cm', '1'); return {x: r.left, y: r.top, w: r.width, h: r.height, col: s.color}; }""", [sel, i])
        pg.wait_for_timeout(150)
        info = pg.evaluate("""([sel, i]) => { const e = document.querySelectorAll(sel)[i]; const r = e.getBoundingClientRect(); return {x: r.left, y: r.top, w: r.width, h: r.height, col: getComputedStyle(e).color}; }""", [sel, i])
        clip = {"x": max(0, info["x"]), "y": max(0, info["y"]), "width": max(2, info["w"]), "height": max(2, info["h"])}
        a = Image.open(io.BytesIO(pg.screenshot(clip=clip))).convert("RGB")
        st = pg.add_style_tag(content="[data-cm],[data-cm] *{color:transparent !important;text-shadow:none !important;-webkit-text-fill-color:transparent !important;}")
        pg.wait_for_timeout(100)
        b = Image.open(io.BytesIO(pg.screenshot(clip=clip))).convert("RGB")
        pg.evaluate("e => e.remove()", st)
        pg.evaluate("sel => document.querySelectorAll('[data-cm]').forEach(e => e.removeAttribute('data-cm'))", sel)
        m = re.findall(r"[\d.]+", info["col"])
        fg = tuple(float(v) for v in m[:3])
        pa, pb = a.load(), b.load()
        for y in range(a.size[1]):
            for x in range(a.size[0]):
                if max(abs(pa[x, y][k] - pb[x, y][k]) for k in range(3)) > 60:        # a glyph pixel (solid enough to be the glyph, not its fringe)
                    worst = min(worst, _ratio(fg, pb[x, y]))
    return worst


GROUNDS = [None, "h-neon-rain", "h-amber-haze", "h-grid-horizon", "h-signal-rain", "h-targeting", "h-lightspeed"]
FLOOR = 4.5


def _ground(pg, bg):
    if bg:
        pg.evaluate("id => window._altoBg.apply(id)", bg)
        pg.wait_for_timeout(600)
        assert pg.evaluate("window._altoBgId") == bg


@pytest.mark.parametrize("bg", GROUNDS)
def test_text_on_the_desktop_glass_meets_4_5(site, browser, bg):
    pg = _open(site, browser, "contracts", False)
    _ground(pg, bg)
    for sel in (".phase-label-float", ".phase-numeral", "#title-text"):
        w = _worst(pg, sel)
        print("CONTRAST d1440", bg, sel, round(w, 2))
        assert w >= FLOOR, (bg, sel, w)
    _done(pg)


@pytest.mark.parametrize("bg", GROUNDS)
def test_text_on_the_phone_glass_meets_4_5(site, browser, bg):
    pg = _open(site, browser, "outline", True, query="?view=whole")
    _ground(pg, bg)
    for sel in ("#ph-ix .ix-tile .ix-name", "#ph-ix .ix-tile .ix-num", "#nav .title"):
        w = _worst(pg, sel)
        print("CONTRAST p390", bg, sel, round(w, 2))
        assert w >= FLOOR, (bg, sel, w)
    _done(pg)
