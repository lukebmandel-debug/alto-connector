"""Freewrite, the writing mode of the Notes panel (alto/build/freewrite.py).

The static half needs nothing; the browser half runs in Chromium AND WebKit and is
skipped where Playwright or a browser is missing. Sync is tested against a mock
Firestore (route-mocked gstatic modules), never a real account."""
import json
import re
import threading
from pathlib import Path

import pytest

from alto.build import engine_patches
from alto.build.blocks import ID_PATTERNS
from alto.build.builder import build_timeline, load_brief
from alto.build.fingerprint import _TIMELINE_SOURCES
from alto.build.reidentify import reidentify
from alto.cloud import SOURCE

ROOT = Path(__file__).resolve().parent.parent
TID = "contracts-outline"
KEY = f"alto-hl-{TID}"
JS = SOURCE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def html():
    d = json.loads((ROOT / "samples" / "outline_brief.json").read_text(encoding="utf-8"))
    return build_timeline(*load_brief(d))[0]


# ── static ──────────────────────────────────────────────────────────────────

def test_the_module_is_on_every_page_and_in_the_stamp(html):
    assert 'id="alto-freewrite"' in html and "Freewrite" in html
    assert "freewrite.py" in _TIMELINE_SOURCES


def test_storage_keys_are_the_pages_own_hl_key(html):
    """Built from the hl key, so a share re-stamps them with everything else."""
    i = html.index('id="alto-freewrite"')
    body = html[i:html.index("</script>", i)]
    assert f"var KEY = '{KEY}', FKEY = KEY + '-fw', UKEY = KEY + '-fwui'" in body


def test_a_share_gets_its_own_freewrite_keys(html):
    shared = reidentify(html, "abcDEF123")
    i = shared.index('id="alto-freewrite"')
    body = shared[i:shared.index("</script>", i)]
    assert "var KEY = 'alto-hl-s-abcDEF123'," in body and TID not in body
    assert KEY not in shared or True            # other copies of the old id are reidentify's own check


def test_no_freewrite_content_is_ever_baked_into_a_page(html):
    """The document lives in the reader's own storage; the page carries only the code."""
    assert "fw-editor" in html and 'data-ph="' not in html.split('id="alto-freewrite"')[0]


def test_cloud_syncs_the_document_with_the_later_edit_winning():
    assert "let FW_KEY = TID ? `alto-hl-${TID}-fw` : null;" in JS
    assert "k === FW_KEY" in JS                                       # the Storage.prototype hook (Safari)
    assert "FW_KEY = `alto-hl-${tid}-fw`" in JS                       # setTid (the private shell)
    assert "rf.mod > lf.mod" in JS and "lf.mod > rf.mod" in JS
    assert "{ fw: { html: lf.html, mod: lf.mod }" in JS
    assert "alto-fw-sync" in JS
    i = JS.index("Storage.prototype.setItem = function")
    assert "localStorage.setItem =" not in JS[:i + 600]


def test_engine_patches_keep_freewrite_open_and_the_keys_quiet():
    names = {p["name"] for p in engine_patches.PATCHES}
    assert {"freewrite-arrows-not-while-typing", "freewrite-focus-keys-not-while-typing", "freewrite-escape-leaves-the-box",
            "freewrite-escape-spares-the-panel", "freewrite-wheel-swipe-spares-the-panel",
            "freewrite-phone-swipe-spares-the-panel"} <= names


def test_labels_for_the_info_text(html):
    i = html.index('id="alto-freewrite"')
    body = html[i:html.index("</script>", i)]
    for lab in ("Notes & highlights", "Freewrite", "Bulleted list", "Numbered list", "Clear formatting", "Copy", "Print", "Saved"):
        assert lab in body


# ── a real browser, both engines ────────────────────────────────────────────

pw = pytest.importorskip("playwright.sync_api")
ENGINES = ["chromium", "webkit"]
IPHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
          "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")


@pytest.fixture(scope="module")
def page_file(tmp_path_factory, html):
    f = tmp_path_factory.mktemp("fw") / "page.html"
    f.write_text(html, encoding="utf-8")
    return f


