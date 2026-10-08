"""Renaming (1.9.60): a timeline from the ⋯ on its homepage card or, in edit mode, by clicking its name
on the timeline; a project from the pencil beside its name. Also the homepage's bottom-right toggles,
which now mirror the account toggle. The browser parts are skipped when Playwright is not installed."""
import functools
import http.server
import json
import socketserver
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from alto.build.builder import build_timeline, load_brief   # noqa: E402
from alto.build.pages import build_home                      # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None
needs_browser = pytest.mark.skipif(pw is None, reason="Playwright is not installed")
CLOUD = (ROOT / "alto" / "cloud" / "alto-cloud.js").read_text(encoding="utf-8")


@pytest.fixture(params=["chromium", "webkit"])
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


def _serve(root):
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    h.log_message = lambda *a: None
    socketserver.TCPServer.allow_reuse_address = True
    srv = socketserver.TCPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


# ── the account side: alto-cloud.js against an in-memory Firestore ──────────

PAGE = ('<!doctype html><html><head><meta charset="utf-8"><title>Torts — Alto Timeline</title>'
        '<meta name="alto-label" content="Law"></head><body><div id="title-bar"><span id="title-text">Torts</span></div>'
        "<script>var d = ['    <span id=\"nav-drawer-title\">Torts</span>',];</script>"
        '<p>Torts are mentioned in the body: Torts.</p></body></html>')


def _docs():
    pm = lambda k, tid, head, proj: {"title": proj, "heading": head, "project": proj, "tid": tid, "units": [], "search": [], "added": 1}
    return {
        "users/u1/pagemeta/k1": pm("k1", "torts", "Torts", "Law"),
        "users/u1/pagemeta/k2": pm("k2", "civ", "Civ Pro", "Law"),
        "users/u1/pagemeta/k3": pm("k3", "crim", "Crim", "Crime"),
        "users/u1/pages/k1": {"html": PAGE, "title": "Law", "tid": "torts", "shareKey": "sk1"},
        "users/u1/pages/k2": {"html": PAGE.replace("Torts", "Civ Pro"), "title": "Law", "tid": "civ"},
        "users/u1/pages/k3": {"html": PAGE.replace("Torts", "Crim").replace('"Law"', '"Crime"').replace("content=\"Law\"", "content=\"Crime\""), "title": "Crime", "tid": "crim"},
        "users/u1/alto_timelines/torts": {"data": json.dumps({"timeline_id": "torts", "project_id": "p-law", "brief": {"title": "Torts"}})},
        "users/u1/alto_timelines/civ": {"data": json.dumps({"timeline_id": "civ", "project_id": "p-law", "brief": {"title": "Civ Pro"}})},
        "users/u1/alto_projects/p-law": {"data": json.dumps({"project_id": "p-law", "name": "Law"})},
        "users/u1/alto_projects/p-crime": {"data": json.dumps({"project_id": "p-crime", "name": "Crime"})},
        "users/u1": {"pagemetaV": 1},
    }


@pytest.fixture(scope="module")
def cloud_site(tmp_path_factory):
    import test_backgrounds as tb
    from alto.cloud import emit_cloud_js
    d = tmp_path_factory.mktemp("rename")
    (d / "alto-cloud.js").write_text(emit_cloud_js({
        "apiKey": "k", "authDomain": "p.firebaseapp.com", "projectId": "p", "storageBucket": "",
        "messagingSenderId": "", "appId": "a"}), encoding="utf-8")
    (d / "sync.html").write_text('<!doctype html><html><head><meta charset="utf-8"></head><body>'
                                 '<script type="module" src="/alto-cloud.js"></script></body></html>', encoding="utf-8")
    stubs = dict(tb._STUBS)
    # pages are written compressed (Bytes): hand the same object back rather than a JSON copy of it
    stubs["firebase-firestore.js"] = stubs["firebase-firestore.js"].replace(
        "data:()=>d?JSON.parse(JSON.stringify(d)):undefined", "data:()=>d")
    # a query snapshot has forEach as well as docs
    stubs["firebase-firestore.js"] = stubs["firebase-firestore.js"].replace(
        "return {docs:ks.map(k=>({id:k.split('/').pop(), data:()=>fs.docs[k], ref:{path:k}}))};",
        "const docs=ks.map(k=>({id:k.split('/').pop(), data:()=>fs.docs[k], ref:{path:k}})); return {docs, forEach:(f)=>docs.forEach(f)};")
    # the signed-in user, as the SDK's auth object reports it
    stubs["firebase-auth.js"] = stubs["firebase-auth.js"].replace(
        "export function getAuth(){ return {}; }", "export function getAuth(){ return (window.__auth = window.__auth || {}); }").replace(
        "setTimeout(()=>cb({uid:'u1'", "setTimeout(()=>{ const u={uid:'u1'").replace(
        ",photoURL:''}),0);", ",photoURL:''}; (window.__auth=window.__auth||{}).currentUser=u; cb(u); },0);")
    srv, base = _serve(d)
    yield base, stubs
    srv.shutdown()


