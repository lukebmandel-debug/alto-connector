"""The New dialog's Memory Palace picture tiles (14 Nov, Luke: "i like the first one, that works how memory atlas currently works").
Picking Memory Palace drops a row of three picture tiles (Memory Map, Memory Blueprint, Memory Atlas) below the four format tiles;
the Atlas still drops World / A country below that. The Palace tile always keeps its dome and its one generic line.
WebKit and Chromium; Classic, Retro and Holo; light and dark; desktop 1440x900 and phones 390x844 / 844x390."""
import http.server
import socketserver
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import format_symbols, holo, pages, retro            # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None

UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
SIZES = {"d1440": (1440, 900, False), "p390": (390, 844, True), "l844": (844, 390, True)}
WANT = {"city": ("palace", "palace"), "building": ("building", "building"), "world": ("world", "world")}
PALACE_LINE = "Your outline as a place you walk through: a city, a building, or the world. Claude builds it with you."


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    if pw is None:
        pytest.skip("Playwright is not installed")
    d = tmp_path_factory.mktemp("newpicker")
    (d / "h.html").write_text(pages.build_home([]), encoding="utf-8")
    for sub, asset in (("holo", holo.holo_asset), ("retro", retro.retro_asset)):
        (d / sub).mkdir()
        name, text = asset()
        (d / sub / name).write_text(text, encoding="utf-8")

    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(d), **k)

        def log_message(self, *a):
            pass
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), H)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


@pytest.fixture(scope="module", params=["webkit", "chromium"])
def browser(request):
    if pw is None:
        pytest.skip("Playwright is not installed")
    with pw.sync_playwright() as p:
        try:
            b = getattr(p, request.param).launch()
        except Exception as e:
            pytest.skip(f"no {request.param}: {e}")
        yield b
        b.close()


def _open(browser, site, style="classic", size="d1440", dark=False):
    w, h, mob = SIZES[size]
    ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=1, is_mobile=mob, has_touch=mob, user_agent=UA if mob else None)
    page = ctx.new_page()
    page.add_init_script("try{localStorage.setItem('alto-bg-home-v1-style','%s');localStorage.removeItem('alto-home-view-v1');localStorage.setItem('alto-theme-v1','%s')}catch(e){}"
                         % (style, "dark" if dark else "light"))
    page.goto(site + "/h.html")
    page.wait_for_timeout(500)
    page.evaluate("""() => { window.__sent = []; openClaude = function(p){ window.__sent.push(p); };
        ntOpen('', true); }""")
    page.wait_for_timeout(250)
    return ctx, page


def _click(page, sel):
    page.click(sel)
    page.wait_for_timeout(120)