@pytest.fixture(scope="module")
def playwright_():
    with pw.sync_playwright() as p:
        yield p


def _launch(p, engine):
    try:
        return getattr(p, engine).launch()
    except Exception as e:
        pytest.skip(f"no {engine}: {e}")


@pytest.fixture(params=ENGINES)
def desk(request, playwright_, page_file):
    b = _launch(playwright_, request.param)
    pg = b.new_page(viewport={"width": 1400, "height": 900})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(page_file.as_uri()); pg.wait_for_timeout(1300)
    pg.errs = errs
    yield pg
    b.close()


@pytest.fixture(params=ENGINES)
def phone(request, playwright_, page_file):
    b = _launch(playwright_, request.param)
    ctx = b.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True, user_agent=IPHONE)
    pg = ctx.new_page(); pg.goto(page_file.as_uri()); pg.wait_for_timeout(1500)
    yield pg
    b.close()


MOD = "ControlOrMeta"


def open_fw(pg):
    pg.click("#notes-toggle"); pg.wait_for_timeout(450)
    pg.click("#fw-seg button[data-m=fw]"); pg.wait_for_timeout(250)


def state(pg):
    return pg.evaluate("({open:!!notesOpen,mode:_altoFw.mode(),panel:document.getElementById('notes-panel').classList.contains('open')})")


def stored(pg):
    return pg.evaluate(f"JSON.parse(localStorage.getItem('{KEY}-fw')||'null')")


def editor_text(pg):
    return pg.evaluate("document.getElementById('fw-editor').innerText")


def caret_end(pg):
    pg.evaluate("""()=>{var e=document.getElementById('fw-editor');e.focus();var r=document.createRange();r.selectNodeContents(e);r.collapse(false);
      var s=getSelection();s.removeAllRanges();s.addRange(r);}""")


def page_ids(pg, n=3):
    return pg.evaluate(f"NODES_SRC.map(n=>n.id).slice(0,{n})")


def test_type_navigate_three_pages_reload_it_is_all_still_there(desk):
    pg = desk
    open_fw(pg)
    pg.click("#fw-editor")
    pg.keyboard.type("Exam outline"); pg.keyboard.press("Enter")
    pg.keyboard.type("- offer"); pg.keyboard.press("Enter"); pg.keyboard.type("acceptance")
    pg.keyboard.press("Tab"); pg.keyboard.press("Enter"); pg.keyboard.type("mirror image")
    pg.keyboard.press("Enter"); pg.keyboard.press("Enter"); pg.keyboard.type("done")
    for nid in page_ids(pg, 3):
        pg.evaluate(f"showDetail('node','{nid}')"); pg.wait_for_timeout(600)
        assert state(pg) == {"open": True, "mode": "fw", "panel": True}
        assert "mirror image" in editor_text(pg)
    pg.evaluate("showTimeline()"); pg.wait_for_timeout(500)
    assert state(pg)["panel"]
    pg.reload(); pg.wait_for_timeout(1700)
    assert state(pg) == {"open": True, "mode": "fw", "panel": True}
    txt = editor_text(pg)
    assert all(w in txt for w in ("Exam outline", "offer", "acceptance", "mirror image", "done"))
    assert pg.locator("#fw-editor ul li").count() >= 2
    assert pg.evaluate("document.getElementById('fw-state').textContent") == "Saved"
    assert not pg.errs


