"""Adversarial tests for the notes rich-text path (the allowlist rebuild) and the note `fmt` field.

Written independently of the fix, as defensive regression tests. Every payload carries only a harmless marker
(it sets window.__xss); nothing reaches out. Runs in WebKit and Chromium; skipped where Playwright is missing.

What must hold:
  * the rebuild keeps only b strong i em u br p ul ol li, in the HTML namespace, with NO attributes, and copies
    text as text: whatever is nested, namespaced, encoded or misnested, nothing runs, live or after any
    re-serialise and reparse, and the canonical string form is stable;
  * the rebuild terminates and does not throw on DOM clobbering (form / named-property tricks);
  * a #share= payload's fmt can only mean 'rich' -> stored 'html' (through the allowlist) or else plain 'text';
    no other value or field survives;
  * an fmt 'text' note is never handed to an HTML parser and reads exactly as written.

The `control` tests load deliberately weakened copies of the page and prove the same checks catch them.
"""
import base64
import json
from pathlib import Path

import pytest

try:
    import playwright.sync_api as pw
except Exception:  # pragma: no cover
    pw = None

from alto.build.builder import build_timeline, load_brief

ROOT = Path(__file__).resolve().parent.parent
KEY = "alto-hl-contracts-outline"
M = "top.__xss=1"
OK_TAGS = ["b", "strong", "i", "em", "u", "br", "p", "ul", "ol", "li"]

