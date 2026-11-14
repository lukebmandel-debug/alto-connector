"""DOM clobbering of the notes walks, attacked from every side (stamp author, independent of the builder's 5 cases).

The two walks (_altoNoteFrag, _altoPlainNote) parse old rich notes with DOMParser and walk the result. A parsed
document is attacker-shaped: forms expose their controls as named properties, and an HTML document exposes
<img>/<form>/<embed>/<object>/<iframe> names as document properties. Every case below must finish in under 1 s,
never fire the marker, never throw out of the helper, and yield only bare allowlisted tags. The marker is harmless:
it only sets a window flag. Runs in WebKit and Chromium; skipped where Playwright is missing."""
import base64
import json
import re
import time
from pathlib import Path

import pytest

try:
    import playwright.sync_api as pw
except Exception:  # pragma: no cover
    pw = None

from alto.build.builder import build_timeline, load_brief

ROOT = Path(__file__).resolve().parent.parent
KEY = "alto-hl-contracts-outline"
OK_TAGS = ["b", "strong", "i", "em", "u", "br", "p", "ul", "ol", "li"]
M = "top.__xss=1"                                     # harmless marker

# every property a tree walk might read off a node or a document
PROPS = ["firstChild", "nextSibling", "nodeType", "nodeName", "nodeValue", "parentNode", "childNodes", "lastChild",
         "previousSibling", "children", "firstElementChild", "attributes", "localName", "tagName", "namespaceURI",
         "ownerDocument", "textContent", "content", "length", "item", "namedItem", "elements", "toString", "valueOf",
         "constructor", "__proto__", "hasChildNodes", "getAttribute", "toLowerCase", "call", "apply"]
CONTROLS = ["input", "button", "select", "textarea", "output", "fieldset", "object", "img"]
DOC_NAMES = ["body", "documentElement", "head", "createElement", "createTextNode", "createTreeWalker", "defaultView",
             "implementation", "querySelector", "getElementsByTagName", "childNodes", "firstChild", "nodeType"]
DOC_TAGS = ["img", "form", "embed", "object", "iframe"]


def _cases():
    out = []
    for p in PROPS:                                       # the getters' targets, through every form-associated control
        for c in CONTROLS:
            close = "" if c in ("input", "img") else "</%s>" % c
            out.append(("form-%s-%s" % (c, p), "<form><%s name=%s>%s<b>in</b>t</form>after" % (c, p, close), "intafter"))
        out.append(("dup-%s" % p, "<form><input name=%s><input name=%s>t</form>after" % (p, p), "tafter"))
        out.append(("outside-%s" % p, "<input form=f name=%s><form id=f>t</form>after" % p, "tafter"))
        out.append(("formid-%s" % p, "<form id=%s name=%s><input id=%s>t</form>" % (p, p, p), "t"))
    for n in DOC_NAMES:                                   # document-level names on the parsed document
        for tg in DOC_TAGS:
            body = "<%s name=%s>" % (tg, n) + ("" if tg in ("img", "embed") else "</%s>" % tg)
            out.append(("doc-%s-%s" % (tg, n), "x<b>bold</b>" + body + "y", "xboldy"))
        out.append(("docid-%s" % n, "x<img id=%s name=%s>y" % (n, n), "xy"))
    # form.elements and its collection methods
    out.append(("elements-all", "<form><input name=elements><input name=length><input name=item><input name=namedItem>"
                "<input name=0><input name=1>t</form>z", "tz"))
    # nested forms (and the walk's names) inside every allowed tag, alone and stacked
    for t in OK_TAGS:
        if t == "br":
            continue
        inner = "<form><input name=nextSibling><input name=firstChild><input name=nodeName><input name=nodeType>" \
                "<img name=nodeValue>X</form>"
        wrap = {"li": "<ul><li>%s</li></ul>", "ul": "<ul>%s</ul>", "ol": "<ol>%s</ol>"}.get(t, "<" + t + ">%s</" + t + ">")
        out.append(("nested-in-%s" % t, wrap % inner + "Y", "XY"))
    stack = "".join("<%s>" % t for t in OK_TAGS if t not in ("br", "ul", "ol", "li", "p"))
    out.append(("nested-in-all", stack + "<p><form><input name=nextSibling><img name=nodeName>X</form></p>Y", "XY"))
    # forms re-opened through mis-nesting (tables, templates, adoption agency)
    out.append(("misnest-table", "<table><form><input name=nextSibling><tr><td>X</td></tr></form></table>Y", "XY"))
    out.append(("misnest-adopt", "<b><form><i><input name=nextSibling>X</b>Y</i></form>Z", "XYZ"))
    out.append(("template-form", "<template><form><input name=nextSibling></form></template>X", "X"))
    return out


