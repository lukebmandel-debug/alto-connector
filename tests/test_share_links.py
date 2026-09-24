"""A share link: readable without signing in, and unable to touch the original.

Two things are worth testing hardest, because both fail silently.

The first is ISOLATION. A share and its master are the same document twice,
served from the same origin, and a srcdoc iframe inherits that origin — so
unless their identities differ they address the same localStorage keys and the
same users/{uid}/tl/{tid} document. The owner opening their own share link
would merge a recipient's highlights into their master, and nothing anywhere
would report it.

The second is the RULES. `allow read` would cover both get and list, and a
listable shares collection turns 110 bits of unguessable key into a directory
anyone can walk. The feature works perfectly either way.
"""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build.blocks import ID_PATTERNS                    # noqa: E402
from alto.build.builder import build_timeline, load_brief    # noqa: E402
from alto.build.reidentify import (                          # noqa: E402
    ReidentifyError, identity_of, reidentify, share_id)
from alto.build.share_shell import shell                     # noqa: E402
from alto.build.single_file import private_page              # noqa: E402

SAMPLE = ROOT / "samples" / "contracts_brief.json"
CLOUD_JS = (ROOT / "alto" / "cloud" / "alto-cloud.js").read_text(encoding="utf-8")
RULES = (ROOT / "firestore.rules").read_text(encoding="utf-8")
KEY = "czckq4utebcx5rvgdptrgt"


@pytest.fixture(scope="module")
def master():
    d = json.loads(SAMPLE.read_text(encoding="utf-8"))
    b, nodes, conns = load_brief(d)
    html, _ = build_timeline(b, nodes, conns)
    return b, private_page(b, html, "Contracts — Section A")


# ── isolation ───────────────────────────────────────────────────────────────

def test_a_share_carries_none_of_the_masters_storage_keys(master):
    """The whole feature rests on this one assertion."""
    b, page = master
    share = reidentify(page, KEY)
    for name, tmpl in ID_PATTERNS.items():
        stale = tmpl.format(tid=b.timeline_id)
        assert stale not in share, f"{name} still points at the master"


def test_every_identity_pattern_actually_occurs_in_a_real_page(master):
    """A pattern that never matches proves nothing, and would hide the day a
    template stopped using it — leaving that storage key shared in silence."""
    b, page = master
    for name, tmpl in ID_PATTERNS.items():
        assert tmpl.format(tid=b.timeline_id) in page, f"{name} matches nothing"


def test_the_legacy_highlight_key_is_rewritten_too(master):
    """hl_key_legacy is hl_key plus a suffix, so it is deliberately not its own
    pattern. If that ever stops being true, a share keeps reading the master's
    pre-migration highlights."""
    b, page = master
    assert f"alto-hl-{b.timeline_id}-legacy" in page
    share = reidentify(page, KEY)
    assert f"alto-hl-{b.timeline_id}-legacy" not in share
    assert f"alto-hl-{share_id(KEY)}-legacy" in share


def test_a_share_is_otherwise_the_same_page(master):
    b, page = master
    share = reidentify(page, KEY)
    assert abs(len(share) - len(page)) < 1000
    assert "function initLayout(" in share


def test_two_shares_of_one_timeline_do_not_share_storage(master):
    b, page = master
    a = reidentify(page, KEY)
    c = reidentify(page, "aaaaaaaaaaaaaaaaaaaaaa")
    assert identity_of(a) != identity_of(c)


def test_a_page_that_is_not_a_timeline_is_refused():
    with pytest.raises(ReidentifyError):
        reidentify("<html><head></head><body>hello</body></html>", KEY)


def test_the_browser_and_the_builder_agree_on_the_patterns():
    """These two lists must match exactly. Nothing else here would notice if
    they drifted — the share would simply keep one of the master's keys."""
    block = CLOUD_JS[CLOUD_JS.index("const ID_PATTERNS = ["):]
    block = block[:block.index("\n  ];")]
    found = dict(re.findall(r'\["([a-z_]+)", (".*?")\]', block))
    assert {k: json.loads(v) for k, v in found.items()} == dict(ID_PATTERNS)


