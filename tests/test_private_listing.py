"""The homepage shows you your own private timelines once you sign in.

A private timeline is listed nowhere — not on the homepage, not in search, not
in the sitemap. That is the feature. It is also how five published outlines
became unreachable the moment their 22-character URLs were mislaid: unlisted to
the world had come to mean unlisted to their owner too.

The hard part is not showing them. It is showing them to nobody else, and in
particular not to the SIMULATED sign-in that any site without a Firebase
project falls back to.
"""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build.builder import build_timeline, load_brief   # noqa: E402
from alto.build.pages import build_home                     # noqa: E402
from alto.build.private_shell import shell                  # noqa: E402
from alto.build.single_file import private_page             # noqa: E402

SAMPLE = ROOT / "samples" / "contracts_brief.json"
CLOUD_JS = (ROOT / "alto" / "cloud" / "alto-cloud.js").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def home():
    return build_home([])


@pytest.fixture(scope="module")
def built():
    d = json.loads(SAMPLE.read_text(encoding="utf-8"))
    b, nodes, conns = load_brief(d)
    html, _ = build_timeline(b, nodes, conns)
    return b, html


# ── who the list is shown to ────────────────────────────────────────────────

def test_the_listing_is_gated_on_firebase_not_on_local_storage(home):
    """Account.get() reads localStorage['alto-account-v1'], which the simulated
    sign-in path writes on any site with no Firebase project. Gating on it would
    offer a private section to someone signed in to nothing at all — and then
    fail to fill it, which looks exactly like data loss."""
    fn = home[home.index("function renderPrivate()"):]
    fn = fn[:fn.index("\n}")]
    assert "!c.enabled || !c.user" in fn
    assert "Account.get()" not in fn


def test_signing_out_removes_the_list_from_the_page(home):
    """renderAccount fires on every auth change, including sign-out. Leaving
    the slab behind would keep every private title on screen afterwards."""
    assert "function clearPrivate()" in home
    assert "privateSlab.remove()" in home
    body = home[home.index("function renderPrivate()"):]
    assert "clearPrivate(); return; }" in body[:400]


def test_render_account_drives_the_listing(home):
    """alto-cloud.js calls renderAccount() and nothing else on an auth change."""
    fn = home[home.index("function renderAccount()"):]
    fn = fn[:fn.index("\nfunction ")]
    assert "renderPrivate();" in fn


def test_a_failed_lookup_leaves_no_half_rendered_slab(home):
    assert ".catch(() => clearPrivate());" in home


# ── what the list contains ──────────────────────────────────────────────────

def test_a_private_tile_links_to_the_opaque_key(home):
    assert "'/pv/' + encodeURIComponent(pg.key) + '/'" in home


def test_a_title_from_firestore_is_not_parsed_as_markup(home):
    """Every other title on this page is template output. These have been to
    Firestore and back, so they are the one string here that an attacker with
    write access to the account could shape."""
    block = home[home.index("function renderPrivate()"):]
    block = block[:block.index("\n}\n")]
    assert ".tile-title').textContent = pg.title" in block
    assert "innerHTML = pg.title" not in block


def test_the_empty_case_renders_nothing_at_all(home):
    """Not an empty slab captioned 'Private' — that reads as 'your work is
    gone' to someone whose sign-in simply has not resolved yet."""
    assert "if(!pages || !pages.length) return;" in home


def test_the_public_homepage_is_unchanged_when_signed_out(home):
    """The slab is built in JS from a Firestore read. Nothing about a private
    timeline can reach the served HTML, which is what a logged-out visitor,
    a crawler and curl all see."""
    block = home[home.index("const PROJECTS = ["):]
    assert block[:block.index("\n];") + 3] == "const PROJECTS = [];" or "pv/" not in block[:200]
    assert home.count("/pv/") == 1, "the only /pv/ is the href template"


# ── titles ──────────────────────────────────────────────────────────────────

