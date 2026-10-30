"""Every detail-page block on ONE page, PASS/FAIL per block (Testing, brief
detail-blocks-test): made from the brief and through manual edit, opened and
answered, worked from the keyboard, in Chromium AND WebKit at desktop 1440 and
phone 390, Classic and Retro, light and dark, and printed. Built offline from
samples/outline_brief.json; never a cloud store. Skipped where Playwright or a
browser is missing."""
import copy
import pytest
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTLINE = ROOT / "samples" / "outline_brief.json"
TID = "contracts-outline"
NID = "formation"

MARKUP = ("<b>Bold</b> <i>italic</i> <u>under</u> <mark>marked</mark> <code>code</code> x<sup>2</sup> H<sub>2</sub>O "
          "<q>a quote</q> <cite>Restatement</cite>, as in Lucy v. Zehmer; see <a href=\"src:file-notes\">my notes</a>."
          "<blockquote>The outward expression controls.</blockquote>"
          "<ul><li>first</li><li>second</li></ul><dl><dt>Offer</dt><dd>A promise.</dd></dl>")
TABLE = ("<table><tr><th>Element</th><th>Test</th></tr><tr><td>Offer</td><td>Definite terms</td></tr></table>"
         "<figure>Assent in one line.<figcaption>Figure 1: assent</figcaption></figure>")
LIST = "<ul><li>Lucy v. Zehmer</li><li>Carlill v. Carbolic Smoke Ball</li><li>Hamer v. Sidway</li></ul>"
TREE = {"label": "Is there an offer?", "nodes": [
    {"id": "q", "title": "Was a definite promise communicated?", "tag": "Question"},
    {"id": "no", "parent": "q", "edge": "No", "title": "No offer", "tone": "red", "text": "An invitation to deal."},
    {"id": "yes", "parent": "q", "edge": "Yes", "title": "Offer", "tone": "green", "link": "definiteness",
     "sections": [{"h": "Why", "t": "The terms are <em>definite</em>."}]}]}
TL = {"label": "Road to the Charter", "layout": "timeline", "nodes": [
    {"id": "john", "title": "John crowned", "when": "1199", "text": "Succeeds Richard."},
    {"id": "interdict", "title": "Interdict", "when": "1208", "tone": "red", "link": "definiteness"},
    {"id": "bouvines", "title": "Bouvines", "when": "1214", "sections": [{"h": "Why it matters", "t": "Sets the barons against scutage."}]},
    {"id": "runnymede", "title": "Runnymede", "when": "1215", "tone": "green"},
    {"id": "f1", "kind": "flag", "title": "Reign of John", "when": "1199", "to": "1216"}]}
CARDS = {"label": "Elements", "cards": [
    {"id": "c1", "front": "What is an offer?", "back": "A manifestation of willingness to bargain."},
    {"id": "c2", "front": "What is acceptance?", "back": "Assent to the terms of the offer."}]}
QUIZ = {"label": "Formation quiz", "questions": [
    {"id": "q1", "q": "Which is judged by outward expression?", "choices": ["Assent", "Damages"], "answer": 0,
     "explain": "Outward expression, not secret intent."},
    {"id": "q2", "q": "Which are elements?", "choices": ["Offer", "Acceptance", "Notary"], "answer": [0, 1]}]}

# section index on the formation page -> what it is
SEC = {"text": 1, "table": 2, "list": 3, "tree": 4, "timeline": 5, "cards": 6, "quiz": 7}


def brief():
    d = json.loads(OUTLINE.read_text(encoding="utf-8"))
    b = d["brief"]
    b["source_docs"] = [{"id": "casebook", "name": "Contracts casebook", "url": "https://example.com/casebook",
                         "local": "/Users/owner/Documents/casebook.pdf"}]
    b["linked_files"] = [{"id": "file-notes", "name": "My notes.pdf", "local": "/Users/owner/Documents/notes.pdf"}]
    ax = b["axes"][0]
    ax["cite_link"] = {"label": "Casebook", "url": "https://example.com/cb/{sec}#page-{p}", "sections": {"1": "s1"}}
    ax["index_sections"] = [{"h": "Pages", "t": "Page numbers are from the casebook."}]
    lucy = next(v for v in ax["values"] if v["id"] == "lucy-v-zehmer")
    lucy["cite"] = {"ch": "Chapter 1 — Assent", "p": "12"}
    n = next(x for x in d["nodes"] if x["id"] == NID)
    n["sources"] = ["casebook"]
    n["sections"] += [
        {"h": "Rule text", "t": MARKUP, "prov": "quoted"},
        {"h": "Compare", "t": TABLE, "prov": "summary"},
        {"h": "Cases", "t": LIST, "prov": "notes"},
        {"h": "Decision tree", "t": "Follow the answers.", "tree": copy.deepcopy(TREE)},
        {"h": "Timeline", "t": "Follow the years.", "tree": copy.deepcopy(TL)},
        {"h": "Flash cards", "t": "Flip through these.", "cards": copy.deepcopy(CARDS)},
        {"h": "Quiz", "t": "", "quiz": copy.deepcopy(QUIZ)}]
    return d


