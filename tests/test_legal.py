"""The beta's legal pages and the terms gate (Luke 2026-10-30, REQUIRED-for-beta R1/R2/R4).

The pages are alto/legal/*.md rendered by alto/build/legal.py; the version a person agrees to is alto/legal/VERSION, shared by the pages, the sign-in
box and the Firestore record. The gate lives in the hosted alto-cloud.js: an unticked box before the first sign-in, a create-once record at
terms_acceptance/{uid}_{version}, no copy kept in the browser, a blocking question again when the version changes. The browser parts run alto-cloud.js against stubbed Firebase modules
(no network, no cloud environment) and are skipped without Playwright."""
import functools
import http.server
import json
import re
import socketserver
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import legal            # noqa: E402
from alto.build.pages import build_home  # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None


# ── the pages ───────────────────────────────────────────────────────────────

def test_three_pages_render_from_the_markdown_with_the_one_version():
    pages = legal.pages()
    assert list(pages) == ["privacy", "terms", "credits"]            # /storage is gone: the storage notice is a section of the policy
    for key, html in pages.items():
        assert html.startswith("<!doctype html>") and 'name="viewport"' in html and "<h1>" in html
        assert "Version " + legal.version() in html
        for k, n in (("privacy", "Privacy"), ("terms", "Beta Terms"), ("credits", "Credits")):
            assert f'<a href="/{k}/"' in html and n in html          # the footer line on every page
        assert "https://www.openstreetmap.org/copyright" in html and "OpenStreetMap contributors (ODbL)" in html
    assert "Privacy Policy" in pages["privacy"] and "Beta Terms" in pages["terms"]
    assert "Google records the name, email address and profile photo" in pages["privacy"]      # the feedback form (a Google Form), Strategy v6
    assert "Storage on your device" in pages["privacy"] and "Alto sets no cookies" in pages["privacy"]
    assert '<a href="/privacy/">Privacy Policy</a>' in pages["terms"]
    assert "__ALTO" not in "".join(pages.values())
    assert "only you can see your own account" not in pages["privacy"]      # held until IT's security sign-off
    assert not (ROOT / "alto" / "legal" / "storage-notice.md").exists()
    cr = pages["credits"]                                            # the registries themselves are credited: every background photo, every hosted painting
    from alto.build import backgrounds_catalog as cat
    for sc in cat.SCENES:
        for k in ("d", "l"):
            assert sc[k]["name"] in cr and sc[k]["lic"] in cr
    assert "Natural Earth" in cr and "Poly Haven" in cr and "Apache License 2.0" in cr and "Portrait of Yarrow Mamout" in cr
    assert 'href="https://commons.wikimedia.org/wiki/File:Portrait_of_Yarrow_Mamout_%28Muhammad_Yaro%29' in cr    # parentheses in a Commons URL survive


def test_the_markdown_is_escaped_and_small():
    title, body = legal.render_body("# T <b>\n\n## H & H\n- one **bold**\n- [a link](https://example.com/x)\n\n<script>x()</script>\n*a note*\n")
    assert title == "T <b>"
    assert "<h2>H &amp; H</h2>" in body and "<ul><li>one <strong>bold</strong></li>" in body
    assert '<a href="https://example.com/x">a link</a>' in body
    assert "<script>" not in body and "&lt;script&gt;" in body
    assert '<p class="note">a note</p>' in body
    assert "<a" not in legal._inline("[x](javascript:alert(1))")


def test_the_final_text_is_version_1_0_with_no_draft_marks():
    assert legal.version() == "1.0"
    for name in ("privacy-policy.md", "beta-terms.md"):
        md = (ROOT / "alto" / "legal" / name).read_text(encoding="utf-8")
        assert "DRAFT" not in md and "Research" not in md and "Version 1.0." in md
        assert not re.search(r"\[(?![^\]]*\]\()", md)                                   # no bracketed placeholder: a [ only opens a link
    priv = (ROOT / "alto" / "legal" / "privacy-policy.md").read_text(encoding="utf-8")
    assert "Google records the name, email address and profile photo" in priv and "stored in our database under your account" in priv
    assert "Help improve Bass (off unless you tick it)" in priv and "Bass conversations you share (optional)" in priv and "15 February 2027" in priv
    assert "third-party analytics tools or trackers" in priv and "only if you opt in, to read Bass conversations" in priv
    assert "Records of who opened saved Bass conversations are kept for 400 days." in priv and "AI tools**: If you opt in" in priv
    assert "plus anything you choose to share under Help improve Bass" in (ROOT / "alto" / "legal" / "beta-terms.md").read_text(encoding="utf-8")


