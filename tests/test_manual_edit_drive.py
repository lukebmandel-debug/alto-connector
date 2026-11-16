"""Manual edit's Drive chip, page side (alto/build/manual_edit.py drive_patch + alto/drive_common.py): the id check, name cleaning, the built address,
and the paste-a-link parser, in Python and in the page's own JS (run in node). Plain venv, no SDK, nothing skipped."""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto import drive_common as DC  # noqa: E402
from alto.build import manual_edit as ME  # noqa: E402

NODE = shutil.which("node") or str(Path.home() / ".local/node/bin/node")
ID = "1AbCdEfGhIjKlMn"
GOOD = [
    ("https://docs.google.com/document/d/%s/edit?usp=sharing" % ID, ID),
    ("https://docs.google.com/spreadsheets/d/%s/edit#gid=0" % ID, ID),
    ("https://docs.google.com/presentation/d/%s" % ID, ID),
    ("https://drive.google.com/file/d/%s/view?usp=drive_link" % ID, ID),
    ("https://drive.google.com/open?id=%s" % ID, ID),
    ("https://drive.google.com/uc?export=download&id=%s" % ID, ID),
    ("  https://drive.google.com/file/d/%s/view  " % ID, ID),
]
BAD = ["", "garbage", "javascript:alert(1)", "https://evil.example/document/d/%s/edit" % ID, "https://docs.google.com.evil.io/document/d/%s/edit" % ID,
       "http://docs.google.com/document/d/%s/edit" % ID, "https://drive.google.com/file/d/short/view", "https://docs.google.com/document/d/%s<x>/edit" % ID,
       "https://drive.google.com/file/d/%s/view\nhttps://x.y" % ID, "data:text/html,<script>1</script>", "https://user@drive.google.com/file/d/%s/view" % ID,
       "https://docs.google.com/forms/d/%s/edit" % ID, "https://drive.google.com/drive/folders/%s" % ID, None, 123]


@pytest.mark.parametrize("link,want", GOOD)
def test_python_parser_takes_the_four_shapes(link, want):
    assert DC.parse_drive_link(link) == want


@pytest.mark.parametrize("link", BAD)
def test_python_parser_refuses_everything_else(link):
    assert DC.parse_drive_link(link) is None


def _js_helpers():
    """The page's own gdName / gdParse, lifted out of the patch text and run in node."""
    src = ME._DRIVE_FN_NEW
    a, b = src.index("var GD_KEY"), src.index("function gdChip")
    return src[a:b]


def _node(items, code):
    body = _js_helpers() + "\nconst I=JSON.parse(process.argv[1]); console.log(JSON.stringify(I.map(function(x){ return " + code + "; })));"
    out = subprocess.run([NODE, "-e", body, json.dumps(items)], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_the_page_parses_exactly_as_python_does():
    cases = [g for g, _ in GOOD] + [b for b in BAD if isinstance(b, str)]
    assert _node(cases, "gdParse(x)") == [DC.parse_drive_link(c) for c in cases]


def test_the_page_cleans_names_as_python_does():
    names = ['a<b>"c\u0001d', "x" * 400, "  spaced  ", "<<<>>>", "Syllabus (final).pdf", "tab\there"]
    got = _node(names, "gdName(x)")
    assert got == [DC.clean_name(n, default="") for n in names]
    assert all(len(g) <= 200 and not re.search(r'[<>"\x00-\x1f]', g) for g in got)


def test_python_name_cleaning_and_the_default():
    assert DC.clean_name('a<b>"c\x01') == "abc" and DC.clean_name("") == "Drive file" and DC.clean_name("<>") == "Drive file"
    assert len(DC.clean_name("y" * 999)) == 200


def test_the_address_is_built_never_copied_and_javascript_is_rejected():
    assert DC.drive_url(ID) == "https://drive.google.com/file/d/%s/view" % ID
    assert DC.drive_url("javascript:alert(1)//aaaa") is None
    src = ME._DRIVE_FN_NEW
    chip = src[src.index("function gdChip"):src.index("function gdMake")]
    assert "'https://drive.google.com/file/d/' + id + '/view'" in chip and "getAttribute('href')" not in chip      # built from the id, nothing read back
    walk = ME._DRIVE_WALK_NEW
    assert "GD_ID.test(gid) ? gid : ''" in walk and "n.getAttribute('href')" not in walk


def _brief():
    return json.loads((ROOT / "samples" / "outline_brief.json").read_text(encoding="utf-8"))


def test_the_patch_is_built_in_only_with_all_three_identifiers(monkeypatch):
    from alto.build.builder import build_timeline, load_brief
    for n in DC.DriveConfig.ENV:
        monkeypatch.delenv(n, raising=False)
    off = build_timeline(*load_brief(_brief()))[0]
    assert "gdChip" not in off and "alto-drive-cfg" not in off and "Choose from Drive" not in off
    monkeypatch.setenv("ALTO_DRIVE_CLIENT_ID", "cid.apps.googleusercontent.com")
    monkeypatch.setenv("ALTO_DRIVE_API_KEY", "key-1")
    assert build_timeline(*load_brief(_brief()))[0] == off                                  # two of three: still nothing, byte for byte
    monkeypatch.setenv("ALTO_DRIVE_APP_ID", "12345")
    on = build_timeline(*load_brief(_brief()))[0]
    assert "function gdChip" in on and "Choose from Drive" in on and "or paste a Drive link" in on
    m = re.search(r'<script id="alto-drive-cfg">window\._ALTO_DRIVE=(\{.*?\});</script>', on)
    assert json.loads(m.group(1)) == {"client_id": "cid.apps.googleusercontent.com", "api_key": "key-1", "app_id": "12345"}


def test_the_patch_fails_loudly_when_manual_js_moves():
    with pytest.raises(ValueError, match="no longer matches"):
        ME.drive_patch("<script>nothing here</script>", "<style></style>")


def test_the_built_page_script_is_valid_javascript(monkeypatch, tmp_path):
    from alto.build.builder import build_timeline, load_brief
    for n, v in zip(DC.DriveConfig.ENV, ("c.apps.googleusercontent.com", "k", "1")):
        monkeypatch.setenv(n, v)
    page = build_timeline(*load_brief(_brief()))[0]
    js = re.search(r'<script id="alto-manual">([\s\S]*?)</script>', page).group(1)
    f = tmp_path / "m.js"
    f.write_text(js, encoding="utf-8")
    r = subprocess.run([NODE, "--check", str(f)], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
