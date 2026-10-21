"""Imported backgrounds (alto/build/backgrounds_import.py): a picture of the user's own,
resized and compressed in the browser, kept in their own account (users/{uid}/bglib +
bgimg) and in this browser (localStorage library + IndexedDB bytes), offered in the
picker beside the built-in ones, renamed and removed (asked first) by its owner, and
drawn by a page that never carries it. The browser parts run the real alto-cloud.js
against an in-memory Firestore and are skipped when Playwright is not installed."""
import base64
import http.server
import io
import json
import re
import shutil
import socketserver
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import backgrounds as bg                       # noqa: E402
from alto.build import backgrounds_import as bi                # noqa: E402
from alto.build.builder import build_timeline, load_brief      # noqa: E402
from alto.build.private_shell import stored_bytes              # noqa: E402

OUTLINE = ROOT / "samples" / "outline_brief.json"
CLOUD = (ROOT / "alto" / "cloud" / "alto-cloud.js").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def timeline():
    d = json.loads(OUTLINE.read_text(encoding="utf-8"))
    brief, nodes, conns = load_brief(d)
    return build_timeline(brief, nodes, conns)[0], brief.timeline_id


# ── what a page carries, and what it does not ──────────────────────────────

def test_a_page_names_the_library_and_its_script_but_carries_no_picture(timeline):
    html = timeline[0]
    head = re.search(r'<script id="alto-bg-head">(.*?)</script>', html, re.S).group(1)
    assert json.dumps(bg.LIB_KEY) in head and json.dumps(bg.LIB_PATH) in head
    assert bi.lib_js()[:200] not in html                       # the import lives on the site, not in the page
    assert "data:image/jpeg" not in html and "data:image/webp" not in html


def test_the_emitted_blocks_carry_no_comments_or_indentation(timeline):
    html = timeline[0]
    for sid in ("alto-bg-head", "alto-bg-ui"):
        js = re.search(r'<script id="%s">(.*?)</script>' % sid, html, re.S).group(1)
        assert not any(ln.startswith((" ", "//")) for ln in js.split("\n")), sid
    css = re.search(r'<style id="alto-bg-css">(.*?)</style>', html, re.S).group(1)
    assert "/*" not in css


def test_the_emitted_blocks_cost_less_than_their_source():
    """What the import added to the head and picker scripts is paid for by leaving their comments and indentation
    out of the page (measured as stored, gzipped, bytes; the whole page is checked against a build before it)."""
    head_now = bg.head_block("alto-hl-x-bg", palace=True)
    ui_now = bg.ui_block("This timeline", rail=True)
    src = bg.HEAD_JS.replace("__CATALOG__", bg.catalog_json(True)) + bg.CSS + bg.UI_CSS + bg.UI_JS
    assert stored_bytes(head_now + ui_now) < stored_bytes(src) - 600


def test_the_site_serves_the_script_beside_the_sync_layer(tmp_path):
    name, text = bi.site_file()
    assert "/" + name == bg.LIB_PATH and text.startswith("(function(){")
    for k in ("__LIBKEY__", "__EDGE__", "__MAXB__", "__MAXF__"):
        assert k not in text
    assert "MAXB=%d" % bi.MAX_BYTES in text and bi.MAX_BYTES < 1048576 - 60000   # one Firestore document, with room


def test_the_account_layer_keeps_imports_under_the_owners_own_records():
    assert "collection(db, 'users', auth.currentUser.uid, 'bglib')" in CLOUD
    assert "doc(db, 'users', auth.currentUser.uid, coll, k)" in CLOUD
    assert "const BG_MAX = 950000;" in CLOUD
    # signing out takes this browser's copies of them too
    assert "localStorage.removeItem('alto-bg-lib-v1'); indexedDB.deleteDatabase('alto-bg-lib');" in CLOUD
    # a share (world-readable) never names them
    assert "bglib" not in (ROOT / "firestore.rules").read_text(encoding="utf-8").split("match /shares/")[1]