def test_the_version_is_one_file_the_cloud_script_reads():
    from alto.cloud import emit_cloud_js
    assert (ROOT / "alto" / "legal" / "VERSION").read_text(encoding="utf-8").strip() == legal.version()
    js = emit_cloud_js({"apiKey": "k"})
    assert f"const TERMS_V = '{legal.version()}';" in js and "__ALTO_TERMS_V__" not in js
    assert "'terms_acceptance', termsDocId(user.uid)" in js and "uid + '_' + TERMS_V" in js     # terms_acceptance/<uid>_<version>, the rule IT wrote
    assert "alto-terms-v" not in js and "localStorage" not in js[js.index("const termsDocId"):js.index("onAuthStateChanged(auth")]   # no local proof


def test_the_homepage_foot_links_the_pages_and_the_map_credit():
    h = build_home([])
    assert 'id="home-legal"' in h
    foot = h[h.index('id="home-legal"'):][:700]
    assert foot.index("/privacy/") < foot.index("/terms/") < foot.index("/credits/") < foot.index("openstreetmap.org/copyright")
    assert "/storage/" not in foot


def test_the_site_publishes_the_pages_and_the_old_connector_page_is_gone():
    src = (ROOT / "alto" / "publish_static.py").read_text(encoding="utf-8")
    assert "legal.pages()" in src and "privacy.html" not in src
    assert not (ROOT / "alto" / "privacy.html").exists()
    web = (ROOT / "alto" / "web.py").read_text(encoding="utf-8")                  # (importing it needs the mcp package, which the browser venv lacks)
    for path in ("/privacy", "/privacy/", "/terms", "/terms/", "/credits", "/credits/"):
        assert f'@app.get("{path}"' in web
    assert "/storage" not in web


# ── the gate, in a browser ──────────────────────────────────────────────────

STUBS = {
    "firebase-app.js": "export function initializeApp(c){ return {c}; }",
    "firebase-auth.js": """
export function getAuth(){ return { get currentUser(){ return window.__user || null; } }; }
export class GoogleAuthProvider {}
const U = {uid:'u1', displayName:'T', email:'t@example.com', photoURL:''};
export async function signInWithPopup(){ window.__signins++; window.__user = U; window.__cb(U); }
export async function signInWithRedirect(){} export async function getRedirectResult(){ return null; }
export async function signOut(){ window.__signouts++; window.__user = null; window.__cb(null); }
export const browserLocalPersistence = {}; export async function setPersistence(){}
export function onAuthStateChanged(a, cb){ window.__cb = cb; setTimeout(()=>cb(window.__user || null),0); return ()=>{}; }
""",
    "firebase-firestore.js": """
const fs = window.__fs;
export function getFirestore(){ return {}; }
export function doc(db, ...s){ return {path:s.join('/'), id:s[s.length-1], kind:'doc'}; }
export function collection(db, ...s){ return {path:s.join('/'), kind:'col'}; }
const snap = (ref) => { const d = fs.docs[ref.path]; return {exists:()=>!!d, data:()=>d, id:ref.id, ref, metadata:{hasPendingWrites:false}}; };
export async function getDoc(ref){ if(fs.failGet && ref.path.startsWith('terms_acceptance')) throw new Error('unavailable'); return snap(ref); }
export async function getDocs(){ return {docs:[], forEach(){}}; }
export async function setDoc(ref, data, o){ if(fs.denySet && ref.path.startsWith('terms_acceptance')) throw new Error('permission-denied'); fs.docs[ref.path] = Object.assign({}, (o&&o.merge) ? (fs.docs[ref.path]||{}) : {}, data); fs.writes.push([ref.path, data]); }
export async function deleteDoc(ref){ delete fs.docs[ref.path]; }
export function onSnapshot(ref, cb){ setTimeout(()=>cb(ref.kind==='col' ? {metadata:{hasPendingWrites:false}, forEach(){}, docs:[]} : snap(ref)),0); return ()=>{}; }
export function serverTimestamp(){ return 'SERVER_TIME'; }
export class Bytes { static fromUint8Array(a){ const b=new Bytes(); b.a=a; return b; } toUint8Array(){ return this.a; } }
""",
}


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    if pw is None:
        pytest.skip("Playwright is not installed")
    from alto.cloud import emit_cloud_js
    from alto.hosted import hosted_home
    d = tmp_path_factory.mktemp("legal")
    (d / "alto-cloud.js").write_text(emit_cloud_js({"apiKey": "k", "authDomain": "p.firebaseapp.com", "projectId": "p", "storageBucket": "",
                                                    "messagingSenderId": "", "appId": "a"}), encoding="utf-8")
    (d / "index.html").write_text(hosted_home(build_home([])), encoding="utf-8")
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(d))
    h.log_message = lambda *a: None
    socketserver.TCPServer.allow_reuse_address = True
    srv = socketserver.TCPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


