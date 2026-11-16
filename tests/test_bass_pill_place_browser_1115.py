"""Bass has no always-visible pill (Luke 2026-11-15): it shows in the New window and on the card's "+ Make a study plan" line, and that line does something every time.
Real home page, real hook and the real pinned bundle against a fake altoext (canned answers); Chromium and WebKit, headless. No network, no key, no Firebase."""
from __future__ import annotations

import http.server
import json
import os
import socketserver
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
try:
    import playwright.sync_api as pw
except Exception:                                                  # noqa: BLE001
    pw = None

from alto.build import bass_hosted_ext, bass_ui, holo, pages, retro   # noqa: E402
from alto.build import phone as _phone                                # noqa: E402
from alto.cloud import ext_hook                                       # noqa: E402
from alto.hosted import hosted_home                                   # noqa: E402

CARDS = [dict(key="k1", title="A", heading="Contracts", project="Law", fmt="timeline", tid="t1", units=["#4a9eff"], plan={"days": ["2026-11-05"], "exam": ""}),
         dict(key="k2", title="B", heading="Torts", project="Law", fmt="timeline", tid="t2", units=["#4a9eff"])]
NOW = "window._altoSpNow=new Date('2026-11-05T12:00:00').getTime();"


def _stub(px: str | None) -> str:
    s = ("const who=(new URLSearchParams(location.search).get('as'))||'';"
         "const user=who?{uid:'u-'+who,email:'a@b.c',displayName:'A',getIdToken:async()=>'tok-'+who}:null;"
         "window.AltoCloud={enabled:true,known:true,user,listPages:()=>Promise.resolve(%s),listShared:()=>Promise.resolve([]),signOut:()=>Promise.resolve(),createTimeline:()=>Promise.resolve({}),signIn:()=>Promise.resolve(),getPage:()=>Promise.resolve(''),forgetShare:()=>Promise.resolve()};"
         "setTimeout(()=>window.dispatchEvent(new CustomEvent('alto-auth')),50);" % json.dumps(CARDS))
    return s + (ext_hook.hook_js(px) if px else "")


class _Env:
    def __init__(self, d: Path):
        self.d = d
        self.home = hosted_home(pages.build_home([]))
        self.bundle = bass_hosted_ext.bundle()
        self.log: list[dict] = []
        env = self
        for mod, sub in ((holo, "holo"), (retro, "retro"), (_phone, "phone")):
            nm, tx = (mod.holo_asset if sub == "holo" else mod.retro_asset if sub == "retro" else mod.phone_asset)()
            (d / sub).mkdir(exist_ok=True)
            (d / sub / nm).write_text(tx, encoding="utf-8")
        lib, js = bass_ui.__dict__.get("site_file", lambda: (None, None))() if False else (None, None)
        try:
            from alto.build import backgrounds_import as bi
            lib, js = bi.site_file()
            (d / lib).write_text(js, encoding="utf-8")
        except Exception:                                              # noqa: BLE001
            pass

        class Page(http.server.SimpleHTTPRequestHandler):
            def __init__(s, *a, **k):
                super().__init__(*a, directory=str(d), **k)

            def log_message(s, *a):
                pass

            def do_GET(s):
                p = s.path.split("?")[0]
                if p in ("/", "/nohook"):
                    tag = '<script src="/stub%s.js"></script>' % ("" if p == "/" else "0")
                    body, ct = env.home.replace('<script type="module" src="/alto-cloud.js"></script>', "").replace("<head>", "<head>" + tag, 1), "text/html"
                elif p == "/stub.js":
                    body, ct = _stub(f"http://127.0.0.1:{env.px_port}/altoext"), "text/javascript"
                elif p == "/stub0.js":
                    body, ct = _stub(None), "text/javascript"
                else:
                    return super().do_GET()
                b = body.encode()
                s.send_response(200); s.send_header("Content-Type", ct + "; charset=utf-8"); s.send_header("Content-Length", str(len(b))); s.end_headers(); s.wfile.write(b)

        class Px(http.server.BaseHTTPRequestHandler):
            def log_message(s, *a):
                pass

            def _do(s):
                n = int(s.headers.get("Content-Length") or 0)
                body = json.loads(s.rfile.read(n) or b"{}") if n else {}
                tok = (s.headers.get("Authorization") or "")[7:]
                act = body.get("action")
                env.log.append((tok, act))
                if tok != "tok-luke":
                    out = {}
                elif act == "ext":
                    out = {"x": env.bundle}
                elif act == "make_study_plan":
                    out = {"ok": False, "status": "estimate", "estimate_credits": 30, "credits": {}}
                else:
                    out = {"ok": True, "status": "ok", "credits": 400, "ack": "x"}
                b = json.dumps(out).encode()
                s.send_response(200)
                for k, v in (("Content-Type", "application/json"), ("Access-Control-Allow-Origin", "*"), ("Access-Control-Allow-Headers", "*"), ("Content-Length", str(len(b)))):
                    s.send_header(k, v)
                s.end_headers()
                if s.command != "OPTIONS":
                    s.wfile.write(b)

            do_POST = do_OPTIONS = _do

        self.srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Page); self.srv.daemon_threads = True
        self.px = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Px); self.px.daemon_threads = True
        self.px_port = self.px.server_address[1]
        for s in (self.srv, self.px):
            threading.Thread(target=s.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}"

    def close(self):
        for s in (self.srv, self.px):
            s.shutdown(); s.server_close()


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    if pw is None:
        pytest.skip("Playwright is not installed")
    e = _Env(tmp_path_factory.mktemp("pill"))
    yield e
    e.close()