# ── in a browser ────────────────────────────────────────────────────────────

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None


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


# A stand-in for the Firebase SDK: auth signs in as u1 unless window.__signedOut, and Firestore is
# window.__fs.docs, where a field {__b64: ...} is read back as Bytes (so a second "device" can be given
# what the first one stored).
_STUBS = {
    "firebase-app.js": "export function initializeApp(c){ return {c}; }",
    "firebase-auth.js": """
export function getAuth(){ return window.__auth = window.__auth || {currentUser:null}; }
export class GoogleAuthProvider {}
export async function signInWithPopup(){ window.__signIns=(window.__signIns||0)+1; } export async function signInWithRedirect(){}
export async function getRedirectResult(){ return null; } export async function signOut(){}
export const browserLocalPersistence = {}; export async function setPersistence(){}
export function onAuthStateChanged(a, cb){ setTimeout(()=>{ const u = window.__signedOut ? null : {uid:'u1',displayName:'T',email:'t@example.com',photoURL:''}; window.__auth.currentUser=u; cb(u); },0); return ()=>{}; }
""",
    "firebase-firestore.js": """
const fs = window.__fs; const ls = [];
export class Bytes { static fromUint8Array(a){ const b=new Bytes(); b.a=a; return b; } toUint8Array(){ return this.a; } }
const unb = (v) => { const o = {}; for (const k in v) { const x = v[k]; o[k] = x && x.__b64 ? Bytes.fromUint8Array(Uint8Array.from(atob(x.__b64), c=>c.charCodeAt(0))) : x; } return o; };
const snap = (ref) => { const d = fs.docs[ref.path]; return {exists:()=>!!d, data:()=>d?unb(d):undefined, id:ref.id, ref, metadata:{hasPendingWrites:false}}; };
const kids = (c) => Object.keys(fs.docs).filter(k=>k.startsWith(c.path+'/') && k.split('/').length===c.path.split('/').length+1);
const fire = (L) => { if(L.ref.kind==='col'){ const ks=kids(L.ref); L.cb({metadata:{hasPendingWrites:false}, forEach:f=>ks.forEach(k=>f({id:k.split('/').pop(), data:()=>unb(fs.docs[k]), ref:{path:k}}))}); } else L.cb(snap(L.ref)); };
const notify = (path) => ls.forEach(L=>{ if((L.ref.kind==='doc'&&L.ref.path===path)||(L.ref.kind==='col'&&path.startsWith(L.ref.path+'/'))) setTimeout(()=>fire(L),0); });
export function getFirestore(){ return {}; }
export function doc(db, ...s){ return {path:s.join('/'), id:s[s.length-1], kind:'doc'}; }
export function collection(db, ...s){ return {path:s.join('/'), kind:'col'}; }
export async function getDoc(ref){ return snap(ref); }
export async function getDocs(c){ const ks=kids(c); return {docs:ks.map(k=>({id:k.split('/').pop(), data:()=>unb(fs.docs[k]), ref:{path:k}}))}; }
// Firestore's own limit: 1 MiB per document, counting the name, field names and values (Bytes at their raw length)
const sizeOf = (path, d) => { let n = path.length + 1 + 16 + 32; for (const k in d) { const v = d[k]; n += k.length + 1 + (v && v.a instanceof Uint8Array ? v.a.length : typeof v === 'string' ? new TextEncoder().encode(v).length + 1 : typeof v === 'boolean' ? 1 : 8); } return n; };
export async function setDoc(ref, data, o){ if(window.__fail) throw new Error(window.__fail); { const all=(o&&o.merge) ? Object.assign({},fs.docs[ref.path]||{},data) : data; const n=sizeOf(ref.path, all); fs.sizes=fs.sizes||{}; fs.sizes[ref.path]=n; if(n>1048576) throw new Error('invalid-argument: document is '+n+' bytes, over 1048576'); } const cur=fs.docs[ref.path]||{}; fs.docs[ref.path] = (o&&o.merge) ? Object.assign({},cur,data) : Object.assign({},data); fs.writes.push(ref.path); notify(ref.path); }
export async function deleteDoc(ref){ delete fs.docs[ref.path]; fs.deletes.push(ref.path); notify(ref.path); }
export function onSnapshot(ref, cb){ const L={ref,cb}; ls.push(L); setTimeout(()=>fire(L),0); return ()=>{ const i=ls.indexOf(L); if(i>=0) ls.splice(i,1); }; }
export function serverTimestamp(){ return Date.now(); }
""",
}