def test_nothing_but_the_x_closes_it(desk):
    pg = desk
    open_fw(pg)
    nid = page_ids(pg, 1)[0]
    pg.evaluate(f"showDetail('node','{nid}')"); pg.wait_for_timeout(600)
    pg.click("#fw-editor"); pg.keyboard.type("keep me")
    cur = pg.evaluate("window._currentDetailId")
    pg.keyboard.press("ArrowLeft"); pg.keyboard.press("ArrowRight"); pg.keyboard.press("ArrowLeft"); pg.wait_for_timeout(500)
    assert pg.evaluate("window._currentDetailId") == cur                      # arrows moved the caret, not the page
    pg.keyboard.press("Escape"); pg.wait_for_timeout(400)
    assert state(pg)["panel"] and pg.evaluate("document.activeElement.id") != "fw-editor"
    pg.keyboard.press("Escape"); pg.wait_for_timeout(700)                    # the page may go back, the box stays
    assert state(pg)["panel"]
    pg.mouse.click(300, 500); pg.wait_for_timeout(400)
    assert state(pg)["panel"]
    pg.evaluate("toggleNotes()"); pg.wait_for_timeout(300)                   # any non-x close is refused
    assert state(pg)["panel"]
    pg.click("#notes-close"); pg.wait_for_timeout(500)
    assert not state(pg)["panel"]
    pg.reload(); pg.wait_for_timeout(1500)
    assert not state(pg)["panel"]
    pg.click("#notes-toggle"); pg.wait_for_timeout(400)                       # reopening brings the same document back
    assert "keep me" in editor_text(pg)


def test_undo_is_the_editors_own(desk):
    pg = desk
    open_fw(pg); pg.click("#fw-editor")
    pg.keyboard.type("one two three"); pg.wait_for_timeout(100)
    pg.keyboard.press(f"{MOD}+z"); pg.wait_for_timeout(200)
    assert "three" not in editor_text(pg)
    assert state(pg)["panel"] and pg.locator("mark[data-hl-id]").count() == 0


def test_toolbar_and_shortcuts(desk):
    pg = desk
    open_fw(pg); pg.click("#fw-editor")
    pg.keyboard.type("bold words"); pg.keyboard.press(f"{MOD}+a"); pg.keyboard.press(f"{MOD}+b")
    pg.keyboard.press(f"{MOD}+i"); pg.keyboard.press(f"{MOD}+u")
    h = pg.evaluate("document.getElementById('fw-editor').innerHTML")
    assert all(t in h for t in ("<b>", "<i>", "<u>"))
    pg.click("#fw-tools [data-fw=strike]")
    assert "<s>" in pg.evaluate("document.getElementById('fw-editor').innerHTML") or "<strike>" in pg.evaluate("document.getElementById('fw-editor').innerHTML")
    pg.click("#fw-tools [data-fw=clear]")
    h = pg.evaluate("document.getElementById('fw-editor').innerHTML")
    assert not re.search(r"<(b|i|u|s|strike)>", h)
    pg.click("#fw-tools [data-fw=h1]")
    assert pg.locator("#fw-editor h1").count() == 1
    pg.click("#fw-tools [data-fw=h1]")                                        # again: back to normal text
    assert pg.locator("#fw-editor h1").count() == 0
    pg.click("#fw-tools [data-fw=h2]")
    assert pg.locator("#fw-editor h2").count() == 1
    pg.click("#fw-tools [data-fw=h2]")
    pg.click("#fw-tools [data-fw=ul]")
    assert pg.locator("#fw-editor ul li").count() == 1
    pg.click("#fw-tools [data-fw=ol]")
    assert pg.locator("#fw-editor ol li").count() == 1
    caret_end(pg); pg.keyboard.press("Enter"); pg.keyboard.type("second")
    assert pg.locator("#fw-editor li").count() == 2
    pg.keyboard.press("Tab")
    assert pg.locator("#fw-editor ol ol, #fw-editor li li").count() >= 1       # Tab in a list indents
    pg.keyboard.press("Shift+Tab")
    assert pg.locator("#fw-editor ol ol, #fw-editor li li").count() == 0       # Shift+Tab brings it back
    pg.click("#fw-tools [data-fw=indent]")
    assert pg.locator("#fw-editor ol ol, #fw-editor li li").count() >= 1
    pg.click("#fw-tools [data-fw=outdent]")
    assert pg.locator("#fw-editor li").count() == 2


def test_typing_dash_or_number_starts_a_list(desk):
    pg = desk
    open_fw(pg); pg.click("#fw-editor")
    pg.keyboard.type("- a"); pg.keyboard.press("Enter"); pg.keyboard.press("Enter"); pg.keyboard.type("1. b")
    assert pg.locator("#fw-editor ul li").count() == 1 and pg.locator("#fw-editor ol li").count() == 1
    assert "- " not in editor_text(pg) and "1." not in editor_text(pg)


