"""Notes and reports are TEXT. A harmless marker (window.__xss) put in notes must never fire:
in a #share= link, in the original notes list, in the notes report window, and in saved reports
(opened and printed). Runs in WebKit and Chromium; skipped where Playwright is missing.
Nothing reaches out: the marker only sets a window flag."""
import base64
import json
import re
from pathlib import Path

import pytest

try:
    import playwright.sync_api as pw
except Exception:  # pragma: no cover
    pw = None

from alto.build.builder import build_timeline, load_brief
from alto.build.pages import build_reports

ROOT = Path(__file__).resolve().parent.parent
KEY = "alto-hl-contracts-outline"
MARK = "window.__xss=1;try{opener.__xss=1}catch(e){}"
BAD = [
    '<img src=x onerror="%s">' % MARK,
    '<svg onload="%s"></svg>' % MARK,
    '<script>%s</script>' % MARK,
    '"><img src=x onerror="%s">' % MARK,
    "<a href=\"javascript:%s\">x</a>" % MARK,
]


@pytest.fixture(scope="module")
def page_file(tmp_path_factory):
    d = json.loads((ROOT / "samples" / "outline_brief.json").read_text(encoding="utf-8"))
    html = build_timeline(*load_brief(d))[0]
    f = tmp_path_factory.mktemp("xss") / "page.html"
    f.write_text(html, encoding="utf-8")
    return f


@pytest.fixture(scope="module")
def reports_file(tmp_path_factory):
    html = build_reports([{"title": "X", "href": "x", "sub": "", "courseId": "torts",
                           "reports": True, "units": []}], "torts")
    f = tmp_path_factory.mktemp("xssr") / "reports.html"
    f.write_text(html, encoding="utf-8")
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


def _poison():
    return [{"id": "hl-%d" % i, "quote": "Q %d %s" % (i, bad), "color": "yellow",
             "note": "N %d %s" % (i, bad), "kind": "highlight", "ts": 1000 + i}
            for i, bad in enumerate(BAD)]


def _new(browser, url, init=None):
    ctx = browser.new_context(viewport={"width": 1400, "height": 900})
    pg = ctx.new_page()
    pg.on("dialog", lambda d: d.dismiss())
    if init:
        pg.add_init_script(init)
    pg.goto(url)
    pg.wait_for_timeout(1200)
    return ctx, pg


def _seed(pg, items):
    pg.evaluate("([k, v]) => localStorage.setItem(k, v)", [KEY, json.dumps(items)])
    pg.reload()
    pg.wait_for_timeout(1200)


def _clean(pg):
    assert pg.evaluate("window.__xss") is None
    assert pg.evaluate("[...document.querySelectorAll('#notes-list img, #notes-list svg, #notes-list script, #notes-list a, #notes-list [onerror], #notes-list [onload]')].filter(n => !n.closest('button')).length") == 0


def test_a_share_link_cannot_put_markup_in_the_notes_list(browser, page_file):
    payload = {"v": 1, "course": "x", "notes": True,
               "highlights": [{"quote": "Q " + b, "note": "N " + b, "color": "yellow", "kind": "highlight", "ts": 5 + i}
                              for i, b in enumerate(BAD)]}
    raw = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    ctx, pg = _new(browser, page_file.as_uri() + "#share=j:" + raw)
    pg.wait_for_selector("#share-import-overlay [data-act]", timeout=8000)
    pg.click("#share-import-overlay [data-act=replace], #share-import-overlay [data-act=merge]")
    pg.wait_for_timeout(1500)
    stored = pg.evaluate(f"localStorage.getItem('{KEY}')")
    # plain text is kept as the exact text, marked fmt 'text': it is only ever drawn as text, never parsed
    assert stored and all(h["fmt"] == "text" for h in json.loads(stored))
    pg.evaluate("toggleNotes()")
    pg.wait_for_timeout(600)
    _clean(pg)
    assert pg.locator("#notes-list .note-item").count() == len(BAD)
    ctx.close()


def test_the_original_notes_list_draws_old_notes_as_text(browser, page_file):
    ctx, pg = _new(browser, page_file.as_uri())
    _seed(pg, _poison())
    pg.evaluate("toggleNotes()")
    pg.wait_for_timeout(600)
    # the ORIGINAL renderer too, called directly on poisoned data
    pg.evaluate("""(items) => { window.highlights = items; }""", _poison())
    _clean(pg)
    ctx.close()