def build(d):
    from alto.build.builder import build_timeline, load_brief
    return build_timeline(*load_brief(d))


# ── 1. made through manual edit (the page's own ops, folded into the draft) ──

def _sig(v):
    from alto.build.manual_edit import jhash
    return jhash(json.dumps(v, ensure_ascii=False, separators=(",", ":")))


def test_every_block_with_an_edit_key_is_made_through_manual_edit():
    from alto.edits import fold, study_list, tree_list
    from tests.test_manual_edit import Store, _build as build_store, _view
    st = Store(brief())
    own = _view(st).owner("n", NID).sections
    node = next(n for n in st.nodes if n["id"] == NID)
    secs = node["sections"]
    tree, tl = tree_list(own[SEC["tree"]]), tree_list(own[SEC["timeline"]])
    cards, quiz = study_list(own[SEC["cards"]]), study_list(own[SEC["quiz"]])
    t2, tl2, c2, q2 = (copy.deepcopy(x) for x in (tree, tl, cards, quiz))
    t2.append({"i": "s-new1", "p": "q", "e": "Maybe", "t": "Ask again"})
    tl2.append({"i": "s-new2", "k": "e", "t": "Charter reissued"})
    c2["n"].append({"i": "c-new1", "f": "What is a counter-offer?", "b": "A rejection plus a new offer."})
    q2["n"].append({"i": "q-new1", "q": "Is a gift consideration?", "c": ["Yes", "No"], "a": 1})
    text = (secs[SEC["text"]]["t"] + ' Edited: <b>bold</b>, a <a data-file="file-notes">file link</a>.'
            "<table><tr><td>T2</td></tr></table>")
    lst = LIST.replace("</ul>", "<li>Kirksey v. Kirksey</li></ul>")
    st.edits = {"v": 1, "ops": {
        f"n|{NID}|s|{SEC['text']}|t": {"b": secs[SEC["text"]]["t"], "v": text, "t": 1},
        f"n|{NID}|s|{SEC['list']}|t": {"b": LIST, "v": lst, "t": 2},
        f"dt|n-{NID}-{SEC['tree']}|tree": {"b": _sig(tree), "v": t2, "t": 3},
        f"dt|n-{NID}-{SEC['tree']}|s-new1|title": {"b": "Ask again", "v": "Ask again", "t": 4},
        f"dt|n-{NID}-{SEC['timeline']}|tree": {"b": _sig(tl), "v": tl2, "t": 5},
        f"dt|n-{NID}-{SEC['timeline']}|s-new2|when": {"b": "", "v": "1216", "t": 6},
        f"sd|n-{NID}-{SEC['cards']}|study": {"b": _sig(cards), "v": c2, "t": 7},
        f"sd|n-{NID}-{SEC['quiz']}|study": {"b": _sig(quiz), "v": q2, "t": 8},
        "ne|env|new-case": {"b": None, "v": {"name": "New Case", "cite": "9 U.S. 9", "h": "Holding", "t": "Held."}, "t": 9},
        "u|0|label": {"b": st.doc["brief"]["acts"][0]["label"], "v": "UNIT ONE — MAKING A CONTRACT", "t": 10}}}
    r = fold(st, "u", "t1")
    assert not r["conflicts"] and not r["gone"], r
    html, _ = build_store(st)
    for want in ("Edited: <b>bold</b>", 'data-src="file-notes"', "<td>T2</td>", "Kirksey v. Kirksey</li>",
                 "Ask again", "Charter reissued", "What is a counter-offer?", "Is a gift consideration?",
                 "9 U.S. 9", "MAKING A CONTRACT"):
        assert want in html.replace("\\u003c", "<").replace('\\"', '"'), want


# ── 2-5. in a real browser ───────────────────────────────────────────────────

ENGINES = ["chromium", "webkit"]
DESK, PHONE = {"width": 1440, "height": 900}, {"width": 390, "height": 844}