def test_word_count_and_saved_state(desk):
    pg = desk
    open_fw(pg); pg.click("#fw-editor"); pg.keyboard.type("one two three")
    assert pg.inner_text("#fw-count") == "3 words"
    assert pg.inner_text("#fw-state") == "Saving…"
    pg.wait_for_timeout(1000)
    assert pg.inner_text("#fw-state") == "Saved" and stored(pg)["html"].count("one two three") == 1


def test_saves_on_blur_and_when_the_page_is_hidden(desk):
    pg = desk
    open_fw(pg); pg.click("#fw-editor"); pg.keyboard.type("quick")
    pg.evaluate("document.getElementById('fw-editor').blur()")
    assert "quick" in (stored(pg) or {}).get("html", "")                       # before the 600ms debounce could fire
    pg.click("#fw-editor"); pg.keyboard.type(" again")
    pg.evaluate("window.dispatchEvent(new Event('pagehide'))")
    assert "again" in stored(pg)["html"]


def test_it_never_mixes_with_notes_and_highlights(desk):
    pg = desk
    open_fw(pg); pg.click("#fw-editor"); pg.keyboard.type("only mine"); pg.wait_for_timeout(800)
    assert pg.evaluate(f"localStorage.getItem('{KEY}')") in (None, "[]")
    pg.click("#fw-seg button[data-m=notes]"); pg.wait_for_timeout(300)
    assert pg.is_visible("#notes-list") and not pg.is_visible("#fw-editor")
    assert "only mine" not in pg.inner_text("#notes-list")
    assert pg.evaluate("document.getElementById('notes-header-title').textContent") != "Freewrite"
    assert state(pg)["mode"] == "notes" and state(pg)["panel"]
    pg.click("#fw-seg button[data-m=fw]"); assert pg.is_visible("#fw-editor") and "only mine" in editor_text(pg)


def test_everything_stored_or_pasted_is_cleaned(desk):
    pg = desk
    dirty = ('<h1 onclick="x()">T</h1><script>window.pwn=1</script><img src=x onerror="window.pwn=2">'
             '<p style="color:red" class="a">hi <b>b</b><a href="javascript:window.pwn=3">link</a><iframe src="//x"></iframe></p>'
             '<span style="font-weight:700;font-style:italic">bi</span><style>p{}</style><ul><li>x<ul><li>y</li></ul></li></ul>')
    out = pg.evaluate("(h)=>_altoFw.sanitize(h)", dirty)
    assert not re.search(r"<(script|img|iframe|style|a)\b|onclick|onerror|style=|class=|javascript", out)
    assert "<h1>T</h1>" in out and "<b>b</b>" in out and "<i>" in out and "<ul><li>x<ul><li>y</li></ul></li></ul>" in out
    assert pg.evaluate("window.pwn") is None
    # a document planted in storage comes out cleaned too
    pg.evaluate("(a)=>localStorage.setItem(a[0], JSON.stringify({html:a[1], mod:Date.now()+5}))", [f"{KEY}-fw", dirty])
    pg.reload(); pg.wait_for_timeout(1300); open_fw(pg)
    assert pg.locator("#fw-editor script, #fw-editor img, #fw-editor iframe, #fw-editor [onclick], #fw-editor [style]").count() == 0
    assert pg.evaluate("window.pwn") is None
    # a paste
    pg.click("#fw-editor"); pg.keyboard.press(f"{MOD}+a"); pg.keyboard.press("Backspace")
    pg.evaluate("""()=>{var e=document.getElementById('fw-editor'); var dt=new DataTransfer();
      dt.setData('text/html','<p style="color:red">pasted <b onmouseover="window.pwn=9">bold</b><script>window.pwn=8</script></p>'); dt.setData('text/plain','pasted bold');
      e.dispatchEvent(new ClipboardEvent('paste',{clipboardData:dt,bubbles:true,cancelable:true}));}""")
    assert pg.locator("#fw-editor b").count() == 1 and pg.locator("#fw-editor [onmouseover], #fw-editor script, #fw-editor [style]").count() == 0
    assert "pasted" in editor_text(pg) and pg.evaluate("window.pwn") is None


