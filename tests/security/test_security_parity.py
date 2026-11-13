"""B4 (security review, HIGH): the Bass branch must carry the SAME share viewer, cloud client and Firestore rules as alto-security-beta
(F1-F3, R1), so that publishing from alto-bass can never undo them. Bass adds nothing to these files; its only rules addition is the
Documents path in storage.rules (one file for both trees, B5: tests/security/test_storage_rules.py).

Two checks:
  pinned  the files hash to alto-security-beta at the commit in security_parity.json (always runs, offline)
  live    when a ref of alto-security-beta is available locally (git fetch <alto-connector> alto-security-beta, then ALTO_SECURITY_REF=<ref>,
          default `sec/alto-security-beta`), the files are byte-identical to it: a newer security fix not yet merged fails here.
When either fails: merge the latest alto-security-beta into this branch, then refresh security_parity.json from it."""
import hashlib
import json
import os
import subprocess
from pathlib import Path

import re

import pytest

ROOT = Path(__file__).resolve().parents[2]
PIN = json.loads((Path(__file__).with_name("security_parity.json")).read_text("utf-8"))
FILES = sorted(PIN["sha256"])
REF = os.environ.get("ALTO_SECURITY_REF", "sec/alto-security-beta")

# The ONLY Bass additions allowed in these files, each removed exactly once before comparing (anything else that differs fails):
#   firestore.rules (both copies): the three deny-all `match /bass_research*/{document=**} { allow read, write: if false; }` blocks for
#   the opt-in conversation sharing (research_share.py), with their comment. Deny-all only: any allow rule there fails the pattern.
#   publish_static.py: the Bass proxy origin in connect-src (_bass_src), empty unless the build has the Bass UI AND a proxy URL; and the
#   /drive-picker/ page + its own header rule (_picker_csp), likewise None unless the build has the Bass UI AND a proxy URL.
_RESEARCH_RULES = [(r'\n    // Opt-in conversation sharing[^\n]*\n    // [^\n]*\n(?:    match /bass_research(?:_consent|_purge)?/\{document=\*\*\} \{\n      allow read, write: if false;\n    \}\n){3}', '')]
BASS_ADDITIONS = {
    "firestore.rules": _RESEARCH_RULES,
    "alto/firestore.rules": _RESEARCH_RULES,
    "alto/publish_static.py": [
        (r' \+ _bass_src\(\),\n', ',\n'),
        (r'\n\ndef _bass_src\(\) -> str:\n(?:    .*\n|\n)*?    return \(" " \+ m\.group\(1\)\) if m else ""\n', ''),
        # Add from Drive: /drive-picker/, the one page that loads Google's Picker, and the one path whose CSP names Google's origins (gated like _bass_src)
        (r', picker_csp=_picker_csp\(\)\)\n', ')\n'),
        (r'\n\ndef _picker_csp\(\)[^\n]*\n(?:    .*\n|\n)*?    return PICKER_CSP[^\n]*\n', ''),
        (r', picker_csp: str \| None = None\) -> list\[dict\]:', ') -> list[dict]:'),
        (r'        # Bass "Add from Drive": the Picker\'s page and ONLY[^\n]*\n        \*\(\[\{"source": "/drive-picker/\*\*", "headers": \[\n[^\n]*\n        \]\}\] if picker_csp else \[\]\),\n', ''),
        (r'    # Bass "Add from Drive": the Picker\'s own page[^\n]*\n    if _picker_csp\(\):\n(?:        .*\n)+\n', ''),
    ],
}


def ours(path) -> bytes:
    raw = (ROOT / path).read_bytes()
    text = raw.decode("utf-8")
    for pat, sub in BASS_ADDITIONS.get(path, []):
        text, n = re.subn(pat, sub, text)
        if n > 1:
            raise AssertionError(f"{path}: the Bass addition {pat!r} appears {n} times")
    return text.encode("utf-8")


def test_the_bass_csp_addition_is_gated():
    src = (ROOT / "alto/publish_static.py").read_text("utf-8")
    if "_bass_src" in src:
        body = src[src.index("def _bass_src"):].split("\n\n\ndef ")[0]
        assert "if not bass_ui.enabled():" in body and 'return ""' in body and "re.fullmatch(" in body     # gated, one checked origin


def test_the_pin_covers_the_files_b4_names():
    assert {"alto/build/share_shell.py", "alto/cloud/alto-cloud.js", "firestore.rules", "alto/firestore.rules"} <= set(FILES)


@pytest.mark.parametrize("path", FILES)
def test_same_as_alto_security_beta_pinned(path):
    got = hashlib.sha256(ours(path)).hexdigest()
    assert got == PIN["sha256"][path], f"{path} differs from alto-security-beta @ {PIN['commit'][:7]}: merge it, do not edit it here"


def _live(path):
    r = subprocess.run(["git", "-C", str(ROOT), "show", f"{REF}:{path}"], capture_output=True)
    return r.stdout if r.returncode == 0 else None


@pytest.mark.parametrize("path", FILES)
def test_same_as_alto_security_beta_live(path):
    theirs = _live(path)
    if theirs is None:
        pytest.skip(f"{REF} is not fetched here")
    assert ours(path) == theirs, f"{path} differs from {REF}: merge the latest alto-security-beta"