@pytest.fixture(scope="module")
def browser():
    if pw is None:
        pytest.skip("Playwright is not installed")
    with pw.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:
            pytest.skip(f"no chromium: {e}")
        yield b
        b.close()


def _open(browser, site, docs=None, user=False, flags=""):
    pg = browser.new_page(viewport={"width": 1200, "height": 800})
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.route("https://www.gstatic.com/firebasejs/**", lambda r: r.fulfill(status=200, content_type="text/javascript", body=STUBS[r.request.url.rsplit("/", 1)[1]]))
    init = "window.__fs={docs:%s,writes:[]};window.__signins=0;window.__signouts=0;%s" % (json.dumps(docs or {}), flags)
    if user:
        init += "window.__user={uid:'u1',displayName:'T',email:'t@example.com',photoURL:''};"
    pg.add_init_script(init)
    pg.goto(site + "/index.html")
    pg.wait_for_function("window.AltoCloud && window.AltoCloud.terms && document.querySelector('#acct-signed-out .acct-legal')", timeout=15000)
    pg.wait_for_timeout(400)
    return pg, errors


def test_the_box_is_unticked_the_button_waits_and_a_tick_writes_the_record_once(browser, site):
    import alto.build.legal as lg
    pg, errors = _open(browser, site)
    try:
        assert pg.evaluate("document.getElementById('acct-terms-box').checked") is False
        assert pg.is_disabled("#account-modal .acct-provider")
        assert "I am 18 or over and agree to the Beta Terms and Privacy Policy" in pg.inner_text("#account-modal .acct-terms")
        assert pg.evaluate("[...document.querySelectorAll('.acct-legal a, .acct-terms a')].map(a => a.getAttribute('href') + ':' + a.target).join()") \
            == "/terms/:_blank,/privacy/:_blank,/privacy/:_blank,/terms/:_blank"
        pg.evaluate("Account.signIn('google')")                                            # a script or a key getting past the disabled button
        pg.wait_for_timeout(300)
        assert pg.evaluate("window.__signins") == 0
        pg.evaluate("toggleAccount()")
        pg.check("#acct-terms-box", force=True)
        assert not pg.is_disabled("#account-modal .acct-provider")
        pg.evaluate("Account.signIn('google')")
        pg.wait_for_function("window.__fs.writes.length > 0", timeout=5000)
        path, data = pg.evaluate("window.__fs.writes.find(w => w[0].startsWith('terms_acceptance'))")
        assert path == "terms_acceptance/u1_" + lg.version()
        assert data == {"uid": "u1", "version": lg.version(), "ageConfirmed": True, "acceptedAt": "SERVER_TIME"}
        assert pg.evaluate("Object.keys(localStorage).filter(k => /terms/i.test(k)).length") == 0      # nothing kept here as proof
        assert pg.locator("#alto-terms-scrim").count() == 0 and pg.evaluate("window.AltoCloud.terms.version") == lg.version()
        assert errors == []
    finally:
        pg.close()