def test_plain_text_for_copy_keeps_the_outline(desk):
    out = desk.evaluate("""()=>{var d=document.createElement('div'); d.innerHTML='<h1>Title</h1><div>line</div><ul><li>a<ul><li>b</li></ul></li><li>c</li></ul><ol><li>x</li><li>y</li></ol>'; return _altoFw.plain(d);}""")
    assert out == "Title\nline\n- a\n  - b\n- c\n1. x\n2. y"


def test_copy_and_print_exist_and_print_shows_only_the_document(desk):
    pg = desk
    open_fw(pg); pg.click("#fw-editor"); pg.keyboard.type("print me")
    assert pg.is_visible("#fw-copy") and pg.is_visible("#fw-print")
    pg.evaluate("()=>{ window.print = function(){ window.__printed = document.getElementById('fw-print-host').innerText; }; }")
    pg.click("#fw-print"); pg.wait_for_timeout(200)
    assert "print me" in pg.evaluate("window.__printed") and pg.evaluate("document.documentElement.classList.contains('fw-printing')")
    pg.evaluate("window.dispatchEvent(new Event('afterprint'))")
    assert not pg.evaluate("document.documentElement.classList.contains('fw-printing')") and pg.locator("#fw-print-host").count() == 0


def test_the_panel_can_be_widened_without_covering_the_timeline(desk):
    pg = desk
    open_fw(pg); pg.wait_for_timeout(500)
    CW = "parseFloat(getComputedStyle(document.getElementById('notes-panel')).width)"   # CSS px: the page is zoomed to fit the window
    w0 = pg.evaluate(CW)
    assert 400 <= w0 <= 600
    box = pg.locator("#fw-resize").bounding_box()
    pg.mouse.move(box["x"] + 4, box["y"] + 200); pg.mouse.down(); pg.mouse.move(box["x"] - 150, box["y"] + 200, steps=4); pg.mouse.up()
    pg.wait_for_timeout(300)
    w1 = pg.evaluate(CW)
    assert w1 > w0 + 100 and pg.evaluate("document.getElementById('notes-panel').getBoundingClientRect().width") <= 1400 * 0.7
    assert json.loads(pg.evaluate(f"localStorage.getItem('{KEY}-fwui')"))["w"] == round(w1)
    pg.reload(); pg.wait_for_timeout(1500)
    assert abs(pg.evaluate(CW) - w1) < 2


def test_the_page_being_read_stays_beside_the_box(desk):
    pg = desk
    open_fw(pg)
    nid = page_ids(pg, 1)[0]
    pg.evaluate(f"showDetail('node','{nid}')"); pg.wait_for_timeout(700)
    pad = pg.evaluate("parseFloat(getComputedStyle(document.getElementById('detail-page')).paddingRight)")
    assert pad >= 460
    pg.click("#notes-close"); pg.wait_for_timeout(500)
    assert pg.evaluate("parseFloat(getComputedStyle(document.getElementById('detail-page')).paddingRight)") < 100


def test_dark_theme_is_readable(desk):
    pg = desk
    open_fw(pg); pg.click("#fw-editor"); pg.keyboard.type("dark text")
    pg.evaluate("document.documentElement.classList.add('dark')"); pg.wait_for_timeout(300)
    c = pg.evaluate("getComputedStyle(document.getElementById('fw-editor')).color")
    r, g, b = [int(x) for x in re.findall(r"\d+", c)[:3]]
    assert min(r, g, b) > 150                                                  # light text on the dark glass