# block -> (page, [selectors that must be drawn and inside the screen's width]).
# "sec:<Heading>" is the detail section with that heading; "A >> B" is B inside A.
PAGES = {"node": ("node", NID), "chip": ("char", "formation"), "case": ("env", "lucy-v-zehmer"), "index": ("index", "env")}
BLOCKS = {
    "01 section text": ("node", ["sec:Rule text >> " + t for t in ("b", "i", "u", "mark", "code", "sup", "sub", "q", "cite", "blockquote", "ul", "dl")]),
    "02 provenance label": ("node", [".sec-prov"]),
    "03 summary lead": ("node", [".alto-lead"]),
    "04 table / figure": ("node", ["sec:Compare >> table", "sec:Compare >> figure", "sec:Compare >> figcaption"]),
    "05 list section": ("node", ["sec:Cases >> li"]),
    "06 decision tree": ("node", [".adt:not(.amt)"]),
    "06b mini timeline": ("node", [".adt.amt"]),
    "07 flash cards": ("node", [".ast-cards", ".ast-cards .asc-card"]),
    "08 quiz": ("node", [".ast-quiz", ".ast-quiz .asq-q"]),
    "09 connections (Contains)": ("node", ["sec:Contains >> .ol-row"]),
    "10 chip page body": ("chip", ["sec:Concepts"]),
    "11 cited authority": ("case", ['sec:Casebook >> a[href="https://example.com/cb/s1#page-12"]']),
    "12 source notes": ("node", ['sec:Source notes >> a[data-src="casebook"]']),
    "13 linked file": ("node", ['a[data-src="file-notes"]']),
    "14 auto deep link": ("node", ['.alto-link.autolink[data-sd-id="lucy-v-zehmer"]']),
    "15 unit label / path numbers": ("node", [".detail-role", "sec:Contains >> .ol-num"]),
    "16 index page": ("index", ["sec:Pages"]),
}

BOXES = """([sels]) => { var W = innerWidth, out = {};
  function sec(h){ return [].slice.call(document.querySelectorAll('#detail-content .detail-section')).filter(function(s){
    var x = s.querySelector('h3'); return x && x.firstChild && x.firstChild.textContent.trim().toLowerCase() === h.toLowerCase(); })[0]; }
  sels.forEach(function(s){
    var parts = s.split(' >> '), els;
    if(parts[0].indexOf('sec:') === 0){ var c = sec(parts[0].slice(4)); els = !c ? [] : parts[1] ? [].slice.call(c.querySelectorAll(parts[1])) : [c]; }
    else els = [].slice.call(document.querySelectorAll('#detail-content ' + parts[0]));
    if(!els.length){ out[s] = 'missing'; return; }
    els.forEach(function(e){ var r = e.getBoundingClientRect();
      if(r.width < 2 || r.height < 2) out[s] = 'not drawn (' + Math.round(r.width) + 'x' + Math.round(r.height) + ')';
      else if(r.left < -1 || r.right > W + 1) out[s] = 'off the side (' + Math.round(r.left) + '..' + Math.round(r.right) + ' of ' + W + ')'; });
  });
  return out; }"""

RESULTS = {}            # (block, column) -> {cell: "" or why}; written out when ALTO_MATRIX_OUT is set


# Defects found on v1.9.189 (Testing report, 30 Oct 2026). Each is an expected failure, strictly: a new
# failure anywhere still fails, and once one is fixed its test fails until its line here is removed.
KNOWN = {
    ("06 decision tree", "interact", "chromium phone"): "list view: .adt.list .adt-kids{display:block} beats .adt-sub.folded>.adt-kids{display:none}, so Fold hides nothing",
    ("06 decision tree", "interact", "webkit phone"): "list view: Fold hides nothing (same CSS)",
    ("06b mini timeline", "print", "chromium Letter"): "the band is laid out at screen width; on paper the later events are cut off",
    ("07 flash cards", "flip facing", "webkit"): "WebKit: the front face shows through the flipped card, mirrored",
    ("09 connections (Contains)", "keyboard", "chromium reach+focus"): ".ol-name is a span with no tabindex",
    ("09 connections (Contains)", "keyboard", "chromium operate"): ".ol-name is a span with no tabindex",
    ("09 connections (Contains)", "keyboard", "webkit reach+focus"): ".ol-name is a span with no tabindex",
    ("09 connections (Contains)", "keyboard", "webkit operate"): ".ol-name is a span with no tabindex",
    ("14 auto deep link", "keyboard", "chromium reach+focus"): ".alto-link.autolink is a span with no tabindex",
    ("14 auto deep link", "keyboard", "chromium operate"): ".alto-link.autolink is a span with no tabindex",
    ("14 auto deep link", "keyboard", "webkit reach+focus"): ".alto-link.autolink is a span with no tabindex",
    ("14 auto deep link", "keyboard", "webkit operate"): ".alto-link.autolink is a span with no tabindex",
    # Playwright WebKit sends no click for a tap on a plain span (Chromium does); confirm on the iPhone Simulator.
    ("09 connections (Contains)", "interact", "webkit phone"): "WebKit tap on span.alto-link: no click",
    ("14 auto deep link", "interact", "webkit phone"): "WebKit tap on span.alto-link: no click",
    ("16 index page", "interact", "webkit phone"): "WebKit tap on span.alto-link: no click",
    ("17 back to previous", "interact", "webkit phone"): "follows from the link tap above",
}


