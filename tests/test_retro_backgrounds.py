"""Retro's own backgrounds, the Art Deco scenes (alto/build/retro_backgrounds.py; Luke 2026-11-27 replaced "Green Light"): offered only in
Retro and never on a System, kept per timeline, hosted (the page grows by nothing), and every part of them low enough inside the content band
that Retro's gold and cream text keep WCAG AA (4.5:1), with the gilt frame 20 px off the window's edge."""
import json
import http.server
import socketserver
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import backgrounds_import as bi, holo, retro, retro_backgrounds as rb   # noqa: E402
from alto.build.builder import build_timeline, load_brief       # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None

GOLD, CREAM = "#d9ae55", "#efe6cf"        # Retro's text tokens (retro.py COMMON_CSS)


@pytest.fixture(scope="module")
def outline():
    d = json.loads((ROOT / "samples" / "outline_brief.json").read_text(encoding="utf-8"))
    brief, nodes, conns = load_brief(d)
    return build_timeline(brief, nodes, conns)[0]


IDS = list(rb.SCENES)
FIRST = IDS[0]
NAMES = {"r-deco-setback": "Setback", "r-deco-portal": "Portal"}


def test_the_deco_scenes_group_retro_kind_h_light_and_dark_alike_and_green_light_is_gone():
    e = rb.client_entries()
    assert FIRST == "r-deco-setback" and set(IDS) <= set(NAMES) and "r-" + "green-light" not in e
    for k, v in e.items():
        assert v["g"] == "Retro" and v["k"] == "h" and v["n"] == NAMES[k] and v["l"] == v["d"]
        assert f"var({rb.SCENES[k]['var']})" in v["l"]["b"] and "linear-gradient" in v["l"]["b"]


def test_the_art_is_small_flat_and_original_vector():
    import gzip
    for k in IDS:
        for fr in rb.FRAMINGS:
            svg = rb.svg(k, fr)
            assert len(gzip.compress(svg.encode(), 9)) < 15 * 1024
            assert "<image" not in svg and "http://" not in svg.replace("http://www.w3.org/2000/svg", "")


def test_the_scenes_ride_in_the_hosted_script_not_the_page(outline):
    for k, v in rb.SCENES.items():
        assert k in retro.ASSET and v["var"] in retro.ASSET
        assert k not in outline and v["var"] not in outline
    assert "--rt-gl" not in retro.ASSET


def test_the_sheet_paints_the_chosen_ground_through_retros_layer():
    css = retro.css()
    assert "alto-bg-h #page-bg" in css and all(v["var"] in css for v in rb.SCENES.values())


@pytest.fixture(scope="module")
def site(outline, tmp_path_factory):
    if pw is None:
        pytest.skip("Playwright is not installed")
    d = tmp_path_factory.mktemp("rbsite")
    (d / "t.html").write_text(outline, encoding="utf-8")
    (d / "retro").mkdir()
    name, text = retro.retro_asset()
    (d / "retro" / name).write_text(text, encoding="utf-8")
    lib, js = bi.site_file()
    (d / lib).write_text(js, encoding="utf-8")
    holo_name, holo_text = holo.holo_asset()
    (d / "holo").mkdir()
    (d / "holo" / holo_name).write_text(holo_text, encoding="utf-8")

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


_MEASURE = """async (args) => {
  const [svg, x0, y0, x1, y1, W, H, lx, ly, ex] = args;
  const img = new Image(); img.src = 'data:image/svg+xml,' + encodeURIComponent(svg);
  await img.decode();
  const c = document.createElement('canvas'); c.width = W; c.height = H; const g = c.getContext('2d'); g.drawImage(img, 0, 0, W, H);
  const d = g.getImageData(0, 0, W, H).data; let worst = 0, at = null;
  const f = v => { v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); };
  for (let y = y0; y < y1; y += 2) for (let x = x0; x < x1; x += 2) {
    if (Math.hypot(x - lx, y - ly) < ex) continue;
    const i = (y * W + x) * 4, L = .2126 * f(d[i]) + .7152 * f(d[i + 1]) + .0722 * f(d[i + 2]);
    if (L > worst) { worst = L; at = [x, y]; }
  }
  return [worst, at];
}"""