CASES = _cases()

RUN_JS = """([cases, OK]) => {
  const out = [];
  const bad = (root) => [...root.querySelectorAll('*')].filter(e => OK.indexOf(e.localName) < 0
      || e.namespaceURI !== 'http://www.w3.org/1999/xhtml' || e.attributes.length).length;
  for (const [name, v, want] of cases) {
    const t0 = performance.now(); let err = null, txt = null, b = 0, same = true, plain = '';
    try {
      const d = document.createElement('div'); d.appendChild(window._altoNoteFrag(v, 4000));
      txt = d.textContent; b = bad(d);
      same = d.innerHTML === window._altoNoteStr(v, 4000, 'html');
      plain = window._altoPlainNote(v, 4000, true) + window._altoPlainNote(v);
    } catch (e) { err = String(e && e.message || e).slice(0, 80); }
    const ms = performance.now() - t0;
    if (err || b || !same || ms > 1000 || /</.test(plain) || (want != null && txt !== want))
      out.push([name, {err, b, same, ms: Math.round(ms), txt, plain: plain.slice(0, 40)}]);
  }
  return out;
}"""

# breaks an endless walk inside _altoNoteFrag (it creates a node per step), so a weakened control cannot hang the run
GUARD = """(() => { let n = 0; const ct = Document.prototype.createTextNode, ce = Document.prototype.createElement;
  window.__budget = () => { n = 0; };
  Document.prototype.createTextNode = function(){ if(++n > 200000) throw new Error('UNBOUNDED'); return ct.apply(this, arguments); };
  Document.prototype.createElement = function(){ if(++n > 200000) throw new Error('UNBOUNDED'); return ce.apply(this, arguments); }; })()"""


def _page_html():
    d = json.loads((ROOT / "samples" / "outline_brief.json").read_text(encoding="utf-8"))
    return build_timeline(*load_brief(d))[0]


@pytest.fixture(scope="module")
def page_html():
    return _page_html()


@pytest.fixture(scope="module")
def page_file(page_html, tmp_path_factory):
    f = tmp_path_factory.mktemp("xssclob") / "page.html"
    f.write_text(page_html, encoding="utf-8")
    return f


@pytest.fixture(params=["webkit", "chromium"])
def browser(request):
    if pw is None:
        pytest.skip("Playwright is not installed")
    with pw.sync_playwright() as p:
        try:
            b = getattr(p, request.param).launch()
        except Exception as e:
            try:
                if request.param != "chromium":
                    raise e
                b = p.chromium.launch(channel="chrome")
            except Exception:
                pytest.skip(f"no {request.param}: {e}")
        yield b
        b.close()


def _new(browser, url, init=()):
    ctx = browser.new_context(viewport={"width": 1400, "height": 900})
    pg = ctx.new_page()
    pg.on("dialog", lambda d: d.dismiss())
    for s in init:
        pg.add_init_script(s)
    pg.goto(url)
    pg.wait_for_timeout(1200)
    return ctx, pg


def _share_url(page_file, notes):
    payload = {"v": 1, "course": "x", "notes": True, "highlights": notes}
    raw = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return page_file.as_uri() + "#share=j:" + raw


def _bad_in(pg, sel):
    return pg.evaluate("""([sel, OK]) => [...document.querySelectorAll(sel)].filter(e => OK.indexOf(e.localName) < 0
        || e.namespaceURI !== 'http://www.w3.org/1999/xhtml' || e.attributes.length).length""", [sel, OK_TAGS])


# ── 1. every clobbering shape, through all three helpers ──

def test_no_clobbering_shape_steers_slows_or_breaks_the_walks(browser, page_file):
    assert len(CASES) > 400
    ctx, pg = _new(browser, page_file.as_uri())
    t0 = time.time()
    out = pg.evaluate(RUN_JS, [CASES, OK_TAGS])
    assert out == [], json.dumps(out[:20], indent=1)
    assert time.time() - t0 < len(CASES) * 0.05          # the whole set, not just each case, stays fast
    assert pg.evaluate("window.__xss") is None
    ctx.close()


# ── 2. the node budget: parser amplification, at, under and over the budget ──

