"""The edit toggle is Claude star | Bass | pencil (Board B-1117-TOGGLE, approved B-1117-TOGOK): bytes (the Bass segment exists only in the luke-alto hook shell; every other build keeps
two segments and zero bass bytes) and geometry in real WebKit and Chromium at d1440 and p390 (all three segments on a phone, 44pt), in Holo, Classic and Retro.
Shots: EDIT_PILL_SHOTS=<dir>."""
import functools
import http.server
import json
import os
import re
import socketserver
import subprocess
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
URL = "https://us-central1-demo-project.cloudfunctions.net/altoext"
NODE = Path.home() / ".local/node/bin/node"
SHOTS = os.environ.get("EDIT_PILL_SHOTS", "")


def _page():
    from alto.build.builder import build_timeline, load_brief
    from alto.build.single_file import private_page
    samples = json.loads((ROOT / "samples" / "outline_brief.json").read_text("utf-8"))
    b, nodes, conns = load_brief({"brief": samples["brief"], "nodes": samples["nodes"], "connections": samples.get("connections", [])})
    html, _ = build_timeline(b, nodes, conns)
    return private_page(b, html, "x")


def _hooked(page, tmp_path):
    """Run the REAL pillBass() of the luke-alto shell on a page (node)."""
    mp = pytest.MonkeyPatch()
    mp.setenv("ALTO_EXT_URL", URL)
    try:
        from alto.build import private_shell
        shell = private_shell.shell("v", "s")
    finally:
        mp.undo()
    js = re.findall(r"<script>(.*?)</script>\n<script type", shell, re.S)[0]
    fn = js[js.index("function pillBass"):js.index("function render")]
    (tmp_path / "p.html").write_text(page, "utf-8")
    (tmp_path / "e.js").write_text(fn + "\nconst fs=require('fs');fs.writeFileSync(process.argv[3],pillBass(fs.readFileSync(process.argv[2],'utf8')));", "utf-8")
    subprocess.check_call([str(NODE), str(tmp_path / "e.js"), str(tmp_path / "p.html"), str(tmp_path / "o.html")])
    return (tmp_path / "o.html").read_text("utf-8")


def test_bytes_the_segment_is_in_the_hook_shell_only(monkeypatch):
    from alto.build import private_shell
    monkeypatch.delenv("ALTO_EXT_URL", raising=False)
    off = private_shell.shell("v", "s")
    monkeypatch.setenv("ALTO_EXT_URL", URL)
    on = private_shell.shell("v", "s")
    assert "bass" not in off.lower() and "aep-bass" not in off
    assert "function pillBass" in on and "aep-bass" in on


def test_the_hooked_page_gains_one_segment_and_the_plain_page_none(tmp_path):
    page = _page()
    assert "aep-bass" not in page and page.count("aep-half aep-claude") == 1
    grown = _hooked(page, tmp_path)
    assert grown.count('class="aep-half aep-bass" href="/#bass-edit=') == 1
    i = grown.index("aep-half aep-claude")
    assert i < grown.index("aep-half aep-bass") < grown.index("aep-half aep-manual")
    assert 0 < len(grown) - len(page) < 2400


def test_a_page_that_has_no_toggle_is_left_alone(tmp_path):
    odd = "<html><head></head><body>var COURSE_ID = 'x';</body></html>"
    assert _hooked(odd, tmp_path) == odd


pw = pytest.importorskip("playwright.sync_api")
FAKE = """(function(){ var store=null;
 var C={enabled:true, known:true, user:{uid:'u1', email:'tester@example.com'}, getEdits:function(){ return Promise.resolve(store); },
  putEdits:function(t,d){ store=JSON.parse(JSON.stringify(d)); return Promise.resolve(); }, watchEdits:function(){ return function(){}; }};
 Object.defineProperty(window,'AltoCloud',{get:function(){return C;}, set:function(){}, configurable:true}); })();"""
UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
MEASURE = """() => { const P = document.querySelector('.alto-edit-pill:not(.in-page)') && getComputedStyle(document.querySelector('.alto-edit-pill:not(.in-page)')).display !== 'none' ? document.querySelector('.alto-edit-pill:not(.in-page)') : document.querySelector('.alto-edit-pill.in-page');
  if(!P) return {nopill: true};
  const R = e => e.getBoundingClientRect(), p = R(P);
  return {inpage: P.classList.contains('in-page'), pill: [p.left, p.top, p.right, p.bottom], vw: innerWidth, vh: innerHeight,
    halves: [...P.querySelectorAll('.aep-half')].map(h => { const r = R(h); return {cls: h.className.replace('aep-half ', ''), tag: h.tagName, label: h.getAttribute('aria-label'), tip: h.getAttribute('data-tip'), w: r.width, h: r.height, href: h.getAttribute('href'), pad: getComputedStyle(h).textDecorationLine}; }),
    divs: P.querySelectorAll('.aep-div').length, claudeFn: typeof window._altoEditTimeline}; }"""


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    from alto.build import bass_ui, holo, retro
    root = tmp_path_factory.mktemp("pill")
    page = _page()
    (root / "off.html").write_text(page, "utf-8")
    (root / "on.html").write_text(_hooked(page, tmp_path_factory.mktemp("hk")), "utf-8")
    for m, fn in ((retro, retro.retro_asset), (holo, holo.holo_asset)):
        f = root / m.PATH.lstrip("/"); f.parent.mkdir(parents=True, exist_ok=True); f.write_text(fn()[1], encoding="utf-8")
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root)); h.log_message = lambda *a: None
    socketserver.TCPServer.allow_reuse_address = True
    srv = socketserver.TCPServer(("127.0.0.1", 0), h); threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def _open(b, server, which, w, h, style, theme="light"):
    phone = w < 700
    ctx = b.new_context(viewport={"width": w, "height": h}, is_mobile=phone, has_touch=phone, user_agent=UA if phone else None, device_scale_factor=2 if phone else 1)
    ctx.add_init_script(FAKE + ";try{localStorage.setItem('alto-theme-v1','%s')}catch(e){}" % theme)
    pg = ctx.new_page()
    pg.goto(f"{server}/{which}.html", wait_until="domcontentloaded")
    pg.wait_for_function("typeof showDetail === 'function'", timeout=30000); pg.wait_for_timeout(1200)
    if style != "classic":
        pg.evaluate("window._altoStyle.set('%s');0" % style); pg.wait_for_timeout(1500)
    if phone:
        pg.evaluate("showDetail('node','definiteness')"); pg.wait_for_timeout(900)
        pg.evaluate("() => { const t = document.querySelector('.alto-edit-pill.in-page'); if(t) t.scrollIntoView({block: 'center'}); }"); pg.wait_for_timeout(500)
    return ctx, pg


CASES = [(s, t, w, h) for s, t in (("holo", "dark"), ("classic", "light"), ("retro", "dark")) for (w, h) in ((1440, 900), (390, 844))]


@pytest.fixture(scope="module", params=["webkit", "chromium"])
def pills(request, server):
    out = []
    with pw.sync_playwright() as p:
        b = getattr(p, request.param).launch()
        for which in ("on", "off"):
            for style, theme, w, h in (CASES if request.param == "webkit" else [c for c in CASES if c[0] == "classic"]):
                ctx, pg = _open(b, server, which, w, h, style, theme)
                m = pg.evaluate(MEASURE); m["case"] = [request.param, which, style, w]
                if SHOTS and request.param == "webkit":
                    pg.screenshot(path=f"{SHOTS}/{style}-{'p390' if w < 700 else 'd1440'}-{'with-bass' if which == 'on' else 'no-bass'}.png")
                    if which == "on" and w > 700:
                        pg.hover(".aep-bass"); pg.wait_for_timeout(350); pg.screenshot(path=f"{SHOTS}/{style}-d1440-with-bass-tip.png")
                out.append(m); ctx.close()
        b.close()
    return out


def test_every_build_has_the_star_and_the_pencil_and_only_the_hook_build_has_bass(pills):
    for m in pills:
        assert not m.get("nopill"), m["case"]
        names = [h["label"] for h in m["halves"]]
        if m["case"][1] == "on":
            assert names == ["Edit with Claude", "Edit with Bass", "Edit manually"], (m["case"], names)
            assert m["divs"] == 2
        else:
            assert names == ["Edit with Claude", "Edit manually"], (m["case"], names)
            assert m["divs"] == 1


def test_all_three_segments_are_on_a_phone_at_44pt_and_the_star_opens_claude(pills):
    seen = 0
    for m in pills:
        if m["case"][3] > 700:
            continue
        seen += 1
        assert m["inpage"], m["case"]
        for h in m["halves"]:
            assert h["w"] >= 43.5 and h["h"] >= 43.5, (m["case"], h)
        assert m["claudeFn"] == "function", m["case"]
        l, t, r, b = m["pill"]
        assert l >= 20 and m["vw"] - r >= 20, (m["case"], m["pill"])
    assert seen >= 2


def test_the_desktop_toggle_keeps_20px_from_the_window_edge_and_has_tips_and_names(pills):
    seen = 0
    for m in pills:
        if m["case"][3] < 700:
            continue
        seen += 1
        l, t, r, b = m["pill"]
        assert m["vw"] - r >= 20 and m["vh"] - b >= 20, (m["case"], m["pill"])
        for h in m["halves"]:
            assert h["tip"] and h["label"] and h["h"] >= 24, (m["case"], h)
        if m["case"][1] == "on":
            bass = m["halves"][1]
            assert bass["tag"] == "A" and bass["href"].startswith("/#bass-edit="), (m["case"], bass)
    assert seen >= 2
