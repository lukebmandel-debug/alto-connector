"""'Shared with you', end to end, on a fake store (no network, no real account).

A second user's shared timeline carries a harmless marker (it only sets window.__xss) in its
title, card text, notes and unit names. The reader opens it from the share link, keeps it,
opens it again from the homepage's "Shared with you" tile, accepts the sharer's notes from a
#share= link, and opens the notes report. On the main origin the marker must never fire.

The share document is written by its owner's own client, so it can hold ANY html, not only what
the builder makes: one share here is the builder's page, the other is raw html. Both run in the
share shell's sandboxed frame, which must not reach the main origin either.
Runs in WebKit and Chromium; skipped where Playwright is missing."""
import base64
import json
from pathlib import Path

import pytest

try:
    import playwright.sync_api as pw
except Exception:  # pragma: no cover
    pw = None

from alto.build.builder import build_timeline, load_brief
from alto.build.pages import build_home
from alto.build.share_shell import shell

ROOT = Path(__file__).resolve().parent.parent
ORIGIN = "http://alto.test"
M = "window.__xss=1;try{parent.__xss=1}catch(e){};try{opener.__xss=1}catch(e){}"
TAG = '<img src=x onerror="%s">' % M
KEYS = {"title", "desc", "h", "t", "name", "role", "label", "short", "subject"}
BUILT, RAW = "sk-built-0001", "sk-raw-0002"


def _poisoned_brief():
    d = json.loads((ROOT / "samples" / "outline_brief.json").read_text(encoding="utf-8"))

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in KEYS and isinstance(v, str):
                    o[k] = v + " " + TAG
                else:
                    walk(v)
        elif isinstance(o, list):
            for x in o:
                walk(x)
    walk(d)
    return d


@pytest.fixture(scope="module")
def site():
    page = build_timeline(*load_brief(_poisoned_brief()))[0]
    raw = ("<!DOCTYPE html><html><head><title>t</title></head><body>"
           "<h1>Raw %s</h1><script>%s</script><svg onload=\"%s\"></svg></body></html>" % (TAG, M, M))
    title = "Their project " + TAG
    shares = {BUILT: {"title": title, "html": page}, RAW: {"title": title, "html": raw}}
    fake = """
(function(){
  var LS = '__fake_shared';
  function rd(){ try{ return JSON.parse(localStorage.getItem(LS) || '[]'); }catch(e){ return []; } }
  var META = %s;
  window.AltoCloud = {
    enabled: true, configured: true, known: true,
    user: { uid: 'reader-uid', displayName: 'Reader' },
    listShared: async function(){ return rd(); },
    getShare: async function(k){ var r = await fetch('/__fixture/' + encodeURIComponent(k) + '.json'); return r.ok ? r.json() : null; },
    saveShare: async function(k, t){ var a = rd().filter(function(x){ return x.key !== k; });
      a.push({ key: k, title: t, heading: META.heading, units: META.units, fmt: 'timeline', savedAt: 1 });
      localStorage.setItem(LS, JSON.stringify(a)); return true; },
    refreshShared: async function(){ return true; },
    forgetShare: async function(){ return true; },
    listPages: async function(){ return []; },
    getPage: async function(){ return null; }
  };
  if(typeof window.renderAccount === 'function') try{ window.renderAccount(); }catch(e){}
})();
""" % json.dumps({"heading": "Heading " + TAG, "units": ["#3B82F6", "Unit " + TAG, TAG]})
    files = {
        "/index.html": (build_home([]), "text/html"),
        "/alto-cloud.js": (fake, "text/javascript"),
        "/t/index.html": (page, "text/html"),
    }
    for k, v in shares.items():
        files["/s/%s/" % k] = (shell(), "text/html")
        files["/__fixture/%s.json" % k] = (json.dumps(v), "application/json")
    return files


@pytest.fixture(params=["webkit", "chromium"])
def browser(request):
    if pw is None:
        pytest.skip("Playwright is not installed")
    with pw.sync_playwright() as p:
        try:
            b = getattr(p, request.param).launch()
        except Exception as e:
            try:
                if request.param != "chromium":
                    raise e
                b = p.chromium.launch(channel="chrome")
            except Exception:
                pytest.skip(f"no {request.param}: {e}")
        yield b
        b.close()


def _ctx(browser, site):
    ctx = browser.new_context(viewport={"width": 1400, "height": 900})

    def handle(route):
        path = route.request.url[len(ORIGIN):].split("?")[0].split("#")[0]
        if path in ("", "/"):
            path = "/index.html"
        if path not in site:
            route.fulfill(status=404, body="")      # nothing leaves the machine
            return
        body, ctype = site[path]
        route.fulfill(status=200, body=body, content_type=ctype)
    ctx.route("**/*", handle)
    ctx.add_init_script("""
      try{ localStorage.setItem('alto-account-v1', JSON.stringify({provider:'google', name:'Reader', email:'reader@example.test', v:1})); }catch(e){}
    """)
    return ctx


