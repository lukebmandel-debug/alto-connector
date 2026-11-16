"""Add from Drive in "Edit this page", in real browsers (Chromium + WebKit), desktop and phone width, with a fake cloud and a STUBBED picker
(window._altoDriveRefPick). Builds the page with the three ALTO_DRIVE_* names set to fake values; no Google page is ever loaded.
Needs Playwright (the pw12 env); skipped in the plain venv by design: it is a browser test, not one of the six plain-venv files."""
import functools
import http.server
import json
import os
import socketserver
import threading
from pathlib import Path

import pytest

pw = pytest.importorskip("playwright.sync_api")

from alto.build import backgrounds_import as bi, holo, retro  # noqa: E402
from alto.build.builder import build_timeline, load_brief  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SHOTS = os.environ.get("ALTO_DRIVE_SHOTS", "")
ID = "1AbCdEfGhIjKlMn"
FAKE = """(function(){ var store=null;
 var C={enabled:true, known:true, user:{uid:'u1', email:'tester@example.com'}, getEdits:function(){ return Promise.resolve(store); },
  putEdits:function(t,d){ store=JSON.parse(JSON.stringify(d)); return Promise.resolve(); }, watchEdits:function(){ return function(){}; }};
 Object.defineProperty(window,'AltoCloud',{get:function(){return C;}, set:function(){}, configurable:true}); })();"""
STUB = "window._altoDriveRefPick=function(cfg){ window.__cfgSeen=cfg; return Promise.resolve([{id:'%s', name:'Syllabus.pdf'},{id:'1ZzYyXxWwVvUuTt', name:'Reading list'}]); };" % ID
OPENED = "window.__opened=[]; window.open=function(u,n,f){ window.__opened.push([String(u),String(n||''),String(f||'')]); return null; };"


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    for n, v in zip(("ALTO_DRIVE_CLIENT_ID", "ALTO_DRIVE_API_KEY", "ALTO_DRIVE_APP_ID"), ("fake.apps.googleusercontent.com", "fake-key", "123456")):
        mp.setenv(n, v)
    root = tmp_path_factory.mktemp("drive")
    d = json.loads((ROOT / "samples" / "outline_brief.json").read_text(encoding="utf-8"))
    (root / "outline.html").write_text(build_timeline(*load_brief(d))[0], encoding="utf-8")
    for m, fn in ((retro, retro.retro_asset), (holo, holo.holo_asset)):          # the hosted looks, so Retro and Holo can be switched on
        f = root / m.PATH.lstrip("/"); f.parent.mkdir(parents=True, exist_ok=True); f.write_text(fn()[1], encoding="utf-8")
    lib, js = bi.site_file(); (root / lib).write_text(js, encoding="utf-8")
    mp.undo()
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    h.log_message = lambda *a: None
    socketserver.TCPServer.allow_reuse_address = True
    srv = socketserver.TCPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


@pytest.fixture(scope="module", params=["chromium", "webkit"])
def browser(request):
    with pw.sync_playwright() as p:
        b = getattr(p, request.param).launch()
        yield b
        b.close()


def _open(browser, server, width, height, phone, style="classic"):
    ctx = browser.new_context(viewport={"width": width, "height": height}, has_touch=phone, is_mobile=phone)
    ctx.add_init_script(FAKE)
    pg = ctx.new_page()
    pg.goto(f"{server}/outline.html", wait_until="domcontentloaded")
    pg.wait_for_function("typeof showDetail === 'function'", timeout=30000)
    pg.wait_for_timeout(1200)
    if style != "classic":
        pg.evaluate("window._altoStyle.set('%s');0" % style)
        pg.wait_for_timeout(1500)
    pg.evaluate(STUB + OPENED + ";0")
    pg.click("#alto-edit-pill .aep-manual")
    pg.wait_for_selector("html.alto-editing", timeout=10000)
    pg.wait_for_timeout(500)
    pg.evaluate("showDetail('node','definiteness')")
    pg.wait_for_timeout(500)
    return pg


def _select_words_in_a_rich_field(pg):
    """Starts the first rich text field and selects its first word; returns False when the page offers none."""
    return pg.evaluate("""() => { var f = document.querySelector('.aed-bodypart, [data-aed="ov|html"]'); if(!f) return false;
      f.dispatchEvent(new MouseEvent('click', {bubbles: true})); var el = document.querySelector('[contenteditable=true]') || f;
      el.focus(); var r = document.createRange(), t = el.firstChild; while(t && t.nodeType !== 3) t = t.firstChild; if(!t) return false;
      r.setStart(t, 0); r.setEnd(t, Math.min(5, t.length)); var s = getSelection(); s.removeAllRanges(); s.addRange(r); return true; }""")