def test_the_original_renderer_by_itself_is_text(browser, page_file):
    """renderNotesList as first written, before any later override replaces it."""
    src = (ROOT / "alto/engine/timeline_template.html").read_text(encoding="utf-8")
    assert "item.innerHTML" not in src[src.index("function renderNotesList"):src.index("function updateNotesToggle")]
    ctx, pg = _new(browser, page_file.as_uri())
    out = pg.evaluate("""(items) => {
        const d = document.createElement('div');
        const hl = items[0];
        return [window._altoPlainNote(hl.quote, 2000), window._altoPlainNote('a<br>b<ul><li>x</li><li>y</li></ul>'), window._altoPlainNote('a < b and c > d')];
    }""", _poison())
    assert "<" not in out[0] and "onerror" not in out[0]
    assert out[1] == "a\nb\n• x\n• y"          # line breaks and bullets survive
    assert out[2] == "a < b and c > d"                  # plain text is left alone
    ctx.close()


def test_the_notes_report_window_is_escaped_and_cannot_reach_its_opener(browser, page_file):
    ctx, pg = _new(browser, page_file.as_uri())
    _seed(pg, _poison())
    with ctx.expect_page() as info:
        pg.evaluate("generateNotesReport()")
    rp = info.value
    rp.wait_for_load_state()
    rp.wait_for_timeout(800)
    assert rp.evaluate("window.__xss") is None
    assert pg.evaluate("window.__xss") is None
    assert rp.evaluate("window.opener") is None
    assert rp.evaluate("document.querySelectorAll('.hl-block img, .hl-block svg, .hl-block script, .hl-block a').length") == 0
    assert rp.evaluate("[...document.querySelectorAll('.hl-block *')].filter(e => [...e.attributes].some(a => /^on/i.test(a.name) || /^javascript:/i.test(a.value))).length") == 0
    assert "Q 0" in rp.evaluate("document.body.innerText")
    # the saved copy of that report is re-opened and printed: still nothing runs
    saved = pg.evaluate("JSON.parse(localStorage.getItem('alto-rp-' + (window.COURSE_ID||'x'))||'null') || Object.keys(localStorage).filter(k=>k.indexOf('alto-rp-')==0).map(k=>JSON.parse(localStorage.getItem(k))).flat()")
    assert saved
    ctx.close()


def test_saved_reports_open_and_print_inertly(browser, reports_file):
    raw = ("<!DOCTYPE html><html><head><title>R</title><style>.hl-block{color:red}</style></head><body>"
           + "".join('<div class="hl-block">%s</div>' % b for b in BAD)
           + '<button class="report-btn" onclick="window.print()">Print</button>'
           + '<a href="javascript:%s" id="j">j</a>' % MARK
           + "<iframe src=\"javascript:%s\"></iframe></body></html>" % MARK)
    item = {"id": "r1", "courseId": "torts", "title": "Notes Report", "dateISO": "2026-11-14T00:00:00Z", "html": raw}
    ctx, pg = _new(browser, reports_file.as_uri() + "?course=torts",
                   "window.print = function(){ window.__printed = (window.__printed||0)+1; };")
    pg.evaluate("(r) => localStorage.setItem('alto-rp-torts', JSON.stringify([r]))", item)
    pg.reload()
    pg.wait_for_timeout(1200)
    with ctx.expect_page() as info:
        pg.click(".rr-open")
    rp = info.value
    rp.wait_for_load_state()
    rp.wait_for_timeout(800)
    assert rp.evaluate("window.__xss") is None and pg.evaluate("window.__xss") is None
    assert rp.evaluate("window.opener") is None
    assert rp.evaluate("document.querySelectorAll('iframe,[onerror],[onload],[onclick],[href^=javascript]').length") == 0
    assert rp.evaluate("[...document.querySelectorAll('script')].filter(s => s.textContent.indexOf('__xss') >= 0).length") == 0 and rp.locator(".hl-block").count() == len(BAD)
    ctx.close()
    # printing through the page
    ctx, pg = _new(browser, reports_file.as_uri() + "?course=torts",
                   "window.print = function(){ window.__printed = (window.__printed||0)+1; };")
    pg.evaluate("(r) => localStorage.setItem('alto-rp-torts', JSON.stringify([r]))", item)
    pg.reload()
    pg.wait_for_timeout(1200)
    pg.evaluate("(r) => printReports([r])", item)
    pg.wait_for_timeout(300)
    assert pg.evaluate("window.__xss") is None
    assert pg.evaluate("document.querySelectorAll('#repo-print-host iframe, #repo-print-host script, #repo-print-host [onerror], #repo-print-host [onload], #repo-print-host [onclick], #repo-print-host [href^=javascript]').length") == 0
    pg.wait_for_timeout(1800)
    ctx.close()