# what the in-memory Firestore holds, with Bytes as base64 (to hand to another "device")
DUMP = """()=>{ const o={}; for(const k in window.__fs.docs){ const d=window.__fs.docs[k], c={};
  for(const f in d){ const x=d[f]; if(x && x.a instanceof Uint8Array){ let s=''; for(let i=0;i<x.a.length;i+=8192) s+=String.fromCharCode.apply(null, x.a.subarray(i,i+8192)); c[f]={__b64:btoa(s), n:x.a.length}; } else c[f]=x; }
  o[k]=c; } return o; }"""

STATE = """()=>({on:document.documentElement.classList.contains('alto-bg'), id:window._altoBgId||'',
  img:getComputedStyle(document.documentElement).getPropertyValue('--alto-bg').trim(),
  lib:JSON.parse(localStorage.getItem('alto-bg-lib-v1')||'{}')})"""


def _picture(path, w=3000, h=2000):
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(im)
    for y in range(0, h, 4):                     # a sky that darkens downward, a sun, hills: something with detail
        d.rectangle([0, y, w, y + 4], fill=(40 + y * 120 // h, 90 + y * 60 // h, 200 - y * 120 // h))
    d.ellipse([w * .62, h * .18, w * .78, h * .42], fill=(255, 214, 120))
    for i in range(0, w, 7):
        d.line([i, h * .7 + (i * 37 % 101), i, h], fill=(30 + i % 50, 110 + i % 70, 60))
    im.save(path, "JPEG", quality=95)
    return path


@pytest.fixture(scope="module")
def site(timeline, tmp_path_factory):
    if pw is None:
        pytest.skip("Playwright is not installed")
    pytest.importorskip("PIL")
    from alto.cloud import emit_cloud_js
    from alto.hosted import hosted_timeline
    d = tmp_path_factory.mktemp("bgsite")
    html, tid = timeline
    (d / "t.html").write_text(hosted_timeline(html, tid), encoding="utf-8")
    shutil.copytree(ROOT / "alto" / "assets" / "backgrounds", d / "bg" / f"v{bg.BG_V}")
    (d / "alto-cloud.js").write_text(emit_cloud_js({
        "apiKey": "k", "authDomain": "p.firebaseapp.com", "projectId": "p", "storageBucket": "",
        "messagingSenderId": "", "appId": "a"}), encoding="utf-8")
    name, text = bi.site_file()
    (d / name).write_text(text, encoding="utf-8")
    _picture(d / "beach.jpg")
    from PIL import Image                            # noise: compresses worst, so it lands at the cap
    import random
    rnd = random.Random(7)
    Image.frombytes("RGB", (3000, 2000), bytes(rnd.getrandbits(8) for _ in range(3000 * 2000 * 3))).save(d / "noise.png")
    (d / "notes.pdf").write_bytes(b"%PDF-1.4 not a picture")
    (d / "broken.jpg").write_bytes(b"\xff\xd8\xff\xe0 truncated")

    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(d), **k)

        def log_message(self, *a):
            pass
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), H)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", tid, d
    srv.shutdown()
    srv.server_close()


def _page(ctx, base, docs=None, signed_out=False):
    pg = ctx.new_page()
    pg.route("https://www.gstatic.com/firebasejs/**",
             lambda r: r.fulfill(status=200, content_type="text/javascript",
                                 body=_STUBS[r.request.url.rsplit("/", 1)[1]]))
    pg.add_init_script("window.__fs={docs:%s,writes:[],deletes:[]};%s"
                       % (json.dumps(docs or {}), "window.__signedOut=true;" if signed_out else ""))
    pg.goto(base + "/t.html")
    pg.wait_for_function("window.AltoCloud && window.AltoCloud.known", timeout=15000)
    pg.wait_for_timeout(400)
    return pg