def _rec(block, col, cell, why=""):
    RESULTS.setdefault((block, col), {})[cell] = why or ""


def _finish(pg, col, cells):
    """Fail on any new failure or a fixed known one; an expected failure when only known ones are left."""
    errs = list(getattr(pg, "errs", []) or [])
    if pg is not None:
        pg.context.close()
    assert not errs, errs
    new, fixed, known = {}, [], []
    for (b, c), got in RESULTS.items():
        for cell, why in got.items():
            if c != col or cell not in cells:
                continue
            k = (b, c, cell)
            if why and k not in KNOWN:
                new[f"{b} [{cell}]"] = why
            elif why:
                known.append(f"{b} [{cell}]: {KNOWN[k]}")
            elif k in KNOWN:
                fixed.append(f"{b} [{cell}]")
    assert not new, new
    assert not fixed, f"fixed, drop from KNOWN: {fixed}"
    if known:
        pytest.xfail("; ".join(known))


def pytest_sessionfinish_write():
    import os
    out = os.environ.get("ALTO_MATRIX_OUT")
    if out:
        prev = json.loads(Path(out).read_text()) if Path(out).exists() else {}
        for (b, c), cells in RESULTS.items():
            prev.setdefault(b, {}).setdefault(c, {}).update(cells)
        Path(out).write_text(json.dumps(prev, indent=1, sort_keys=True))


@pytest.fixture(scope="module")
def page_file(tmp_path_factory):
    html, rep = build(brief())
    f = tmp_path_factory.mktemp("blocks") / "blocks.html"
    f.write_text(html, encoding="utf-8")
    yield f
    pytest_sessionfinish_write()


@pytest.fixture(scope="module")
def playwright_():
    sp = pytest.importorskip("playwright.sync_api")
    with sp.sync_playwright() as p:
        yield p


@pytest.fixture(scope="module", params=ENGINES)
def browser(request, playwright_):
    try:
        b = getattr(playwright_, request.param).launch()
    except Exception as e:
        pytest.skip(f"no {request.param}: {e}")
    b.engine = request.param
    yield b
    b.close()


def _open(browser, page_file, size=DESK, retro=False, dark=False):
    phone = size["width"] < 600
    ctx = browser.new_context(viewport=size, has_touch=phone, is_mobile=phone and browser.engine != "firefox",
                              color_scheme="dark" if dark else "light")
    pg = ctx.new_page()
    pg.errs = []
    pg.on("pageerror", lambda e: pg.errs.append(str(e)))
    pg.goto(page_file.as_uri(), wait_until="domcontentloaded")
    pg.wait_for_function("typeof showDetail === 'function'", timeout=30000)
    pg.wait_for_timeout(1200)
    if retro:
        from alto.build.retro import retro_asset
        pg.add_script_tag(content=retro_asset()[1])
        pg.evaluate("window._altoRetro.on()")
    if dark and not retro:
        pg.evaluate("document.documentElement.classList.add('dark')")
    _go(pg, "node", NID)
    return pg


def _go(pg, kind, i):
    pg.evaluate(f"showDetail('{kind}', '{i}')")
    pg.wait_for_function("(function(){ var s = document.querySelector('#detail-content .detail-section');"
                         " return s && s.getBoundingClientRect().height > 2; })()", timeout=15000)
    pg.wait_for_timeout(500)


def _hit(pg, sel):
    """What a tap at the middle of `sel` would land on."""
    el = pg.locator(sel).first
    el.scroll_into_view_if_needed()
    b = el.bounding_box()
    return pg.evaluate("([x, y]) => { var e = document.elementFromPoint(x, y); return e ? e.tagName + '.' + String(e.className).split(' ')[0] + '#' + e.id : null; }",
                       [b["x"] + b["width"] / 2, b["y"] + b["height"] / 2])


def _here(pg):
    return pg.evaluate("window._currentDetailId")


