"""The Memory Atlas's country flags (Luke, 2026-11-04: "please have country flags pop up with nodes. In holo style, it should be animated like the
file-type glyphs"): the enlarged card shows the flag of the country its node sits in, a hosted SVG (world_flags.py) fetched when the card opens and never
carried by the page; Classic a plain still flag, Retro a square gold-rimmed one, Holographic turns on Y like the format symbols (still under reduced motion,
paused while the tab is hidden); Antarctica and the disputed areas get a neutral pennant, never a wrong flag.

The data tests need no browser. The browser tests skip without Playwright and are served from 127.0.0.1 like test_atlas_holo_nodes.py (a WebKit
page.close() can hang at teardown, so a page is never closed on its own and the browser's own close is given 15 s by an alarm)."""
import http.server
import json
import re
import signal
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import palace_assets, palace_world, world_flags, world_plan as wp  # noqa: E402
from alto.build.builder import build_timeline, load_brief  # noqa: E402
from alto.build.world_geo import gazetteer  # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None

PAGE_BYTES_BEFORE = 1454434          # the same sample page built without flags (measured on origin/main 789c58d0, whose page grew since defa53c3)


# ── the data ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_every_country_the_atlas_can_place_has_a_flag_or_the_neutral_pennant():
    ids = set(gazetteer()["countries"])
    man = world_flags.manifest()
    assert ids and set(man) | set(world_flags.NEUTRAL) == ids and not set(man) & set(world_flags.NEUTRAL)
    assert set(palace_world._countries()) <= set(man) | set(world_flags.NEUTRAL)      # (the picker's list)


def test_antarctica_and_the_disputed_areas_never_get_a_flag():
    man = world_flags.manifest()
    for iso in ("ATA", "CYN", "KAS", "SOL", "SAH", "ATC", "IOA", "HMD", "SHN"):
        assert iso not in man, iso
    assert "<svg" in world_flags.flags()["MLI"] and "ATA" not in world_flags.flags()


def test_a_flag_is_the_countrys_own():
    f = world_flags.flags()
    for iso, colour in (("USA", "#bd3d44"), ("MLI", "#009a00"), ("JPN", "#bc002d"), ("DEU", "#fc0"), ("BRA", "#229e45"), ("CAN", "#d52b1e"), ("FRA", "#000091")):
        assert 'fill="%s"' % colour in f[iso], iso
    shared = [v for v in {x: 1 for x in f.values()} if sum(1 for y in f.values() if y == v) > 1]     # (a territory that flies its state's flag)
    assert len(shared) <= 1


def test_the_hosted_files_exist_and_are_plain_images():
    names = {n for n, _ in world_flags.hosted()}
    assert len(names) == len(world_flags.flags()) and all(re.match(r"^flag-[A-Z]{3}-[0-9a-f]{10}\.svg$", n) for n in names)
    for iso, url in world_flags.manifest().items():
        ct, text = palace_assets.find(url)
        assert ct.startswith("image/svg+xml") and text.startswith("<svg") and len(text) > 100
        assert not re.search(r"<script|base64|<foreignObject|on\w+=", text), iso
    assert palace_assets.find("/world/flag-ATA-0123456789.svg") is None


def test_the_licence_is_noted():
    lic = (ROOT / "alto" / "assets" / "flags" / "LICENSE").read_text()
    assert lic.startswith("The MIT License") and "Panayiotis Lipiridis" in lic
    for p in ("NOTICE", "alto/assets/flags/NOTICE", "alto/legal/credits.md"):
        assert "flag-icons" in (ROOT / p).read_text(), p
    assert "assets/flags/*.gz" in (ROOT / "pyproject.toml").read_text()


def test_the_script_loads_one_flag_at_a_time_and_the_page_carries_none():
    html, _ = _page()
    assert not re.search(r"flag-[A-Z]{3}-[0-9a-f]{10}", html) and "wp-flag" not in html and "viewBox=\"0 0 640 480\"" not in html
    assert len(html.encode("utf-8")) <= PAGE_BYTES_BEFORE + 1000
    js = palace_world.WORLD_ASSET
    assert re.search(r'"flag": ?\{', js) and "/world/flag-MLI-" in js and js.count("viewBox=\"0 0 640 480\"") == 0   # (the manifest, not the drawings)
    assert palace_world.WORLD_PATH in html


# ── the page ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def _page():
    d = json.load(open(ROOT / "samples" / "outline_brief.json"))
    d["brief"].update({"mode": "palace", "palace_view": "world"})
    ids = [n["id"] for n in d["nodes"] if n.get("parent")][:3]        # (a unit's top card is its hub: no country of its own)
    d["brief"]["world"] = {"places": {ids[0]: wp.resolve("Mali"), ids[1]: wp.resolve("Antarctica"), ids[2]: wp.resolve("Peru")}}
    _page.ids = ids
    return build_timeline(*load_brief(d))[0], ids