def _open_import(pg):
    pg.click("#bg-toggle")
    pg.wait_for_selector("#bg-yours .bg-add", timeout=8000)
    pg.click("#bg-yours .bg-add")
    pg.wait_for_selector("#bg-panel .bg-imp .bg-zone")


def _import(pg, path, name=None, shot=None):
    _open_import(pg)
    pg.set_input_files("#bg-panel .bg-zone input[type=file]", str(path))
    pg.wait_for_selector("#bg-panel .bg-fr img", timeout=8000)
    pg.wait_for_timeout(300)
    box = pg.locator("#bg-panel .bg-fr").bounding_box()
    pg.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    pg.mouse.down(); pg.mouse.move(box["x"] + box["width"] / 2 - 40, box["y"] + box["height"] / 2 + 10, steps=5); pg.mouse.up()
    pg.locator("#bg-panel .bg-row input[type=range]").fill("1.3")
    if name:
        pg.fill("#bg-panel .bg-ed .bg-in", name)
    if shot:
        pg.screenshot(path=str(shot))
    pg.click("#bg-panel .bg-go")
    pg.wait_for_function("!document.querySelector('#bg-panel .bg-imp')", timeout=30000)
    pg.wait_for_function("(getComputedStyle(document.documentElement).getPropertyValue('--alto-bg')||'').indexOf('blob:')>=0",
                         timeout=10000)


def test_import_store_choose_reload_and_open_on_another_device(browser, site, tmp_path):
    base, tid, d = site
    ctx = browser.new_context(viewport={"width": 1400, "height": 860})
    pg = _page(ctx, base)
    _import(pg, d / "beach.jpg", name="Beach at dusk")
    s = pg.evaluate(STATE)
    assert s["on"] and s["id"].startswith("u:") and "blob:" in s["img"]
    key = s["id"][2:]
    e = s["lib"][s["id"]]
    assert e["n"] == "Beach at dusk" and e["k"] == "p" and e["u"] == 1 and e["th"].startswith("data:image/jpeg")
    assert max(e["l"]["w"], e["l"]["h"]) <= bi.EDGE and e["l"]["w"] / e["l"]["h"] == pytest.approx(1.5, abs=.01)
    assert e["l"]["w"] == round(3000 / 1.3)                     # zoomed in 1.3x: cropped to that, never enlarged
    assert 0 < e["l"]["x"] < 1 and e["l"]["q"].startswith("#") and e["d"]["v"] >= .2
    # the timeline's choice is the account's too, by id
    pg.wait_for_timeout(800)
    assert pg.evaluate(f"window.__fs.docs['users/u1/tl/{tid}']")["bg"] == s["id"]
    fs = pg.evaluate(DUMP)
    img = fs[f"users/u1/bgimg/{key}"]
    assert 10_000 < img["d"]["n"] <= bi.MAX_BYTES and img["type"] in ("image/webp", "image/jpeg")
    rec = fs[f"users/u1/bglib/{key}"]
    assert rec["del"] is False and json.loads(rec["e"])["n"] == "Beach at dusk"
    # the tile sits in "Yours", chosen
    assert pg.locator(f'#bg-yours .bg-tile[data-bg="{s["id"]}"].active').count() == 1
    # reload: drawn again from this browser's own copies
    pg.reload(); pg.wait_for_function("(getComputedStyle(document.documentElement).getPropertyValue('--alto-bg')||'').indexOf('blob:')>=0",
                                      timeout=10000)
    assert pg.evaluate(STATE)["id"] == s["id"]
    pg.close(); ctx.close()
    # another device: nothing in this browser; the choice and the picture come from the account
    ctx2 = browser.new_context(viewport={"width": 1400, "height": 860})
    pg2 = _page(ctx2, base, docs=fs)
    pg2.wait_for_function("(getComputedStyle(document.documentElement).getPropertyValue('--alto-bg')||'').indexOf('blob:')>=0",
                          timeout=15000)
    s2 = pg2.evaluate(STATE)
    assert s2["id"] == s["id"] and s2["lib"][s["id"]]["n"] == "Beach at dusk"
    ctx2.close()