# 4. every block is drawn, inside the screen, with no script error: 2 engines x 2 sizes x Classic/Retro x light/dark
LOOKS = [(s, st, th) for s in ("desk", "phone") for st in ("classic", "retro") for th in ("light", "dark")]


@pytest.mark.parametrize("size,style,theme", LOOKS, ids=["-".join(x) for x in LOOKS])
def test_every_block_is_drawn_inside_the_screen(browser, page_file, size, style, theme):
    pg = _open(browser, page_file, DESK if size == "desk" else PHONE, retro=style == "retro", dark=theme == "dark")
    cell = f"{browser.engine} {size} {style} {theme}"
    if style == "retro":
        assert pg.evaluate("document.documentElement.classList.contains('alto-retro')")
    bad = {}
    for page, (kind, i) in PAGES.items():
        _go(pg, kind, i)
        for block, (where, sels) in BLOCKS.items():
            if where == page:
                why = pg.evaluate(BOXES, [sels])
                _rec(block, browser.engine, cell, "; ".join(f"{k}: {v}" for k, v in why.items()))
                if why:
                    bad[block] = why
        wide = pg.evaluate("document.documentElement.scrollWidth - innerWidth")
        if wide > 1:
            bad[f"page {page}"] = f"page scrolls sideways by {wide}px"
            _rec("page", browser.engine, cell, f"{page}: sideways {wide}px")
    assert pg.evaluate("document.documentElement.classList.contains('dark')") == (theme == "dark" or style == "retro")
    _finish(pg, browser.engine, [cell])


# 2. open / flip / answer / follow, as each block offers: desktop and phone, both engines

def _check(bad, block, col, cell, fn):
    try:
        fn()
        _rec(block, col, cell)
    except Exception as e:                       # one block's failure must not hide the next one's
        why = (str(e).strip().splitlines() or [type(e).__name__])[0][:240]
        _rec(block, col, cell, why)
        bad[block] = why