# inside a <p>, each new <p> closes the old one and re-opens every active formatting element (13 kinds x 3): ~40 nodes per 4 characters of note
_FMT = "".join("<%s>" % t for t in ["b", "i", "u", "em", "strong", "s", "small", "big", "code", "tt", "nobr", "strike", "font"]) * 3
AMPLIFY = "<p>" + _FMT + "<p>x" * 900


def test_a_huge_note_at_the_node_budget_finishes_fast_and_falls_back_to_plain_text(browser, page_file):
    ctx, pg = _new(browser, page_file.as_uri())
    res = pg.evaluate("""(v) => {
        const doc = new DOMParser().parseFromString(v.slice(0, 4000), 'text/html');
        let nodes = 0; const w = doc.createTreeWalker(doc.body, 0xFFFFFFFF); while (w.nextNode()) nodes++;
        const t0 = performance.now(); const d = document.createElement('div'); d.appendChild(window._altoNoteFrag(v, 4000));
        const s = window._altoNoteStr(v, 4000, 'html'); const p = window._altoPlainNote(v, 4000, true);
        return {nodes, ms: performance.now() - t0, tags: d.querySelectorAll('*').length, txt: d.textContent, p, s: s.length}; }""", AMPLIFY)
    assert res["nodes"] > window_budget(pg) * 5, res["nodes"]           # the parse really does amplify past the budget
    assert res["ms"] < 1000, res
    assert res["tags"] == 0 and "<" not in res["txt"] and "<" not in res["p"]   # over budget: plain text, markup gone
    # just under / at / just over the budget: plain <b> nodes, each 'x<b></b>' is 2 nodes
    for n, rich in ((1490, True), (1499, True), (1501, False), (1600, False)):
        v = "x<i></i>" * n
        r = pg.evaluate("""(v) => { const t0 = performance.now(); const d = document.createElement('div');
            d.appendChild(window._altoNoteFrag(v, 100000)); return [performance.now() - t0, d.querySelectorAll('i').length, d.textContent.length]; }""", v)
        assert r[0] < 1000, (n, r)
        assert (r[1] == n) if rich else (r[1] == 0 and r[2] == n), (n, r)
    # a huge LEGACY note (the editor and the mail text parse it without the 4000 cut): 400 KB, mixed shapes
    big = ("<b>bold</b> text &amp; more<ul><li>one</li></ul>" + _FMT + "<p>x" * 50 + "<form><input name=nextSibling></form>") * 120
    r = pg.evaluate("""(v) => { const t0 = performance.now(); const a = window._altoPlainNote(v, 4000, true), b = window._altoPlainNote(v);
        const d = document.createElement('div'); d.appendChild(window._altoNoteFrag(v, 4000)); return [performance.now() - t0, a.length, /</.test(a + b)]; }""", big)
    assert r[0] < 1000 and r[1] <= 4000 and not r[2], r
    assert pg.evaluate("window.__xss") is None
    ctx.close()


def window_budget(pg):
    return pg.evaluate("window._altoNoteBudget")


# ── 3. a deep nesting stack ──

@pytest.mark.parametrize("tag,n", [("b", 1300), ("div", 3000), ("span", 3000), ("ul", 1300), ("li", 1300),
                                   ("table", 600), ("blockquote", 3000), ("svg", 1000), ("form", 1000)])
def test_a_deep_nesting_stack_finishes_fast(browser, page_file, tag, n):
    v = ("<%s>" % tag) * n + "<input name=nextSibling>X" + ("</%s>" % tag) * n + "Y"
    ctx, pg = _new(browser, page_file.as_uri())
    for max_ in (4000, 10 ** 6):                         # cut at the display cap, and whole (a legacy note in the editor)
        r = pg.evaluate("""([v, max]) => { const t0 = performance.now(); let err = null, bad = 0, txt = '';
            try { const d = document.createElement('div'); d.appendChild(window._altoNoteFrag(v, max)); txt = d.textContent;
                  bad = [...d.querySelectorAll('*')].filter(e => e.attributes.length || ['b','strong','i','em','u','br','p','ul','ol','li'].indexOf(e.localName) < 0).length;
                  window._altoPlainNote(v, max, true); window._altoNoteStr(v, max, 'html'); }
            catch (e) { err = String(e.message); }
            return {ms: performance.now() - t0, err, bad, depth: (() => { let k = 0, e = document.createElement('div'); e.appendChild(window._altoNoteFrag(v, max)); while (e.firstElementChild) { e = e.firstElementChild; k++; } return k; })(), txt: txt.slice(-2)}; }""", [v, max_])
        assert r["ms"] < 1000 and r["err"] is None and r["bad"] == 0, (tag, max_, r)
        assert r["depth"] <= 20, (tag, r)                # the rebuilt tree is never deeper than the cap
    assert pg.evaluate("window.__xss") is None
    ctx.close()


