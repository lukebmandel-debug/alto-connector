"""✎ Edit timeline: every timeline's way back to Claude (detail_extras.EDIT_TILE).

The tile sits after the last unit on the desktop map and at the end of the
MENU drawer on a phone, and opens Claude with a prompt naming the timeline.
A share snapshot — someone else's timeline — must not offer it.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build.blocks import ID_PATTERNS  # noqa: E402
from alto.build.builder import load_brief, build_timeline  # noqa: E402
from alto.build import detail_extras as dx  # noqa: E402
from alto.build.reidentify import reidentify  # noqa: E402
from alto.build.single_file import bundle, private_page  # noqa: E402

NODE = __import__("shutil").which("node") or str(Path.home() / ".local/node/bin/node")
KEY = "czckq4utebcx5rvgdptrgt"


@pytest.fixture(scope="module", params=["outline_brief.json", "contracts_brief.json"])
def built(request):
    d = json.loads((ROOT / "samples" / request.param).read_text(encoding="utf-8"))
    b, nodes, conns = load_brief(d)
    html, _ = build_timeline(b, nodes, conns)
    return b, html


def _edit_data(html):
    return json.loads(re.search(r"window\._ALTO_EDIT=(\{.*?\});</script>", html).group(1))


def test_every_timeline_carries_the_tile(built):
    b, html = built
    assert html.count('<script id="alto-edit-tile">') == 1
    assert _edit_data(html) == {"title": b.title,
                                "key": ID_PATTERNS["doc_save_key"].format(tid=b.timeline_id)}


def test_the_offline_copy_and_private_page_keep_it(built):
    b, html = built
    assert "alto-edit-tile" in bundle(b, html)
    assert "alto-edit-tile" in private_page(b, html)


def test_a_share_reads_back_as_a_share(built):
    """The key is rewritten with the rest of the identity, so the tile's own
    check (an 's-' id) hides it in the share."""
    b, html = built
    share = reidentify(private_page(b, html), KEY)
    assert _edit_data(share)["key"] == "alto-doc-s-" + KEY
    js = dx.EDIT_TILE
    assert "tid.indexOf('s-') === 0) return;" in js


def test_never_on_a_phone_or_in_print():
    """Timelines are made and changed with Claude on a computer."""
    js = dx.EDIT_TILE
    assert "html.mobile .alto-edit-tile{display:none !important;}" in js
    assert "@media print{.alto-edit-tile{display:none !important;}}" in js
    assert "nav-drawer" not in js and "drawer-edit-btn" not in js


def test_a_title_cannot_break_out_of_its_script():
    class B:
        title, timeline_id = 'x</script><script>alert(1)</script>"', "t"
    out = dx.edit_tile(B())
    assert "</script><script>alert" not in out.split('<style id="alto-edit-css">')[0]


MAC = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15"
IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Mobile/15E148"


def _prompt(title, key, ua=MAC):
    if not Path(NODE).is_file():
        pytest.skip("needs node")
    script = dx.EDIT_TILE.split('<script id="alto-edit-tile">', 1)[1].rsplit("</script>", 1)[0]
    harness = r"""
    const [script, title, key, ua] = JSON.parse(process.argv[1]);
    const went = [];
    global.window = global;
    window._ALTO_EDIT = { title, key };
    global.document = { title: 'x', getElementById: () => null, addEventListener(){},
                        createElement: () => ({ classList: { add(){}, remove(){} }, appendChild(){} }),
                        body: { appendChild(){} } };
    Object.defineProperty(globalThis, 'navigator', { value: { userAgent: ua, maxTouchPoints: 0 }, configurable: true });
    window.top = { location: { set href(u){ went.push(u); } } };
    window.addEventListener = () => {}; global.setTimeout = () => 0;
    eval(script);
    if (window._altoEditTimeline) window._altoEditTimeline();
    console.log(JSON.stringify(went));
    """
    out = subprocess.run([NODE, "-e", harness, json.dumps([script, title, key, ua])],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def test_the_prompt_names_the_timeline_and_how_to_edit_it():
    went = _prompt("Torts", "alto-doc-torts")
    assert len(went) == 1 and went[0].startswith("claude://claude.ai/new?q=")
    from urllib.parse import unquote
    q = unquote(went[0].split("?q=", 1)[1])
    for must in ('"Torts" (timeline id: torts)', "https://alto-get.web.app",
                 "get_timeline", "new notes to add, sources to link",
                 "rebuild and republish"):
        assert must in q, must


def test_a_share_opens_nothing():
    assert _prompt("Torts", "alto-doc-s-" + KEY) == []


def test_a_phone_gets_no_tile():
    assert _prompt("Torts", "alto-doc-torts", IPHONE) == []


def test_the_guide_explains_the_button():
    g = (ROOT / "alto" / "interview_guide.md").read_text(encoding="utf-8")
    sec = g[g.index("## Changes go through Claude"):g.index("## What the user gets")]
    assert "Edit timeline" in sec and "get_timeline(<id>)" in sec and "list_projects" in sec


def test_the_tile_sits_inside_the_last_band(built):
    """Luke: extend the timeline's background rather than hang the tile on a
    bar of its own below it. The last band grows by the tile's row, set only
    where the tile shows."""
    b, html = built
    assert "bands[bands.length-1].endY += 100 + (window._altoEditRoom || 0);" in html
    js = dx.EDIT_TILE
    ro = js.index("window._altoEditRoom = ROOM;")
    assert js.index("tid.indexOf('s-') === 0) return;") < ro   # not in a share
    assert js.index("Windows Phone/i.test(navigator.userAgent)) return;") < ro  # nor on a phone
    assert "return b - ROOM - 60;" in js
