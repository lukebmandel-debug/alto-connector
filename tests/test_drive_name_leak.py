"""No UNFLAGGED Drive file name may appear ANYWHERE in what goes to other people: share links, offline copies, previews. Every way a chip is made
(one pick, a pick of several, a pasted link with a typed name) and every later change (switched off after being shown, renamed, re-linked, removed).
The names are distinctive markers and the whole output is searched: markup, attributes, JSON blocks, packed blocks. Plain venv, no SDK, nothing skipped."""
import base64
import gzip
import html as H
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from alto.build import manual_edit as ME  # noqa: E402
from alto.build.builder import build_timeline, load_brief  # noqa: E402
from alto.build.reidentify import reidentify  # noqa: E402
from alto.build.sanitize import clean_linked_markup  # noqa: E402
from alto.build.single_file import bundle, preview, private_page  # noqa: E402
from alto.edits import fold  # noqa: E402
from test_manual_edit import Store, _d, _node  # noqa: E402

NODE = shutil.which("node") or str(Path.home() / ".local/node/bin/node")
KEY = "n|formation|s|0|t"
SHARE_KEY = "czckq4utebcx5rvgdptrgt"
M = ["ZQXALPHAMARK", "ZQXBRAVOMARK", "ZQXCHARLIEMARK", "ZQXDELTAMARK", "ZQXECHOMARK"]          # marker names: letters only, so no escaping can hide one
IDS = ["1AaaaaaaaaaaaaaZQ%d" % i for i in range(5)]


def _chip(i, share="0", key=None, name=None, words=None):
    """A chip exactly as the page writes it (manual_edit gdChip)."""
    did = IDS[i]
    return ('<a class="note-link" data-src="%s" data-gdrive="%s" data-gdrive-share="%s" href="https://drive.google.com/file/d/%s/view" target="_blank" '
            'rel="noopener noreferrer" data-gdrive-id="%s" data-file-name="%s" title="Hidden on share links. Opens in Google Drive.">%s</a>'
            % (key or "gd-mark%02d" % i, key or "gd-mark%02d" % i, share, did, did, name or M[i] + ".pdf", words or "my own words"))


