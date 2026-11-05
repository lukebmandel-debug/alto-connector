"""Style C of the System format (Luke, 2026-11-05, option C of the star-chart-retire sheet): the bar keeps System | Star chart (the old 3D Star chart under the plainer
name); Retro and Holographic are the page's Style in the Scene panel and work in both modes, restyling the frame, labels and bars while the 3D bodies keep their own
light. Behind a flag (solar.STYLE_C, off; localStorage alto-style-c=1 turns it on, 0 off); nothing of the five-button bar is deleted. Saved charts migrate:
Star chart (flat) -> Star chart, Retro chart -> System in Retro, Holographic stays. No WebGL: the Star chart stays and draws the flat scene. Phone unchanged.
The browser parts are skipped when Playwright is not installed."""
import copy
import http.server
import shutil
import socketserver
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from alto.build import backgrounds as bg, backgrounds_import as bi, holo, retro, solar   # noqa: E402
import test_solar_draw as _sol                                                         # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None

IPHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
NOGL = ("(function(){var g=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(t){ if(/webgl/.test(t)) return null; "
        "return g.apply(this,arguments); };})()")
STYLE = "alto-hl-solar-draw-style"       # the page's own style key (backgrounds.py head script)


def test_the_flag_is_on_in_the_plan_and_off_when_cleared(monkeypatch):
    assert solar.STYLE_C is True and '"stylec":1' in _sol._page()
    monkeypatch.setattr(solar, "STYLE_C", False)
    assert '"stylec"' not in _sol._page()


def test_a_system_page_carries_the_style_switch_under_its_own_name_and_the_hosted_retro_hook():
    html = _sol._page()
    assert "_altoStyleC=" in html and "window._altoStyle=SO" in html, "the head script defines both names"
    assert html.count('"retro"') >= 1 and retro.PATH in html and holo.PATH in html


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    if pw is None:
        pytest.skip("Playwright is not installed")
    d = tmp_path_factory.mktemp("starchartc")
    (d / "system.html").write_text(_sol._page(), encoding="utf-8")
    shutil.copytree(ROOT / "alto" / "assets" / "backgrounds", d / "bg" / f"v{bg.BG_V}")
    (d / "holo").mkdir()
    (d / "retro").mkdir()
    n, t = holo.holo_asset()
    (d / "holo" / n).write_text(t, encoding="utf-8")
    n, t = retro.retro_asset()
    (d / "retro" / n).write_text(t, encoding="utf-8")
    lib, js = bi.site_file()
    (d / lib).write_text(js, encoding="utf-8")

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


@pytest.fixture(params=["webkit", "chromium"])
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


def _open(browser, site, ls=None, nogl=False, phone=False, wait=2200):
    ctx = browser.new_context(viewport={"width": 390 if phone else 1400, "height": 844 if phone else 860}, has_touch=phone, is_mobile=phone,
                              user_agent=IPHONE if phone else None)
    if nogl:
        ctx.add_init_script(NOGL)
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(site + "/system.html")
    pg.wait_for_timeout(250)
    pg.evaluate("localStorage.clear()")
    pg.evaluate("(o)=>{for(var k in o) localStorage.setItem(k,o[k]);}", ls or {})
    pg.reload()
    pg.wait_for_timeout(wait)
    return pg, ctx, errors


def _cls(pg):
    return set(pg.evaluate("[].slice.call(document.documentElement.classList)"))


def _bar(pg):
    return pg.evaluate("[].map.call(document.querySelectorAll('#sol-sty button'), function(b){ return b.textContent.trim()+(b.classList.contains('on')?'*':''); })")


def _real(errors):
    return [e for e in errors if "ResizeObserver" not in e]


ON = {"alto-style-c": "1"}
OFF = {"alto-style-c": "0"}      # the rollback: a viewer's localStorage (the plan's flag is solar.STYLE_C)


def test_rolled_back_the_bar_keeps_its_five_styles(browser, site):
    pg, ctx, errors = _open(browser, site, OFF)
    assert len(_bar(pg)) == 5 and "sk-real" not in _cls(pg) and not _real(errors)
    ctx.close()


def test_the_bar_is_system_and_star_chart_by_default_and_the_star_chart_is_the_3d_one(browser, site):
    pg, ctx, errors = _open(browser, site)
    assert _bar(pg) == ["System", "Star chart*"], _bar(pg)
    c = _cls(pg)
    assert {"alto-stars", "sk-real"} <= c and "sk-retro" not in c and "alto-retro" not in c and "alto-holo" not in c
    pg.click("#sol-sty button:first-child")
    pg.wait_for_timeout(600)
    assert _bar(pg) == ["System*", "Star chart"] and "alto-solar-hub" in _cls(pg) and "sk-real" not in _cls(pg)
    pg.click("#sol-sty button:last-child")
    pg.wait_for_timeout(900)
    assert "sk-real" in _cls(pg)
    assert not _real(errors), errors
    ctx.close()


def _scene_style(pg, name):
    pg.evaluate("document.getElementById('bg-toggle').click()")
    pg.wait_for_timeout(1200)
    labels = pg.evaluate("[].map.call(document.querySelectorAll('#bg-style .bg-segb'), function(b){ return b.textContent.trim(); })")
    pg.evaluate("(n)=>{ [].forEach.call(document.querySelectorAll('#bg-style .bg-segb'), function(b){ if(b.textContent.trim()===n) b.click(); }); }", name)
    pg.wait_for_timeout(1500)
    return labels