def test_the_browser_refuses_a_partial_rewrite():
    """A half-rewritten share reads the master's storage for whichever key was
    missed, and looks entirely normal doing it."""
    fn = CLOUD_JS[CLOUD_JS.index("function _reidentify("):]
    fn = fn[:fn.index("\n  }")]
    assert "throw new Error('share still carries the original identity: '" in fn


def test_the_share_is_reidentified_before_it_is_written():
    order = CLOUD_JS[CLOUD_JS.index("async function _sharePush("):]
    order = order[:order.index("\n  }")]
    assert order.index("_reidentify(page.html") < order.index("_putShare(")


# ── the rules ───────────────────────────────────────────────────────────────

def test_shares_are_gettable_but_never_listable():
    m = re.search(r"match /shares/\{key\} \{(.*?)\n    \}", RULES, re.S)
    assert m, "no shares rule"
    body = m.group(1)
    assert "allow get: if true;" in body
    assert "allow list: if false;" in body
    assert "allow read" not in body, "read covers list — the key stops being a secret"


def test_only_the_owner_may_change_or_revoke_a_share():
    m = re.search(r"match /shares/\{key\} \{(.*?)\n    \}", RULES, re.S)
    body = m.group(1)
    assert "request.auth.uid == request.resource.data.owner" in body
    assert "request.auth.uid == resource.data.owner" in body


def test_the_owner_field_is_written_by_us_not_by_the_caller():
    """It is what every later update and delete is checked against."""
    fn = CLOUD_JS[CLOUD_JS.index("async function _putShare("):]
    fn = fn[:fn.index("\n  }")]
    assert "{ owner: u.uid," in fn


def test_publishing_deploys_the_rules():
    """Nothing in Alto used to deploy firestore.rules — it was a README step
    that everything silently depended on. A Firestore left in test mode is
    world-readable, and this feature adds a rule that must be live or sharing
    simply does not work."""
    src = (ROOT / "alto" / "publish_static.py").read_text(encoding="utf-8")
    assert 'targets.append("firestore:rules")' in src
    assert '"firestore"' in src


def test_a_failed_rules_deploy_fails_the_publish():
    """Pages shipped and rules not is the worst of both: it looks published and
    it is not protected."""
    src = (ROOT / "alto" / "publish_static.py").read_text(encoding="utf-8")
    fn = src[src.index("def deploy_site("):]
    assert "raise PublishError(f\"firebase deploy failed" in fn
    # A retry without firestore:rules would need a second deploy call. There is
    # exactly one, so there is no quiet path to a half-published site.
    assert fn.count("subprocess.run(") == 1


# ── the shell ───────────────────────────────────────────────────────────────

def test_the_shell_is_the_same_for_every_share():
    assert shell() == shell()
    assert len(shell()) < 20_000


def test_the_shell_carries_no_timeline_content(master):
    b, page = master
    s = shell()
    for leak in (b.title, b.timeline_id, KEY, "Contracts"):
        assert leak not in s


def test_the_shell_asks_search_engines_to_stay_away():
    assert 'name="robots" content="noindex, nofollow"' in shell()


def test_the_shell_does_not_wait_to_learn_who_you_are():
    """A share is readable signed out. Gating the first paint on an auth
    round-trip would make every recipient watch a spinner for nothing."""
    s = shell()
    assert "window.addEventListener('load', function(){ setTimeout(start, 250); });" in s
    body = s[s.index("function start()"):]
    assert "auth" not in body[:body.index("\n  }")].lower()


def test_a_revoked_share_and_a_wrong_key_read_the_same():
    """Distinguishing them would confirm that a given key once existed."""
    s = shell()
    assert s.count("This link is not shared any more.") >= 2


def test_getshare_does_not_require_a_user():
    fn = CLOUD_JS[CLOUD_JS.index("async function _getShare("):]
    fn = fn[:fn.index("\n  }")]
    assert "auth.currentUser" not in fn