@pytest.fixture(scope="module", params=["chromium", "webkit"])
def browser(request):
    if pw is None:
        pytest.skip("Playwright is not installed")
    with pw.sync_playwright() as p:
        try:
            b = getattr(p, request.param).launch()
        except Exception as ex:                                        # noqa: BLE001
            pytest.skip(f"{request.param} is not installed: {ex}")
        yield b
        b.close()


def open_home(browser, env, path="/", who="luke", style="classic", dark=False, size=(1440, 900), wait=1800):
    ctx = browser.new_context(viewport={"width": size[0], "height": size[1]}, has_touch=size[0] < 900, is_mobile=size[0] < 500)
    pg = ctx.new_page()
    init = NOW + "try{localStorage.setItem('alto-bg-home-v1-style','%s');localStorage.setItem('alto-theme-v1','%s')}catch(e){}" % (style, "dark" if dark else "light")
    pg.add_init_script(init)
    pg.goto(env.url + path + (f"?as={who}" if who else "")); pg.wait_for_timeout(wait)
    if path == "/" and who == "luke":
        pg.wait_for_function("!!window._altoBass && !!document.getElementById('nt-bass')", timeout=20000)          # the hook has run
    return ctx, pg


CORNER = "['account-btn','mode-toggle','info-btn','search-btn','download-all','bin-btn','bg-toggle'].map(i=>{const e=document.getElementById(i);if(!e)return [i,null];const r=e.getBoundingClientRect();return [i,[r.x,r.y,r.width,r.height].map(v=>Math.round(v*10)/10),getComputedStyle(e).display]})"
STYLES = [("classic", False), ("classic", True), ("retro", True), ("holo", True), ("holo", False), ("retro", False)]


def test_the_bundle_has_no_pill_and_no_beta_label():
    b = bass_hosted_ext.bundle()
    assert "alto-bass-beta" not in b and "(beta)" not in b and "Bass (beta)" not in b
    assert "nt-bass" in b and "_altoStudyPlanMake" in b
    assert bass_hosted_ext.pin() == (ROOT / "alto" / "cloud" / "ext_pin.txt").read_text().strip()


@pytest.mark.parametrize("style,dark", STYLES)
def test_no_pill_corner_unchanged_and_new_window_and_study_plan_reach_bass(browser, env, style, dark):
    ctx, ref = open_home(browser, env, "/nohook", who="luke", style=style, dark=dark)
    ref_corner = ref.evaluate(CORNER); ctx.close()
    ctx, pg = open_home(browser, env, "/", style=style, dark=dark)
    assert pg.query_selector("#alto-bass-beta") is None
    assert "(beta)" not in pg.evaluate("document.body.innerText").lower()
    assert pg.evaluate(CORNER) == ref_corner                               # the corner controls sit exactly where they do without Bass
    # the New window: tabs, Bass first and chosen; Claude and Write it yourself beside it
    pg.evaluate("ntOpen('', true)"); pg.wait_for_timeout(500)
    assert pg.evaluate("[...document.querySelectorAll('#nt-tabs .nt-tab')].map(b=>b.dataset.tab)") == ["bass", "claude", "self"]
    assert pg.evaluate("document.getElementById('nt-modal').dataset.tab") == "bass" and pg.is_visible("#nt-bass") and not pg.is_visible("#nt-claude")
    pg.click("#nt-tabs .nt-tab[data-tab=claude]"); pg.wait_for_timeout(200)
    assert not pg.is_visible("#nt-bass") and pg.is_visible("#nt-claude")
    pg.click("#nt-tabs .nt-tab[data-tab=self]"); pg.wait_for_timeout(200)
    assert pg.is_visible("#nt-title") and not pg.is_visible("#nt-bass") and not pg.is_visible("#nt-claude")
    pg.click("#nt-tabs .nt-tab[data-tab=bass]"); pg.wait_for_timeout(200)
    pg.click("#nt-bass"); pg.wait_for_timeout(900)
    assert pg.query_selector("#bass-root") is not None and not pg.is_visible("#nt-modal")
    pg.evaluate("window._altoBass.close&&window._altoBass.close()"); pg.wait_for_timeout(200)
    # the study plan line opens Bass for that card, and it takes the student's words to an estimate
    before = pg.url
    pg.click(".sp-card.sp-make"); pg.wait_for_timeout(900)
    assert pg.url == before and pg.query_selector("#bass-root") is not None
    assert "study plan" in pg.inner_text("#bass-root").lower()
    ctx.close()