@pytest.fixture(scope="module")
def origin():
    html, _ = _page()
    log = []

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            path = self.path.split("?")[0]
            log.append(path)
            hit = (("text/html", html) if path in ("/", "/index.html") else ("text/javascript", "") if path == "/alto-cloud.js" else palace_assets.find(path))
            body = (hit[1] if hit else "no").encode("utf-8")
            self.send_response(200 if hit else 404)
            self.send_header("Content-Type", hit[0] if hit else "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    srv.log = log
    yield f"http://127.0.0.1:{srv.server_address[1]}", log
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


PROBE = """() => { const q = s => document.querySelector(s), w = q('#wpal-root .wp-enl .wp-where .wp-flag'); if (!w) return null;
  const cs = e => e ? getComputedStyle(e) : null, a = w.querySelector('img.fl-a'), b = w.querySelector('img.fl-b'), sp = w.querySelector('.fl-spin'), sc = w.querySelector('.fl-s');
  return {none: w.classList.contains('none'), label: w.getAttribute('aria-label'), first: w.parentNode.firstChild === w, c: w.getAttribute('data-c'),
    loaded: a ? a.complete && a.naturalWidth > 0 : false, src: a && a.getAttribute('src'), radius: a ? cs(a).borderTopLeftRadius : null, shadow: a ? cs(a).boxShadow : null,
    anim: sp ? cs(sp).animationName : null, dur: sp ? cs(sp).animationDuration : null, state: sp ? cs(sp).animationPlayState : null, tf: sp ? cs(sp).transform : null,
    ghost: b ? cs(b).display : null, scan: sc ? cs(sc).display : null, w: w.getBoundingClientRect().width, h: w.getBoundingClientRect().height,
    pennant: w.querySelector('svg') ? cs(w.querySelector('svg')).stroke : null}; }"""


def _open(browser, base, style, idx, globe=False, size=(1400, 900), reduced=False, block=None):
    ctx = browser.new_context(viewport={"width": size[0], "height": size[1]}, has_touch=size[0] < 500, is_mobile=size[0] < 500,
                              reduced_motion="reduce" if reduced else "no-preference")
    if block:
        ctx.route(block, lambda route: route.fulfill(status=404, body="no"))
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(base + "/index.html")
    page.wait_for_function("window.AltoWorld && document.querySelector('#wpal-root .wp-pin')", timeout=30000)
    page.evaluate("document.documentElement.classList.add('dark')")
    page.evaluate("window._altoStyle.set(%r)" % style)
    page.wait_for_timeout(600)
    if globe:
        page.evaluate("AltoWorld.globe(true)")
    page.evaluate("AltoWorld.select(%r)" % _page.ids[idx])
    page.wait_for_function("document.querySelector('#wpal-root .wp-enl .wp-where')", timeout=15000)
    page.wait_for_timeout(1500)
    return page, errors


@pytest.mark.parametrize("globe", [False, True])
def test_holographic_flag_turns_like_the_format_symbols(browser, origin, globe):
    base, log = origin
    page, errors = _open(browser, base, "holo", 0, globe)
    r = page.evaluate(PROBE)
    assert not errors, errors
    assert r and not r["none"] and r["loaded"] and r["first"] and r["c"] == "MLI" and r["label"] == "Flag of Mali"
    assert r["anim"] == "wp-flag-spin" and r["dur"] == "10s" and r["state"] == "running"        # (the glyphs: rotateY, 10 s, linear, infinite)
    assert r["ghost"] == "block" and r["scan"] == "block" and r["radius"] == "0px" and "rgb" in r["shadow"]
    assert any(f.startswith("/world/flag-MLI-") for f in log) and not any(f.startswith("/world/flag-PER-") for f in log)       # only the one that was needed
    # paused while the tab is hidden, running again when it is back
    page.evaluate("Object.defineProperty(document,'hidden',{configurable:true,get:()=>true}); document.dispatchEvent(new Event('visibilitychange'))")
    assert page.evaluate(PROBE)["state"] == "paused"
    page.evaluate("Object.defineProperty(document,'hidden',{configurable:true,get:()=>false}); document.dispatchEvent(new Event('visibilitychange'))")
    assert page.evaluate(PROBE)["state"] == "running"


def test_holographic_flag_is_still_under_reduced_motion(browser, origin):
    page, errors = _open(browser, origin[0], "holo", 0, reduced=True)
    r = page.evaluate(PROBE)
    assert not errors and r["loaded"] and r["anim"] == "none" and r["tf"] not in (None, "none") and r["ghost"] == "none"


@pytest.mark.parametrize("globe", [False, True])
def test_retro_flag_is_square_and_still(browser, origin, globe):
    page, errors = _open(browser, origin[0], "retro", 0, globe)
    r = page.evaluate(PROBE)
    assert not errors and r["loaded"] and r["radius"] == "0px" and "217, 174, 85" in r["shadow"]
    assert r["anim"] == "none" and r["ghost"] == "none" and r["scan"] == "none"


@pytest.mark.parametrize("globe", [False, True])
def test_classic_flag_is_plain_and_still(browser, origin, globe):
    page, errors = _open(browser, origin[0], "classic", 0, globe)
    r = page.evaluate(PROBE)
    assert not errors and r["loaded"] and r["radius"] == "3px" and r["anim"] == "none" and r["ghost"] == "none" and r["first"]


@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
def test_antarctica_gets_the_neutral_pennant_never_a_flag(browser, origin, style):
    base, log = origin
    page, errors = _open(browser, base, style, 1)
    r = page.evaluate(PROBE)
    assert not errors and r["none"] and r["label"] == "No flag shown" and r["c"] == "ATA" and r["pennant"] not in (None, "none")
    assert page.evaluate("document.querySelectorAll('#wpal-root .wp-enl .wp-flag img').length") == 0
    assert not any("flag-ATA" in f for f in log)


def test_a_missing_hosted_file_falls_back_to_the_pennant(browser, origin):
    page, errors = _open(browser, origin[0], "classic", 2, block="**/world/flag-PER-*")        # Peru, its flag file refused
    r = page.evaluate(PROBE)
    assert not errors and r and r["none"] and r["c"] == "PER" and r["label"] == "No flag shown"


def test_the_flag_shows_on_a_phone_too(browser, origin):
    page, errors = _open(browser, origin[0], "classic", 0, size=(390, 844))
    r = page.evaluate(PROBE)
    assert not errors and r and r["loaded"] and r["w"] > 10 and r["h"] > 8