CORPUS = [
    # nested inside allowed tags
    ("nested-img", '<b><i><u><img src=x onerror="%s">t</u></i></b>' % M),
    ("nested-list", '<ul><li><ol><li><svg onload="%s"></svg>x</li></ol></li></ul>' % M),
    ("nested-script", '<p><em><script>%s</script>s</em></p>' % M),
    ("nested-link", '<li><strong><a href="javascript:%s">k</a></strong></li>' % M),
    ("deep", "<b>" * 60 + '<img src=x onerror="%s">' % M + "</b>" * 60),
    # attributes on allowed tags
    ("attr-handlers", '<b onclick="%s" onmouseover="%s" id=a name=b class=c>x</b>' % (M, M)),
    ("attr-autofocus", '<i tabindex=1 autofocus onfocus="%s">f</i>' % M),
    ("attr-style", '<p style="background:url(javascript:%s);behavior:url(x)">s</p>' % M),
    ("attr-href", '<u href="javascript:%s" src="javascript:%s" formaction="javascript:%s">h</u>' % (M, M, M)),
    ("attr-br", '<br onload="%s" style="x"><li onanimationstart="%s" style="animation:spin 1s">a</li>' % (M, M)),
    ("attr-quote-break", '<b title="x" "><img src=x onerror="%s">">q</b>' % M),
    # SVG and MathML
    ("svg-script", '<svg><script>%s</script></svg>' % M),
    ("svg-animate", '<svg><animate onbegin="%s" attributeName=x dur=1s></animate></svg>' % M),
    ("svg-foreign", '<svg><foreignObject><img src=x onerror="%s"></foreignObject></svg>' % M),
    ("svg-style-break", '<svg></p><style><a id="</style><img src=x onerror=%s>">' % M),
    ("svg-b-breakout", '<svg><b><img src=x onerror="%s"></b></svg>' % M),
    ("math-mglyph", '<math><mtext><table><mglyph><style><img src=x onerror="%s"></style></mglyph></table></mtext></math>' % M),
    ("math-href", '<math><mi xlink:href="javascript:%s" href="javascript:%s">m</mi></math>' % (M, M)),
    ("math-comment", '<math><mtext><table><mglyph><style><!--</style><img title="--&gt;&lt;img src=x onerror=%s&gt;">' % M),
    # template, noscript, style, iframe srcdoc and other raw-text elements
    ("template", '<template><img src=x onerror="%s"></template>t' % M),
    ("noscript-mxss", '<noscript><p title="</noscript><img src=x onerror=%s>">' % M),
    ("style", '<style><img src=x onerror="%s"></style>' % M),
    ("style-in-b", '<b><style></b><img src=x onerror="%s"></style>' % M),
    ("iframe-srcdoc", '<iframe srcdoc="&lt;script&gt;%s&lt;/script&gt;"></iframe>' % M),
    ("textarea", '<textarea><img src=x onerror="%s"></textarea>' % M),
    ("title", '<title><img src=x onerror="%s"></title>' % M),
    ("xmp", '<xmp><img src=x onerror="%s"></xmp>' % M),
    ("noembed", '<noembed><img src=x onerror="%s"></noembed>' % M),
    ("plaintext", '<plaintext><img src=x onerror="%s">' % M),
    ("object-embed", '<object data="javascript:%s"></object><embed src="javascript:%s">' % (M, M)),
    ("details", '<details open ontoggle="%s">d</details>' % M),
    ("meta-base", '<meta http-equiv=refresh content="0;url=javascript:%s"><base href="javascript:%s//">' % (M, M)),
    # entity-encoded and double-encoded markup
    ("ent", '&lt;img src=x onerror="%s"&gt;' % M),
    ("ent-double", '&amp;lt;img src=x onerror="%s"&amp;gt;' % M),
    ("ent-numeric", '&#60;img src=x onerror="%s"&#62;&#x3C;script&#x3E;%s&#x3C;/script&#x3E;' % (M, M)),
    ("ent-in-b", '<b>&lt;img src=x onerror="%s"&gt;</b>' % M),
    ("ent-in-attr", '<b title="&quot;&gt;&lt;img src=x onerror=%s&gt;">t</b>' % M),
    ("ent-no-semicolon", '&ltimg src=x onerror="%s"&gt <b>&ampx</b>' % M),
    # mutation XSS through a DOMParser round trip, misnesting
    ("mxss-form-math", '<form><math><mtext></form><form><mglyph><style></math><img src=x onerror="%s">' % M),
    ("mxss-listing", '<listing>&lt;img src=x onerror="%s"&gt;</listing>' % M),
    ("mxss-misnest", '<b><p><i></b><img src=x onerror="%s"></p></i>' % M),
    ("mxss-table", '<table><b><tr><td><img src=x onerror="%s"></td></tr></b></table>' % M),
    ("mxss-select", '<select><template><style><img src=x onerror="%s"></style></template></select>' % M),
    ("mxss-comment", '<!--><img src=x onerror="%s">--><p>c</p>' % M),
    ("mxss-cdata", '<![CDATA[><img src=x onerror="%s">]]>' % M),
    # DOM clobbering by id or name (outputs must carry no id or name)
    ("clobber-id", '<b id="notes-list">x</b><p id="_altoNoteFrag" name="highlights">y</p>'),
    ("clobber-img-body", '<img name=body><b>still</b>'),
    ("clobber-form-firstchild", '<form><input name=firstChild>t</form><b>ok</b>'),
]
_BY = dict(CORPUS)

# clobbering that targets the rebuild's own tree walk; run only under a guard, as it may not terminate
CLOBBER_WALK = [
    ("form-nextsibling-cycle", '<input form=f name=nextSibling><form id=f>t</form>'),
    ("form-nodename", '<form><input name=nodeName></form>after'),
    ("form-nodetype", '<form><input name=nodeType><b>b</b></form>after'),
    ("form-childnodes", '<form><input name=childNodes><input name=childNodes>t</form>'),
]

# text notes for the fmt tests (exact text must survive)
TEXTS = ["Tom & Jerry", "a < b > c", "&amp; literal", "R&D <3", "5 > 3 && 2 < 4", "café \U0001F600 ok",
         'raw <img src=x onerror="%s"> <b>not bold</b> &lt;i&gt;' % M]