def _cloud_page(browser, cloud_site):
    base, stubs = cloud_site
    pg = browser.new_page()
    pg.route("https://www.gstatic.com/firebasejs/**",
             lambda r: r.fulfill(status=200, content_type="text/javascript", body=stubs[r.request.url.rsplit("/", 1)[1]]))
    pg.add_init_script("window.__fs={docs:%s,writes:[]};" % json.dumps(_docs()))
    pg.goto(base + "/sync.html"); pg.wait_for_timeout(2500)
    return pg


@needs_browser
def test_renaming_a_timeline_rewrites_its_name_where_it_lives_and_nothing_else(browser, cloud_site):
    pg = _cloud_page(browser, cloud_site)
    r = pg.evaluate("window.AltoCloud.renameTimeline('k1','torts','Torts & \"Remedies\"')")
    assert r["title"] == "Torts and “Remedies”"
    new = r["title"]
    html = pg.evaluate("window.AltoCloud.getPage('k1')")
    assert f"<title>{new} — Alto Timeline</title>" in html.replace("&quot;", '"').replace("&amp;", "&") or new in html
    assert html.count(new) == 3                                                # title, title bar, drawer
    assert "Torts are mentioned in the body: Torts." in html                   # the body is not searched and replaced
    assert 'content="Law"' in html                                             # the project is untouched
    d = pg.evaluate("window.__fs.docs")
    assert json.loads(d["users/u1/alto_timelines/torts"]["data"])["brief"]["title"] == new   # the next build keeps it
    assert d["users/u1/pagemeta/k1"]["heading"] == new and d["users/u1/pagemeta/k1"]["project"] == "Law"
    assert d["users/u1/pages/k1"]["shareKey"] == "sk1"                         # its share link is the share flow's
    assert d["users/u1/pagemeta/k2"]["heading"] == "Civ Pro"                   # a neighbour is not touched
    # a name that is only quotes and markup is refused
    with pytest.raises(Exception):
        pg.evaluate("window.AltoCloud.renameTimeline('k1','torts','   ')")
    pg.close()


@needs_browser
def test_renaming_a_project_renames_it_on_every_timeline_and_never_merges_two(browser, cloud_site):
    pg = _cloud_page(browser, cloud_site)
    r = pg.evaluate("window.AltoCloud.renameProject('Law','Law School')")
    assert r == {"project": "Law School", "moved": 2}
    d = pg.evaluate("window.__fs.docs")
    assert json.loads(d["users/u1/alto_projects/p-law"]["data"])["name"] == "Law School"       # the same record, renamed
    for k in ("k1", "k2"):
        assert d[f"users/u1/pagemeta/{k}"]["project"] == "Law School"
    html = pg.evaluate("window.AltoCloud.getPage('k2')")
    assert 'content="Law School"' in html
    assert json.loads(d["users/u1/alto_timelines/civ"]["data"])["project_id"] == "p-law"
    assert d["users/u1/pagemeta/k3"]["project"] == "Crime"                                        # another project is untouched
    # a name another project already has is refused (use Move to put a timeline in it)
    with pytest.raises(Exception) as e:
        pg.evaluate("window.AltoCloud.renameProject('Law School','crime')")
    assert "already a project called" in str(e.value)
    # a change of capitals only is allowed
    assert pg.evaluate("window.AltoCloud.renameProject('Crime','CRIME')")["moved"] == 1
    pg.close()


@needs_browser
def test_a_timeline_renamed_in_the_page_tells_the_listing(browser, cloud_site):
    pg = _cloud_page(browser, cloud_site)
    key = "abcdefghjkmnpqrstuvwxy"                         # a page key is 22 characters
    assert pg.evaluate(f"window.AltoCloud.setHeading('{key}','The Law of Torts')")
    d = pg.evaluate("window.__fs.docs")
    assert d[f"users/u1/pagemeta/{key}"]["heading"] == "The Law of Torts"
    assert not pg.evaluate("window.AltoCloud.setHeading('../../x','Nope')")
    pg.close()


# ── the homepage ────────────────────────────────────────────────────────────