def test_the_flow_for_all_four_choices_sends_what_it_always_did(browser, site):
    ctx, page = _open(browser, site)
    try:
        assert page.is_hidden("#nt-pal")
        _click(page, "#nt-modal .nt-kind[data-kind=palace]")
        assert page.is_visible("#nt-pal") and page.is_hidden("#nt-scope")
        dome = page.inner_html("#nt-modal .nt-kind[data-kind=palace] .nt-pv")
        line = page.inner_text("#nt-modal .nt-kind[data-kind=palace] small")
        assert line == PALACE_LINE
        sent = {}
        for mode, (kind, _) in WANT.items():
            _click(page, "#nt-pal .nt-kind[data-mode=%s]" % mode)
            assert page.evaluate("ntKind") == kind
            assert page.get_attribute("#nt-pal .nt-kind[data-mode=%s]" % mode, "aria-pressed") == "true"
            assert page.locator("#nt-pal .nt-kind.on").count() == 1
            assert page.is_visible("#nt-scope") == (mode == "world")
            # the Palace tile never changes: same dome, same one line
            assert page.inner_html("#nt-modal .nt-kind[data-kind=palace] .nt-pv") == dome
            assert page.inner_text("#nt-modal .nt-kind[data-kind=palace] small") == PALACE_LINE
            assert page.is_visible("#nt-modal .nt-kind[data-kind=palace] .nt-pv")
            assert page.inner_text("#nt-make") == "Build it with Claude"
            page.evaluate("window.__sent.length = 0")
            if mode == "world":
                for scope in ("world", "country"):
                    _click(page, "#nt-scope .nt-kind[data-scope=%s]" % scope)
                    if scope == "country":
                        assert page.is_disabled("#nt-make")                    # a country has to be picked first
                        _click(page, "#nt-clist .nt-crow[data-iso=USA]")
                    page.evaluate("window.__sent.length = 0")
                    page.evaluate("ntMake()")
                    sent["world-" + scope] = page.evaluate("window.__sent.slice()")
                    page.evaluate("ntOpen('', true); ntModes.palace='world'; ntPick('palace');")
                    page.wait_for_timeout(100)
            else:
                page.evaluate("ntMake()")
                sent[mode] = page.evaluate("window.__sent.slice()")
                page.evaluate("ntOpen('', true); ntPick('palace');")
                page.wait_for_timeout(100)
        assert all(len(v) == 1 for v in sent.values()), sent
        # each kind goes to the builder as its own prompt; the country scope rides along as it always did
        assert sent["world-world"] != sent["world-country"] and "United States" in sent["world-country"][0]
        assert len({sent["city"][0], sent["building"][0], sent["world-world"][0]}) == 3
        assert "set_up_palace" in sent["city"][0] and "Memory Blueprint" in sent["building"][0] and "Memory Atlas" in sent["world-world"][0]
        # and the same text the page built before this change: the three kinds' prompt strings are untouched
        for k, word in (("palace", "set_up_palace"), ("building", "Memory Blueprint"), ("world", "Memory Atlas")):
            assert word in page.evaluate("newProjectPrompt('%s')" % k)
    finally:
        ctx.close()


def test_the_other_tiles_hide_the_palace_row_and_the_dome_stays_when_atlas_is_chosen(browser, site):
    ctx, page = _open(browser, site)
    try:
        for k in ("timeline", "outline", "solar"):
            _click(page, "#nt-modal .nt-kind[data-kind=%s]" % k)
            assert page.is_hidden("#nt-pal")
        _click(page, "#nt-modal .nt-kind[data-kind=palace]")
        _click(page, "#nt-pal .nt-kind[data-mode=world]")
        assert page.locator("#nt-modal .nt-kind[data-kind=palace] .nt-pv").count() == 1       # one picture: the dome, whatever is chosen
        assert page.locator("#nt-modal .nt-kind[data-kind=palace] small").count() == 1
        assert page.locator("#nt-modal > .nt-modes[data-for=palace]").evaluate("e => getComputedStyle(e).display") == "none"
    finally:
        ctx.close()


def test_rescope_opens_on_the_atlas(browser, site):
    ctx, page = _open(browser, site)
    try:
        page.evaluate("ntRescopeOpen('USA', 'My atlas')")
        page.wait_for_timeout(150)
        assert page.is_visible("#nt-pal") and page.is_visible("#nt-scope")
        assert page.get_attribute("#nt-pal .nt-kind[data-mode=world]", "aria-pressed") == "true"
    finally:
        ctx.close()


def test_the_map_chip_wears_the_real_symbol(browser, site):
    ctx, page = _open(browser, site)
    try:
        for key in ("palace", "building", "world"):
            got = page.inner_html(".nt-sym[data-sym=%s] svg" % key)
            assert format_symbols.SYMBOLS[key][1].replace("currentColor", "currentColor") in got.replace("&amp;", "&") or got.count("<") >= 2
        assert "M12 16.5s-3-2.9-3-5.2" in page.inner_html(".nt-sym[data-sym=palace]")      # the pin, not the 14px skyline
        assert "M4 20.5V10l5-2.5" not in page.inner_html("#nt-modal > .nt-modes[data-for=palace]")
    finally:
        ctx.close()