GUARD = """(() => { let n = 0, on = false; const ct = Document.prototype.createTextNode, ce = Document.prototype.createElement;
  window.__budget = () => { n = 0; on = true; };
  Document.prototype.createTextNode = function(){ if(on && ++n > 50000) throw new Error('UNBOUNDED'); return ct.apply(this, arguments); };
  Document.prototype.createElement = function(){ if(on && ++n > 50000) throw new Error('UNBOUNDED'); return ce.apply(this, arguments); }; })()"""

# records any string handed to an HTML parser in the page (to prove fmt 'text' notes are never parsed)
SPY = """(() => { const seen = window.__parsed = [];
  const keep = (v) => { try { seen.push(String(v)); } catch(e){} };
  const dp = DOMParser.prototype.parseFromString; DOMParser.prototype.parseFromString = function(s){ keep(s); return dp.apply(this, arguments); };
  const cf = Range.prototype.createContextualFragment; Range.prototype.createContextualFragment = function(s){ keep(s); return cf.apply(this, arguments); };
  const ia = Element.prototype.insertAdjacentHTML; Element.prototype.insertAdjacentHTML = function(p, s){ keep(s); return ia.apply(this, arguments); };
  for (const [proto, prop] of [[Element.prototype, 'innerHTML'], [Element.prototype, 'outerHTML'], [ShadowRoot.prototype, 'innerHTML']]) {
    const d = Object.getOwnPropertyDescriptor(proto, prop); if(!d || !d.set) continue;
    Object.defineProperty(proto, prop, {configurable: true, enumerable: d.enumerable, get: d.get, set(v){ keep(v); return d.set.call(this, v); }});
  }
  const dw = Document.prototype.write; Document.prototype.write = function(){ keep([].join.call(arguments, '')); return dw.apply(this, arguments); };
})()"""

# checks one payload through every rich path: live fragment, string form reparsed in the live document (twice),
# a DOMParser round trip of the string form, and stability of the canonical form (it may settle once, a parser
# normalising a misnest, but must then be a fixed point: no layer of escaping is ever added)
CHECK_JS = """async ([cases, OK]) => {
  const XHTML = 'http://www.w3.org/1999/xhtml', out = {};
  const bad = (root) => [...root.querySelectorAll('*')].filter(e => OK.indexOf(e.localName) < 0 || e.namespaceURI !== XHTML || e.attributes.length)
                                                     .map(e => e.localName + (e.attributes.length ? '[' + [...e.attributes].map(a => a.name).join(',') + ']' : ''));
  for (const [name, v] of cases) {
    const viol = []; window.__xss = undefined;
    const roots = [];
    try {
      const a = document.createElement('div'); document.body.appendChild(a); a.appendChild(window._altoNoteFrag(v, 4000)); roots.push(a);
      const s1 = window._altoNoteStr(v, 4000, 'html');
      const b = document.createElement('div'); document.body.appendChild(b); b.innerHTML = s1; roots.push(b);
      const c = document.createElement('div'); document.body.appendChild(c); c.innerHTML = b.innerHTML; roots.push(c);
      const d = new DOMParser().parseFromString(s1, 'text/html');
      const e = document.createElement('div'); document.body.appendChild(e);
      for (const n of [...d.body.childNodes]) e.appendChild(document.importNode(n, true)); roots.push(e);
      const s2 = window._altoNoteStr(s1, 4000, 'html'), s3 = window._altoNoteStr(s2, 4000, 'html');
      if (s3 !== s2) viol.push('canonical form not stable');
      if (a.textContent !== b.textContent) viol.push('string form changes the text');
    } catch (err) { viol.push('threw: ' + err.message); }
    for (const el of document.querySelectorAll('[autofocus]')) { try { el.focus(); } catch(e){} }
    await new Promise(r => setTimeout(r, 120));
    for (const r of roots) { const x = bad(r); if (x.length) viol.push('elements: ' + x.join(' ')); }
    if (window.__xss) viol.push('MARKER FIRED');
    roots.forEach(r => r.remove());
    if (viol.length) out[name] = viol;
  }
  return out;
}"""