@pytest.mark.parametrize("phone", [False, True], ids=["desktop", "phone"])
def test_pick_from_drive_makes_chips_and_the_token_never_exists_on_the_page(browser, server, phone):
    pg = _open(browser, server, *((390, 844, True) if phone else (1440, 900, False)))
    try:
        assert _select_words_in_a_rich_field(pg), "no rich field found"
        pg.evaluate("document.querySelector('#aed-bar [data-a=link]').click()")
        pg.wait_for_selector("#aed-link.show", timeout=5000)
        assert pg.evaluate("!!document.querySelector('#aed-link [data-a=drive]') && !!document.querySelector('#aed-link .al-dl')")
        if SHOTS:
            pg.screenshot(path=os.path.join(SHOTS, f"link-a-file-{browser.browser_type.name}-{'phone' if phone else 'desktop'}.png"))
        pg.evaluate("document.querySelector('#aed-link [data-a=drive]').click()")
        pg.wait_for_function("document.querySelectorAll('a[data-gdrive]').length >= 2", timeout=5000)
        chips = pg.evaluate("Array.from(document.querySelectorAll('a[data-gdrive]')).map(a => ({id: a.getAttribute('data-gdrive-id'), href: a.getAttribute('href'), share: a.getAttribute('data-gdrive-share'), rel: a.rel}))")
        assert chips[0]["id"] == ID and chips[0]["href"] == f"https://drive.google.com/file/d/{ID}/view" and chips[0]["share"] == "0" and "noopener" in chips[0]["rel"]
        # the words: the first chip wraps the owner's own selected words; a further file gets neutral words, never its Drive name (a hidden chip's words are shared)
        words = pg.evaluate("Array.from(document.querySelectorAll('a[data-gdrive]')).map(a => a.textContent)")
        assert words[1] == "Drive file 2" and not [t for t in words if "Reading list" in t or "Syllabus" in t], words
        assert pg.evaluate("Object.keys(window.__cfgSeen).sort().join()") == "api_key,app_id,client_id"
        assert pg.evaluate("document.documentElement.outerHTML.indexOf('ya29')") == -1 and pg.evaluate("typeof window.__cfgSeen.token") == "undefined"
        if SHOTS:
            pg.screenshot(path=os.path.join(SHOTS, f"chip-on-a-card-{browser.browser_type.name}-{'phone' if phone else 'desktop'}.png"))
    finally:
        pg.context.close()


def test_paste_a_link_and_a_bad_one(browser, server):
    pg = _open(browser, server, 1440, 900, False)
    try:
        assert _select_words_in_a_rich_field(pg)
        pg.evaluate("document.querySelector('#aed-bar [data-a=link]').click()")
        pg.wait_for_selector("#aed-link.show")
        pg.fill("#aed-link .al-dl", "javascript:alert(1)")
        pg.evaluate("document.querySelector('#aed-link [data-a=dlink]').click()")
        assert "Paste a Google Drive link" in pg.inner_text("#aed-link .al-msg")
        assert pg.evaluate("document.querySelectorAll('a[data-gdrive]').length") == 0
        pg.fill("#aed-link .al-dl", f"https://docs.google.com/document/d/{ID}/edit?usp=sharing")
        pg.fill("#aed-link .al-dn", "My notes")
        pg.evaluate("document.querySelector('#aed-link [data-a=dlink]').click()")
        pg.wait_for_selector("a[data-gdrive]")
        assert pg.evaluate("document.querySelector('a[data-gdrive]').getAttribute('data-file-name')") == "My notes"
    finally:
        pg.context.close()