# ── 4. end to end: a rich #share= link and stored legacy notes carrying the clobbering set ──

E2E = [v for _, v, _ in CASES[::9]] + [AMPLIFY, "<b>" * 1300 + "X"]


def test_a_rich_share_link_of_clobbering_notes_loads_fast_and_imports_clean(browser, page_file):
    notes = [{"quote": "Q%d" % i, "note": v, "fmt": "rich", "color": "yellow", "kind": "highlight", "ts": 100 + i}
             for i, v in enumerate(E2E)]
    ctx = browser.new_context(viewport={"width": 1400, "height": 900})
    pg = ctx.new_page()
    pg.on("dialog", lambda d: d.dismiss())
    t0 = time.time()
    pg.goto(_share_url(page_file, notes))
    pg.wait_for_selector("#share-import-overlay [data-act]", timeout=8000)
    assert time.time() - t0 < 8
    t1 = time.time(); assert pg.evaluate("1 + 1") == 2; assert time.time() - t1 < 1      # the tab is not frozen
    pg.click("#share-import-overlay [data-act=replace], #share-import-overlay [data-act=merge]")
    pg.wait_for_timeout(1200)
    stored = pg.evaluate(f"JSON.parse(localStorage.getItem('{KEY}') || '[]')")
    assert len(stored) == len(E2E)
    assert all(h["fmt"] == "html" and not re.search(r"<(?!/?(b|strong|i|em|u|br|p|ul|ol|li)>)", h["note"]) for h in stored)
    t1 = time.time(); pg.evaluate("toggleNotes()"); pg.wait_for_timeout(600)
    assert time.time() - t1 < 3
    assert _bad_in(pg, "#notes-list .note-text *") == 0
    with ctx.expect_page() as info:
        pg.evaluate("generateNotesReport()")
    rp = info.value; rp.wait_for_load_state(); rp.wait_for_timeout(500)
    assert _bad_in(rp, ".hl-note *") == 0 and rp.evaluate("window.__xss") is None
    assert pg.evaluate("window.__xss") is None
    ctx.close()


def test_stored_legacy_clobbering_notes_render_and_open_in_the_editor_fast(browser, page_file):
    seed = [{"id": "c%d" % i, "quote": "Q%d" % i, "color": "yellow", "note": v, "kind": "highlight", "ts": 1 + i}
            for i, v in enumerate(E2E)]                         # no fmt: stored before the field existed
    init = "localStorage.setItem(%s, %s)" % (json.dumps(KEY), json.dumps(json.dumps(seed)))
    ctx = browser.new_context(viewport={"width": 1400, "height": 900})
    ctx.add_init_script("if(!sessionStorage.getItem('__s')){ sessionStorage.setItem('__s', 1); %s }" % init)
    pg = ctx.new_page(); pg.on("dialog", lambda d: d.dismiss())
    pg.goto(page_file.as_uri()); pg.wait_for_timeout(1500)
    t1 = time.time(); pg.evaluate("document.getElementById('notes-panel').classList.contains('open') || toggleNotes()")
    pg.wait_for_timeout(600); assert time.time() - t1 < 3
    assert pg.evaluate("document.querySelectorAll('#notes-list .note-text').length") >= len(E2E)
    assert _bad_in(pg, "#notes-list .note-text *") == 0
    for i in (0, len(E2E) - 2, len(E2E) - 1):
        t1 = time.time(); pg.evaluate("id => openNoteForHighlight(id)", "c%d" % i); pg.wait_for_timeout(200)
        assert time.time() - t1 < 1.5
        assert "<" not in pg.input_value("#note-input")
        pg.evaluate("cancelNote()")
    assert pg.evaluate("window.__xss") is None
    ctx.close()


# ── 5. static guard: the walks read no node property directly, only through the cached prototype getters ──

_DIRECT = re.compile(r"\.(firstChild|nextSibling|nodeType|nodeName|nodeValue|childNodes|parentNode|lastChild|previousSibling|"
                     r"children|firstElementChild|attributes|tagName|localName|documentElement|textContent|innerHTML|outerHTML)\b")