def _page_html():
    d = json.loads((ROOT / "samples" / "outline_brief.json").read_text(encoding="utf-8"))
    return build_timeline(*load_brief(d))[0]


@pytest.fixture(scope="module")
def page_html():
    return _page_html()


@pytest.fixture(scope="module")
def page_file(page_html, tmp_path_factory):
    f = tmp_path_factory.mktemp("xssadv") / "page.html"
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


def _accept(pg):
    pg.wait_for_selector("#share-import-overlay [data-act]", timeout=8000)
    pg.click("#share-import-overlay [data-act=replace], #share-import-overlay [data-act=merge]")
    pg.wait_for_timeout(1500)


def _stored(pg):
    return pg.evaluate(f"JSON.parse(localStorage.getItem('{KEY}') || '[]')")


def _bad_in(pg, sel):
    """Elements under `sel` that are not allowlisted, not HTML, or carry any attribute."""
    return pg.evaluate("""([sel, OK]) => [...document.querySelectorAll(sel)].filter(e => OK.indexOf(e.localName) < 0
        || e.namespaceURI !== 'http://www.w3.org/1999/xhtml' || e.attributes.length).map(e => e.outerHTML.slice(0, 80))""", [sel, OK_TAGS])


def _report(ctx, pg):
    with ctx.expect_page() as info:
        pg.evaluate("generateNotesReport()")
    rp = info.value
    rp.wait_for_load_state()
    rp.wait_for_timeout(600)
    return rp


def _corpus_violations(pg, cases):
    return pg.evaluate(CHECK_JS, [cases, OK_TAGS])


# ── 1. the allowlist rebuild, called directly, on every payload, with every re-serialise path ──

def test_the_rebuild_is_inert_allowlisted_attribute_free_and_stable_for_every_payload(browser, page_file):
    ctx, pg = _new(browser, page_file.as_uri())
    out = _corpus_violations(pg, CORPUS)
    assert out == {}, json.dumps(out, indent=1)
    assert pg.evaluate("window.__xss") is None
    # the text inside survives as text (nothing is decoded twice or lost to a parse quirk)
    got = pg.evaluate("v => { const d = document.createElement('div'); d.appendChild(window._altoNoteFrag(v, 4000)); return d.textContent; }",
                      _BY["ent-double"])
    assert got == '&lt;img src=x onerror="%s"&gt;' % M
    got = pg.evaluate("v => { const d = document.createElement('div'); d.appendChild(window._altoNoteFrag(v, 4000)); return d.innerHTML; }",
                      _BY["ent-in-b"])
    assert got == '<b>&lt;img src=x onerror="%s"&gt;</b>' % M
    ctx.close()


def test_the_rebuild_terminates_and_does_not_throw_on_dom_clobbering(browser, page_file):
    """Form elements let named children shadow nextSibling, nodeName, childNodes and so on. A tree walk that
    reads those properties from the parsed (attacker-shaped) document can loop for ever or throw. A #share=
    link with fmt 'rich' reaches this walk on page load, before any click."""
    ctx, pg = _new(browser, page_file.as_uri(), [GUARD])
    res = pg.evaluate("""(cases) => cases.map(([name, v]) => { __budget();
        try { const d = document.createElement('div'); d.appendChild(window._altoNoteFrag(v, 4000));
              const s = window._altoNoteStr(v, 4000, 'html'); window._altoPlainNote(v);
              return [name, 'ok', d.innerHTML === s]; }
        catch(e){ return [name, String(e.message).slice(0, 60)]; } })""", CLOBBER_WALK)
    failing = [r for r in res if r[1] != "ok"]
    assert failing == [], failing
    # and nothing a payload names can shadow the page's own functions or elements
    for name in ("clobber-id", "clobber-img-body", "clobber-form-firstchild"):
        pg.evaluate("v => { const d = document.createElement('div'); d.id = '__adv'; document.body.appendChild(d); d.appendChild(window._altoNoteFrag(v, 4000)); }", _BY[name])
    assert pg.evaluate("typeof window._altoNoteFrag === 'function' && typeof window._altoNoteStr === 'function'")
    assert pg.evaluate("document.querySelectorAll('#__adv [id], #__adv [name]').length") == 0
    assert pg.evaluate("document.querySelectorAll('[id=\"notes-list\"]').length") <= 1
    ctx.close()