@pytest.mark.parametrize("path,who,style,dark", [("/nohook", "luke", st, dk) for st, dk in STYLES] + [("/", "other", "classic", False), ("/", "", "classic", False)])
def test_without_bass_the_line_still_does_something_and_never_opens_the_timeline(browser, env, path, who, style, dark):
    ctx, pg = open_home(browser, env, path, who=who, style=style, dark=dark)
    assert pg.query_selector("#nt-bass") is None and pg.query_selector("#bass-root") is None
    before = pg.url
    if not who:                                                           # signed out the home lists no cards, so there is no line to press
        assert pg.query_selector(".sp-card.sp-make") is None
        ctx.close(); return
    pg.click(".sp-card.sp-make"); pg.wait_for_timeout(700)
    assert pg.url == before                                               # it no longer falls through to the card's own link
    assert pg.is_visible("#claude-toast")                                # a visible answer: the plan goes to Claude, as the New window's path does
    # the New window is the one it always was
    pg.evaluate("ntOpen('', true)"); pg.wait_for_timeout(300)
    assert pg.query_selector("#nt-bass") is None and pg.is_visible("#nt-claude")
    ctx.close()


@pytest.mark.parametrize("size", [(390, 844), (844, 390)])
def test_phone_corner_controls_do_not_change_with_bass(browser, env, size):
    ctx, ref = open_home(browser, env, "/nohook", size=size, style="classic")
    a = ref.evaluate(CORNER); ctx.close()
    ctx, pg = open_home(browser, env, "/", size=size, style="classic")
    assert pg.query_selector("#alto-bass-beta") is None and pg.evaluate(CORNER) == a
    ctx.close()


@pytest.mark.parametrize("size", [(390, 844), (844, 390)])
def test_bass_new_entry_is_a_44pt_target_on_a_phone(browser, env, size):
    ctx, pg = open_home(browser, env, "/", size=size, style="classic")
    pg.evaluate("ntOpen('', true)"); pg.wait_for_timeout(500)
    w, h = pg.evaluate("(()=>{const r=document.getElementById('nt-bass').getBoundingClientRect();return [r.width,r.height]})()")
    assert w >= 44 and h >= 44, (w, h)
    ctx.close()


def test_no_visible_beta_in_the_bass_ui():
    import re
    from alto.bass import errors
    from alto.build import bass_ui_js
    lits = re.findall(r"'([^'\n]*)'", bass_ui_js.JS) + re.findall(r'"([^"\n]*)"', bass_ui_js.JS)
    assert [t for t in lits if " " in t and re.search("beta", t, re.I) and not re.search(r"BETA|balLab", t)] == []         # no prose string of the UI says beta
    assert [p.code for p in errors.POLICIES.values() if re.search("beta", p.user_message, re.I) and p.code not in ()] == []
    # the sign-in box's legal "Beta Terms" link (alto-cloud.js) keeps the document's name until the document is renamed: out of this scope


def test_no_visible_beta_in_the_open_bass_panels(browser, env):
    ctx, pg = open_home(browser, env, "/")
    pg.evaluate("ntOpen('', true)"); pg.click("#nt-bass"); pg.wait_for_timeout(900)
    assert "beta" not in pg.inner_text("#bass-root").lower()
    pg.evaluate("window._altoBass.close&&window._altoBass.close()")
    pg.click(".sp-card.sp-make"); pg.wait_for_timeout(900)
    assert "beta" not in pg.inner_text("#bass-root").lower()
    ctx.close()