def test_a_chip_opens_drive_in_a_new_tab_and_a_hidden_one_opens_from_the_local_map(browser, server):
    pg = _open(browser, server, 1440, 900, False)
    try:
        pg.evaluate("""() => { window._ALTO_LOCAL = {drive: {'gd-hid111': '%s'}}; var p = document.createElement('p');
          p.innerHTML = '<a href="#" class="note-link" data-src="gd-hid111" data-gdrive="gd-hid111" data-gdrive-share="0">hidden</a>'; document.body.appendChild(p); }""" % ID)
        pg.evaluate("document.documentElement.classList.remove('alto-editing')")
        pg.dispatch_event("a[data-gdrive-share='0']", "click")
        assert pg.evaluate("window.__opened") == [[f"https://drive.google.com/file/d/{ID}/view", "_blank", "noopener,noreferrer"]]
        pg.evaluate("window._ALTO_LOCAL = {}; window.__opened = [];")                     # a share: the map is empty, the chip is only words
        pg.dispatch_event("a[data-gdrive-share='0']", "click")
        assert pg.evaluate("window.__opened") == []
    finally:
        pg.context.close()


REVOKE = "https://oauth2.googleapis.com/revoke"


def test_the_picker_pages_own_csp_does_not_block_the_revoke(browser):
    """google.accounts.oauth2.revoke (Google's gsi/client) is an XHR POST of token=… to https://oauth2.googleapis.com/revoke. The picker page is served here
    with its real CSP header and makes that same request: it must go out (answered by a stand-in, nothing reaches Google) and no other googleapis address may."""
    from alto.build import drive_picker_page as PK
    ctx = browser.new_context()
    seen = []

    def route(r):
        u = r.request.url
        seen.append((r.request.method, u))
        if u == "http://alto.test/drive-picker/":
            return r.fulfill(status=200, content_type="text/html", headers={"Content-Security-Policy": PK.PICKER_CSP}, body=PK.picker_page())
        if u == REVOKE:
            return r.fulfill(status=200, content_type="application/json", headers={"Access-Control-Allow-Origin": "*"}, body="{}")
        return r.fulfill(status=404, content_type="text/plain", headers={"Access-Control-Allow-Origin": "*"}, body="")
    ctx.route("**/*", route)
    pg = ctx.new_page()
    try:
        pg.goto("http://alto.test/drive-picker/", wait_until="domcontentloaded")
        pg.evaluate("window.__v=[]; document.addEventListener('securitypolicyviolation', function(e){ window.__v.push(e.effectiveDirective + ' ' + e.blockedURI); });0")
        post = """(u) => new Promise(function(res){ var x = new XMLHttpRequest(); x.open('POST', u, true); x.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
          x.onload = function(){ res('sent ' + x.status); }; x.onerror = function(){ res('blocked'); }; try{ x.send('token=fake-token'); }catch(e){ res('blocked'); } })"""
        assert pg.evaluate(post, REVOKE) == "sent 200"
        pg.wait_for_timeout(200)
        assert pg.evaluate("window.__v") == [] and ("POST", REVOKE) in seen, seen
        for other in ("https://oauth2.googleapis.com/token", "https://oauth2.googleapis.com/revoke2/x", "https://www.googleapis.com/drive/v3/files", "https://example.com/revoke"):
            assert pg.evaluate(post, other) == "blocked", other
        pg.wait_for_timeout(200)
        v = pg.evaluate("window.__v")
        assert len(v) == 4 and all(x.startswith("connect-src") for x in v), v
        assert not [u for m, u in seen if "googleapis" in u and u != REVOKE], seen
    finally:
        ctx.close()


SIZES = [(1440, 900, False), (1280, 800, False), (390, 844, True), (844, 390, True)]