# ── 2. the rich path end to end: a #share= link with fmt 'rich', three hops, list and report ──

def test_a_rich_share_of_every_payload_runs_nothing_in_the_list_or_the_report_and_is_stable_over_hops(browser, page_file):
    notes = [{"quote": "Q%d" % i, "note": v, "fmt": "rich", "color": "yellow", "kind": "highlight", "ts": 100 + i}
             for i, (_, v) in enumerate(CORPUS)]
    prev = None
    for hop in range(3):
        ctx, pg = _new(browser, _share_url(page_file, notes))
        _accept(pg)
        stored = _stored(pg)
        assert len(stored) == len(CORPUS) and all(h["fmt"] == "html" for h in stored)
        if prev is not None and hop == 2:
            assert [h["note"] for h in stored] == prev, "the canonical rich form changed on a re-share"
        prev = [h["note"] for h in stored]
        pg.evaluate("toggleNotes()")
        pg.wait_for_timeout(800)
        assert pg.evaluate("window.__xss") is None
        assert _bad_in(pg, "#notes-list .note-text *") == []
        rp = _report(ctx, pg)
        assert rp.evaluate("window.__xss") is None and pg.evaluate("window.__xss") is None
        assert rp.evaluate("window.opener") is None
        assert _bad_in(rp, ".hl-note *") == []
        notes = pg.evaluate("""k => JSON.parse(localStorage.getItem(k)).map(h => ({quote: h.quote, color: h.color, note: h.note || '',
            fmt: h.fmt === 'text' ? 'text' : 'rich', kind: h.kind || 'highlight', ts: h.ts || 0}))""", KEY)
        ctx.close()


def test_legacy_notes_without_fmt_holding_every_payload_run_nothing(browser, page_file):
    items = [{"id": "o%d" % i, "quote": "Q%d" % i, "note": v, "color": "pink", "kind": "highlight", "ts": i}
             for i, (_, v) in enumerate(CORPUS)]
    ctx, pg = _new(browser, page_file.as_uri())
    pg.evaluate("([k, v]) => localStorage.setItem(k, v)", [KEY, json.dumps(items)])
    pg.reload()
    pg.wait_for_timeout(1200)
    pg.evaluate("toggleNotes()")
    pg.wait_for_timeout(800)
    for el in pg.query_selector_all("#notes-list [autofocus]"):
        el.focus()
    assert pg.evaluate("window.__xss") is None
    assert _bad_in(pg, "#notes-list .note-text *") == []
    rp = _report(ctx, pg)
    assert rp.evaluate("window.__xss") is None and pg.evaluate("window.__xss") is None
    assert _bad_in(rp, ".hl-note *") == []
    ctx.close()


# ── 3. the fmt field itself ──

FORGED = ["rich", "html", "RICH", "Rich", " rich", "text ", "markdown", "", None, 1, True, ["rich"], {"rich": 1},
          'text" onerror="%s' % M, "html'><img src=x onerror=%s>" % M, "__proto__"]


