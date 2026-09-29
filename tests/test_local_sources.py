"""Sources with a copy on the author's own computer (source_docs[].local).

An offline copy opened from disk offers the local file beside every link to
that source, and opens it in place of the web copy when there is no internet.
On the web nothing changes, a share snapshot carries none of the owner's
paths, and a timeline with no local copies is built exactly as before.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build.brief import BriefError  # noqa: E402
from alto.build.builder import load_brief, build_timeline  # noqa: E402
from alto.build import detail_extras as dx  # noqa: E402
from alto.build.reidentify import LOCAL_BLOCK, LOCAL_EMPTY, reidentify  # noqa: E402
from alto.build.sanitize import SourceMap, clean_linked_markup, clean_overview  # noqa: E402
from alto.build.single_file import bundle, private_page  # noqa: E402

OUTLINE = ROOT / "samples" / "outline_brief.json"
CLOUD_JS = (ROOT / "alto" / "cloud" / "alto-cloud.js").read_text(encoding="utf-8")
NODE = __import__("shutil").which("node") or str(Path.home() / ".local/node/bin/node")
DOC = "https://docs.google.com/document/d/abc123/edit"
KEY = "czckq4utebcx5rvgdptrgt"


def _d():
    return json.loads(OUTLINE.read_text(encoding="utf-8"))


@pytest.fixture
def notes(tmp_path):
    folder = tmp_path / "Contracts"
    folder.mkdir()
    f = folder / "Notes 9_3rd & 8th.docx"
    f.write_bytes(b"PK")
    return f


def _with_local(d, path, url=DOC):
    d["brief"]["source_docs"] = [{"id": "notes", "name": "Contracts notes",
                                  "url": url, "local": str(path)}]
    root = next(n for n in d["nodes"] if not n.get("parent"))
    root["sections"] = [{"h": "Rule", "t": f'Class <a href="{DOC}?usp=sharing">9/3</a>.'}]
    return d


# ── the manifest ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("bad", ["notes.docx", "Downloads/x.docx",
                                 "file:///Users/x/a.docx", "/x/\n.docx"])
def test_local_must_be_a_full_path(bad):
    d = _d()
    d["brief"]["source_docs"] = [{"id": "x", "name": "x", "local": bad}]
    with pytest.raises(BriefError, match="local must be a full path"):
        build_timeline(*load_brief(d))


@pytest.mark.parametrize("good", ["/Users/x/a.docx", "~/Downloads/a b.docx",
                                  "C:\\Users\\x\\a.docx"])
def test_full_paths_are_accepted(good):
    d = _d()
    d["brief"]["source_docs"] = [{"id": "x", "name": "x", "local": good}]
    _, rep = build_timeline(*load_brief(d))
    assert any("source x: no file at" in w for w in rep["warnings"])


def test_the_consent_manifest_carries_local_into_the_build():
    from alto.mcp_server import _source_docs
    doc = {"consent": {"sources": [{"id": "n", "name": "N", "kind": "notes",
                                    "url": DOC, "local": "~/n.docx"}]}}
    assert _source_docs(doc) == [{"id": "n", "name": "N", "url": DOC,
                                  "local": "~/n.docx"}]


# ── recognising links to a source ───────────────────────────────────────────

def _src(local=True, url=DOC):
    return SourceMap([{"id": "notes", "name": "N", "url": url,
                       "local": "/a/b.docx" if local else ""}])


@pytest.mark.parametrize("href", [DOC, DOC + "?usp=sharing", DOC + "#heading=h.x",
                                  "https://docs.google.com/document/d/abc123/",
                                  "https://docs.google.com/document/d/abc123/view"])
def test_any_link_to_the_document_is_recognised(href):
    out, w = clean_linked_markup(f'<a href="{href}" title="t">9/3</a>', {}, _src())
    assert 'data-src="notes"' in out and 'class="alto-src-local"' in out, out
    assert f'href="{DOC}"' in out and 'title="t"' in out
    assert 'class="note-link" target="_blank" rel="noopener"' in out
    assert not w


def test_no_icon_for_a_source_with_no_local_copy():
    out, _ = clean_linked_markup(f'<a href="{DOC}">9/3</a>', {}, _src(local=False))
    assert 'data-src="notes"' in out and "alto-src-local" not in out


def test_other_links_are_untouched():
    a = '<a href="https://example.com/x">x</a>'
    assert clean_linked_markup(a, {}, _src())[0] == clean_linked_markup(a, {})[0]
    assert "data-src" not in clean_linked_markup(a, {}, _src())[0]


def test_src_links_resolve_by_id():
    out, w = clean_linked_markup('<a href="src:notes">my notes</a>', {}, _src())
    assert f'href="{DOC}"' in out and 'data-src="notes"' in out and "my notes" in out
    assert not w


def test_a_src_link_to_a_local_only_source_goes_nowhere_on_the_web():
    out, _ = clean_linked_markup('<a href="src:notes">n</a>', {}, _src(url=""))
    assert out.startswith('<a href="#" class="note-link" data-src="notes">n</a>')
    assert 'data-src-local="notes"' in out


def test_an_unknown_src_link_keeps_only_its_text():
    out, w = clean_linked_markup('<a href="src:nope">n</a>', {}, _src())
    assert out == "n" and "unknown source 'nope'" in w[0]


def test_the_overview_recognises_sources_too():
    out, _ = clean_overview(f'<p><a href="{DOC}">notes</a></p>', set(), _src())
    assert 'data-src="notes"' in out and "alto-src-local" in out


def test_an_icon_follows_even_an_unclosed_link():
    out, _ = clean_linked_markup(f'<a href="{DOC}">9/3', {}, _src())
    assert out.endswith("</a>" + '<a href="#" class="alto-src-local" data-src-local="notes" '
                        'title="Open the copy on this computer"></a>')


# ── the built page ──────────────────────────────────────────────────────────

def test_without_local_copies_nothing_is_added():
    d = _d()
    d["brief"]["source_docs"] = [{"id": "notes", "name": "N", "url": DOC}]
    html, _ = build_timeline(*load_brief(d))
    for s in ("alto-local", "_ALTO_LOCAL", "alto-src-local", "_altoOpenLocal"):
        assert s not in html


def test_the_page_maps_each_source_to_its_file(notes):
    html, rep = build_timeline(*load_brief(_with_local(_d(), notes)))
    assert html.count('<script id="alto-local-src">') == 1
    m = re.search(r'window\._ALTO_LOCAL=(\{.*?\});</script>', html)
    data = json.loads(m.group(1).replace("<\\/", "</"))
    assert data == {"root": str(notes.parent), "files": {"notes": {"p": str(notes)}}}
    assert 'data-src=\\"notes\\"' in html or 'data-src="notes"' in html
    assert not any("no file at" in w for w in rep["warnings"])


def test_tilde_is_expanded_at_build(monkeypatch, notes):
    # HOME on POSIX, USERPROFILE on Windows
    monkeypatch.setenv("HOME", str(notes.parent.parent))
    monkeypatch.setenv("USERPROFILE", str(notes.parent.parent))
    loc = "~/Contracts/" + notes.name
    html, rep = build_timeline(*load_brief(_with_local(_d(), loc)))
    assert json.dumps(__import__("os").path.expanduser(loc)) in html
    assert not any("no file at" in w for w in rep["warnings"])


def test_source_notes_offer_the_local_copy(notes):
    d = _with_local(_d(), notes)
    next(n for n in d["nodes"] if not n.get("parent"))["sources"] = ["notes"]
    html, _ = build_timeline(*load_brief(d))
    nd = html.split("const NODE_DETAILS=", 1)[1].split("\n};", 1)[0]
    # the inline link and the Source notes entry each carry the icon
    assert "Contracts notes\\u003c/a>" in nd and nd.count("data-src-local") >= 2


def test_offline_bundle_and_private_page_keep_the_map(notes):
    b, nodes, conns = load_brief(_with_local(_d(), notes))
    html, _ = build_timeline(b, nodes, conns)
    assert "alto-local-src" in private_page(b, html)
    assert "alto-local-src" in bundle(b, html)


# ── shares ──────────────────────────────────────────────────────────────────

def test_a_share_carries_none_of_the_owners_paths(notes):
    b, nodes, conns = load_brief(_with_local(_d(), notes))
    html, _ = build_timeline(b, nodes, conns)
    share = reidentify(private_page(b, html), KEY)
    assert str(notes.parent) not in share
    assert LOCAL_EMPTY in share


def test_the_browser_strips_the_same_block():
    """alto-cloud.js makes the live shares; reidentify.py is its tested twin."""
    js = re.search(r"const LOCAL_BLOCK = /(.*?)/g;", CLOUD_JS).group(1)
    assert js.replace("<\\/", "</") == LOCAL_BLOCK.pattern
    assert f"const LOCAL_EMPTY = '{LOCAL_EMPTY}';" in CLOUD_JS
    fn = CLOUD_JS[CLOUD_JS.index("function _reidentify("):]
    fn = fn[:fn.index("\n  }")]
    assert "html = html.replace(LOCAL_BLOCK, LOCAL_EMPTY);" in fn
    assert fn.index("LOCAL_BLOCK") < fn.index("if (oldId === newId) return html;")


# ── the click handler, run for real ─────────────────────────────────────────

_HARNESS = r"""
const [script, base, root, file, online, clickSel] = JSON.parse(process.argv[1]);
const opened = [], classes = new Set();
let handler = null, prevented = false;
function el(attrs){ return { hasAttribute: k => k in attrs, getAttribute: k => attrs[k] ?? null,
  closest(sel){ return sel.split(',').some(s => {
    const m = /^a\[([a-z-]+)\]$/.exec(s.trim()); return m && m[1] in attrs; }) ? this : null; } }; }
