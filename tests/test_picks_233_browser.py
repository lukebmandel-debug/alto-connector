"""v1.9.233 browser checks for the New dialog tabs: the Bass tab shows its sentence, the Bass steps and Cancel (the build made with ALTO_BASS_UI=1, the
in-page simulator, no network); the plain build's Claude tab shows its sentence, Open Claude and Cancel; the light plate is solid."""
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parent.parent

SCRIPT = textwrap.dedent('''
    import sys, os, json, http.server, socketserver, threading, tempfile
    from pathlib import Path
    sys.path.insert(0, %(root)r)
    from alto.build import pages, bass_ui, holo, retro
    import playwright.sync_api as pw
    d = Path(tempfile.mkdtemp()); (d / "h.html").write_text(pages.build_home([]), encoding="utf-8")
    for sub, asset in (("holo", holo.holo_asset), ("retro", retro.retro_asset)):
        (d / sub).mkdir(); n, t = asset(); (d / sub / n).write_text(t, encoding="utf-8")
    if bass_ui.enabled():
        (d / "bass").mkdir(); n, t = bass_ui.bass_asset(); (d / "bass" / n).write_text(t, encoding="utf-8")
    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(s, *a, **k): super().__init__(*a, directory=str(d), **k)
        def log_message(s, *a): pass
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), H); srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = "http://127.0.0.1:%%d" %% srv.server_address[1]
    out = []
    with pw.sync_playwright() as p:
        b = p.webkit.launch()
        for style, theme, size in %(cases)r:
            w, h = size
            ctx = b.new_context(viewport={"width": w, "height": h}); pg = ctx.new_page()
            pg.add_init_script("try{localStorage.setItem('alto-bg-home-v1-style','%%s');localStorage.setItem('alto-theme-v1','%%s')}catch(e){}" %% (style, theme))
            pg.goto(base + "/h.html"); pg.wait_for_timeout(700)
            pg.evaluate("ntOpen('',true)"); pg.wait_for_timeout(1500)
            out.append(pg.evaluate("""()=>{const v=s=>{const e=document.querySelector(s);if(!e)return false;const r=e.getBoundingClientRect(),c=getComputedStyle(e);return r.width>0&&r.height>0&&c.display!=='none'&&c.visibility!=='hidden'};
              const m=document.getElementById('nt-modal');return {tab:m.dataset.tab,sentence:v('.nt-pane:not([hidden]) .nt-pn'),pane:v('.nt-pane:not([hidden])'),cancel:v('#nt-cancel')||[...document.querySelectorAll('#bass-root button')].some(b=>/Cancel/.test(b.textContent)&&b.offsetWidth>0),
              button:v('.nt-pane:not([hidden]) button')||v('#nt-bass button')||v('#bass-root button'),root:!!document.getElementById('bass-root'),bassBtns:document.querySelectorAll('#nt-bass button').length,
              bg:getComputedStyle(m).backgroundColor,gutter:[m.getBoundingClientRect().left,innerWidth-m.getBoundingClientRect().right]}}"""))
            ctx.close()
        b.close()
    print("RESULT" + json.dumps(out))
''')


def run(bass, cases):
    env = {k: v for k, v in os.environ.items() if k not in ("ALTO_BASS_UI", "ALTO_BASS_BASE", "ALTO_EXT_URL")}
    env["ALTO_NO_NETWORK"] = "1"
    if bass:
        env["ALTO_BASS_UI"] = "1"
    r = subprocess.run([sys.executable, "-c", SCRIPT % {"root": str(ROOT), "cases": cases}], capture_output=True, text=True, env=env, timeout=240)
    line = [l for l in r.stdout.splitlines() if l.startswith("RESULT")]
    if not line:
        pytest.skip("browser not available: " + r.stderr[-300:])
    return json.loads(line[0][6:])


CASES = [("holo", "dark", (1440, 900)), ("holo", "dark", (390, 844)), ("classic", "light", (1440, 900)), ("classic", "light", (390, 844))]


def test_the_bass_tab_shows_its_sentence_its_steps_and_cancel():
    for c, r in zip(CASES, run(True, CASES)):
        assert r["tab"] == "bass", (c, r)
        assert r["pane"] and r["sentence"] and r["cancel"], (c, r)                   # the sentence panel and Cancel are on screen
        assert r["root"] and r["bassBtns"] >= 1 and r["button"], (c, r)              # the Bass step is mounted and has its button


def test_the_plain_claude_tab_has_sentence_button_and_cancel_and_a_20px_phone_gutter():
    for c, r in zip(CASES, run(False, CASES)):
        assert r["tab"] == "claude" and r["sentence"] and r["button"] and r["cancel"], (c, r)
        if c[2][0] == 390:
            assert r["gutter"] == [20, 20], (c, r)


def test_the_light_plate_is_solid():
    rs = run(False, [("classic", "light", (1440, 900))])
    assert rs[0]["bg"].startswith("rgb(") and not rs[0]["bg"].startswith("rgba("), rs