def _interact(pg, phone, engine):
    t = "tap" if phone else "click"
    tree, band = ".adt:not(.amt)", ".adt.amt"

    def act(sel):
        getattr(pg.locator(sel).first, t)()
        pg.wait_for_timeout(350)

    def back_home():
        _go(pg, "node", NID)

    def cards():
        c = pg.locator(".ast-cards")
        act(".ast-cards .asc-card"); pg.wait_for_timeout(400)
        assert "flip" in c.locator(".asc-card").get_attribute("class"), "the card did not flip"
        getattr(c.get_by_role("button", name="✓ Know it"), t)(); pg.wait_for_timeout(350)
        assert c.locator(".asc-count").inner_text() == "2 / 2", c.locator(".asc-count").inner_text()
        assert "flip" not in c.locator(".asc-card").get_attribute("class"), "the next card is not on its front"

    def quiz():
        q = pg.locator(".ast-quiz")
        for qq, cc in (("q1", 0), ("q2", 0), ("q2", 1)):
            q.locator(f'input[data-q={qq}][data-c="{cc}"]').check()
        getattr(q.get_by_role("button", name="Submit answers"), t)(); pg.wait_for_timeout(400)
        assert "2 / 2" in q.locator(".asq-score").inner_text().replace("\n", " "), q.locator(".asq-score").inner_text()
        assert "Outward expression" in q.inner_text(), "no explanation after grading"

    def dtree():
        act(f'{tree} .adt-card[data-i="yes"] .adt-t')
        assert "definite" in pg.locator(f"{tree} .adt-panel").inner_text(), "the step's own words did not open"
        act(f"{tree} .adt-panel .adt-btn")
        assert pg.evaluate(f"document.querySelector('{tree} .adt-panel').hidden"), "the panel did not close"
        act(f'{tree} .adt-fold[data-fold="q"]')
        assert not pg.locator(f'{tree} .adt-card[data-i="no"]').is_visible(), "fold left the steps showing"
        act(f'{tree} .adt-fold[data-fold="q"]')
        assert pg.locator(f'{tree} .adt-card[data-i="no"]').is_visible(), "unfold did not bring them back"
        act(f'{tree} .adt-card[data-i="yes"] [data-go]')
        assert _here(pg) == "definiteness", f"link went to {_here(pg)}"
        back_home()

    def band_():
        ev = ".amt-chip" if phone else ".amt-ev"
        act(f'{band} {ev}[data-i="bouvines"]' + ("" if phone else " .adt-t"))
        assert "scutage" in pg.locator(band).inner_text(), "the event's own words did not open"
        if phone:
            pg.keyboard.press("Escape")
        if not phone:
            act(f'{band} .amt-ev[data-i="interdict"] [data-go]')
            assert _here(pg) == "definiteness", f"link went to {_here(pg)}"
            back_home()

    def autolink():
        hit = _hit(pg, '.alto-link.autolink[data-sd-id="lucy-v-zehmer"]')
        act('.alto-link.autolink[data-sd-id="lucy-v-zehmer"]')
        assert _here(pg) == "lucy-v-zehmer", f"went to {_here(pg)}; the tap landed on {hit}"

    def back_prev():                              # 17: after a link, the way back to the page it came from
        b = pg.locator("#alto-back-prev")
        assert b.count() and b.is_visible(), "no back-to-previous control after following a link"
        getattr(b, t)(); pg.wait_for_timeout(500)
        assert _here(pg) == NID, f"back went to {_here(pg)}"

    def contains():
        hit = _hit(pg, "#detail-content .ol-row .ol-name")
        act("#detail-content .ol-row .ol-name")
        assert _here(pg) == "definiteness", f"went to {_here(pg)}; the tap landed on {hit}"
        back_home()

    def links():                                  # 11-13: real targets, opened in a new tab / offered locally
        a = pg.locator('#detail-content a.note-link[data-src="casebook"]')
        assert a.get_attribute("href") == "https://example.com/casebook" and a.get_attribute("target") == "_blank"
        assert pg.locator('#detail-content .alto-src-local[data-src-local="casebook"]').count() == 1
        assert pg.locator('#detail-content .alto-src-local[data-src-local="file-notes"]').count() == 1

    def cite():
        _go(pg, "env", "lucy-v-zehmer")
        a = pg.locator('#detail-content a[href="https://example.com/cb/s1#page-12"]')
        assert a.count() == 1 and a.inner_text() == "p. 12"
        back_home()

    def index():
        _go(pg, "index", "env")
        row = pg.locator("#detail-content .alto-link", has_text="Lucy v. Zehmer").first
        getattr(row, t)(); pg.wait_for_timeout(500)
        assert _here(pg) == "lucy-v-zehmer", f"index row went to {_here(pg)}"
        back_home()

    bad = {}
    def fresh(fn):
        def run():
            if fn is not back_prev:              # back_prev follows on from the link autolink just took
                back_home()
            fn()
        return run

    for block, fn in (("07 flash cards", cards), ("08 quiz", quiz), ("06 decision tree", dtree),
                      ("06b mini timeline", band_), ("14 auto deep link", autolink), ("17 back to previous", back_prev),
                      ("09 connections (Contains)", contains), ("12/13 source + linked file", links),
                      ("11 cited authority", cite), ("16 index page", index)):
        _check(bad, block, "interact", f"{engine} {'phone' if phone else 'desk'}", fresh(fn))
    return bad


@pytest.mark.parametrize("size", ["desk", "phone"])
def test_every_block_opens_and_answers(browser, page_file, size):
    pg = _open(browser, page_file, DESK if size == "desk" else PHONE)
    _interact(pg, size == "phone", browser.engine)
    _finish(pg, "interact", [f"{browser.engine} {size}"])


# 18-20. the panels opened from a page: a highlight with a note, Freewrite, and the report of both

SELECT = """() => { var c = document.getElementById('detail-content'), w = document.createTreeWalker(c, NodeFilter.SHOW_TEXT), n;
  while((n = w.nextNode())) if(n.textContent.indexOf('judged by outward expression') !== -1){
    var r = document.createRange(), i = n.textContent.indexOf('judged'); r.setStart(n, i); r.setEnd(n, i + 26);
    var s = getSelection(); s.removeAllRanges(); s.addRange(r);
    n.parentElement.dispatchEvent(new MouseEvent('mouseup', {bubbles: true})); return true; }
  return false; }"""