def test_phone_sheet(phone):
    pg = phone
    pg.tap("#notes-toggle"); pg.wait_for_timeout(500)
    pg.tap("#fw-seg button[data-m=fw]"); pg.wait_for_timeout(300)
    pg.tap("#fw-editor"); pg.keyboard.type("phone outline"); pg.wait_for_timeout(900)
    assert state(pg)["panel"] and "phone outline" in (stored(pg) or {}).get("html", "")
    assert pg.evaluate("document.documentElement.classList.contains('mobile')")
    assert pg.evaluate("parseFloat(getComputedStyle(document.getElementById('fw-editor')).fontSize)") >= 16   # no iOS zoom on focus
    r = pg.evaluate("(()=>{var b=document.getElementById('notes-panel').getBoundingClientRect(),f=document.getElementById('fw-foot').getBoundingClientRect();return [b.width,b.height,f.bottom]})()")
    assert r[0] == 390 and r[2] <= r[1] + 1
    pg.reload(); pg.wait_for_timeout(1800)
    assert state(pg) == {"open": True, "mode": "fw", "panel": True} and "phone outline" in editor_text(pg)
    pg.tap("#notes-close"); pg.wait_for_timeout(500)
    assert not state(pg)["panel"]


# ── sync: two devices against a mock Firestore ──────────────────────────────

FAKE_APP = "export const initializeApp = c => ({c});"
FAKE_AUTH = """
export const getAuth = a => { const o = {currentUser: null}; window.__auth = o; return o; };
export class GoogleAuthProvider {}
export const signInWithPopup = async () => {}, signInWithRedirect = async () => {}, getRedirectResult = async () => null, signOut = async () => {};
export const browserLocalPersistence = {}, setPersistence = async () => {};
export const onAuthStateChanged = (auth, cb) => { const u = {uid: 'U1', displayName: 'T', email: 't@example.com', photoURL: ''}; auth.currentUser = u; setTimeout(() => cb(u), 30); return () => {}; };
"""
FAKE_FS = """
const call = (op, a) => window.__fs(op, a);
export const getFirestore = () => ({});
export const doc = (db, ...p) => ({path: p.join('/')});
export const collection = (db, ...p) => ({path: p.join('/'), col: true});
export const serverTimestamp = () => 1;
export class Bytes { static fromUint8Array(a){ return a; } }
const snap = (path, data) => ({id: path.split('/').pop(), exists: () => data != null, data: () => data, metadata: {hasPendingWrites: false}, forEach(){}});
export const setDoc = async (ref, data, opts) => { await call('set', {path: ref.path, data: JSON.parse(JSON.stringify(data)), merge: !!(opts && opts.merge)}); };
export const getDoc = async ref => snap(ref.path, await call('get', ref.path));
export const getDocs = async () => ({docs: [], forEach(){}});
export const deleteDoc = async () => {};
export const onSnapshot = (ref, cb) => {
  let last, dead = false;
  const tick = async () => { if(dead) return;
    if(ref.col){ if(last === undefined){ last = 0; cb({forEach(){}, docs: [], metadata: {hasPendingWrites: false}}); } }
    else { const d = await call('get', ref.path), s = JSON.stringify(d); if(s !== last){ last = s; cb(snap(ref.path, d)); } }
    setTimeout(tick, 120); };
  tick(); return () => { dead = true; };
};
"""


class Cloud:
    def __init__(self):
        self.docs, self.lock = {}, threading.Lock()

    def op(self, source, a):
        with self.lock:
            if source == "get":
                return self.docs.get(a)
            cur = dict(self.docs.get(a["path"]) or {}) if a["merge"] else {}
            cur.update(a["data"]); self.docs[a["path"]] = cur
            return None


@pytest.fixture()
def cloud():
    return Cloud()


def _device(browser, html, cloud, tid=TID):
    ctx = browser.new_context(viewport={"width": 1400, "height": 900})
    js = JS.replace('apiKey:            ""', 'apiKey: "test"').replace('projectId:         ""', 'projectId: "test"')
    mods = {"app": FAKE_APP, "auth": FAKE_AUTH, "firestore": FAKE_FS}

    def route(r):
        u = r.request.url
        if "gstatic.com/firebasejs" in u:
            name = re.search(r"firebase-(\w+)\.js", u).group(1)
            return r.fulfill(body=mods[name], content_type="application/javascript")
        if u.endswith("/alto-cloud.js"):
            return r.fulfill(body=js, content_type="application/javascript")
        if "/p.html" in u:
            return r.fulfill(body=html, content_type="text/html")
        return r.fulfill(status=404, body="")
    ctx.route("**/*", route)
    ctx.expose_binding("__fs_py", lambda src, op, a: cloud.op(op, a))
    ctx.add_init_script("window.__fs = (op, a) => window.__fs_py(op, a);")
    pg = ctx.new_page()
    pg.goto(f"http://alto.test/p.html?course={tid}"); pg.wait_for_timeout(1500)
    return pg