def test_the_walks_read_node_properties_only_through_prototype_getters(browser, page_file):
    ctx, pg = _new(browser, page_file.as_uri())
    src = pg.evaluate("[window._altoNoteFrag.toString(), window._altoPlainNote.toString()]")
    for s in src:
        assert not _DIRECT.findall(s), _DIRECT.findall(s)
        assert not re.search(r"(?<!A)\.body\b", s)
        assert "A.first.call" in s and "A.next.call" in s and "A.type.call" in s and "A.name.call" in s
        assert "--budget" in s
    api = pg.evaluate("""() => { const A = window._altoNodeAPI, N = Node.prototype, D = Document.prototype, g = (p, n) => Object.getOwnPropertyDescriptor(p, n).get;
        return [A.first === g(N, 'firstChild'), A.next === g(N, 'nextSibling'), A.type === g(N, 'nodeType'), A.name === g(N, 'nodeName'),
                A.val === g(N, 'nodeValue'), A.body === g(D, 'body'), A.root === g(D, 'documentElement')]; }""")
    assert api == [True] * 7
    ctx.close()


# ── 6. control: the old direct-property walk is caught by the same checks ──

def test_control_a_direct_property_walk_is_caught(browser, page_html, tmp_path_factory):
    html = page_html
    swaps = [("A.first.call(src)", "src.firstChild"), ("A.next.call(c)", "c.nextSibling"), ("A.type.call(c)", "c.nodeType"),
             ("A.name.call(c)", "c.nodeName"), ("A.body.call(doc)", "doc.body")]
    for old, new in swaps:
        assert old in html, f"control: '{old}' is gone; update the control"
        html = html.replace(old, new)
    f = tmp_path_factory.mktemp("xssclobw") / "weak.html"
    f.write_text(html, encoding="utf-8")
    ctx, pg = _new(browser, f.as_uri(), [GUARD])
    safe = [c for c in CASES if "nextSibling" not in c[1] or "dup-" in c[0]]        # cases that could loop are left out
    out = pg.evaluate(RUN_JS, [safe, OK_TAGS])
    assert len(out) >= 10, out                              # throws, wrong text or a clobbered body
    src = pg.evaluate("window._altoNoteFrag.toString()")
    assert _DIRECT.findall(src)                             # and the static guard sees it
    ctx.close()


# ── 7. legacy formatted notes in the editor (Board B-1114-xss4 MUST-FIX): no tags shown, untouched keeps formatting,
#        edits keep the text the user saw, undo brings the formatting back ──

LEGACY = "Tom &amp; Jerry &lt;3 <b>bold</b> 5 &gt; 3<ul><li>one</li><li>two \U0001F600</li></ul>"
LEGACY_PLAIN = "Tom & Jerry <3 bold 5 > 3\n• one\n• two \U0001F600"


def _seeded(browser, page_file, items):
    ctx = browser.new_context(viewport={"width": 1400, "height": 900})
    init = "localStorage.setItem(%s, %s)" % (json.dumps(KEY), json.dumps(json.dumps(items)))
    ctx.add_init_script("if(!sessionStorage.getItem('__s')){ sessionStorage.setItem('__s', 1); %s }" % init)
    pg = ctx.new_page(); pg.on("dialog", lambda d: d.dismiss())
    pg.goto(page_file.as_uri()); pg.wait_for_timeout(1500)
    return ctx, pg


def _stored1(pg):
    return pg.evaluate(f"JSON.parse(localStorage.getItem('{KEY}'))[0]")


def _list_html(pg):
    pg.evaluate("document.getElementById('notes-panel').classList.contains('open') || toggleNotes()")
    pg.wait_for_timeout(400)
    pg.evaluate("window.renderNotesList && renderNotesList()")
    pg.wait_for_timeout(300)
    return pg.evaluate("document.querySelector('#notes-list .note-text').innerHTML")