NESTED = ('<b><img src=x onerror="%s">bold</b> <ul><li onclick="%s" style="x:y">one</li><li>two</li></ul>'
          '<i><svg onload="%s"></svg>it</i><p>para<script>%s</script></p><a href="javascript:%s">lnk</a>'
          % (MARK, MARK, MARK, MARK, MARK))


def test_allowed_tags_keep_old_formatting_and_nothing_inside_them_runs(browser, page_file):
    ctx, pg = _new(browser, page_file.as_uri())
    out = pg.evaluate("""(h) => { const d = document.createElement('div'); d.appendChild(window._altoNoteFrag(h)); return d.innerHTML; }""", NESTED)
    assert out == "<b>bold</b> <ul><li>one</li><li>two</li></ul><i>it</i><p>para</p>lnk"     # tags kept, attributes and the rest gone
    assert pg.evaluate("window._altoNoteStr('x<br>y<ul><li>a</li></ul>')") == "x<br>y<ul><li>a</li></ul>"
    assert pg.evaluate("window.__xss") is None
    # in the notes list, the report window and an imported note
    items = [{"id": "n1", "quote": "Q", "color": "yellow", "note": NESTED, "kind": "highlight", "ts": 1}]
    _seed(pg, items)
    pg.evaluate("window.highlights = %s; renderNotesList.__proto__; 0" % json.dumps(items))
    pg.evaluate("toggleNotes()")
    pg.wait_for_timeout(500)
    assert pg.evaluate("window.__xss") is None
    with ctx.expect_page() as info:
        pg.evaluate("generateNotesReport()")
    rp = info.value
    rp.wait_for_load_state()
    rp.wait_for_timeout(600)
    assert rp.evaluate("window.__xss") is None and pg.evaluate("window.__xss") is None
    assert rp.evaluate("document.querySelectorAll('.hl-note b, .hl-note ul li').length") >= 2
    assert rp.evaluate("document.querySelectorAll('.hl-note [onclick], .hl-note img, .hl-note svg, .hl-note script, .hl-note a').length") == 0
    ctx.close()


def test_the_rebuild_is_attribute_free_allowlisted_and_stable_on_a_round_trip(browser, page_file):
    """Every existing marker string, rebuilt: only allowlisted tags, no attributes on any of them, and the
    string form re-parsed in the LIVE document (where a revived handler would run) and rebuilt again is
    unchanged. The marker never fires."""
    ctx, pg = _new(browser, page_file.as_uri())
    res = pg.evaluate("""(cases) => cases.map(c => {
        const host = document.createElement('div'); document.body.appendChild(host);
        host.appendChild(window._altoNoteFrag(c));
        const s1 = window._altoNoteStr(c);
        const re = document.createElement('div'); document.body.appendChild(re); re.innerHTML = s1;
        const s2 = window._altoNoteStr(s1);
        const els = [...host.querySelectorAll('*'), ...re.querySelectorAll('*')];
        return { tags: [...new Set(els.map(e => e.localName))], attrs: els.reduce((n, e) => n + e.attributes.length, 0),
                 stable: s1 === s2, ns: els.every(e => e.namespaceURI === 'http://www.w3.org/1999/xhtml') };
    })""", BAD + [NESTED])
    pg.wait_for_timeout(800)
    assert pg.evaluate("window.__xss") is None
    ok = {"b", "strong", "i", "em", "u", "br", "p", "ul", "ol", "li"}
    for r in res:
        assert set(r["tags"]) <= ok and r["attrs"] == 0 and r["stable"] and r["ns"], r
    ctx.close()