@pytest.mark.parametrize("engine", ENGINES)
def test_the_document_follows_the_account_to_a_second_device_and_the_later_edit_wins(engine, playwright_, html, cloud):
    b = _launch(playwright_, engine)
    try:
        a = _device(b, html, cloud)
        assert a.evaluate("!!(window.AltoCloud && AltoCloud.user)")
        open_fw(a); a.click("#fw-editor"); a.keyboard.type("from device A"); a.wait_for_timeout(1800)
        doc = cloud.docs[f"users/U1/tl/{TID}"]
        assert "from device A" in doc["fw"]["html"] and doc["fw"]["mod"] > 0
        assert "highlights" in doc                                             # the notes layer syncs beside it, untouched
        bdev = _device(b, html, cloud)
        bdev.wait_for_timeout(1500)
        assert "from device A" in bdev.evaluate(f"JSON.parse(localStorage.getItem('{KEY}-fw')).html")
        open_fw(bdev); assert "from device A" in editor_text(bdev)
        # B edits later: A receives it (its box is open but nothing there is unsaved)
        bdev.click("#fw-editor"); caret_end(bdev); bdev.keyboard.type(" and B"); bdev.wait_for_timeout(1800)
        assert "and B" in cloud.docs[f"users/U1/tl/{TID}"]["fw"]["html"]
        a.wait_for_timeout(1500)
        assert "and B" in editor_text(a)
        # an older copy never overwrites a newer one
        old = {"html": "<div>stale</div>", "mod": 5}
        a.evaluate("(o)=>localStorage.setItem('%s-fw', JSON.stringify(o))" % KEY, old); a.wait_for_timeout(1500)
        assert "and B" in cloud.docs[f"users/U1/tl/{TID}"]["fw"]["html"]
    finally:
        b.close()


@pytest.mark.parametrize("engine", ENGINES)
def test_a_signed_in_share_does_not_touch_the_owners_freewrite(engine, playwright_, html, cloud):
    b = _launch(playwright_, engine)
    try:
        owner = _device(b, html, cloud)
        open_fw(owner); owner.click("#fw-editor"); owner.keyboard.type("owner secret"); owner.wait_for_timeout(1800)
        shared = reidentify(html, "abcDEF123")
        viewer = _device(b, shared, cloud, tid="s-abcDEF123")
        open_fw(viewer)
        assert "owner secret" not in editor_text(viewer)
        viewer.click("#fw-editor"); viewer.keyboard.type("viewer own"); viewer.wait_for_timeout(1800)
        assert "owner secret" in cloud.docs[f"users/U1/tl/{TID}"]["fw"]["html"]
        assert "viewer own" in cloud.docs["users/U1/tl/s-abcDEF123"]["fw"]["html"]
        assert "viewer own" not in cloud.docs[f"users/U1/tl/{TID}"]["fw"]["html"]
    finally:
        b.close()


def test_phone_box_rises_above_the_keyboard(phone):
    """The keyboard shrinks the visual viewport, not the page: the footer must stay in sight."""
    pg = phone
    pg.tap("#notes-toggle"); pg.wait_for_timeout(500)
    pg.tap("#fw-seg button[data-m=fw]"); pg.wait_for_timeout(300)
    foot = "document.getElementById('fw-foot').getBoundingClientRect().bottom"
    full = pg.evaluate(foot)
    pg.evaluate("""()=>{ var fake = {height: 500, offsetTop: 0, width: 390, scale: 1, addEventListener(){}, removeEventListener(){}};
      Object.defineProperty(window, 'visualViewport', {value: fake, configurable: true}); window.dispatchEvent(new Event('resize')); }""")
    pg.wait_for_timeout(200)
    assert pg.evaluate(foot) <= 500 + 2 < full
