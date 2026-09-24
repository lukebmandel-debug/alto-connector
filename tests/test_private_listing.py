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
    # The cached list stays up if Firestore fails; with none, nothing is left behind.
    assert ".catch(() => { if(!early) clearPrivate(); });" in home


# ── what the list contains ──────────────────────────────────────────────────

def test_a_private_tile_links_to_the_opaque_key(home):
    assert "'/pv/' + encodeURIComponent(pg.key) + '/'" in home


def test_a_title_from_firestore_is_not_parsed_as_markup(home):
    """Every other title on this page is template output. These have been to
    Firestore and back, so they are the one string here that an attacker with
    write access to the account could shape."""
    block = home[home.index("function drawPrivate("):]
    block = block[:block.index("\n}\n")]
    assert "const heading = pg.heading || pg.title" in block
    assert ".tile-title').textContent = heading" in block
    helper = home[home.index("function projectSlab("):]
    assert "kicker.textContent = name;" in helper[:600]
    assert "innerHTML = pg." not in block


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
    assert "cloud.ensureTitle(KEY, titleOf(page), idOf(page))" in s


def test_a_backfill_never_overwrites_what_is_already_there(built):
    """It heals documents written before these fields existed. It must not get
    an opinion about current ones — a backfill that overwrote would quietly
    undo a rename every time the page was opened."""
    fn = CLOUD_JS[CLOUD_JS.index("async function _ensureTitle("):]
    fn = fn[:fn.index("\n  }")]
    assert "if (title && !have.title) add.title = title;" in fn
    assert "if (tid && !have.tid) add.tid = tid;" in fn
    assert "{ merge: true }" in fn
    assert "if (!Object.keys(add).length) return false;" in fn, "writes on every open"


def test_the_listing_carries_the_course_id(built):
    """The chip's reports button and its notes lookup both need it, and the
    listing deliberately never downloads the page it could be read from."""
    assert "tid: v.tid || ''" in CLOUD_JS
    fn = CLOUD_JS[CLOUD_JS.index("async function _putPage("):]
    fn = fn[:fn.index("\n  }")]
    assert "tid: _identityOf(html)" in fn


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


# ── a private chip is still a chip ──────────────────────────────────────────

def test_a_private_chip_carries_the_same_three_controls(home):
    """A private timeline is still a timeline: it has a reports repository and
    it can be taken offline. Rendering it with fewer buttons than the chip
    beside it was a regression, not a design decision."""
    block = home[home.index("function drawPrivate("):]
    block = block[:block.index("\n}\n")]
    for cls in ("tile-reports", "tile-share", "tile-download"):
        assert f"'{cls}'" in block, f"private chip has no {cls}"


def test_both_kinds_of_chip_draw_the_same_glyphs(home):
    """Two copies of the markup is exactly how chips start looking different."""
    assert home.count("const REPORTS_GLYPH = ") == 1
    assert home.count("rb.innerHTML = REPORTS_GLYPH;") == 2
    # 3 for share: the two chip builders plus the project slab's own button.
    assert home.count("SHARE_GLYPH;") == 3
    assert home.count("DOWNLOAD_GLYPH;") >= 2


def test_a_private_chip_downloads_from_the_account_not_the_web(home):
    """There is no offline.html for a private timeline — publishing one is the
    whole thing being avoided. The only copy is the one this account can read
    out of Firestore."""
    block = home[home.index("function drawPrivate("):]
    block = block[:block.index("\n}\n")]
    assert "altoDownloadOffline(() => window.AltoCloud.getPage(pg.key)" in block
    code = "\n".join(l for l in block.splitlines() if not l.strip().startswith("//"))
    assert "offline.html" not in code, "a private timeline has no published bundle"


def test_the_downloader_accepts_a_page_it_cannot_fetch(home):
    assert "if(typeof src === 'function'){" in home
    assert "html = await src();" in home


def test_a_downloaded_private_page_does_not_navigate_to_a_missing_file():
    """Opened on its own there is no router above it and no sibling file, so
    following the href lands on a 404. Doing nothing is the honest outcome."""
    from alto.build.single_file import SHIM
    assert "window.__altoGo=function(u){go(u);};" in SHIM


def test_the_reports_button_needs_a_course_to_point_at(home):
    """Documents written before the id was stored have none; the chip draws
    without that button rather than linking at an empty course."""
    block = home[home.index("function drawPrivate("):]
    block = block[:block.index("\n}\n")]
    assert "if(pg.tid){" in block
    assert "if(!pg.tid) shb.style.right = '14px';" in block, "gap not closed"


def test_every_cloud_function_declares_what_its_body_uses():
    """_putPage once read `title` without taking it, so every upload failed
    with "title is not defined" — and nothing noticed, because the only code
    path that uploads a page is a hand-driven file picker nothing can run."""
    import re
    src = CLOUD_JS
    for m in re.finditer(r"async function (_\w+)\(([^)]*)\)\s*\{", src):
        name = m.group(1)
        params = [a.strip() for a in m.group(2).split(",") if a.strip()]
        body = src[m.end():]
        body = body[:body.index("\n  }")]
        # Property accesses (.html) and object keys (html:) are not references
        # to a binding; object shorthand ({ html }) is, and is what broke.
        code = "\n".join(l for l in body.splitlines()
                         if not l.strip().startswith(("//", "/*", "*")))
        code = re.sub(r"\.\s*\w+", "", code)
        code = re.sub(r"\b\w+\s*:", "", code)
        declared = set(params) | set(re.findall(r"\b(?:const|let|var)\s+(\w+)", body))
        for ident in ("title", "tid", "html", "shareKey"):
            if re.search(rf"\b{ident}\b", code) and ident not in declared:
                raise AssertionError(
                    f"{name}() uses `{ident}` but never takes or declares it "
                    f"— params were {params}")


def test_the_reports_page_names_a_private_timeline_properly():
    """COURSE_META lists what is published publicly, so a private timeline
    falls back to its raw id — "civ-pro-jade" where the owner expects "Civil
    Procedure — Jade". Restoring the reports button made that heading visible."""
    from alto.build.pages import build_reports
    page = build_reports([], "")
    assert "if(!COURSE_META[courseId]){" in page
    assert "p.tid === courseId" in page
    # never on an unauthenticated page: the name is the owner's alone
    fn = page[page.index("if(!COURSE_META[courseId]){"):]
    assert "!c.user" in fn[:fn.index("listPages()")]