def test_the_listing_never_downloads_the_pages_to_name_them(home):
    """Each private page is ~600 KB. Fetching five of them to render five
    titles would make opening the homepage cost more than opening a timeline."""
    fn = CLOUD_JS[CLOUD_JS.index("async function _listPages()"):]
    fn = fn[:fn.index("\n  }")]
    code = "\n".join(l for l in fn.splitlines() if not l.strip().startswith("//"))
    assert "html" not in code, "listPages must not read the html field"
    assert "title" in code


def test_put_page_records_the_title(built):
    assert "title: title || ''" in CLOUD_JS


def test_the_shell_recovers_a_title_from_the_page_it_just_opened(built):
    """Everything published before titles were stored has none, and the listing
    deliberately never fetches the html a title could be read from — so the one
    moment it is in hand is when the shell renders it."""
    s = shell()
    assert "function titleOf(pageHtml)" in s
    assert "cloud.ensureTitle(KEY, titleOf(page))" in s


def test_a_backfill_never_overwrites_a_title_that_is_already_there(built):
    fn = CLOUD_JS[CLOUD_JS.index("async function _ensureTitle("):]
    fn = fn[:fn.index("\n  }")]
    assert "if (!snap.exists() || (snap.data() || {}).title) return false;" in fn
    assert "{ merge: true }" in fn


def test_the_recovered_title_is_the_timeline_name(built):
    """The shell strips Alto's own suffix, so the homepage shows 'Contracts I'
    rather than 'Contracts I — Alto Timeline'."""
    b, html = built
    page = private_page(b, html)
    raw = re.search(r"<title>([^<]*)</title>", page, re.I).group(1)
    # the same expression the shell ships, applied here
    js = [l for l in shell().splitlines() if "replace(/" in l and "Alto" in l][0]
    pattern = js[js.index("replace(/") + 9:js.index("/, '')")]
    assert re.sub(pattern, "", raw).strip() == b.title


def test_the_shell_still_carries_no_timeline_content():
    """Titles are read from the uploaded page at runtime; none of this may put
    one into the world-readable shell."""
    s = shell()
    for leak in ("Contracts", "Civil Procedure", "timeline_id"):
        assert leak not in s


# ── telling one outline from another ────────────────────────────────────────

def test_the_page_carries_the_publishers_own_name_for_it(built):
    """Five outlines of one course share a brief title, so five tiles reading
    'Civil Procedure' are exactly as useful as five reading 'Untitled'. The
    project name is what distinguishes them and only the publisher knows it."""
    from alto.build.single_file import PRIVATE_LABEL
    b, html = built
    page = private_page(b, html, "Civil Procedure — Jade")
    m = re.search(r'<meta name="%s" content="([^"]*)"' % PRIVATE_LABEL, page)
    assert m and m.group(1) == "Civil Procedure — Jade"


def test_the_label_falls_back_to_the_brief_title(built):
    from alto.build.single_file import PRIVATE_LABEL
    b, html = built
    page = private_page(b, html)
    m = re.search(r'<meta name="%s" content="([^"]*)"' % PRIVATE_LABEL, page)
    assert m and m.group(1) == b.title


def test_a_label_with_markup_in_it_cannot_break_out(built):
    b, html = built
    page = private_page(b, html, '"><script>alert(1)</script>')
    assert "<script>alert(1)" not in page
    assert "&lt;script&gt;alert(1)" in page


def test_the_shell_prefers_the_label_over_the_title():
    s = shell()
    i, j = s.index('name="alto-label"'), s.index("<title>([^<]*)")
    assert i < j, "the <title> fallback must come after the label"


def test_publishing_passes_the_project_name(tmp_path):
    """A label that is always the brief title would defeat the whole point."""
    src = (ROOT / "alto" / "publish_static.py").read_text(encoding="utf-8")
    assert 'private_page(\n                b, raw, name_by_pid.get(' in src