def test_rename_and_remove_are_the_owners_and_removing_is_asked_first(browser, site):
    base, tid, d = site
    ctx = browser.new_context(viewport={"width": 1400, "height": 860})
    pg = _page(ctx, base)
    _import(pg, d / "beach.jpg", name="Shore")
    uid = pg.evaluate("window._altoBgId")
    # built-in tiles have no rename/remove control
    assert pg.locator("#bg-panel .bg-tile:not(.bg-mine) .bg-more").count() == 0
    # rename, from the credit line
    pg.click("#bg-panel .bg-foot .bg-lnk:has-text('Rename')")
    pg.fill("#bg-yours .bg-mng .bg-in", "Shore at noon")
    pg.click("#bg-yours .bg-mng .bg-go")
    pg.wait_for_function("JSON.parse(localStorage.getItem('alto-bg-lib-v1'))[%r].n==='Shore at noon'" % uid, timeout=8000)
    assert json.loads(pg.evaluate(f"window.__fs.docs['users/u1/bglib/{uid[2:]}'].e"))["n"] == "Shore at noon"
    # remove: asked first, Keep changes nothing
    pg.click(f'#bg-yours .bg-tile[data-bg="{uid}"] .bg-more')
    pg.click("#bg-yours .bg-mng .bg-btn:has-text('Remove')")
    assert "Remove “Shore at noon”" in pg.inner_text("#bg-yours .bg-mng")
    pg.click("#bg-yours .bg-mng .bg-btn:has-text('Keep it')")
    assert pg.evaluate(f"!!window.__fs.docs['users/u1/bgimg/{uid[2:]}']")
    pg.click(f'#bg-yours .bg-tile[data-bg="{uid}"] .bg-more')
    pg.click("#bg-yours .bg-mng .bg-btn:has-text('Remove')")
    pg.click("#bg-yours .bg-mng .bg-go")
    pg.wait_for_function("!JSON.parse(localStorage.getItem('alto-bg-lib-v1'))[%r]" % uid, timeout=8000)
    assert pg.evaluate(f"window.__fs.docs['users/u1/bglib/{uid[2:]}'].del") is True
    assert pg.evaluate(f"!window.__fs.docs['users/u1/bgimg/{uid[2:]}']")
    assert not pg.evaluate(STATE)["on"]                         # the timeline that used it: the Alto wallpaper
    assert pg.locator(f'#bg-yours .bg-tile[data-bg="{uid}"]').count() == 0
    ctx.close()