def test_notes_freewrite_and_the_report(browser, page_file):
    pg = _open(browser, page_file)
    bad = {}

    def notes():
        assert pg.evaluate(SELECT), "no text to select"
        pg.wait_for_timeout(300)
        pg.click(".alto-note-pop"); pg.fill("#note-input", "Objective test"); pg.click(".note-dialog-btn.primary")
        pg.wait_for_timeout(300)
        pg.evaluate("document.getElementById('notes-panel').classList.contains('open') || toggleNotes()")
        pg.wait_for_timeout(400)
        assert "Objective test" in pg.locator("#notes-list").inner_text(), "the note is not in the panel"
        assert pg.locator("#detail-content mark").count() >= 1, "the highlight is not on the page"

    def freewrite():
        pg.click("#fw-seg button[data-m=fw]"); pg.wait_for_timeout(250)
        pg.click("#fw-editor"); pg.keyboard.type("My own summary.")
        pg.wait_for_timeout(1500)
        assert pg.evaluate("document.getElementById('fw-state').textContent") == "Saved"
        _go(pg, "node", "definiteness")
        assert "My own summary." in pg.evaluate("document.getElementById('fw-editor').innerText"), "Freewrite did not stay open"
        _go(pg, "node", NID)

    def report():
        pg.evaluate("document.getElementById('notes-panel').classList.contains('open') || toggleNotes()")
        pg.click("#fw-seg button[data-m=notes]"); pg.wait_for_timeout(250)
        pg.check("#fw-attach input")                 # "Attach my Freewrite" (off by default)
        with pg.context.expect_page(timeout=10000) as pop:
            pg.click("#notes-report-btn")
        r = pop.value
        r.wait_for_load_state()
        body = r.inner_text("body")
        assert "Objective test" in body and "judged by outward" in body, body[:200]
        assert "My own summary." in body, "the Freewrite is not in the report"
        r.close()

    for block, fn in (("18 notes & highlights", notes), ("19 freewrite", freewrite), ("20 report", report)):
        _check(bad, block, "interact", f"{browser.engine} desk", fn)
    _finish(pg, "interact", [f"{browser.engine} desk"])


# 3. the keyboard alone: every block can be reached with Tab, shows where focus is, and works

KEYBLOCKS = {"07 flash cards": ".ast-cards", "08 quiz": ".ast-quiz", "06 decision tree": ".adt:not(.amt)",
             "06b mini timeline": ".adt.amt", "14 auto deep link": ".alto-link.autolink",
             "09 connections (Contains)": ".ol-row", "12 source notes": 'a[data-src="casebook"]',
             "13 linked file": '[data-src="file-notes"],[data-src-local="file-notes"]'}

WHO = """(m) => { var e = document.activeElement; if(!e || !e.closest('#detail-content')) return null;
  var s = getComputedStyle(e), shown = (s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0) || (s.boxShadow && s.boxShadow !== 'none');
  for(var k in m) if(e.closest(m[k])) return [k, shown, e.tagName + '.' + String(e.className).split(' ')[0]];
  return ['other', shown, e.tagName]; }"""


def test_every_block_works_from_the_keyboard(browser, page_file):
    pg = _open(browser, page_file)
    pg.evaluate("var c = document.getElementById('detail-content'); c.setAttribute('tabindex', '-1'); c.focus();")
    reached, unseen = {}, {}
    for _ in range(90):
        pg.keyboard.press("Tab")
        w = pg.evaluate(WHO, KEYBLOCKS)
        if w and w[0] != "other":
            reached.setdefault(w[0], w[2])
            if not w[1]:
                unseen.setdefault(w[0], w[2])
    bad = {}
    for block in KEYBLOCKS:
        why = ("not reachable with Tab" if block not in reached
               else f"no visible focus on {unseen[block]}" if block in unseen else "")
        _rec(block, "keyboard", f"{browser.engine} reach+focus", why)
        if why:
            bad[block] = why

    def cards():
        pg.focus(".ast-cards .asc-card"); pg.keyboard.press("Space"); pg.wait_for_timeout(600)
        assert "flip" in pg.locator(".ast-cards .asc-card").get_attribute("class"), "Space did not flip"
        pg.keyboard.press("ArrowRight"); pg.wait_for_timeout(300)
        assert pg.locator(".ast-cards .asc-count").inner_text() == "2 / 2", "→ did not move on"

    def quiz():
        pg.focus('.ast-quiz input[data-q=q1][data-c="0"]'); pg.keyboard.press("Space")
        pg.focus('.ast-quiz input[data-q=q2][data-c="0"]'); pg.keyboard.press("Space")
        pg.keyboard.press("Tab"); pg.keyboard.press("Space")
        pg.locator(".ast-quiz").get_by_role("button", name="Submit answers").focus(); pg.keyboard.press("Enter")
        pg.wait_for_timeout(400)
        assert "2 / 2" in pg.locator(".ast-quiz .asq-score").inner_text().replace("\n", " ")

    def dtree():
        pg.focus('.adt:not(.amt) .adt-card[data-i="yes"]'); pg.keyboard.press("Enter"); pg.wait_for_timeout(350)
        assert "definite" in pg.locator(".adt:not(.amt) .adt-panel").inner_text(), "Enter did not open the step"

    def band_():
        pg.focus('.amt-ev[data-i="john"]'); pg.keyboard.press("ArrowRight")
        assert pg.evaluate("document.activeElement.getAttribute('data-i')") == "interdict"

    def autolink():
        el = pg.locator('.alto-link.autolink[data-sd-id="lucy-v-zehmer"]').first
        el.focus()
        assert pg.evaluate("document.activeElement.classList.contains('autolink')"), "the link cannot take focus"
        pg.keyboard.press("Enter"); pg.wait_for_timeout(500)
        assert _here(pg) == "lucy-v-zehmer", "Enter on the link did nothing"
        _go(pg, "node", NID)

    def contains():
        pg.locator("#detail-content .ol-row .ol-name").first.focus()
        assert pg.evaluate("document.activeElement.classList.contains('ol-name')"), "the row cannot take focus"
        pg.keyboard.press("Enter"); pg.wait_for_timeout(500)
        assert _here(pg) == "definiteness", "Enter on the row did nothing"
        _go(pg, "node", NID)

    def fresh(fn):
        def run():
            _go(pg, "node", NID)
            fn()
        return run

    for block, fn in (("07 flash cards", cards), ("08 quiz", quiz), ("06 decision tree", dtree),
                      ("06b mini timeline", band_), ("14 auto deep link", autolink), ("09 connections (Contains)", contains)):
        _check(bad, block, "keyboard", f"{browser.engine} operate", fresh(fn))
    _finish(pg, "keyboard", [f"{browser.engine} reach+focus", f"{browser.engine} operate"])