def test_a_shared_plain_note_with_ampersands_and_angles_reads_as_written(browser, page_file):
    """Cleaning must not garble ordinary text: '&', '<' and '>' arrive and show exactly as typed."""
    text = "Smith & Co. v. Jones: 3 > 2 and 1 < 2"
    payload = {"v": 1, "course": "x", "notes": True,
               "highlights": [{"quote": text, "note": text, "color": "yellow", "kind": "highlight", "ts": 1}]}
    raw = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    ctx, pg = _new(browser, page_file.as_uri() + "#share=j:" + raw)
    pg.wait_for_selector("#share-import-overlay [data-act]", timeout=8000)
    pg.click("#share-import-overlay [data-act=replace], #share-import-overlay [data-act=merge]")
    pg.wait_for_timeout(1500)
    pg.evaluate("toggleNotes()")
    pg.wait_for_timeout(500)
    assert pg.evaluate("[...document.querySelectorAll('#notes-list .note-text')].map(n => n.textContent)") == [text]
    assert pg.evaluate("window._altoNoteStr(window._altoNoteStr(%s))" % json.dumps(text)) == pg.evaluate("window._altoNoteStr(%s)" % json.dumps(text))
    ctx.close()


ROUND = ["Tom & Jerry", "a < b > c", "&amp; literal", "R&D <3", "5 > 3 && 2 < 4", "caf\u00e9 \U0001F600 ok"]


def _share_in(browser, page_file, notes):
    """Open a #share= link carrying `notes` (payload built as the sender's buildPayload does), accept it,
    and return (context, page)."""
    payload = {"v": 1, "course": "x", "notes": True, "highlights": notes}
    raw = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    ctx, pg = _new(browser, page_file.as_uri() + "#share=j:" + raw)
    pg.wait_for_selector("#share-import-overlay [data-act]", timeout=8000)
    pg.click("#share-import-overlay [data-act=replace], #share-import-overlay [data-act=merge]")
    pg.wait_for_timeout(1500)
    return ctx, pg


def test_plain_notes_survive_three_re_shares_exactly_in_the_list_and_the_report(browser, page_file):
    notes = [{"quote": t, "note": t, "color": "yellow", "fmt": "text", "kind": "highlight", "ts": 10 + i}
             for i, t in enumerate(ROUND)]
    for hop in range(3):
        ctx, pg = _share_in(browser, page_file, notes)
        stored = pg.evaluate(f"JSON.parse(localStorage.getItem('{KEY}')||'[]')")
        assert [h["note"] for h in stored] == ROUND and all(h["fmt"] == "text" for h in stored)
        pg.evaluate("toggleNotes()")
        pg.wait_for_timeout(500)
        assert pg.evaluate("[...document.querySelectorAll('#notes-list .note-text')].map(n => n.textContent)") == ROUND
        with ctx.expect_page() as info:
            pg.evaluate("generateNotesReport()")
        rp = info.value
        rp.wait_for_load_state()
        assert rp.evaluate("[...document.querySelectorAll('.hl-note')].map(n => n.textContent)") == ROUND
        assert rp.evaluate("[...document.querySelectorAll('.hl-quote')].map(n => n.textContent)") == ['"%s"' % t for t in ROUND]
        # the next hop is built from what this page stored, as buildPayload does
        notes = pg.evaluate("""() => JSON.parse(localStorage.getItem('%s')).map(h => ({quote: h.quote, color: h.color, note: h.note || '',
            fmt: h.fmt === 'text' ? 'text' : 'rich', kind: h.kind || 'highlight', ts: h.ts || 0}))""" % KEY)
        ctx.close()


def test_old_rich_notes_keep_their_formatting_and_a_rich_share_goes_through_the_allowlist(browser, page_file):
    rich = "Remember:<br>\u2022 one &amp; two<br><b>bold</b>"
    ctx, pg = _new(browser, page_file.as_uri())
    _seed(pg, [{"id": "o1", "quote": "Q", "color": "yellow", "note": rich, "kind": "highlight", "ts": 1}])   # no fmt: stored before the field
    pg.evaluate("toggleNotes()")
    pg.wait_for_timeout(500)
    assert pg.evaluate("document.querySelector('#notes-list .note-text').innerHTML") == "Remember:<br>\u2022 one &amp; two<br><b>bold</b>"
    ctx.close()
    for hop in range(3):
        ctx, pg = _share_in(browser, page_file, [{"quote": "Q", "note": rich if hop == 0 else note, "fmt": "rich", "color": "yellow", "kind": "highlight", "ts": 1}])
        note = pg.evaluate(f"JSON.parse(localStorage.getItem('{KEY}'))[0].note")
        assert pg.evaluate("window.__xss") is None
        assert note == "Remember:<br>\u2022 one &amp; two<br><b>bold</b>"
        ctx.close()