FAKE_HOME = """(function(){
  var db=%s, calls=[];
  var C={enabled:true, known:true, user:{uid:'u1'}, binDays:30,
    listPages:function(){ return Promise.resolve(JSON.parse(JSON.stringify(db))); },
    listShared:function(){ return Promise.resolve([]); },
    purgeExpired:function(){ return Promise.resolve(0); },
    cleanTitle:function(s){ return s; },
    renameTimeline:function(key,tid,title){ calls.push(['t',key,tid,title]); db.forEach(function(p){ if(p.key===key) p.heading=title; }); return Promise.resolve({title:title}); },
    renameProject:function(from,to){ calls.push(['p',from,to]);
      if(/^crime$/i.test(to)) return Promise.reject(new Error('There is already a project called \\u201c'+to+'\\u201d.'));
      db.forEach(function(p){ if(p.project===from){ p.project=to; p.title=to; } }); return Promise.resolve({project:to, moved:1}); }};
  window.__calls=calls;
  Object.defineProperty(window,'AltoCloud',{get:function(){return C;}, set:function(){}, configurable:true});
  localStorage.setItem('alto-account-v1', JSON.stringify({provider:'google',name:'T',email:'t@example.com',ts:'x',v:1}));
})();""" % json.dumps([
    {"key": "k1", "tid": "torts", "title": "Law", "heading": "Torts", "project": "Law", "units": [], "search": [], "added": 1, "binned": 0},
    {"key": "k2", "tid": "civ", "title": "Law", "heading": "Civ Pro", "project": "Law", "units": [], "search": [], "added": 2, "binned": 0},
    {"key": "k3", "tid": "crim", "title": "Crime", "heading": "Crim", "project": "Crime", "units": [], "search": [], "added": 3, "binned": 0}])


@pytest.fixture(scope="module")
def home_site(tmp_path_factory):
    d = tmp_path_factory.mktemp("home")
    (d / "index.html").write_text(build_home([]), encoding="utf-8")
    srv, base = _serve(d)
    yield base
    srv.shutdown()


def _home(browser, home_site, w=1440, h=900):
    ctx = browser.new_context(viewport={"width": w, "height": h})
    ctx.add_init_script(FAKE_HOME)
    pg = ctx.new_page()
    pg.goto(home_site + "/index.html"); pg.wait_for_timeout(1500)
    return pg


@needs_browser
def test_the_homepage_renames_a_timeline_from_its_menu(browser, home_site):
    pg = _home(browser, home_site)
    tile = '.course-tile[data-key="k1"]'
    assert pg.inner_text(tile + " .tile-title") == "Torts"
    pg.hover(tile); pg.click(tile + " .tile-more"); pg.wait_for_timeout(200)
    assert pg.evaluate("[...document.querySelectorAll('.share-menu .sm-body button')].map(b=>b.textContent)")[:3] == \
        ["Rename timeline…", "Move to another project…", "Print…"]
    pg.click("text=Rename timeline…"); pg.wait_for_timeout(200)
    assert pg.input_value(".share-menu input.sm-link") == "Torts"
    pg.fill(".share-menu input.sm-link", "  Torts   and Remedies ")
    pg.keyboard.press("Enter"); pg.wait_for_timeout(600)
    assert pg.evaluate("window.__calls") == [["t", "k1", "torts", "Torts and Remedies"]]
    assert pg.evaluate("!!document.querySelector('.share-scrim')") is False
    assert pg.inner_text(tile + " .tile-title") == "Torts and Remedies"
    # an unchanged name just closes; Escape cancels
    pg.hover(tile); pg.click(tile + " .tile-more"); pg.click("text=Rename timeline…")
    pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
    assert pg.evaluate("!!document.querySelector('.share-scrim')") is False
    assert len(pg.evaluate("window.__calls")) == 1
    pg.close()


@needs_browser
def test_the_homepage_renames_a_project_from_the_pencil_and_shows_a_refusal(browser, home_site):
    pg = _home(browser, home_site)
    slab = '.private-slab[data-project="Law"]'
    pg.hover(slab); pg.click(slab + " .slab-rename"); pg.wait_for_timeout(200)
    assert pg.input_value(".share-menu input.sm-link") == "Law"
    pg.fill(".share-menu input.sm-link", "Law School"); pg.click(".share-menu .sm-row button"); pg.wait_for_timeout(600)
    assert pg.evaluate("window.__calls") == [["p", "Law", "Law School"]]
    assert pg.evaluate("[...document.querySelectorAll('.private-slab .slab-kicker')].map(e=>e.textContent)").count("Law School") == 1
    assert pg.evaluate("document.querySelectorAll('.private-slab[data-project=\"Law School\"] .course-tile[data-key]').length") == 2
    # a refusal stays in the dialog, with its reason, and nothing is drawn differently
    slab = '.private-slab[data-project="Crime"]'
    pg.hover(slab); pg.click(slab + " .slab-rename")
    pg.fill(".share-menu input.sm-link", "crime"); pg.click(".share-menu .sm-row button"); pg.wait_for_timeout(500)
    assert "already a project called" in pg.inner_text(".share-menu .sm-status")
    assert pg.evaluate("!!document.querySelector('.share-scrim')")
    pg.close()


