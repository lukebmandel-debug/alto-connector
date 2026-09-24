"""Listing records, the homepage reaching into private timelines, and the
reports page's way home.

The homepage used to list private timelines by reading users/{uid}/pages —
which returns every page in full, so a title list cost several megabytes. It
now reads users/{uid}/pagemeta: one small record per page carrying what a chip
and the homepage search need (colours, project, card titles).
"""
from pathlib import Path

from alto.build.pages import build_home, build_reports
from alto.build.private_shell import shell as private_shell
from alto.build.share_shell import shell as share_shell
from alto.build.engine_patches import apply_patches
from alto.engine import template as engine_template
from alto.hosted import hosted_reports

ROOT = Path(__file__).resolve().parent.parent
CLOUD_JS = (ROOT / "alto" / "cloud" / "alto-cloud.js").read_text(encoding="utf-8")


def _fn(src, head):
    body = src[src.index(head):]
    return body[:body.index("\n  }\n")]


# ── the listing record ──────────────────────────────────────────────────────

def test_the_list_reads_records_not_pages():
    fn = _fn(CLOUD_JS, "async function _listPages(")
    assert "collection(db, 'users', u.uid, 'pagemeta')" in fn
    assert "'pages')" not in fn, "listing pages downloads every page in full"


def test_old_pages_get_records_once_per_account():
    fn = _fn(CLOUD_JS, "async function _listPages(")
    assert "pagemetaV !== META_V) await _migrateMeta(u.uid)" in fn
    mig = _fn(CLOUD_JS, "async function _migrateMeta(")
    assert "{ pagemetaV: META_V }, { merge: true }" in mig


def test_an_upload_writes_its_record():
    fn = _fn(CLOUD_JS, "async function _putPage(")
    assert "'pagemeta', key)" in fn and "_metaOf(html)" in fn
    # merge, so an upload never clears the share link the share flow set
    assert "{ merge: true });" in fn[fn.index("'pagemeta', key)"):]


def test_the_record_follows_the_share_link():
    for head in ("async function _sharePush(", "async function _shareRevoke("):
        assert "'pagemeta', pageKey), { shareKey" in _fn(CLOUD_JS, head)


def test_the_record_carries_colours_project_and_card_text():
    fn = _fn(CLOUD_JS, "function _metaOf(")
    assert "const PHASE_META = [" in fn and "colorRaw" in fn
    assert '<meta name="alto-label"' in fn
    assert "const NODES_SRC=[" in fn
    # bounded, so a huge timeline cannot push the record past Firestore's cap
    assert "search.length < SEARCH_CAP" in fn and ".slice(0, DESC_CAP)" in fn


def test_signing_out_forgets_what_this_browser_cached():
    tail = CLOUD_JS[CLOUD_JS.index("onAuthStateChanged(auth"):]
    out = tail[tail.index("} else {"):]
    assert "localStorage.removeItem('alto-pages-cache-v1')" in out
    assert "indexedDB.deleteDatabase('alto-pv-cache')" in out


def test_the_redirect_check_no_longer_gates_every_page_load():
    assert "await getRedirectResult(auth)" not in CLOUD_JS
    assert "getRedirectResult(auth).catch(() => {});" in CLOUD_JS


def test_sign_in_opens_inside_the_tap_once_firebase_is_up():
    assert "signIn:  () => _isReady ? _signIn() : ready.then(() => _signIn())," in CLOUD_JS


# ── the homepage ────────────────────────────────────────────────────────────

def _home():
    return build_home([])


def test_private_chips_show_colours_and_project():
    block = _home()[_home().index("function drawPrivate("):]
    block = block[:block.index("\n}\n")]
    assert "unitStrip(pg.units)" in block
    assert "tile-project" in block
    assert "kicker.textContent = 'Private';" in block
    assert "visible only to you" not in _home()


def test_colours_from_firestore_are_checked_before_styling():
    fn = _home()[_home().index("function unitStrip("):]
    fn = fn[:fn.index("\n}\n")]
    assert "/^#[0-9a-fA-F]{3,8}$/.test(c)" in fn


def test_the_lists_draw_from_cache_until_firebase_answers():
    h = _home()
    assert "if(c && c.known) return null;" in h
    assert "k.uid === s.uid" in h, "another account's cache is never drawn"


def test_search_reaches_into_private_timelines():
    h = _home()
    assert "return idx.concat(extraIndex());" in h
    assert "location.href = t.href + '#find=' + n.id;" in h


def test_signed_in_account_shows_the_photo_without_glass():
    h = _home()
    assert "html #account-btn.signed-in{" in h
    assert "im.referrerPolicy = 'no-referrer';" in h
    assert "abtn.classList.add('signed-in')" in h


def test_a_private_share_link_is_handed_over_after_the_write():
    h = _home()
    assert "if(altoIsTouch()){ showLink(r.shareKey); return; }" in h
    assert "navigator.maxTouchPoints > 1" in h, "iPads report a Mac user agent"


# ── the shells ──────────────────────────────────────────────────────────────

def test_shells_allow_the_native_share_sheet():
    for s in (private_shell(), share_shell()):
        assert 'allow="clipboard-write; clipboard-read; web-share"' in s


def test_shells_hand_a_find_link_to_the_framed_page():
    for s in (private_shell(), share_shell()):
        assert "window.__altoQuery={hash:" in s
        assert "'\\\\u003c'" in s, "a hash must not be able to close the script tag"


def test_the_private_shell_opens_from_cache_for_the_same_account_only():
    s = private_shell()
    assert "v.uid === s.uid" in s
    assert "var mine = cached && cached.uid === uid ? cached : null;" in s


# ── the timeline ────────────────────────────────────────────────────────────

def test_phones_follow_a_find_link_too():
    t = apply_patches(engine_template("timeline_template.html"))
    mobile = t[t.index('<script id="alto-search-mobile">'):]
    assert "/[#&]find=([\\w-]+)/" in mobile[:6000]
    assert "window.featureNode(id,true);" in mobile[:6000]


def test_section_headers_sit_inside_the_window_edges():
    t = apply_patches(engine_template("timeline_template.html"))
    assert "bar.style.left='20px'; bar.style.right='20px';" in t
    assert "lbl.style.left='29px';" in t
    assert "right:29px !important;" in t
    assert "font-weight:700; text-transform:uppercase;" in t


# ── reports ─────────────────────────────────────────────────────────────────

def _reports():
    return hosted_reports(build_reports([], "x"))


def test_home_from_reports_goes_home():
    r = _reports()
    assert '<a id="home-link" href="/">' in r
    assert "back.href = '/';" in r
    assert "href=\"index.html\"" not in r


def test_reports_carry_the_homepage_glyphs():
    r = _reports()
    for el in ('id="search-btn"', 'id="account-btn"', 'id="info-btn"',
               'class="mode-glyph mode-moon"', 'class="mode-glyph mode-sun"',
               'id="account-scrim"'):
        assert el in r, el
    assert "function _altoSignInFailed(" in r