def _page(ctx):
    pg = ctx.new_page()
    pg.on("dialog", lambda d: d.dismiss())
    return pg


def _stage(pg):
    pg.wait_for_selector("#stage.on", timeout=15000)
    pg.wait_for_timeout(2500)
    fr = [f for f in pg.frames if f is not pg.main_frame]
    assert fr, "the shared page never rendered in the stage frame"
    return fr[0]


def _main_clean(pg):
    assert pg.evaluate("window.__xss") is None


def test_a_share_link_and_its_shared_with_you_tile_run_nothing_on_the_main_origin(browser, site):
    ctx = _ctx(browser, site)
    pg = _page(ctx)
    # 1. the share link (the builder's page, poisoned in title, cards and unit names)
    pg.goto(ORIGIN + "/s/%s/" % BUILT)
    fr = _stage(pg)
    _main_clean(pg)
    assert fr.evaluate("window.__xss") is None          # the builder kept it inert even inside the sandbox
    assert fr.evaluate("origin") == "null"               # opaque origin: no storage, no cookies, no parent
    # keep it ("Save to my Alto")
    pg.wait_for_selector("#pill.on", timeout=8000)
    pg.click("#pill")
    pg.wait_for_timeout(800)
    assert len(pg.evaluate("JSON.parse(localStorage.getItem('__fake_shared')||'[]')")) == 1
    _main_clean(pg)
    # 2. the homepage's "Shared with you" tile
    pg.goto(ORIGIN + "/index.html")
    pg.wait_for_selector(".shared-group .course-tile", timeout=10000)
    pg.wait_for_timeout(800)
    _main_clean(pg)
    grp = ".shared-group"
    assert pg.evaluate("document.querySelectorAll('%s img, %s svg [onload], %s [onerror], %s script').length"
                       % (grp, grp, grp, grp)) == 0
    assert "onerror" in pg.evaluate("document.querySelector('.shared-group .tile-title').textContent")  # shown as text
    pg.click(".shared-group .course-tile")
    fr = _stage(pg)
    assert pg.url.startswith(ORIGIN + "/s/%s/" % BUILT)
    _main_clean(pg)
    assert fr.evaluate("window.__xss") is None
    ctx.close()


def test_a_raw_hostile_share_stays_inside_the_sandbox(browser, site):
    """The owner can upload any html as their share: it may run in its own opaque frame, never here."""
    ctx = _ctx(browser, site)
    pg = _page(ctx)
    pg.goto(ORIGIN + "/s/%s/" % RAW)
    fr = _stage(pg)
    assert fr.evaluate("origin") == "null"
    _main_clean(pg)
    assert pg.evaluate("document.querySelectorAll('#gate img, #pill img, #gate [onerror]').length") == 0
    ctx.close()


def test_accepting_a_sharers_notes_and_opening_the_report_runs_nothing(browser, site):
    """The sharer's #share= link with poisoned notes, opened on a timeline on the main origin."""
    from tests.test_xss_notes import BAD, NESTED
    hls = [{"quote": "Q %d %s" % (i, b), "note": "N %d %s" % (i, b), "color": "yellow", "kind": "highlight", "ts": 5 + i}
           for i, b in enumerate(BAD + [NESTED])]
    payload = {"v": 1, "course": "x", "notes": True, "highlights": hls}
    raw = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    ctx = _ctx(browser, site)
    pg = _page(ctx)
    pg.goto(ORIGIN + "/t/index.html#share=j:" + raw)
    pg.wait_for_selector("#share-import-overlay [data-act]", timeout=10000)
    _main_clean(pg)
    assert pg.evaluate("document.querySelectorAll('#share-import-overlay img, #share-import-overlay svg, #share-import-overlay [onerror]').length") == 0
    with pg.expect_navigation():
        pg.click("#share-import-overlay [data-act=replace], #share-import-overlay [data-act=merge]")
    pg.wait_for_timeout(1500)
    _main_clean(pg)
    pg.evaluate("toggleNotes()")
    pg.wait_for_timeout(800)
    _main_clean(pg)
    assert pg.locator("#notes-list .note-item").count() == len(hls)
    with ctx.expect_page() as info:
        pg.evaluate("generateNotesReport()")
    rp = info.value
    rp.wait_for_load_state()
    rp.wait_for_timeout(800)
    assert rp.evaluate("window.__xss") is None and pg.evaluate("window.__xss") is None
    assert rp.evaluate("window.opener") is None
    assert rp.evaluate("document.querySelectorAll('.hl-block img, .hl-block svg, .hl-block math, .hl-block script, .hl-block a, .hl-block [onerror]').length") == 0
    ctx.close()