@pytest.mark.parametrize("look", ["stars", "hub"])
def test_scene_has_the_style_row_and_retro_and_holo_work_in_both_modes(browser, site, look):
    ls = dict(ON)
    ls["alto-solar-look:page"] = look
    pg, ctx, errors = _open(browser, site, ls)
    assert _scene_style(pg, "Retro") == ["Classic", "Retro", "Holographic"]
    c = _cls(pg)
    assert "alto-retro" in c and ("sk-real" in c) == (look == "stars") and "alto-holo" not in c
    assert pg.evaluate("localStorage.getItem(%r)" % STYLE) == "retro"
    if look == "stars":      # the frame is drawn round the 3D scene, the 3D scene is still there
        assert pg.evaluate("getComputedStyle(document.getElementById('sk-frame')).display") == "block"
        assert pg.evaluate("!!document.getElementById('sk3d')") and "sk-3d" in c
    _scene_style(pg, "Holographic")
    c = _cls(pg)
    assert "alto-holo" in c and "alto-retro" not in c and ("sk-real" in c) == (look == "stars")
    _scene_style(pg, "Classic")
    c = _cls(pg)
    assert "alto-holo" not in c and "alto-retro" not in c
    assert pg.evaluate("localStorage.getItem(%r)" % STYLE) == "classic"
    assert not _real(errors), errors
    ctx.close()


def test_a_saved_flat_star_chart_becomes_the_star_chart(browser, site):
    pg, ctx, errors = _open(browser, site, { "alto-solar-look:page": "stars", "alto-solar-style:page": "classic"})
    assert _bar(pg) == ["System", "Star chart*"] and "sk-real" in _cls(pg)
    assert pg.evaluate("localStorage.getItem('alto-solar-style:page')") == "real"
    ctx.close()


def test_a_saved_retro_chart_becomes_system_in_retro(browser, site):
    pg, ctx, errors = _open(browser, site, { "alto-solar-look:page": "stars", "alto-solar-style:page": "retro"})
    c = _cls(pg)
    assert _bar(pg) == ["System*", "Star chart"] and "alto-retro" in c and "alto-solar-hub" in c and "sk-retro" not in c and "sk-real" not in c
    assert pg.evaluate("localStorage.getItem(%r)" % STYLE) == "retro"
    assert pg.evaluate("localStorage.getItem('alto-solar-look:page')") == "hub"
    assert not _real(errors), errors
    ctx.close()


def test_a_saved_holographic_stays_holographic(browser, site):
    pg, ctx, errors = _open(browser, site, {STYLE: "holo", "alto-solar-look:page": "hub"})
    assert "alto-holo" in _cls(pg) and _bar(pg) == ["System*", "Star chart"]
    ctx.close()


def test_without_webgl_the_star_chart_stays_and_draws_the_flat_scene(browser, site):
    pg, ctx, errors = _open(browser, site, None, nogl=True)
    c = _cls(pg)
    assert _bar(pg) == ["System", "Star chart*"] and "sk-real" in c and "sk-3d" not in c and not pg.evaluate("!!document.getElementById('sk3d')")
    assert pg.evaluate("document.querySelectorAll('#world .node[data-solar]').length") > 3
    assert pg.evaluate("document.querySelectorAll('#world .node[data-solar] .sk-rot').length") > 0, "the flat scene's turning globes are drawn"
    _scene_style(pg, "Retro")        # and Retro still dresses it
    assert "alto-retro" in _cls(pg) and not _real(errors), errors
    ctx.close()


def test_a_phone_is_unchanged_with_the_flag_on(browser, site):
    pg, ctx, errors = _open(browser, site, None, phone=True)
    c = _cls(pg)
    assert "mobile" in c and not pg.evaluate("!!document.getElementById('sol-ctl')") and "sk-real" not in c and "sk-3d" not in c
    assert not _real(errors), errors
    ctx.close()


def test_holo_css_gives_the_star_chart_the_dark_tokens():
    css = holo.css()
    assert "html.alto-holo.alto-stars.sk-real" in css and "html.alto-holo.dark" in css


def test_retro_css_dresses_the_ship_tour_and_craft_popups_without_the_retro_charts_art():
    css = retro.FORMAT_CSS
    for want in ("#sol-craft-pop", ".nvo", "#nvo-map"):
        assert want in css
    assert ".sh-" not in css.split("the ship and craft popups")[1].split("\n  X.alto")[0]      # the ship art and flames stay on sk-retro


@pytest.mark.parametrize("style", ["Retro", "Holographic"])
def test_the_craft_and_nav_popups_wear_the_page_style(browser, site, style):
    pg, ctx, errors = _open(browser, site)
    _scene_style(pg, style)
    pg.evaluate("var c=document.getElementById('sol-craft'); if(c) c.click();")
    pg.wait_for_timeout(600)
    got = pg.evaluate("""()=>['#sol-craft-pop','.nvo'].map(function(s){ var e=document.querySelector(s); if(!e) return null; var c=getComputedStyle(e);
        return [c.borderTopLeftRadius, c.borderTopWidth, c.backgroundColor]; })""")
    assert got[0], "the craft popup opens"
    for g in got:
        if g:
            assert g[0] == "0px" and g[1] != "0px", got
    assert not _real(errors), errors
    ctx.close()