def test_a_person_with_a_record_for_this_version_is_not_asked_and_nothing_is_written(browser, site):
    import alto.build.legal as lg
    pg, errors = _open(browser, site, docs={"terms_acceptance/u1_" + lg.version(): {"uid": "u1", "version": lg.version(), "ageConfirmed": True}}, user=True)
    try:
        pg.wait_for_timeout(500)
        assert pg.locator("#alto-terms-scrim").count() == 0
        assert pg.evaluate("window.__fs.writes.filter(w => w[0].startsWith('terms_acceptance')).length") == 0
        assert pg.evaluate("document.getElementById('acct-terms-box').checked") is False             # the box is unticked at every sign-in screen
        assert errors == []
    finally:
        pg.close()


def test_a_new_version_asks_again_and_declining_signs_out(browser, site):
    import alto.build.legal as lg
    old = {"terms_acceptance/u1_0.0": {"uid": "u1", "version": "0.0", "ageConfirmed": True}}
    pg, errors = _open(browser, site, docs=old, user=True)
    try:
        pg.wait_for_selector("#alto-terms-scrim", timeout=5000)
        assert pg.is_disabled("#alto-terms-go")                                           # blocked until ticked
        pg.check("#alto-terms-ok")
        pg.click("#alto-terms-go")
        pg.wait_for_function("window.__fs.docs['terms_acceptance/u1_%s'] && window.__fs.docs['terms_acceptance/u1_%s'].version === %s" % (lg.version(), lg.version(), json.dumps(lg.version())), timeout=5000)
        assert pg.locator("#alto-terms-scrim").count() == 0 and pg.evaluate("window.__signouts") == 0
        assert pg.evaluate("window.__fs.docs['terms_acceptance/u1_0.0'].version") == "0.0"             # the old record is never touched
        assert errors == []
    finally:
        pg.close()
    pg, errors = _open(browser, site, docs=old, user=True)
    try:
        pg.wait_for_selector("#alto-terms-scrim", timeout=5000)
        pg.click("#alto-terms-no")
        pg.wait_for_function("window.__signouts === 1", timeout=5000)
        assert pg.locator("#alto-terms-scrim").count() == 0
        assert pg.evaluate("window.__fs.writes.filter(w => w[0].startsWith('terms_acceptance')).length") == 0
        assert errors == []
    finally:
        pg.close()


def test_a_refused_save_says_so_and_keeps_asking_and_an_unreadable_record_is_never_written_over(browser, site):
    import alto.build.legal as lg
    pg, errors = _open(browser, site, user=True, flags="window.__fs.denySet=true;")
    try:
        pg.wait_for_selector("#alto-terms-scrim", timeout=5000)                           # nothing to read, nothing could be saved: the dialog, not a crash
        pg.check("#alto-terms-ok")
        pg.click("#alto-terms-go")
        pg.wait_for_function("document.getElementById('alto-terms-msg').textContent.includes(\"couldn't save\")", timeout=5000)
        assert pg.locator("#alto-terms-scrim").count() == 1 and not pg.is_disabled("#alto-terms-go")
        assert pg.evaluate("window.__signouts") == 0
        pg.evaluate("window.__fs.denySet = false")
        pg.click("#alto-terms-go")
        pg.wait_for_function("window.__fs.docs['terms_acceptance/u1_%s']" % lg.version(), timeout=5000)
        assert errors == []
    finally:
        pg.close()
    pg, errors = _open(browser, site, user=True, flags="window.__fs.failGet=true;")
    try:
        pg.wait_for_timeout(600)
        assert pg.locator("#alto-terms-scrim").count() == 0                                # fail-open (the Bass proxy checks the same record and fails closed)
        assert pg.evaluate("window.__fs.writes.filter(w => w[0].startsWith('terms_acceptance')).length") == 0
        assert errors == []
    finally:
        pg.close()
