"""Roman-numeral section labels (.phase-numeral) never fade: not in focus mode,
not while panning/zooming, in Chromium and WebKit. Skipped where no browser."""
import functools, http.server, json, socketserver, threading
from pathlib import Path
import pytest

pw = pytest.importorskip("playwright.sync_api")
from alto.build.builder import build_timeline, load_brief  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ENGINES = ["chromium", "webkit"]


@pytest.fixture(scope="module")
def url(tmp_path_factory):
    d = json.loads((ROOT / "samples" / "contracts_brief.json").read_text(encoding="utf-8"))
    root = tmp_path_factory.mktemp("roman")
    (root / "page.html").write_text(build_timeline(*load_brief(d))[0], encoding="utf-8")
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    h.log_message = lambda *a: None
    socketserver.TCPServer.allow_reuse_address = True
    srv = socketserver.TCPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/page.html"
    srv.shutdown()


OPS = """() => [...document.querySelectorAll('.phase-numeral')].map(e => +getComputedStyle(e).opacity)"""


@pytest.mark.parametrize("engine", ENGINES)
def test_numerals_stay_fully_visible(url, engine):
    with pw.sync_playwright() as p:
        try:
            try:
                b = getattr(p, engine).launch()
            except Exception:
                if engine != "chromium":
                    raise
                b = p.chromium.launch(channel="chrome")   # system Chrome when no bundled build
        except Exception as e:
            pytest.skip(f"no {engine}: {e}")
        pg = b.new_page(viewport={"width": 1400, "height": 900})
        pg.goto(url)
        pg.wait_for_timeout(1500)
        assert pg.evaluate(OPS) and all(o == 1 for o in pg.evaluate(OPS))
        pg.evaluate("document.getElementById('canvas').classList.add('focus-mode')")
        pg.wait_for_timeout(600)          # past the .3s transition
        assert all(o == 1 for o in pg.evaluate(OPS))
        pg.mouse.move(700, 450)
        for dy in (400, -250, 900):
            pg.mouse.wheel(0, dy)
            pg.wait_for_timeout(500)
            assert all(o == 1 for o in pg.evaluate(OPS))
        b.close()


NUM = """() => { const e = document.querySelector('.phase-numeral'), r = e.getBoundingClientRect(),
  c = document.getElementById('canvas').getBoundingClientRect(), s = getComputedStyle(e), o = [];
  for (let n = e; n; n = n.parentElement) o.push(+getComputedStyle(n).opacity);
  return {right: r.right, edge: c.right, bg: s.backgroundColor, ops: o}; }"""


@pytest.mark.parametrize("cls", ["alto-bg", "alto-bg alto-retro"])
@pytest.mark.parametrize("engine", ENGINES)
def test_unit_numeral_solid_and_on_screen_over_a_background(url, engine, cls):
    """With a wallpaper chosen (and in Retro) the unit-bar numeral keeps full opacity all the way up
    its parents, a non-translucent backing, and stays inside the window even when the board is wider."""
    with pw.sync_playwright() as p:
        try:
            try:
                b = getattr(p, engine).launch()
            except Exception:
                if engine != "chromium":
                    raise
                b = p.chromium.launch(channel="chrome")
        except Exception as e:
            pytest.skip(f"no {engine}: {e}")
        pg = b.new_page(viewport={"width": 1000, "height": 800})
        pg.goto(url)
        pg.wait_for_timeout(1500)
        pg.evaluate("c => document.documentElement.classList.add(...c.split(' '))", cls)
        pg.wait_for_timeout(1200)          # past the keep-on-screen tick
        d = pg.evaluate(NUM)
        assert all(o == 1 for o in d["ops"]), d
        assert d["bg"] != "rgba(0, 0, 0, 0)" and not d["bg"].endswith("0.35)"), d
        assert d["right"] <= d["edge"] + 1, d
        b.close()
