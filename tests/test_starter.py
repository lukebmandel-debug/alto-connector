"""A timeline started on the homepage, without Claude (alto/build/starter.py):
the starter pages the site serves, and what the browser makes of them."""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import starter  # noqa: E402
from alto.build.builder import load_brief  # noqa: E402
from alto.build.brief import validate_brief, validate_nodes  # noqa: E402

NODE = shutil.which("node") or str(Path.home() / ".local/node/bin/node")
needs_node = pytest.mark.skipif(not Path(NODE).is_file(), reason="needs node")
CLOUD_JS = (ROOT / "alto" / "cloud" / "alto-cloud.js").read_text(encoding="utf-8")


def _fn(name):
    """One function out of alto-cloud.js, to run under node."""
    i = CLOUD_JS.index(f"  function {name}(")
    j = CLOUD_JS.index("\n  }\n", i)
    return CLOUD_JS[i:j + 4]


def _browser(js_body: str):
    out = subprocess.check_output([NODE, "-e", js_body], timeout=60)
    return json.loads(out)


@pytest.mark.parametrize("kind", starter.KINDS)
def test_the_starter_draft_is_a_timeline_that_builds(kind):
    d = starter.draft(kind)
    b, nodes, _ = load_brief(d)
    validate_brief(b)
    validate_nodes(b, nodes)
    assert len(b.acts) == 2 and len(nodes) == 2
    assert b.mode == ("outline" if kind == "outline" else "linear")


@needs_node
@pytest.mark.parametrize("kind", starter.KINDS)
def test_a_title_with_every_awkward_character_fills_the_page_safely(kind, tmp_path):
    raw = 'Bob\'s "Draft" & <b>${x}</b> `tick` \\ back — 2026'
    clean = _browser(_fn("_cleanTitle") + f"\nconsole.log(JSON.stringify(_cleanTitle({json.dumps(raw)})));")
    assert clean == "Bob\u2019s \u201cDraft\u201d and b$ {x}/b \u2019tick\u2019 back \u2014 2026"
    page = starter.page(kind)
    filled = (page.replace("subject=" + starter.TITLE, "subject=X")
              .replace(starter.TITLE, clean).replace(starter.TID, "my-new-timeline")
              .replace(starter.LABEL, "Law &amp; Society"))
    assert f"<title>{clean} — Alto Timeline</title>" in filled
    assert 'window._ALTO_EDIT={"title": "' + clean + '", "key": "alto-doc-my-new-timeline"}' in filled
    # every inline script still parses
    scripts = re.findall(r"<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)</script>", filled)
    assert len(scripts) > 10
    f = tmp_path / "s.js"
    for i, s in enumerate(scripts):
        f.write_text(s, encoding="utf-8")
        r = subprocess.run([NODE, "--check", str(f)], capture_output=True, text=True)
        assert r.returncode == 0, (i, r.stderr[-400:])


def test_the_site_carries_the_starters(tmp_path):
    starter.write(tmp_path)
    for k in starter.KINDS:
        h = (tmp_path / "new" / f"{k}.html").read_text(encoding="utf-8")
        assert starter.TID in h and starter.TITLE in h and starter.LABEL in h
        assert json.loads((tmp_path / "new" / f"{k}.json").read_text())["brief"]["timeline_id"] == starter.TID


def test_the_browser_writes_drafts_the_connector_reads():
    """The draft documents createTimeline writes are the ones store/cloud.py
    reads: {data: JSON text} with a `created`, nodes with `_seq`."""
    js = CLOUD_JS[CLOUD_JS.index("async function _createTimeline"):]
    for want in ("'alto_projects', pid), {", "'alto_timelines', tid), { data: JSON.stringify(tdoc)",
                 "'nodes', n.id)", "{ _seq: i + 1 })), _seq: i + 1 }", "'meta', 'connections'), { data: '[]' }",
                 "status: 'published', visibility: 'private-web', private_key: key"):
        assert want in js, want