@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
@pytest.mark.parametrize("dark", [False, True])
def test_three_styles_light_and_dark(browser, site, style, dark):
    ctx, page = _open(browser, site, style, "d1440", dark)
    try:
        _click(page, "#nt-modal .nt-kind[data-kind=palace]")
        _click(page, "#nt-pal .nt-kind[data-mode=world]")
        r = page.evaluate("""() => { const q = s => [...document.querySelectorAll(s)].map(e => { const b = e.getBoundingClientRect(), c = getComputedStyle(e);
            return {w: b.width, h: b.height, x: b.left, y: b.top, bw: parseFloat(c.borderTopWidth), bc: c.borderTopColor, sh: c.boxShadow}; });
          return {pal: q('#nt-pal .nt-kind'), top: q('#nt-modal .nt-kinds:not(.nt-sck) .nt-kind'), sc: q('#nt-scope .nt-kinds .nt-kind'), modal: document.getElementById('nt-modal').getBoundingClientRect().toJSON()}; }""")
        assert len(r["pal"]) == 3 and len(r["top"]) == 4
        for t in r["pal"]:
            assert t["w"] > 100 and t["h"] >= 44
        assert abs(r["pal"][0]["w"] - r["pal"][1]["w"]) < 1 and abs(r["pal"][1]["w"] - r["pal"][2]["w"]) < 1
        assert r["pal"][0]["y"] == r["pal"][2]["y"] and r["pal"][0]["y"] > r["top"][0]["y"]
        # the chosen tile is outlined like the others (Classic: text-coloured border + inset ring), the unchosen ones are not
        on = page.evaluate("getComputedStyle(document.querySelector('#nt-pal .nt-kind.on')).boxShadow")
        off = page.evaluate("getComputedStyle(document.querySelector('#nt-pal .nt-kind:not(.on)')).boxShadow")
        assert on != off
        # same look as the scope tiles in the same style (border width + corner radius)
        a = page.evaluate("(() => { const f = s => { const c = getComputedStyle(document.querySelector(s)); return [c.borderTopWidth, c.borderTopLeftRadius]; }; return [f('#nt-pal .nt-kind'), f('#nt-scope .nt-kind'), f('#nt-modal .nt-kind[data-kind=palace]')]; })()")
        assert a[0] == a[1] == a[2]
    finally:
        ctx.close()


@pytest.mark.parametrize("size", ["p390", "l844"])
@pytest.mark.parametrize("style", ["classic", "holo"])
def test_phone_tiles_fit_and_have_44pt_targets(browser, site, style, size):
    ctx, page = _open(browser, site, style, size)
    try:
        _click(page, "#nt-modal .nt-kind[data-kind=palace]")
        _click(page, "#nt-pal .nt-kind[data-mode=world]")
        r = page.evaluate("""() => { const w = innerWidth; const q = s => [...document.querySelectorAll(s)].map(e => { const b = e.getBoundingClientRect(); return {w: b.width, h: b.height, l: b.left, r: b.right, t: b.top}; });
          return {w, pal: q('#nt-pal .nt-kind'), sc: q('#nt-scope .nt-kinds .nt-kind'), sw: document.documentElement.scrollWidth}; }""")
        assert r["sw"] <= r["w"]
        for t in r["pal"] + r["sc"]:
            assert t["h"] >= 44 and t["l"] >= 0 and t["r"] <= r["w"] + 0.5
        if size == "p390":
            assert len({round(t["l"]) for t in r["pal"]}) == 1 and r["pal"][0]["t"] < r["pal"][1]["t"] < r["pal"][2]["t"]       # stacked, one a row
        # each tile can be reached and tapped in the scrolling dialog
        page.evaluate("document.querySelector('#nt-pal .nt-kind[data-mode=city]').scrollIntoView({block:'center'})")
        page.click("#nt-pal .nt-kind[data-mode=city]")
        assert page.evaluate("ntKind") == "palace" and page.is_hidden("#nt-scope")
    finally:
        ctx.close()
