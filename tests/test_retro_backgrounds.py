"""Retro's own background, "Green Light" (alto/build/retro_backgrounds.py): offered only in Retro and never on a System, kept per
timeline, hosted (the page grows by nothing), and every part of it low enough that Retro's gold and cream text keep WCAG AA (4.5:1)."""
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


def test_one_entry_group_retro_kind_h_light_and_dark_alike():
    e = rb.client_entries()
    assert list(e) == ["r-green-light"]
    v = e["r-green-light"]
    assert v["g"] == "Retro" and v["k"] == "h" and v["n"] == "Green Light" and v["l"] == v["d"]
    assert "var(--rt-gl)" in v["l"]["b"]


def test_the_art_is_small_flat_and_original_vector():
    import gzip
    for svg in (rb.svg_landscape(), rb.svg_portrait()):
        assert len(gzip.compress(svg.encode(), 9)) < 15 * 1024
        assert "<image" not in svg and "http://" not in svg.replace("http://www.w3.org/2000/svg", "")


def test_the_scene_rides_in_the_hosted_script_not_the_page(outline):
    assert "r-green-light" in retro.ASSET and "--rt-gl" in retro.ASSET
    assert "r-green-light" not in outline and "Green Light" not in outline and "--rt-gl" not in outline


def test_the_sheet_paints_the_chosen_ground_through_retros_layer():
    css = retro.css()
    assert "alto-bg-h #page-bg" in css and "--rt-gl" in css


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


@pytest.mark.parametrize("land", [True, False])
def test_the_art_keeps_gold_and_cream_text_at_aa_across_the_content_band(browser, land):
    W, H = (1440, 900) if land else (390, 844)
    svg = rb.svg_landscape() if land else rb.svg_portrait()
    band = (140, 150, 1300, 800) if land else (16, 90, 374, 844)
    lx = round(W * .93) if land else 300
    ly = round(H * (.62 if land else .80)) - (16 if land else 10)
    pg = browser.new_page()
    worst, at = pg.evaluate(_MEASURE, [svg, *band, W, H, lx, ly, 18 if land else 9])
    pg.close()
    assert _ratio(GOLD, worst) >= 4.5 and _ratio(CREAM, worst) >= 4.5, (worst, at)


def test_on_the_phone_the_light_sits_well_clear_of_the_card_edge():
    # the card's right edge is 374 of 390; the light's halo (r 34) must end 20 px or more short of it
    assert 300 + 34 <= 374 - 20


def test_green_light_is_offered_only_in_retro_kept_per_timeline_and_never_on_a_system(browser, site):
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
    pg.click('.bg-tile[data-bg="r-green-light"]')
    pg.wait_for_timeout(400)
    assert pg.evaluate(cls + ".contains('alto-bg-h')")
    assert "data:image/svg+xml" in pg.evaluate("getComputedStyle(document.getElementById('page-bg'), '::before').backgroundImage")
    assert pg.evaluate("getComputedStyle(document.getElementById('page-bg'), '::before').display") != "none"
    pg.reload()                                                           # kept per timeline: the choice survives a reload
    pg.wait_for_timeout(1200)
    assert pg.evaluate(cls + ".contains('alto-bg-h')") and pg.evaluate("window._altoBgId") == "r-green-light"
    pg.evaluate("window._altoStyle.set('classic')")                      # back in Classic: no background, no section; the choice is kept
    pg.wait_for_timeout(400)
    assert not pg.evaluate(cls + ".contains('alto-bg')") and "Retro" not in pg.evaluate(heads)
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