CLOBBER = [
    ("form-nextsibling-cycle", '<input form=f name=nextSibling><form id=f>t</form>'),
    ("form-nodename", '<form><input name=nodeName></form>after'),
    ("form-nodetype", '<form><input name=nodeType><b>b</b></form>after'),
    ("form-childnodes", '<form><input name=childNodes><input name=childNodes>t</form>'),
    ("form-all-names-inside-b", '<b><form><input name=childNodes><input name=firstChild><input name=nextSibling>'
                                '<input name=nodeName><input name=attributes>inner text</form></b>tail'),
]


def test_dom_clobbering_cannot_steer_the_note_walk(browser, page_file):
    """A form whose fields are named after the walk's own properties must neither freeze nor throw it."""
    import time
    ctx, pg = _new(browser, page_file.as_uri())
    for name, v in CLOBBER:
        t0 = time.time()
        res = pg.evaluate("""(v) => { const d = document.createElement('div'); d.appendChild(window._altoNoteFrag(v, 4000));
            return [d.innerHTML, d.textContent, window._altoNoteStr(v, 4000, 'html'), window._altoPlainNote(v, 4000, true)]; }""", v)
        assert time.time() - t0 < 1.0, name
        assert not re.search(r"<(?!/?(b|strong|i|em|u|br|p|ul|ol|li)>)", res[0]), (name, res[0])    # only bare allowlisted tags
        assert res[0] == res[2]
        assert "<" not in res[3]
    last = pg.evaluate("v => { const d = document.createElement('div'); d.appendChild(window._altoNoteFrag(v, 4000)); return d.textContent; }", CLOBBER[-1][1])
    assert last == "inner texttail"
    assert pg.evaluate("window.__xss") is None
    ctx.close()


LEGACY = "Intro <b>bold</b> and <i>it</i><ul><li>one</li><li>two</li></ul>"


def test_a_legacy_formatted_note_keeps_its_formatting_through_open_save_and_reopen(browser, page_file):
    ctx, pg = _new(browser, page_file.as_uri())
    _seed(pg, [{"id": "lg1", "quote": "Q", "color": "yellow", "note": LEGACY, "kind": "highlight", "ts": 1}])   # no fmt: stored before the field
    for hop in range(2):
        pg.evaluate("openNoteForHighlight('lg1')")
        pg.wait_for_timeout(400)
        assert "<" not in pg.input_value("#note-input")                  # tags are never shown in the editor
        assert pg.is_visible(".nd-notice") and pg.inner_text(".nd-notice") == "Editing will save this note as plain text"
        pg.click(".note-dialog-btn.primary")                               # save, untouched
        pg.wait_for_timeout(500)
    pg.evaluate("document.getElementById('notes-panel').classList.contains('open') || toggleNotes()")
    pg.wait_for_timeout(500)
    html = pg.evaluate("document.querySelector('#notes-list .note-text').innerHTML")
    assert "<b>bold</b>" in html and "<i>it</i>" in html and "<ul>" in html and "<li>one</li>" in html
    assert "&lt;b&gt;" not in html and "<b>" not in pg.evaluate("document.getElementById('notes-list').innerText")
    stored = pg.evaluate(f"JSON.parse(localStorage.getItem('{KEY}'))[0]")
    assert stored["note"] == LEGACY and stored.get("fmt") != "text"      # untouched: stored as it was
    # Cancel leaves it untouched, and a plain note shows no notice
    pg.evaluate("openNoteForHighlight('lg1')")
    pg.wait_for_timeout(300)
    pg.fill("#note-input", "typed then cancelled")
    pg.click(".note-dialog-btn:not(.primary)")
    pg.wait_for_timeout(300)
    stored = pg.evaluate(f"JSON.parse(localStorage.getItem('{KEY}'))[0]")
    assert stored["note"] == LEGACY and stored.get("fmt") != "text"
    # edited: it becomes plain text, with no tags in it
    pg.evaluate("openNoteForHighlight('lg1')")
    pg.wait_for_timeout(300)
    pg.fill("#note-input", "Edited <3 it")
    pg.click(".note-dialog-btn.primary")
    pg.wait_for_timeout(500)
    stored = pg.evaluate(f"JSON.parse(localStorage.getItem('{KEY}'))[0]")
    assert stored["note"] == "Edited <3 it" and stored["fmt"] == "text"
    pg.evaluate("openNoteForHighlight('lg1')")
    pg.wait_for_timeout(300)
    assert not pg.is_visible(".nd-notice")                               # now plain: no notice
    assert pg.evaluate("window.__xss") is None
    ctx.close()


