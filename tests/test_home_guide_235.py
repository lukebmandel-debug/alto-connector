"""The home info guide names only controls that are on the home screen (Board B-1116-200821): the Light / Dark line says where the toggle really is, or that this look is always dark;
and the search, account and info controls the guide names exist at d1440 and p390 (headless WebKit, no network)."""
import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parent.parent

SCRIPT = textwrap.dedent('''
    import sys, json, http.server, threading
    sys.path.insert(0, %(root)r)
    from alto.build import pages, holo, retro
    import playwright.sync_api as pw
    ASSETS = {}
    for sub, asset in (("holo", holo.holo_asset), ("retro", retro.retro_asset)):
        n, t = asset(); ASSETS["/%%s/%%s" %% (sub, n)] = t
    home = pages.build_home([])
    class Site(http.server.BaseHTTPRequestHandler):
        def log_message(s, *a): pass
        def do_GET(s):
            path = s.path.split("?")[0]; body = ASSETS.get(path)
            b = (body if body is not None else home).encode(); s.send_response(200); s.send_header("Content-Type", "text/javascript" if body is not None else "text/html"); s.send_header("Content-Length", str(len(b))); s.end_headers(); s.wfile.write(b)
    site = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Site); threading.Thread(target=site.serve_forever, daemon=True).start()
    base = "http://127.0.0.1:%%d/" %% site.server_address[1]
    UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
    MEASURE = """() => {
      const vis = id => { const e = document.getElementById(id); if(!e) return null; const r = e.getBoundingClientRect(), cs = getComputedStyle(e); return (e.offsetParent !== null || cs.position === 'fixed') && r.width > 0 && cs.display !== 'none' && cs.visibility !== 'hidden' ? [r.left + r.width / 2, r.top + r.height / 2] : null; };
      toggleInfo();
      return {text: document.getElementById('info-mode').textContent, mode: vis('mode-toggle'), search: vis('search-btn'), account: vis('account-btn'), info: vis('info-btn'), vw: innerWidth, vh: innerHeight,
              retro: document.documentElement.classList.contains('alto-retro')};
    }"""
    out = []
    with pw.sync_playwright() as p:
        b = p.webkit.launch()
        for style, theme in (("classic", "light"), ("classic", "dark"), ("holo", "dark"), ("retro", "dark")):
            for w, h in ((1440, 900), (390, 844)):
                mob = w < 700
                ctx = b.new_context(viewport={"width": w, "height": h}, is_mobile=mob, has_touch=mob, user_agent=UA if mob else None)
                pg = ctx.new_page()
                pg.add_init_script("try{localStorage.setItem('alto-bg-home-v1-style','%%s');localStorage.setItem('alto-theme-v1','%%s')}catch(e){}" %% (style, theme))
                pg.goto(base); pg.wait_for_timeout(1200)
                m = pg.evaluate(MEASURE); m["case"] = [style, theme, w, h]; out.append(m); ctx.close()
        b.close()
    print("JSON:" + json.dumps(out))
''')


@pytest.fixture(scope="module")
def guide():
    r = subprocess.run([sys.executable, "-c", SCRIPT % {"root": str(ROOT)}], capture_output=True, text=True, timeout=900)
    assert r.returncode == 0, r.stderr[-2000:]
    return json.loads([ln for ln in r.stdout.splitlines() if ln.startswith("JSON:")][-1][5:])


def test_the_light_dark_line_says_only_what_is_on_screen(guide):
    for m in guide:
        t = m["text"]
        if m["mode"]:                                                     # a toggle is on the home: the line names its real corner
            v = "top" if m["mode"][1] < m["vh"] / 2 else "bottom"
            h = "left" if m["mode"][0] < m["vw"] / 2 else "right"
            assert f"at the {v} {h}" in t, (m["case"], t, m["mode"])
        else:                                                             # none is: the line never points at one
            assert "at the" not in t and "tile" not in t and "toggle at" not in t, (m["case"], t)
            if m["case"][0] in ("holo", "retro"):
                assert "always dark" in t, (m["case"], t)
        assert "each page has its own toggle" in t, (m["case"], t)


def test_holo_and_retro_have_no_toggle_and_say_so_and_classic_points_at_the_real_one(guide):
    by = {(m["case"][0], m["case"][1], m["case"][2]): m for m in guide}
    for w in (1440, 390):
        assert by[("holo", "dark", w)]["mode"] is None and "always dark" in by[("holo", "dark", w)]["text"]
        assert by[("retro", "dark", w)]["mode"] is None and "always dark" in by[("retro", "dark", w)]["text"]
    assert by[("classic", "light", 1440)]["mode"] and "switches the whole surface" in by[("classic", "light", 1440)]["text"]


def test_every_other_control_the_guide_names_is_on_the_home_at_both_sizes(guide):
    for m in guide:
        assert m["search"] and m["account"] and m["info"], (m["case"], m["search"], m["account"], m["info"])