def test_a_forged_fmt_in_a_share_payload_is_either_canonical_rich_or_plain_text(browser, page_file):
    note = 'N <img src=x onerror="%s"> <b>b</b> &amp; x' % M
    hl = []
    for i, f in enumerate(FORGED):
        h = {"quote": "Q%d" % i, "note": note, "color": "yellow", "kind": "highlight", "ts": 10 + i,
             "id": "forged-%d" % i, "onclick": M, "style": "x", "html": note, "__proto__": {"fmt": "html"}}
        if f is not None:
            h["fmt"] = f
        hl.append(h)
    ctx, pg = _new(browser, _share_url(page_file, hl))
    _accept(pg)
    stored = _stored(pg)
    assert len(stored) == len(FORGED)
    for f, h in zip(FORGED, stored):
        assert set(h) <= {"id", "quote", "color", "note", "fmt", "kind", "ts"}, h
        assert not str(h["id"]).startswith("forged")
        if f in ("rich", "html"):
            assert h["fmt"] == "html" and "<img" not in h["note"] and h["note"] == 'N  <b>b</b> &amp; x', h
            assert h["note"] == pg.evaluate("v => window._altoNoteStr(v, 4000, 'html')", h["note"])   # canonical
        else:
            assert h["fmt"] == "text" and h["note"] == note, (f, h)
    pg.evaluate("toggleNotes()")
    pg.wait_for_timeout(800)
    assert pg.evaluate("window.__xss") is None
    assert _bad_in(pg, "#notes-list .note-text *") == []
    texts = pg.evaluate("[...document.querySelectorAll('#notes-list .note-text')].map(n => n.textContent)")
    assert texts.count(note) == len([f for f in FORGED if f not in ("rich", "html")])
    rp = _report(ctx, pg)
    assert rp.evaluate("window.__xss") is None and pg.evaluate("window.__xss") is None
    assert _bad_in(rp, ".hl-note *") == []
    ctx.close()


def test_a_text_note_with_markup_is_never_parsed_and_reads_exactly(browser, page_file):
    items = [{"id": "t%d" % i, "quote": "Q%d %s" % (i, t), "note": t, "fmt": "text", "color": "blue", "kind": "highlight", "ts": 10 + i}
             for i, t in enumerate(TEXTS)]
    raw = TEXTS[-1]
    ctx, pg = _new(browser, page_file.as_uri(), [SPY])
    pg.evaluate("([k, v]) => localStorage.setItem(k, v)", [KEY, json.dumps(items)])
    pg.reload()
    pg.wait_for_timeout(1200)
    pg.evaluate("toggleNotes()")
    pg.wait_for_timeout(800)
    assert sorted(pg.evaluate("[...document.querySelectorAll('#notes-list .note-text')].map(n => n.textContent)")) == sorted(TEXTS)
    assert _bad_in(pg, "#notes-list .note-text *") == []
    rp = _report(ctx, pg)
    assert sorted(rp.evaluate("[...document.querySelectorAll('.hl-note')].map(n => n.textContent)")) == sorted(TEXTS)
    assert _bad_in(rp, ".hl-note *") == []
    assert rp.evaluate("window.__xss") is None and pg.evaluate("window.__xss") is None
    # the old renderer too, and both helpers, called on the text note
    pg.evaluate("""([raw]) => { try { renderNotesList(); } catch(e){}
        const d = document.createElement('div'); d.appendChild(window._altoNoteFrag(raw, 4000, 'text')); window.__s = window._altoNoteStr(raw, 4000, 'text'); }""", [raw])
    # nothing in the page ever handed the raw markup of a text note to an HTML parser
    hits = pg.evaluate("p => (window.__parsed || []).filter(s => s.indexOf(p) >= 0).length", '<img src=x onerror="%s">' % M)
    assert hits == 0
    assert pg.evaluate("window.__s") == pg.evaluate("v => window._altoEscHtml(v)", raw)
    ctx.close()


# ── 4. controls: deliberately weakened copies of the page; the same checks must catch each one ──

_FRAG_EL = "var e = document.createElement(g); dst.appendChild(e);"
_OK_DECL = "var OK = {b:1, strong:1, i:1, em:1, u:1, br:1, p:1, ul:1, ol:1, li:1};"
_TEXT_FAST = "if(fmt === 'text'){ frag.appendChild(document.createTextNode(window._altoCapText(t, max))); return frag; }"
_FRAG_HEAD = "window._altoNoteFrag = function(v, max, fmt){"
_RICH_DECL = "var rich = h.fmt === 'rich' || h.fmt === 'html';"