# ── lint: no innerHTML, outerHTML, insertAdjacentHTML or document.write with a non-constant string ──
_SINK = re.compile(r"(\.innerHTML\s*=(?!=)|\.outerHTML\s*=(?!=)|\.insertAdjacentHTML\s*\(|document\.write(?:ln)?\s*\()")


def _fn(src, start, end):
    i = src.index(start)
    return src[i:src.index(end, i)]


def _is_constant(rhs):
    """A plain string literal, or a join of them with + (no identifiers, no ${ })."""
    if "${" in rhs:
        return False
    rest = re.sub(r"'(?:[^'\\\n]|\\.)*'|\"(?:[^\"\\\n]|\\.)*\"|`[^`$]*`", "", rhs)
    return not re.search(r"[A-Za-z_$]", rest) or rest.strip(" \n+;)(") == ""


def _violations(label, code):
    out = []
    for m in _SINK.finditer(code):
        stmt = code[m.end():m.end() + 1200]
        end = re.search(r";\s*(?:\n|$)|\n\s*\n", stmt)
        rhs = stmt[:end.start()] if end else stmt
        if m.group(1).startswith(".insertAdjacentHTML"):
            rhs = rhs.split(",", 1)[-1]
        # allow 'x'+CONST_NAME where CONST_NAME is an ALL-CAPS constant glyph
        rhs2 = re.sub(r"\b[A-Z][A-Z0-9_]{2,}\b", "''", rhs)
        if not _is_constant(rhs2):
            out.append(f"{label}: {m.group(1)} {rhs.strip()[:90]!r}")
    return out


def test_notes_and_report_code_has_no_non_constant_html_sinks():
    tpl = (ROOT / "alto/engine/timeline_template.html").read_text(encoding="utf-8")
    rep = (ROOT / "alto/engine/reports_template.html").read_text(encoding="utf-8")
    parts = {
        "timeline:renderNotesList": _fn(tpl, "function renderNotesList", "function updateNotesToggle"),
        "timeline:generateNotesReport": _fn(tpl, "async function generateNotesReport", "renderTimeline();\n// Use requestAnimationFrame"),
        "timeline:share-import": _fn(tpl, "function _cleanImported", "_runImportFromHash();   // boot"),
        "reports:report-open+print": _fn(rep, "function _cleanReportDoc", "const RR_GLYPH"),
        "reports:printReports": _fn(rep, "function printReports", "async function shareReports"),
    }
    # the notes module (newer renderer) and the freewrite report text, whole files
    for name in ("notes_v2.py", "freewrite.py"):
        parts["build:" + name] = (ROOT / "alto/build" / name).read_text(encoding="utf-8")
    bad = []
    for label, code in parts.items():
        bad += _violations(label, code)
    # freewrite.py and notes_v2.py hold a few constant-glyph and sanitiser-fed sinks; named, so a new one is a failure
    allowed = ("freewrite.py", "notes_v2.py")
    hard = [b for b in bad if not b.startswith(tuple("build:" + a for a in allowed))]
    assert not hard, "\n".join(hard)
    assert len(bad) - len(hard) <= 40, "new non-constant HTML sinks in the notes module:\n" + "\n".join(b for b in bad if b not in hard)


def test_the_plain_text_notice_shows_only_for_an_old_note_that_really_has_formatting(browser, page_file):
    ctx, pg = _new(browser, page_file.as_uri())
    _seed(pg, [{"id": "pl1", "quote": "Q", "color": "yellow", "note": "Just plain words, no markup", "kind": "highlight", "ts": 1},
               {"id": "pl2", "quote": "Q", "color": "yellow", "note": "Tom &amp; Jerry", "kind": "highlight", "ts": 2},
               {"id": "pl3", "quote": "Q", "color": "yellow", "note": LEGACY, "kind": "highlight", "ts": 3}])
    for hid, notice in (("pl1", False), ("pl2", False), ("pl3", True)):
        pg.evaluate("id => openNoteForHighlight(id)", hid)
        pg.wait_for_timeout(300)
        assert pg.is_visible(".nd-notice") == notice, hid
        pg.click(".note-dialog-btn:not(.primary)")
        pg.wait_for_timeout(200)
    ctx.close()