def _gd_make(files):
    """The page's own gdMake, run in node with a stand-in DOM: the words each chip is given."""
    src = ME._DRIVE_FN_NEW
    body = src[src.index("  function gdMake(files){"):src.index("  function linkDriveUrl(){")]
    js = """var GD_ID=/^[A-Za-z0-9_-]{10,100}$/, out=[], savedRange=null, k=0;
function linkBox(){ return {querySelector:function(){ return {checked:false, textContent:''}; }}; }
function gdName(s){ return String(s||''); } function rid(p){ return p+'k'+(k++); }
function el(){ var e={nextSibling:null}; e.parentNode={insertBefore:function(){}}; return e; }
var document={createTextNode:el};
function wrapSel(a){ a.words='(the words the owner selected)'; }
function gdChip(key,id,name,share,words){ var a=el(); a.name=name; a.words=words===undefined?null:words; out.push(a); return a; }
""" + body + "\ngdMake(JSON.parse(process.argv[1])); console.log(JSON.stringify(out.map(function(a){ return {name:a.name, words:a.words}; })));"
    r = subprocess.run([NODE, "-e", js, json.dumps(files)], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def _store():
    st = Store(_d())
    page, _ = clean_linked_markup(_node(st, "formation")["sections"][0]["t"], {})
    return st, page


def _edit(st, base, value, t):
    """One edit of the section on the owner's page (made against what the page showed: base), folded into the draft."""
    st.edits = {"v": 1, "ops": {KEY: {"b": base, "v": value, "t": t}}}
    r = fold(st, "u", "t1")
    assert r["folded"] + r["already_in_draft"] == 1 and not r["conflicts"], r          # a change of the share switch alone leaves the words as they are
    return value


def _packed(text):
    """Every packed block in the text, unpacked: gzip in base64 (any run long enough to be one)."""
    out = []
    for m in re.finditer(r"H4sI[A-Za-z0-9+/_-]{20,}={0,2}", text):
        try:
            out.append(gzip.decompress(base64.b64decode(m.group(0).replace("-", "+").replace("_", "/") + "==")).decode("utf-8", "replace"))
        except Exception:
            pass
    return out


def _forms(text):
    yield text
    yield H.unescape(text)
    try:
        yield text.encode("utf-8").decode("unicode_escape", "replace")
    except Exception:
        pass
    yield text.replace("\\", "")
    for p in _packed(text):
        yield p
        yield H.unescape(p)


def _outputs(st):
    b, nodes, conns = load_brief({"brief": st.doc["brief"], "nodes": st.nodes, "connections": st.conns})
    page, _ = build_timeline(b, nodes, conns)
    private = private_page(b, page)
    return private, {"share": reidentify(private, SHARE_KEY), "offline": bundle(b, page), "preview": preview(b, page)}


def _no_name(st, hidden, shown=()):
    private, outs = _outputs(st)
    for where, text in outs.items():
        assert len(text) > 10000, where
        for form in _forms(text):
            low = form.lower()
            for i in hidden:
                assert M[i].lower() not in low, "%s carries the name %s" % (where, M[i])
                assert IDS[i].lower() not in low, "%s carries the id of %s" % (where, M[i])
        for i in shown:                                                   # the check can see a name when one is there: a chip switched on IS carried
            assert M[i] in text and IDS[i] in text, (where, M[i])
    return private


def test_one_pick_left_hidden():
    st, page = _store()
    _edit(st, page, page + " See " + _chip(0) + ".", 1)
    assert st.doc["brief"]["linked_files"][0]["name"] == M[0] + ".pdf"          # the owner's draft keeps the name
    _no_name(st, [0])


def test_the_page_gives_further_files_neutral_words_never_their_names():
    got = _gd_make([{"id": IDS[i], "name": M[i] + ".pdf"} for i in range(5)])
    assert [g["name"] for g in got] == [M[i] + ".pdf" for i in range(5)]       # the name rides on the chip (data-file-name), which a hidden chip drops
    assert got[0]["words"] == "(the words the owner selected)"
    assert [g["words"] for g in got[1:]] == ["Drive file 2", "Drive file 3", "Drive file 4", "Drive file 5"]
    assert not [g for g in got if any(m in str(g["words"]) for m in M)]


def test_a_pick_of_five_left_hidden():
    words = _gd_make([{"id": IDS[i], "name": M[i] + ".pdf"} for i in range(5)])
    st, page = _store()
    chips = ", ".join(_chip(i, words="my own words" if i == 0 else words[i]["words"]) for i in range(5))
    _edit(st, page, page + " See " + chips + ".", 1)
    assert len(st.doc["brief"]["linked_files"]) == 5
    _no_name(st, range(5))


def test_a_pick_of_several_with_one_shown():
    st, page = _store()
    _edit(st, page, page + " See " + _chip(0) + ", " + _chip(1, share="1", words="Drive file 2") + ", " + _chip(2, words="Drive file 3") + ".", 1)
    _no_name(st, [0, 2], shown=[1])


def test_a_pasted_link_with_a_typed_name():
    st, page = _store()
    _edit(st, page, page + " See " + _chip(3, name=M[3] + " typed by hand") + ".", 1)
    _no_name(st, [3])


def test_shown_then_switched_off():
    st, page = _store()
    p2 = _edit(st, page, page + " See " + _chip(0, share="1") + ".", 1)
    _no_name(st, [], shown=[0])
    assert 'data-gdrive-share="1"' in p2
    off = re.sub(r"<a\b[^>]*data-gdrive=[^>]*>.*?</a>", lambda m: _chip(0, share="0"), p2)
    assert off != p2
    _edit(st, p2, off, 2)
    assert st.doc["brief"]["linked_files"][0]["share"] is False
    _no_name(st, [0])


def test_renamed_while_hidden():
    st, page = _store()
    p2 = _edit(st, page, page + " See " + _chip(0) + ".", 1)
    new = re.sub(r"<a\b[^>]*data-gdrive=[^>]*>.*?</a>", lambda m: _chip(0, name=M[4] + " new name", words="other words"), p2)
    _edit(st, p2, new, 2)
    _no_name(st, [0, 4])


def test_relinked_to_another_file_and_then_removed():
    st, page = _store()
    p2 = _edit(st, page, page + " See " + _chip(0, share="1") + ".", 1)
    new = re.sub(r"<a\b[^>]*data-gdrive=[^>]*>.*?</a>", lambda m: _chip(1, words="other words"), p2)       # a new chip takes the old one's place
    p3 = _edit(st, p2, new, 2)
    _no_name(st, [0, 1])                                                   # the old one, though it was shown, is gone with its chip
    gone = re.sub(r"<a\b[^>]*data-gdrive=[^>]*>.*?</a>", "other words", p3)
    _edit(st, p3, gone, 3)
    _no_name(st, [0, 1])


def test_the_same_key_pointed_at_another_file_while_hidden():
    st, page = _store()
    p2 = _edit(st, page, page + " See " + _chip(0, key="gd-samekey1") + ".", 1)
    new = re.sub(r"<a\b[^>]*data-gdrive=[^>]*>.*?</a>", lambda m: _chip(2, key="gd-samekey1"), p2)
    _edit(st, p2, new, 2)
    _no_name(st, [0, 2])