def test_errors_say_what_happened_and_what_to_do(browser, site, tmp_path):
    base, tid, d = site
    ctx = browser.new_context(viewport={"width": 1400, "height": 860})
    pg = _page(ctx, base)
    _open_import(pg)
    pg.set_input_files("#bg-panel .bg-zone input[type=file]", str(d / "notes.pdf"))
    assert "Choose a JPG, PNG, WebP or HEIC" in pg.inner_text("#bg-panel .bg-err")
    pg.set_input_files("#bg-panel .bg-zone input[type=file]", str(d / "broken.jpg"))
    pg.wait_for_selector("#bg-panel .bg-err:has-text('couldn')", timeout=8000)
    big = tmp_path / "huge.jpg"
    with open(big, "wb") as f:
        f.seek(bi.MAX_FILE + 1024); f.write(b"\0")
    pg.set_input_files("#bg-panel .bg-zone input[type=file]", str(big))
    assert "MB; Alto opens pictures up to 60 MB" in pg.inner_text("#bg-panel .bg-err")
    # offline at Save: the picture stays, the message says to connect and save again
    pg.set_input_files("#bg-panel .bg-zone input[type=file]", str(d / "beach.jpg"))
    pg.wait_for_selector("#bg-panel .bg-fr img")
    ctx.set_offline(True)
    pg.click("#bg-panel .bg-go")
    assert "offline" in pg.inner_text("#bg-panel .bg-err")
    assert pg.locator("#bg-panel .bg-fr img").count() == 1
    ctx.set_offline(False)
    # the account refuses: said plainly, and the picture is still there to try again
    pg.evaluate("window.__fail='FirebaseError: permission-denied'")
    pg.click("#bg-panel .bg-go")
    pg.wait_for_selector("#bg-panel .bg-err:has-text('refused')", timeout=8000)
    assert pg.evaluate("Object.keys(JSON.parse(localStorage.getItem('alto-bg-lib-v1')||'{}')).length") == 0
    ctx.close()
    # signed out: a Sign in button, right there
    ctx = browser.new_context(viewport={"width": 1400, "height": 860})
    pg = _page(ctx, base, signed_out=True)
    _open_import(pg)
    assert "Sign in to keep your own backgrounds" in pg.inner_text("#bg-panel .bg-err")
    pg.click("#bg-panel .bg-err .bg-go")
    assert pg.evaluate("window.__signIns") == 1
    ctx.close()


def test_a_dropped_picture_opens_the_import(browser, site):
    base, tid, d = site
    ctx = browser.new_context(viewport={"width": 1400, "height": 860})
    pg = _page(ctx, base)
    pg.click("#bg-toggle"); pg.wait_for_selector("#bg-yours .bg-add")
    b64 = base64.b64encode((d / "beach.jpg").read_bytes()).decode()
    pg.evaluate("""(b)=>{ const s=atob(b), u=new Uint8Array(s.length); for(let i=0;i<s.length;i++) u[i]=s.charCodeAt(i);
      const dt=new DataTransfer(); dt.items.add(new File([u],'lake.jpg',{type:'image/jpeg'}));
      const p=document.getElementById('bg-panel'); p.dispatchEvent(new DragEvent('dragover',{dataTransfer:dt,bubbles:true,cancelable:true}));
      p.dispatchEvent(new DragEvent('drop',{dataTransfer:dt,bubbles:true,cancelable:true})); }""", b64)
    pg.wait_for_selector("#bg-panel .bg-fr img", timeout=8000)
    assert pg.input_value("#bg-panel .bg-ed .bg-in") == "lake"
    ctx.close()


def test_a_picture_at_the_size_limit_saves_as_bytes_under_firestores_cap_and_syncs(browser, site):
    """The worst case: pure noise, which no quality setting shrinks much. It is stepped down until it fits
    MAX_BYTES, stored as Bytes (raw, not base64), and its document stays under Firestore's 1 MiB."""
    base, tid, d = site
    ctx = browser.new_context(viewport={"width": 1400, "height": 860})
    pg = _page(ctx, base)
    _import(pg, d / "noise.png", name="Static")
    uid = pg.evaluate("window._altoBgId")
    n = pg.evaluate(f"window.__fs.docs['users/u1/bgimg/{uid[2:]}'].d.a.length")
    size = pg.evaluate(f"window.__fs.sizes['users/u1/bgimg/{uid[2:]}']")
    assert pg.evaluate(f"window.__fs.docs['users/u1/bgimg/{uid[2:]}'].d.a instanceof Uint8Array")
    assert 700_000 < n <= bi.MAX_BYTES and size < 1048576, (n, size)
    pg.wait_for_timeout(800)
    fs = pg.evaluate(DUMP)
    ctx.close()
    ctx2 = browser.new_context(viewport={"width": 1400, "height": 860})
    pg2 = _page(ctx2, base, docs=fs)
    pg2.wait_for_function("(getComputedStyle(document.documentElement).getPropertyValue('--alto-bg')||'').indexOf('blob:')>=0",
                          timeout=20000)
    assert pg2.evaluate("window._altoBgId") == uid
    ctx2.close()
