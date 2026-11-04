"""Guards on the rules text and on what the client code touches.

The emulator suite (tests/security/*.test.mjs) checks behaviour; these keep
the shape from drifting between runs of it: one copy of the rules, no
catch-all, nothing world-open but a share's `get`, and no client code
reaching a top-level collection the rules were not written for."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RULES = (ROOT / "firestore.rules").read_text(encoding="utf-8")
CODE = re.sub(r"//[^\n]*", "", RULES)
ALLOWED_TOP = {"users", "shares", "terms_acceptance"}


def test_both_copies_are_identical():
    assert (ROOT / "alto" / "firestore.rules").read_bytes() == (ROOT / "firestore.rules").read_bytes()


def test_there_is_no_catch_all_match():
    assert not re.search(r"match\s+/\{[a-z_]+=\*\*\}", CODE), "a root recursive match"
    assert "{path=**}" not in CODE.replace(" ", ""), "collection-group rules"


def _blocks():
    """(match path, allow line) for every allow, with its enclosing match."""
    out, stack = [], []
    for tok in re.finditer(r"match\s+(\S+)\s*\{|allow\s+[^;]+;|\{|\}", CODE):
        t = tok.group(0)
        if t.startswith("match"):
            stack.append(tok.group(1))
        elif t == "{":
            stack.append(None)
        elif t == "}":
            if stack:
                stack.pop()
        else:
            out.append(("".join(s for s in stack if s), " ".join(t.split())))
    return out


def test_only_a_shares_get_is_open_to_everyone():
    opened = [(p, a) for p, a in _blocks() if re.search(r":\s*if\s+true\s*;", a)]
    assert opened == [("/databases/{database}/documents/shares/{key}", "allow get: if true;")]


def test_no_rule_grants_on_sign_in_alone():
    for p, a in _blocks():
        cond = a.split(": if", 1)[1].strip(" ;")
        assert cond not in ("request.auth != null", "signedIn()"), (p, a)


def test_shares_are_never_listable_and_reads_are_split():
    for p, a in _blocks():
        if p.endswith("/shares/{key}") or "/private/" in p:
            assert not a.startswith("allow read"), (p, a)
    assert ("/databases/{database}/documents/shares/{key}", "allow list: if false;") in _blocks()


def test_the_allowlist_gates_writes_and_is_never_client_writable():
    assert "request.auth.token.email_verified == true" in CODE
    assert "request.auth.token.email.lower()" in CODE
    assert "get(/databases/$(database)/documents/bass_beta/allowlist).data.emails" in CODE
    for p, a in _blocks():
        if "/bass_beta/" in p:
            assert a == "allow read, write: if false;", (p, a)
        if re.match(r"allow (create|update|create, update)\b", a) and "/private/" not in p:
            assert "allowlisted()" in a, (p, a)


def test_no_money_state_under_an_account():
    users = RULES[RULES.index("match /users/{uid}"):RULES.index("// ── share links")]
    for word in ("credit", "ledger", "period", "billing", "bass"):
        assert word not in users.lower()


def _client_top_level():
    """Top-level collections named by the browser and connector code."""
    found = set()
    js = (ROOT / "alto" / "cloud" / "alto-cloud.js").read_text(encoding="utf-8")
    assert "collectionGroup" not in js
    found |= set(re.findall(r"\b(?:doc|collection)\(db,\s*'([^']+)'", js))
    py = (ROOT / "alto" / "store" / "cloud.py").read_text(encoding="utf-8")
    found |= set(re.findall(r"\{self\.root\}/([a-z_]+)", py))
    if re.search(r"def _doc\(self, uid", py):
        found.add("users")
    for tpl in (ROOT / "alto" / "engine").glob("*.html"):
        found |= set(re.findall(r"_fsUrl\('([a-z_]+)", tpl.read_text(encoding="utf-8")))
    return found


def test_client_code_touches_only_known_top_level_collections():
    found = _client_top_level()
    assert "users" in found and "shares" in found
    assert found <= ALLOWED_TOP, found - ALLOWED_TOP


def test_connect_page_says_who_gets_access():
    """It hands this computer the account's sign-in: the page must say so."""
    from alto.build.connect_page import connect_page
    html = connect_page()
    assert "is asking for full access" in html and "(port ' + port + ')" in html
    assert "Continue only if you just asked Claude" in html