# ── keeping a share ─────────────────────────────────────────────────────────

def test_saving_a_share_stores_a_reference_not_a_copy():
    """A copy would outlive revocation: the owner stops sharing and every
    recipient keeps reading it forever."""
    fn = CLOUD_JS[CLOUD_JS.index("async function _saveShare("):]
    fn = fn[:fn.index("\n  }")]
    assert "html" not in fn
    assert "'shared', key)" in fn


def test_revoking_deletes_the_public_copy_before_forgetting_it():
    """The other order leaves a live public document nobody is tracking."""
    fn = CLOUD_JS[CLOUD_JS.index("async function _shareRevoke("):]
    fn = fn[:fn.index("\n  }")]
    assert fn.index("_revokeShare(shareKey)") < fn.index("shareKey: ''")


# ── keys ────────────────────────────────────────────────────────────────────

def test_the_browsers_keys_look_like_the_connectors():
    from alto.mcp_server import _SHARE_ALPHABET
    m = re.search(r"const KEY_ALPHABET = '([^']+)'", CLOUD_JS)
    assert m and m.group(1) == _SHARE_ALPHABET
    assert re.search(r"new Uint8Array\(22\)", CLOUD_JS)


def test_the_key_is_minted_from_a_real_random_source():
    assert "crypto.getRandomValues" in CLOUD_JS
    assert "Math.random" not in CLOUD_JS


def test_the_share_id_cannot_collide_with_a_timeline_id():
    assert share_id(KEY).startswith("s-")
    assert re.fullmatch(r"[a-z0-9-]+", share_id(KEY))


# ── shared with me ──────────────────────────────────────────────────────────

def _home():
    from alto.build.pages import build_home
    return build_home([])


def test_a_kept_share_links_back_to_the_owners_copy():
    """Not to a copy in the recipient's account: the point of keeping a
    reference is that revoking the share revokes it."""
    home = _home()
    assert "'/s/' + encodeURIComponent(it.key) + '/'" in home


def test_your_own_work_sits_above_what_others_sent_you():
    """Both slabs come from independent Firestore reads, so whichever resolved
    first would otherwise decide the order."""
    home = _home()
    assert "wrap.insertBefore(slab, sharedSlab || nps);" in home


def test_signing_out_clears_the_shared_list_too():
    home = _home()
    assert "function clearShared()" in home
    body = home[home.index("function renderShared()"):]
    assert "clearShared(); return; }" in body[:400]
    fn = home[home.index("function renderAccount()"):]
    fn = fn[:fn.index("\nfunction ")]
    assert "renderShared();" in fn


def test_a_shared_title_is_not_parsed_as_markup():
    """This title was written by whoever shared it — the one string on the
    homepage that somebody else controls."""
    block = _home()[_home().index("function renderShared()"):]
    block = block[:block.index("\n}\n")]
    assert ".tile-title').textContent = it.title" in block


def test_a_kept_share_can_be_removed():
    home = _home()
    assert "c.forgetShare(it.key)" in home


def test_a_single_timeline_share_can_still_be_saved():
    """Rendering a timeline replaces the card the save button lived on, so
    without a control outside it the whole "keep what someone sent you" path
    is unreachable for the only kind of share that exists."""
    s = shell()
    assert "function savePill(" in s
    body = s[s.index("if(d.html){"):]
    assert "savePill(" in body[:body.index("return;")]


def test_the_save_offer_follows_sign_in_state():
    s = shell()
    assert "c.user ? 'Save to my Alto' : 'Sign in to save this'" in s
    assert "pill.dataset.t = title || '';" in s


def test_the_pill_stays_clear_of_the_engines_own_controls():
    """The engine keeps its controls bottom-right on every page."""
    s = shell()
    css = s[s.index("#pill{"):s.index("#pill.on{")]
    assert "left:16px" in css and "bottom:16px" in css
    assert "right:" not in css


def test_saving_a_project_share_saves_the_project_not_one_timeline():
    s = shell()
    assert "savePill((MANIFEST && MANIFEST.title) || '')" in s