global.document = { baseURI: base, documentElement: { classList: { add: c => classes.add(c) } },
  addEventListener: (t, f) => { handler = f; }, createElement: () => ({ click(){}, remove(){} }),
  body: { appendChild(){} } };
Object.defineProperty(globalThis, 'navigator', { value: { onLine: online }, configurable: true });
global.window = global;
window._ALTO_LOCAL = root === null ? {} : { root, files: { notes: { p: file } } };
window.open = u => { opened.push(u); return {}; };
eval(script);
const target = clickSel === 'icon' ? el({ href: '#', 'data-src-local': 'notes' })
                                   : el({ href: 'https://docs.google.com/x', 'data-src': 'notes' });
handler({ target, preventDefault(){ prevented = true; }, stopPropagation(){} });
console.log(JSON.stringify({ disk: classes.has('alto-disk'), opened, prevented }));
"""


def _run(base, online=True, click="link", root="/Users/me/Law/Torts",
         file="/Users/me/Law/Torts/Notes 9_3rd & 8th #2.docx"):
    if not Path(NODE).is_file():
        pytest.skip("needs node")
    script = dx.LOCAL_OPEN.split('<script id="alto-local-open">', 1)[1].rsplit("</script>", 1)[0]
    out = subprocess.run([NODE, "-e", _HARNESS, json.dumps([script, base, root, file, online, click])],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def test_web_pages_leave_links_alone():
    r = _run("https://luke-alto.web.app/pv/x/", online=False)
    assert r == {"disk": False, "opened": [], "prevented": False}


def test_on_disk_and_online_the_web_copy_opens():
    r = _run("file:///Users/me/Law/Torts/outline.html", online=True)
    assert r == {"disk": True, "opened": [], "prevented": False}


def test_on_disk_without_internet_the_local_file_opens():
    r = _run("file:///Users/me/Law/Torts/outline.html", online=False)
    assert r["prevented"] and r["opened"] == [
        "file:///Users/me/Law/Torts/Notes%209_3rd%20&%208th%20%232.docx"]


def test_the_icon_always_opens_the_local_file():
    r = _run("file:///Users/me/Desktop/outline.html", online=True, click="icon")
    assert r["opened"] == ["file:///Users/me/Law/Torts/Notes%209_3rd%20&%208th%20%232.docx"]


def test_moved_with_its_folder_the_copy_finds_the_files_beside_it():
    r = _run("file:///Volumes/USB/School/Torts/outline.html", online=False)
    assert r["opened"] == ["file:///Volumes/USB/School/Torts/Notes%209_3rd%20&%208th%20%232.docx"]


def test_a_copy_elsewhere_uses_the_recorded_path():
    r = _run("file:///Users/me/Downloads/outline.html", online=False)
    assert r["opened"] == ["file:///Users/me/Law/Torts/Notes%209_3rd%20&%208th%20%232.docx"]


def test_a_share_on_disk_opens_nothing_locally():
    r = _run("file:///Users/other/share.html", online=False, root=None)
    assert r == {"disk": False, "opened": [], "prevented": False}


def test_windows_paths_become_file_urls():
    r = _run("file:///C:/Users/me/Desktop/outline.html", online=False,
             root="C:\\Users\\me\\Torts", file="C:\\Users\\me\\Torts\\a b.docx")
    assert r["opened"] == ["file:///C:/Users/me/Torts/a%20b.docx"]


# ── publishing ──────────────────────────────────────────────────────────────

def test_the_publish_rebuild_keeps_the_source_map(tmp_path, notes):
    """publish_static._rebuild re-emits every private page from its stored
    brief. It once skipped the consent manifest, so a published private page
    lost every source link the offline copy had."""
    from alto.publish_static import _rebuild
    from alto.store.local import LocalStore
    d = _with_local(_d(), notes)
    manifest = d["brief"].pop("source_docs")
    st = LocalStore(tmp_path / "store")
    tid = d["brief"]["timeline_id"]
    st.put_nodes("local", tid, d["nodes"])
    st.put_connections("local", tid, d["connections"])
    doc = {"timeline_id": tid, "brief": d["brief"],
           "consent": {"granted": True, "sources": [dict(m, kind="notes") for m in manifest]}}
    html, stale = _rebuild(st, "local", doc)
    assert not stale
    assert 'id="alto-local-src"' in html and "data-src-local" in html
    assert json.dumps(str(notes)) in html