@needs_browser
def test_the_bottom_right_toggles_mirror_the_account_toggle(browser, home_site):
    for w, h in ((1440, 900), (1180, 720), (1920, 1080)):
        pg = _home(browser, home_site, w, h)
        r = pg.evaluate("""()=>{const q=id=>document.getElementById(id).getBoundingClientRect(), a=q('account-btn'), m=q('mode-toggle'), i=q('info-btn'), s=q('search-btn');
          return {left:a.left, right:innerWidth-m.right, aB:innerHeight-a.bottom, mB:innerHeight-m.bottom,
                  gaps:[m.left-i.right, i.left-s.right], order:[s.left<i.left, i.left<m.left]}}""")
        assert abs(r["left"] - r["right"]) <= 1 and abs(r["aB"] - r["mB"]) <= 1, (w, r)       # the rightmost is the account's mirror
        assert all(10 <= g <= 14 for g in r["gaps"]) and r["order"] == [True, True], (w, r)
        pg.close()


def test_the_homepage_source_carries_the_rename_and_the_mirror():
    h = (ROOT / "alto" / "engine" / "home_template.html").read_text(encoding="utf-8")
    assert "function altoRenameTimeline" in h and "function altoRenameProject" in h and "Rename timeline…" in h
    assert "const GAP = 12.5, W = 35, INSET = 24;" in h and "EDIT_SLOT" not in h
    assert "renameTimeline: async (key, tid, title)" in CLOUD and "renameProject: async (from, to)" in CLOUD


# ── the timeline: click the name in edit mode ───────────────────────────────

EDIT_FAKE = """(function(){ var store=null; window.__heads=[];
 var C={enabled:true, known:true, user:{uid:'u1'}, getEdits:function(){ return Promise.resolve(store); },
  putEdits:function(t,d){ store=JSON.parse(JSON.stringify(d)); return Promise.resolve(); }, watchEdits:function(){ return function(){}; },
  setHeading:function(k,h){ window.__heads.push([k,h]); return Promise.resolve(true); }};
 Object.defineProperty(window,'AltoCloud',{get:function(){return C;}, set:function(){}, configurable:true}); })();"""


@pytest.fixture(scope="module")
def timeline_site(tmp_path_factory):
    d = json.loads((ROOT / "samples" / "outline_brief.json").read_text(encoding="utf-8"))
    root = tmp_path_factory.mktemp("tl")
    (root / "pv" / "abc").mkdir(parents=True)
    (root / "pv" / "abc" / "index.html").write_text(build_timeline(*load_brief(d))[0], encoding="utf-8")
    srv, base = _serve(root)
    yield base + "/pv/abc/"
    srv.shutdown()


@needs_browser
def test_clicking_the_name_in_edit_mode_renames_the_timeline(browser, timeline_site):
    ctx = browser.new_context(viewport={"width": 1400, "height": 900})
    ctx.add_init_script(EDIT_FAKE)
    pg = ctx.new_page()
    pg.goto(timeline_site); pg.wait_for_timeout(1800)
    old = pg.inner_text("#title-text")
    # outside edit mode the name is only a link to the top
    pg.click("#title-text"); pg.wait_for_timeout(200)
    assert pg.evaluate("document.activeElement && document.activeElement.id") != "title-text"
    pg.click("#alto-edit-pill .aep-manual"); pg.wait_for_timeout(400)
    pg.click("#title-text"); pg.wait_for_timeout(250)
    assert pg.evaluate("document.getElementById('title-text').classList.contains('aed-on')")
    pg.keyboard.press("Meta+a" if pg.evaluate("navigator.platform").startswith("Mac") else "Control+a")
    pg.keyboard.type("Contract Law"); pg.keyboard.press("Enter"); pg.wait_for_timeout(900)
    assert pg.inner_text("#title-text") == "Contract Law"
    assert pg.title() == "Contract Law — Alto Timeline"
    ops = pg.evaluate("JSON.parse(localStorage.getItem(Object.keys(localStorage).filter(k=>k.indexOf('alto-ed-')===0)[0])).ops")
    assert ops["bt|title"]["v"] == "Contract Law" and ops["bt|title"]["b"] == old
    assert pg.evaluate("window.__heads") == [["abc", "Contract Law"]]                 # the listing hears of it
    # undo puts the name back; reload lays the saved change over the page again
    pg.keyboard.press("Escape")
    pg.reload(); pg.wait_for_timeout(1800)
    assert pg.inner_text("#title-text") == "Contract Law"
    ctx.close()