# Art saw a mirrored back on a flipped card in WebKit: the back face must read left to right

def test_a_flipped_card_reads_the_right_way_round(browser, page_file):
    """Flipped, only the back shows: the card looks the same with its front face hidden."""
    import os
    pg = _open(browser, page_file)
    pg.click(".ast-cards .asc-card"); pg.wait_for_timeout(900)
    box = pg.locator(".ast-cards .asc-card")
    shot = box.screenshot(animations="disabled")
    pg.evaluate("document.querySelector('.ast-cards .asc-front').style.visibility = 'hidden'")
    clean = box.screenshot(animations="disabled")
    if os.environ.get("ALTO_SHOTS"):
        (Path(os.environ["ALTO_SHOTS"]) / f"flip-{browser.engine}.png").write_bytes(shot)
    why = "" if shot == clean else "the front shows through the back, mirrored"
    _rec("07 flash cards", "flip facing", browser.engine, why)
    _finish(pg, "flip facing", [browser.engine])


# 5. print: the page with every block on paper, nothing left off (Chromium: page.pdf; WebKit has no pdf)

PRINTED = {"01 section text": ["Bold", "The outward expression controls.", "A promise."],
           "02 provenance label": ["QUOTED", "FROM YOUR NOTES"],
           "03 summary lead": ["A contract forms on mutual assent"],
           "04 table / figure": ["Definite terms", "Figure 1: assent"],
           "05 list section": ["Hamer v. Sidway"],
           "06 decision tree": ["Was a definite promise", "No offer", "An invitation to deal.", "Offer"],
           "06b mini timeline": ["John crowned", "Interdict", "Bouvines", "Runnymede", "Reign of John"],
           "07 flash cards": ["What is acceptance?", "Assent to the terms of the offer."],
           "08 quiz": ["Which are elements?", "Notary", "Answer key"],
           "09 connections (Contains)": ["Preliminary Negotiations"],
           "12 source notes": ["Contracts casebook"],
           "13 linked file": ["my notes"],
           "14 auto deep link": ["Lucy v. Zehmer"]}


def test_the_page_prints_with_every_block_whole(browser, page_file, tmp_path):
    import shutil
    import subprocess
    if browser.engine != "chromium":
        pytest.skip("page.pdf is Chromium-only; WebKit print is checked in real Safari on Home Desktop")
    if not shutil.which("pdftotext"):
        pytest.skip("no pdftotext")
    pg = _open(browser, page_file)
    pg.evaluate("window.dispatchEvent(new Event('beforeprint'))")
    pg.emulate_media(media="print")
    pg.wait_for_timeout(400)
    pdf = tmp_path / "blocks.pdf"
    pdf.write_bytes(pg.pdf(format="Letter", print_background=True))
    words = " ".join(subprocess.run(["pdftotext", str(pdf), "-"], capture_output=True, text=True).stdout.split())
    for block, want in PRINTED.items():
        lost = [w for w in want if " ".join(w.split()) not in words]
        _rec(block, "print", "chromium Letter", f"not on paper: {lost}" if lost else "")
    _finish(pg, "print", ["chromium Letter"])