@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
@pytest.mark.parametrize("size", SIZES, ids=["1440", "1280", "phone390", "phone-landscape"])
def test_the_link_panel_wraps_its_words_clears_all_chrome_and_has_one_cancel(browser, server, size, style):
    w, h, phone = size
    pg = _open(browser, server, w, h, phone, style)
    try:
        assert _select_words_in_a_rich_field(pg)
        pg.evaluate("document.querySelector('#aed-bar [data-a=link]').click()")
        pg.wait_for_selector("#aed-link.show", timeout=5000)
        pg.wait_for_timeout(300)
        r = pg.evaluate("""() => { var p = document.getElementById('aed-link'), bad = [], vw = innerWidth, vh = innerHeight, cv = document.getElementById('canvas');
          p.querySelectorAll('*').forEach(function(e){ if(e.scrollWidth > e.clientWidth + 0 && e.clientWidth > 0 && getComputedStyle(e).display !== 'inline') bad.push(e.className + ':' + e.scrollWidth + '>' + e.clientWidth); });
          var pr = p.getBoundingClientRect(), bar = document.getElementById('aed-bar'), rail = document.getElementById('tab-rail');
          function box(e){ var q = e.getBoundingClientRect(); return [q.left, q.top, q.right, q.bottom]; }
          function seen(e){ var cs = getComputedStyle(e); if(cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity) === 0) return false;
            var q = e.getBoundingClientRect(), iw = Math.min(q.right, vw) - Math.max(q.left, 0), ih = Math.min(q.bottom, vh) - Math.max(q.top, 0); return iw > 1 && ih > 1 && iw * ih < 0.4 * vw * vh; }
          function hits(q){ return q[0] < pr.right - 0.5 && q[2] > pr.left + 0.5 && q[1] < pr.bottom - 0.5 && q[3] > pr.top + 0.5; }
          /* every fixed or sticky thing on screen that is not the panel, not the board, not a whole-window layer: the bars, the rail, the round buttons */
          var chrome = [], over = [];
          document.body.querySelectorAll('*').forEach(function(e){
            if(e === p || p.contains(e) || e === cv || cv.contains(e) || e.contains(cv)) return;
            var pos = getComputedStyle(e).position; if(pos !== 'fixed' && pos !== 'sticky') return; if(!seen(e)) return;
            for(var a = e.parentElement; a; a = a.parentElement) if(getComputedStyle(a).display === 'none') return;
            var q = box(e), name = (e.id ? '#' + e.id : e.tagName + '.' + String(e.className).slice(0, 30)); chrome.push(name); if(hits(q)) over.push(name + ' ' + q.map(Math.round)); });
          var x = p.querySelector('.al-x').getBoundingClientRect(), q = p.querySelector('.al-q').getBoundingClientRect();
          return {bad: bad, pw: p.scrollWidth - p.clientWidth, top: pr.top, bottom: pr.bottom, left: pr.left, right: pr.right, vh: vh, vw: vw,
                  chrome: chrome, over: over, barOn: bar.classList.contains('show') && chrome.indexOf('#aed-bar') >= 0,
                  rail: rail && seen(rail) ? box(rail) : null, railHit: !!(rail && seen(rail) && hits(box(rail))),
                  xq: x.left < q.right && x.right > q.left && x.top < q.bottom && x.bottom > q.top, xIn: x.top >= pr.top && x.bottom <= pr.bottom && x.left >= pr.left && x.right <= pr.right,
                  hdq: q.top - p.querySelector('.al-hd').getBoundingClientRect().bottom, hdTop: p.querySelector('.al-hd').getBoundingClientRect().top - pr.top,
                  scrolls: getComputedStyle(p).overflowY, fits: p.scrollHeight <= p.clientHeight + 1, safe: typeof (window._altoSafeBox && window._altoSafeBox.box),
                  cancels: Array.from(p.querySelectorAll('button')).filter(function(b){ return /cancel|close/i.test(b.textContent + b.getAttribute('aria-label') + b.getAttribute('data-a')); }).length,
                  help: Array.from(p.querySelectorAll('.al-fk')).map(function(e){ return e.scrollHeight <= e.clientHeight + 1 }) }; }""")
        assert r["safe"] == "function", r                # placed by the enlarge safe box, not a second copy
        assert not r["bad"] and r["pw"] <= 0, r          # no descendant overflows
        # 20px or more from every viewport edge
        assert r["left"] >= 20 - 0.5 and r["right"] <= r["vw"] - 20 + 0.5 and r["top"] >= 20 - 0.5 and r["bottom"] <= r["vh"] - 20 + 0.5, r
        assert r["barOn"], r                             # the editing toolbar is up and is one of the chrome boxes checked
        assert not r["over"] and not r["railHit"], r     # clear of the side rail and of every chrome bar
        assert r["bottom"] - r["top"] >= 60, r
        assert r["fits"] or r["scrolls"] == "auto", r    # if it does not fit, it scrolls inside
        assert not r["xq"] and r["xIn"], r               # the close X touches nothing: clear of the search field
        assert r["hdq"] >= 4 and r["hdTop"] <= 2, r       # its header row sits at the panel's top, with a gap above the search field
        assert r["cancels"] == 1, r
        assert all(r["help"]), r
        if SHOTS:
            pg.screenshot(path=os.path.join(SHOTS, f"link-box-{style}-{w}x{h}-AFTER2.png"))
    finally:
        pg.context.close()