def _ratio(hexcol, lum):
    c = [int(hexcol[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    l = 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    return (max(l, lum) + .05) / (min(l, lum) + .05)


BANDS = {"land": (140, 150, 1300, 800), "port": (16, 90, 374, 844), "short": (16, 40, 828, 390)}   # where cards and text pass


@pytest.mark.parametrize("bg", IDS)
@pytest.mark.parametrize("fr", list(BANDS))
def test_the_art_keeps_gold_and_cream_text_at_aa_across_the_content_band(browser, fr, bg):
    (W, H), _, _ = rb.FRAMINGS[fr]
    pg = browser.new_page()
    worst, at = pg.evaluate(_MEASURE, [rb.svg(bg, fr), *BANDS[fr], W, H, -999, -999, 0])
    pg.close()
    assert _ratio(GOLD, worst) >= 4.5 and _ratio(CREAM, worst) >= 4.5, (worst, at)


@pytest.mark.parametrize("bg", IDS)
@pytest.mark.parametrize("fr", ["land", "port", "short"])
def test_the_gilt_frame_keeps_20px_off_the_window_edge(fr, bg):
    import re
    (W, H), _, _ = rb.FRAMINGS[fr]
    frame = [d for d in re.findall(r'<path d="([^"]+)" fill="none"', rb.svg(bg, fr)) if d.count("V") > 6 and d.endswith("Z")]
    assert len(frame) == 2
    xs = [float(n) for n in re.findall(r"[MHL](-?[\d.]+)", frame[0])]
    ys = [float(n) for n in re.findall(r"V(-?[\d.]+)", frame[0])]
    assert min(xs + ys) >= 20 and max(xs) <= W - 20 and max(ys) <= H - 20


def test_the_deco_scenes_are_offered_only_in_retro_kept_per_timeline_and_never_on_a_system(browser, site):
    ctx = browser.new_context(viewport={"width": 1400, "height": 900})
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(site + "/t.html")
    pg.wait_for_timeout(400)
    pg.evaluate("localStorage.clear()")
    heads = "[...document.querySelectorAll('#bg-panel .bg-h')].map(h => h.textContent)"
    cls = "document.documentElement.classList"
    pg.click("#bg-toggle")
    pg.wait_for_timeout(400)
    assert "Retro" not in pg.evaluate(heads)                              # Classic: not offered
    pg.evaluate("window._altoStyle.set('retro')")
    pg.wait_for_timeout(600)
    assert pg.evaluate(heads).count("Retro") == 1                         # Retro: its own section
    shown = "[...document.querySelectorAll('#bg-panel .bg-tile')].filter(t => t.offsetParent).map(t => t.dataset.bg)"
    assert not {"Colors", "Patterns"} & set(pg.evaluate("[...document.querySelectorAll('#bg-panel .bg-h')].filter(h => h.offsetParent).map(h => h.textContent)"))
    assert pg.evaluate(shown) == IDS + ["r:off"]               # Luke 2026-11-26: nothing of the normal picker is drawn (2026-11-27: but Plain is)
    pg.click(f'.bg-tile[data-bg="{FIRST}"]')
    pg.wait_for_timeout(400)
    assert pg.evaluate(cls + ".contains('alto-bg-h')")
    assert "data:image/svg+xml" in pg.evaluate("getComputedStyle(document.getElementById('page-bg'), '::before').backgroundImage")
    assert pg.evaluate("getComputedStyle(document.getElementById('page-bg'), '::before').display") != "none"
    pg.reload()                                                           # kept per timeline: the choice survives a reload
    pg.wait_for_timeout(1200)
    assert pg.evaluate(cls + ".contains('alto-bg-h')") and pg.evaluate("window._altoBgId") == FIRST
    pg.evaluate("window._altoStyle.set('classic')")                      # back in Classic: no background, no section; the choice is kept
    pg.wait_for_timeout(400)
    assert not pg.evaluate(cls + ".contains('alto-bg')") and "Retro" not in pg.evaluate(heads)
    pg.click("#bg-toggle") if not pg.evaluate("document.getElementById('bg-panel').classList.contains('open')") else None
    pg.wait_for_timeout(300)
    assert len(pg.evaluate(shown)) > 20                                   # the normal picker is back in Classic
    pg.evaluate("window._altoStyle.set('holo')")                          # Holographic never shows Retro's
    pg.wait_for_timeout(500)
    assert "Retro" not in pg.evaluate(heads) and not pg.evaluate(cls + ".contains('alto-bg-h')")
    pg.evaluate("window._altoStyle.set('classic')")
    pg.wait_for_timeout(300)
    pg.evaluate("document.documentElement.classList.add('alto-stars')")  # a System: Retro keeps its own ground there
    pg.evaluate("window._altoStyle.set('retro')")
    pg.wait_for_timeout(500)
    assert "Retro" not in pg.evaluate(heads) and not pg.evaluate(cls + ".contains('alto-bg-h')")
    assert not errors, errors
    ctx.close()


def test_retro_has_a_plain_choice_that_turns_its_ground_off_and_gives_classic_its_choice_back(browser, site):
    """Luke 2026-11-27: "you also forgot to make a way to turn off the one background in retro"."""
    ctx = browser.new_context(viewport={"width": 1400, "height": 900})
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(site + "/t.html")
    pg.wait_for_timeout(400)
    pg.evaluate("localStorage.clear()")
    cls = "document.documentElement.classList"
    act = "[...document.querySelectorAll('#bg-panel .bg-tile.active')].filter(t => t.offsetParent).map(t => t.dataset.bg)"
    col = pg.evaluate("Object.keys(window._altoBg.C).find(k => window._altoBg.C[k].g === 'Colors')")
    pg.evaluate("(id) => window._altoBg.choose(id)", col)                # a normal choice in Classic
    pg.wait_for_timeout(300)
    pg.evaluate("window._altoStyle.set('retro')")
    pg.wait_for_timeout(600)
    pg.click("#bg-toggle")
    pg.wait_for_timeout(400)
    assert pg.evaluate(act) == ["r:off"] and not pg.evaluate(cls + ".contains('alto-bg-h')")   # Retro draws it as Plain
    pg.click(f'.bg-tile[data-bg="{FIRST}"]')
    pg.wait_for_timeout(400)
    assert pg.evaluate(cls + ".contains('alto-bg-h')") and pg.evaluate(act) == [FIRST]
    pg.click('.bg-tile[data-bg="r:off"]')                                  # the way back
    pg.wait_for_timeout(400)
    assert not pg.evaluate(cls + ".contains('alto-bg-h')") and not pg.evaluate(cls + ".contains('alto-bg')")
    assert pg.evaluate(act) == ["r:off"]
    pg.reload()                                                            # kept per timeline
    pg.wait_for_timeout(1200)
    assert not pg.evaluate(cls + ".contains('alto-bg-h')")
    pg.evaluate("window._altoStyle.set('classic')")
    pg.wait_for_timeout(400)
    assert pg.evaluate("window._altoBgId") == col                          # Classic's own choice is back
    pg.evaluate("window._altoStyle.set('retro')")
    pg.wait_for_timeout(400)
    pg.evaluate("(id) => window._altoBg.choose(id)", FIRST)
    pg.evaluate("window._altoStyle.set('classic')")                       # a Retro ground chosen: Classic still draws its own
    pg.wait_for_timeout(400)
    assert pg.evaluate("window._altoBgId") == col
    assert not errors, errors
    ctx.close()


def test_a_page_that_chose_green_light_gets_the_first_deco_scene(browser, site):
    """Green Light is retired (Luke 2026-11-27); a timeline that had it chosen opens in Retro on the first Deco scene, not on nothing."""
    ctx = browser.new_context(viewport={"width": 1400, "height": 900})
    pg = ctx.new_page()
    pg.goto(site + "/t.html")
    pg.wait_for_timeout(400)
    pg.evaluate("localStorage.clear()")
    pg.evaluate("window._altoBg.choose('r-' + 'green-light')")
    pg.evaluate("window._altoStyle.set('retro')")
    pg.wait_for_timeout(600)
    assert pg.evaluate("window._altoBgId") == FIRST
    assert pg.evaluate("document.documentElement.classList.contains('alto-bg-h')")
    ctx.close()


UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"


@pytest.mark.parametrize("size", [(1440, 900), (390, 844), (844, 390)])
def test_the_ground_fills_the_window_exactly_so_the_frame_keeps_20px(browser, site, size):
    """A photograph's layer overhangs the window by 40 px (for its blur); a Deco ground's must not, or the gilt frame drawn 20 px in from
    the edge lands under or past it."""
    phone = size[0] < 900                       # a phone's page layer is taller than the window (80 px above it): the ground must not follow it
    kw = dict(device_scale_factor=2, is_mobile=True, has_touch=True, user_agent=UA) if phone and browser.browser_type.name == "webkit" else {}
    ctx = browser.new_context(viewport={"width": size[0], "height": size[1]}, **kw)
    pg = ctx.new_page()
    pg.goto(site + "/t.html")
    pg.wait_for_timeout(600)
    pg.evaluate("localStorage.clear()")
    pg.evaluate("window._altoStyle.set('retro')")
    pg.wait_for_timeout(500)
    pg.evaluate("(id) => window._altoBg.choose(id)", FIRST)
    pg.wait_for_timeout(400)
    s = pg.evaluate("""(() => { const s = getComputedStyle(document.getElementById('page-bg'), '::before'),
      z = parseFloat(getComputedStyle(document.documentElement).zoom) || 1;      // (a desk page is drawn zoomed: html carries the scale)
      return [s.position, s.left, s.top, Math.round(parseFloat(s.width) * z), Math.round(parseFloat(s.height) * z)]; })()""")
    assert s == ["fixed", "0px", "0px", size[0], size[1]], s
    ctx.close()