WEAK = {
    # copy every attribute onto the rebuilt element
    "attrs": [(_FRAG_EL, "var e = document.createElement(g); for(var ai = 0; ai < c.attributes.length; ai++){ try { e.setAttribute(c.attributes[ai].name, c.attributes[ai].value); } catch(x){} } dst.appendChild(e);")],
    # widen the allowlist
    "tags": [(_OK_DECL, "var OK = {b:1, strong:1, i:1, em:1, u:1, br:1, p:1, ul:1, ol:1, li:1, img:1, svg:1, a:1, iframe:1, math:1, details:1, object:1, embed:1};")],
    # no rebuild at all: the parser's own nodes go live
    "raw": [(_FRAG_HEAD, _FRAG_HEAD + " if(fmt !== 'text'){ var _r = document.createRange(); return _r.createContextualFragment(String(v == null ? '' : v)); }")],
    # fmt 'text' notes are parsed like rich ones
    "text-parsed": [(_TEXT_FAST, "")],
    # any fmt but 'text' is trusted as rich
    "fmt-trust": [(_RICH_DECL, "var rich = h.fmt !== 'text' && h.fmt != null;")],
}


def _weak_file(page_html, tmp_path_factory, kind):
    html = page_html
    for old, new in WEAK[kind]:
        assert html.count(old) >= 1, f"control '{kind}': the code it weakens has changed; update the control"
        html = html.replace(old, new)
    f = tmp_path_factory.mktemp("xssweak") / f"weak-{kind}.html"
    f.write_text(html, encoding="utf-8")
    return f


@pytest.mark.parametrize("kind", ["attrs", "tags", "raw"])
def test_control_a_weakened_rebuild_is_caught_by_the_corpus_checks(browser, page_html, tmp_path_factory, kind):
    f = _weak_file(page_html, tmp_path_factory, kind)
    ctx, pg = _new(browser, f.as_uri())
    out = _corpus_violations(pg, CORPUS)
    assert len(out) >= 5, f"control '{kind}' was not caught: {out}"
    if kind == "raw":
        assert any("MARKER FIRED" in v for vs in out.values() for v in vs)
    ctx.close()


def test_control_a_parsed_text_note_is_caught(browser, page_html, tmp_path_factory):
    f = _weak_file(page_html, tmp_path_factory, "text-parsed")
    ctx, pg = _new(browser, f.as_uri(), [SPY])
    items = [{"id": "t%d" % i, "quote": "Q", "note": t, "fmt": "text", "color": "blue", "kind": "highlight", "ts": 10 + i}
             for i, t in enumerate(TEXTS)]
    pg.evaluate("([k, v]) => localStorage.setItem(k, v)", [KEY, json.dumps(items)])
    pg.reload()
    pg.wait_for_timeout(1200)
    pg.evaluate("toggleNotes()")
    pg.wait_for_timeout(800)
    hits = pg.evaluate("p => (window.__parsed || []).filter(s => s.indexOf(p) >= 0).length", '<img src=x onerror="%s">' % M)
    texts = pg.evaluate("[...document.querySelectorAll('#notes-list .note-text')].map(n => n.textContent)")
    assert hits > 0 and sorted(texts) != sorted(TEXTS)
    ctx.close()


def test_control_a_trusted_forged_fmt_is_caught(browser, page_html, tmp_path_factory):
    f = _weak_file(page_html, tmp_path_factory, "fmt-trust")
    note = 'N <img src=x onerror="%s"> <b>b</b>' % M
    hl = [{"quote": "Q%d" % i, "note": note, "fmt": fm, "color": "yellow", "kind": "highlight", "ts": i}
          for i, fm in enumerate(["markdown", "RICH", 1])]
    ctx, pg = _new(browser, _share_url(f, hl))
    _accept(pg)
    stored = _stored(pg)
    assert any(h["fmt"] != "text" or h["note"] != note for h in stored)   # the forged-fmt test's checks would fail
    ctx.close()