def test_a_legacy_note_opens_as_its_text_saves_untouched_and_edits_keep_the_text_the_user_saw(browser, page_file):
    ctx, pg = _seeded(browser, page_file, [{"id": "lg", "quote": "Q", "color": "yellow", "note": LEGACY, "kind": "highlight", "ts": 1}])
    pg.evaluate("openNoteForHighlight('lg')"); pg.wait_for_timeout(300)
    assert pg.input_value("#note-input") == LEGACY_PLAIN                       # decoded once, no tags, bullets kept
    pg.evaluate("saveNote()"); pg.wait_for_timeout(300)
    assert _stored1(pg)["note"] == LEGACY and _stored1(pg).get("fmt") is None    # untouched: byte-identical
    pg.evaluate("openNoteForHighlight('lg')"); pg.wait_for_timeout(200)
    pg.evaluate("addFreeformNote()"); pg.wait_for_timeout(300)                    # switching away settles it untouched
    assert _stored1(pg)["note"] == LEGACY
    pg.evaluate("cancelNote()")
    html = _list_html(pg)
    assert "<b>bold</b>" in html and "<li>one</li>" in html and "&lt;b&gt;" not in html
    # an edit: the text the user saw survives exactly, plus the change
    pg.evaluate("openNoteForHighlight('lg')"); pg.wait_for_timeout(200)
    pg.fill("#note-input", LEGACY_PLAIN + " added")
    pg.evaluate("saveNote()"); pg.wait_for_timeout(300)
    s = _stored1(pg)
    assert s["note"] == LEGACY_PLAIN + " added" and s["fmt"] == "text"
    assert pg.evaluate("document.querySelector('#notes-list .note-text').textContent").endswith("added")
    # undo restores the old formatted note exactly, with its formatting
    pg.evaluate("window._altoNotesV2.hist.undo()"); pg.wait_for_timeout(300)
    s = _stored1(pg)
    assert s["note"] == LEGACY and s.get("fmt") is None, s
    assert "<b>bold</b>" in _list_html(pg)
    assert pg.evaluate("window.__xss") is None
    ctx.close()


def test_editing_a_long_legacy_note_keeps_the_text_the_user_did_not_change(browser, page_file):
    """Every note stored before the fmt field is 'legacy'. The editor must hold ALL of it, or an edit drops the tail."""
    long_note = "<b>start</b> " + ("word &amp; " * 700) + "<i>END</i>"           # ~5,000 characters once the tags are gone
    ctx, pg = _seeded(browser, page_file, [{"id": "lg", "quote": "Q", "color": "yellow", "note": long_note, "kind": "highlight", "ts": 1}])
    pg.evaluate("openNoteForHighlight('lg')"); pg.wait_for_timeout(300)
    ed = pg.input_value("#note-input")
    assert ed.startswith("start word & word") and ed.endswith("word & END"), (len(ed), ed[-20:])
    pg.fill("#note-input", ed + " typed")
    pg.evaluate("saveNote()"); pg.wait_for_timeout(300)
    assert _stored1(pg)["note"] == ed + " typed"
    ctx.close()


def test_the_plain_text_notice_check_is_fast_unclobberable_and_inert(browser, page_file):
    """The notice asks the rebuilt fragment whether it holds an element. Notes that name things after the check
    (querySelector, nodeName, ...) or blow the node budget must neither steer it nor slow the editor."""
    big = ("<b>bold</b> text &amp; more<ul><li>one</li></ul>" + "<form><input name=querySelector></form>") * 2000   # ~180 KB
    notes = [("q1", "<form><input name=querySelector><input name=querySelectorAll><b>x</b></form>", True),
             ("q2", "<img name=querySelector><img name=firstElementChild>x &amp; y", False),
             ("q3", "<form id=querySelector><input name=nextSibling><input name=nodeName>plain</form>", False),
             ("q4", "<i><form><input name=children><input name=length>it</form></i>", True),
             ("q5", AMPLIFY, False),                       # over the budget: plain text, so no notice (and no hang)
             ("q6", big, None),
             ("q7", "a < b && c > d &lt;b&gt;", False)]
    seed = [{"id": i, "quote": "Q", "color": "yellow", "note": v, "kind": "highlight", "ts": k + 1} for k, (i, v, _) in enumerate(notes)]
    ctx, pg = _seeded(browser, page_file, seed)
    for i, _, want in notes:
        t0 = time.time()
        pg.evaluate("id => openNoteForHighlight(id)", i)
        assert time.time() - t0 < 1.0, i
        pg.wait_for_timeout(150)
        if want is not None:
            assert pg.is_visible(".nd-notice") == want, i
        assert "<" not in pg.input_value("#note-input") or i == "q7"
        pg.evaluate("cancelNote()")
    got = pg.evaluate(f"Object.fromEntries(JSON.parse(localStorage.getItem('{KEY}')).map(h => [h.id, [h.note, h.fmt || null]]))")
    assert got == {i: [v, None] for i, v, _ in notes}                                                 # Cancel: untouched
    assert pg.evaluate("window.__xss") is None
    ctx.close()
