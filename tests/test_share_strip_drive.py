"""A Drive chip is shown on share links, offline copies and previews ONLY when the owner switched it on for that chip. Everything else leaves no id, no
name and no address in anything that goes to other people. The private page (the owner's own) keeps it. Plain venv, no SDK, nothing skipped."""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto import drive_common as DC  # noqa: E402
from alto.build.builder import build_timeline, load_brief  # noqa: E402
from alto.build.reidentify import reidentify  # noqa: E402
from alto.build.single_file import bundle, preview, private_page  # noqa: E402

NODE = shutil.which("node") or str(Path.home() / ".local/node/bin/node")
CLOUD_JS = (ROOT / "alto" / "cloud" / "alto-cloud.js").read_text(encoding="utf-8")
HIDDEN, SHOWN = "1HiddenFileIdAbc", "1SharedFileIdXyz"
NAME_H, NAME_S = "Hidden grades sheet", "Shared reading list"
KEY = "czckq4utebcx5rvgdptrgt"


def _page():
    d = json.loads((ROOT / "samples" / "outline_brief.json").read_text(encoding="utf-8"))
    d["brief"]["linked_files"] = [
        {"id": "gd-hid111", "kind": "drive", "drive_id": HIDDEN, "name": NAME_H, "share": False},
        {"id": "gd-shw222", "kind": "drive", "drive_id": SHOWN, "name": NAME_S, "share": True}]
    root = next(n for n in d["nodes"] if not n.get("parent"))
    root["sections"] = [{"h": "Files", "t": 'Read <a href="src:gd-hid111">my private sheet</a> and <a href="src:gd-shw222">the class list</a>.'}]
    b, nodes, conns = load_brief(d)
    html, _ = build_timeline(b, nodes, conns)
    return b, html


def _clean(page, keep_shown=True):
    assert HIDDEN not in page and NAME_H not in page and "my private sheet" in page
    flat = page.replace('\\"', '"')                  # a bundle embeds the page as JSON text
    if keep_shown:
        assert "https://drive.google.com/file/d/%s/view" % SHOWN in flat and 'data-gdrive-share="1"' in flat
    else:
        assert SHOWN not in page


def test_the_build_keeps_a_hidden_chips_id_only_in_the_local_block():
    b, html = _page()
    flat = html.replace('\\"', '"').replace('\\u003c', '<')                      # detail text rides in the page as JSON
    hid = re.search(r'<a href="#"[^>]*data-gdrive="gd-hid111"[^>]*>', flat).group(0)
    assert 'data-gdrive-share="0"' in hid and HIDDEN not in hid and NAME_H not in hid and "data-gdrive-id" not in hid     # no id, no name, no address on the chip
    block = re.search(r'<script id="alto-local-src">([\s\S]*?)</script>', html).group(1)
    assert HIDDEN in block and '"drive": {"gd-hid111": "%s"}' % HIDDEN in block and SHOWN not in block and '"files"' not in block
    assert html.count(HIDDEN) == 1                                                                              # nowhere else in the page
    shown = re.search(r'<a href="[^"]*"[^>]*data-gdrive="gd-shw222"[^>]*>', flat).group(0)
    assert DC.drive_url(SHOWN) in shown and 'data-gdrive-share="1"' in shown and 'data-gdrive-id="%s"' % SHOWN in shown
    assert HIDDEN in private_page(b, html)                                                                      # the owner's own page keeps it


def test_share_links_drop_the_unflagged_chip_and_keep_the_flagged_one():
    b, html = _page()
    share = reidentify(private_page(b, html), KEY)
    _clean(share)
    assert "the class list" in share and DC.drive_url(SHOWN) in share


def test_offline_copy_and_preview_drop_it_too():
    b, html = _page()
    _clean(bundle(b, html))
    _clean(preview(b, html))


def test_no_id_hides_anywhere_else_in_the_page_text():
    b, html = _page()
    for out in (reidentify(private_page(b, html), KEY), bundle(b, html), preview(b, html)):
        assert HIDDEN not in out and NAME_H not in out
        assert re.search(r"data-gdrive-id", out) is None or HIDDEN not in out


def test_every_chip_unflagged_means_no_drive_trace_at_all():
    d = json.loads((ROOT / "samples" / "outline_brief.json").read_text(encoding="utf-8"))
    d["brief"]["linked_files"] = [{"id": "gd-hid111", "kind": "drive", "drive_id": HIDDEN, "name": NAME_H, "share": False}]
    root = next(n for n in d["nodes"] if not n.get("parent"))
    root["sections"] = [{"h": "Files", "t": 'See <a href="src:gd-hid111">the sheet</a>.'}]
    b, nodes, conns = load_brief(d)
    html, _ = build_timeline(b, nodes, conns)
    share = reidentify(private_page(b, html), KEY)
    assert "drive.google.com/file" not in share and "data-gdrive" not in share and "the sheet" in share


# ── the browser makes the live shares with alto-cloud.js, which this change does not touch: it already empties the _ALTO_LOCAL block ──────────────

def test_the_existing_browser_strip_alone_is_enough():
    from alto.build.reidentify import LOCAL_BLOCK, LOCAL_EMPTY
    js = re.search(r"const LOCAL_BLOCK = /(.*?)/g;", CLOUD_JS).group(1)
    assert js.replace("<\\/", "</") == LOCAL_BLOCK.pattern                                                     # the same pattern the cloud client uses
    b, html = _page()
    out = LOCAL_BLOCK.sub(LOCAL_EMPTY, private_page(b, html))
    assert HIDDEN not in out and NAME_H not in out and "data-gdrive-id=\"%s\"" % HIDDEN not in out and "my private sheet" in out
    assert DC.drive_url(SHOWN) in out


def test_strip_unshared_handles_both_spellings_and_the_id_map():
    h = ('x <a class="n" data-gdrive="gd-abc123" data-gdrive-id="%s" data-gdrive-share="0" href="u">My file</a> y '
         '<a data-gdrive="gd-abc124" data-gdrive-share="1" href="#">ok</a> <a href="z">k</a>' % HIDDEN)
    out = DC.strip_unshared(h)
    assert HIDDEN not in out and "My file" in out and 'data-gdrive="gd-abc124"' in out and '<a href="z">k</a>' in out
    j = json.dumps(h).replace("<", "\\u003c")
    outj = DC.strip_unshared(j)
    assert HIDDEN not in outj and "My file" in outj and "gd-abc124" in outj
    blk = '<script id="alto-local-src">window._ALTO_LOCAL={"root":"/a","files":{},"drive":{"gd-abc123":"%s"}};</script>' % HIDDEN
    assert DC.strip_unshared(blk) == '<script id="alto-local-src">window._ALTO_LOCAL={"root":"/a","files":{}};</script>'
    only = '<script id="alto-local-src">window._ALTO_LOCAL={"drive":{"gd-abc123":"%s"}};</script>' % HIDDEN
    assert DC.strip_unshared(only) == '<script id="alto-local-src">window._ALTO_LOCAL={};</script>'
    assert DC.strip_unshared('{"drive":{"other":1}}') == '{"drive":{"other":1}}'                                # only a Drive id map is touched
