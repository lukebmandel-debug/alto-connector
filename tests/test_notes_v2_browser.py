"""The notes module in a real browser. Skipped when Playwright or its Chromium
is not installed (CI does not have them); run it where they are."""
import json
from pathlib import Path

import pytest

pw = pytest.importorskip("playwright.sync_api")

from alto.build.builder import build_timeline, load_brief  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
KEY = "alto-hl-contracts-outline"


@pytest.fixture(scope="module")
def page_file(tmp_path_factory):
    d = json.loads((ROOT / "samples" / "outline_brief.json").read_text(encoding="utf-8"))
    html = build_timeline(*load_brief(d))[0]
    f = tmp_path_factory.mktemp("notes") / "page.html"
    f.write_text(html, encoding="utf-8")
    return f


@pytest.fixture()
def page(page_file):
    with pw.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:                       # no browser downloaded
            pytest.skip(f"no Chromium: {e}")
        pg = b.new_page(viewport={"width": 1400, "height": 900})
        pg.goto(page_file.as_uri())
        pg.wait_for_timeout(1200)
        yield pg
        b.close()


def store(pg):
    return pg.evaluate(f"JSON.parse(localStorage.getItem('{KEY}')||'[]')")


SELECT = """(i)=>{var c=document.getElementById('detail-content');var w=document.createTreeWalker(c,NodeFilter.SHOW_TEXT);
 var n,k=0;while(n=w.nextNode()){ if(n.textContent.trim().length>60 && !n.parentElement.closest('mark')){ if(k++==i){
 var r=document.createRange();r.setStart(n,3);r.setEnd(n,22);var s=getSelection();s.removeAllRanges();s.addRange(r);
 n.parentElement.dispatchEvent(new MouseEvent('mouseup',{bubbles:true}));return true;}}}return false;}"""


def highlight(pg, i=0):
    assert pg.evaluate(SELECT, i)
    pg.wait_for_timeout(250)


def test_a_new_highlight_after_a_reload_does_not_open_the_old_note(page):
    page.evaluate("showDetail('node','definiteness')"); page.wait_for_timeout(600)
    highlight(page); page.click(".alto-note-pop")
    page.fill("#note-input", "OLD NOTE"); page.click(".note-dialog-btn.primary")
    page.reload(); page.wait_for_timeout(1200)
    page.evaluate("showDetail('node','offer')"); page.wait_for_timeout(600)
    highlight(page); page.click(".alto-note-pop")
    assert page.input_value("#note-input") == ""
    page.click(".note-dialog-btn:not(.primary)")
    notes = {h["id"]: h["note"] for h in store(page)}
    assert len(notes) == 2 and sorted(notes.values()) == ["", "OLD NOTE"]


def test_highlights_come_back_when_the_page_is_shown_again(page):
    page.evaluate("showDetail('node','definiteness')"); page.wait_for_timeout(600)
    highlight(page)
    assert page.locator("mark[data-hl-id]").count() == 1
    page.evaluate("showTimeline()"); page.wait_for_timeout(300)
    page.evaluate("showDetail('node','offer')"); page.wait_for_timeout(500)
    assert page.locator("mark[data-hl-id]").count() == 0
    page.evaluate("showDetail('node','definiteness')"); page.wait_for_timeout(600)
    assert page.locator("mark[data-hl-id]").count() == 1


def test_selecting_text_offers_a_note_instead_of_opening_one(page):
    page.evaluate("showDetail('node','definiteness')"); page.wait_for_timeout(600)
    highlight(page)
    assert page.locator(".alto-note-pop").count() == 1
    assert not page.evaluate("document.getElementById('note-dialog').classList.contains('visible')")


def test_box_undo_redo_and_panel_undo_redo(page):
    page.evaluate("showDetail('node','definiteness')"); page.wait_for_timeout(600)
    highlight(page); page.click(".alto-note-pop")
    for t in ("one", "one two"):
        page.fill("#note-input", t); page.wait_for_timeout(750)
    page.click(".nd-undo")
    assert page.input_value("#note-input") == "one"
    page.click(".nd-redo")
    assert page.input_value("#note-input") == "one two"
    page.click(".note-dialog-btn.primary")
    assert store(page)[0]["note"] == "one two"
    page.evaluate("document.getElementById('notes-panel').classList.contains('open')||toggleNotes()")
    page.wait_for_timeout(450)
    page.evaluate("document.getElementById('notes-undo-btn').click()")      # undo the note
    assert store(page)[0]["note"] == ""
    page.evaluate("document.getElementById('notes-redo-btn').click()")
    assert store(page)[0]["note"] == "one two"
    page.evaluate("document.querySelector('#notes-list .note-del').click()")
    assert store(page) == []
    page.evaluate("document.getElementById('notes-undo-btn').click()")
    assert store(page)[0]["note"] == "one two" and page.locator("mark[data-hl-id]").count() == 1


def test_tapping_a_note_goes_to_its_page_and_a_duplicate_id_store_is_repaired(page):
    seed = [{"id": "hl-1", "quote": "agreement too indefinite", "color": "yellow", "note": "first", "kind": "highlight", "ts": 1000},
            {"id": "hl-1", "quote": "Essential terms", "color": "yellow", "note": "second", "kind": "highlight", "ts": 2000}]
    page.evaluate(f"(a)=>localStorage.setItem('{KEY}',JSON.stringify(a))", seed)
    page.reload(); page.wait_for_timeout(1200)
    ids = [h["id"] for h in store(page)]
    assert len(ids) == len(set(ids)) == 2
    page.evaluate("document.getElementById('notes-panel').classList.contains('open')||toggleNotes()")
    page.wait_for_timeout(450)
    page.click("#notes-list .note-item >> nth=0 >> .note-text")
    page.wait_for_timeout(900)
    assert page.evaluate("window._currentDetailId") == "definiteness"
    assert page.locator("mark[data-hl-id]").count() >= 1


def test_a_phone_highlight_survives_leaving_the_page_and_a_reload(page_file):
    ua = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
          "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
    with pw.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:
            pytest.skip(f"no Chromium: {e}")
        pg = b.new_context(viewport={"width": 390, "height": 800}, has_touch=True, is_mobile=True, user_agent=ua).new_page()
        pg.goto(page_file.as_uri()); pg.wait_for_timeout(1200)
        count = "new Set([...document.querySelectorAll('#detail-content mark[data-hl-id]')].map(m=>m.dataset.hlId)).size"
        pg.evaluate("showDetail('node','definiteness')"); pg.wait_for_timeout(800)
        pg.evaluate("""()=>{window._hlMode=true;var c=document.getElementById('detail-content');var w=document.createTreeWalker(c,NodeFilter.SHOW_TEXT);
          var n;while(n=w.nextNode()){if(n.textContent.trim().length>40)break}var r=document.createRange();r.setStart(n,3);r.setEnd(n,25);
          var s=getSelection();s.removeAllRanges();s.addRange(r);n.parentElement.dispatchEvent(new TouchEvent('touchend',{bubbles:true,cancelable:true}))}""")
        pg.wait_for_timeout(400)
        assert pg.evaluate(count) == 1
        pg.evaluate("showTimeline()"); pg.wait_for_timeout(400)
        pg.evaluate("showDetail('node','definiteness')"); pg.wait_for_timeout(700)
        assert pg.evaluate(count) == 1
        pg.reload(); pg.wait_for_timeout(1300)
        pg.evaluate("showDetail('node','definiteness')"); pg.wait_for_timeout(800)
        assert pg.evaluate(count) == 1
        b.close()


def test_tapping_notes_never_opens_the_box(page):
    seed = [{"id": "a1", "quote": "agreement too indefinite", "color": "yellow", "note": "A", "kind": "highlight", "ts": 1,
             "src": {"t": "page", "type": "node", "id": "definiteness"}},
            {"id": "a2", "quote": "Essential terms", "color": "yellow", "note": "B", "kind": "highlight", "ts": 2,
             "src": {"t": "page", "type": "node", "id": "definiteness"}},
            {"id": "f1", "kind": "freeform", "quote": "", "color": "yellow", "note": "free", "ts": 3}]
    page.evaluate(f"(a)=>localStorage.setItem('{KEY}',JSON.stringify(a))", seed)
    page.reload(); page.wait_for_timeout(1200)
    box = "document.getElementById('note-dialog').classList.contains('visible')"
    page.evaluate("showDetail('node','definiteness')"); page.wait_for_timeout(600)
    page.evaluate("document.getElementById('notes-panel').classList.contains('open')||toggleNotes()"); page.wait_for_timeout(450)
    for i in (0, 1, 2, 0):                            # already on the page, then a note with no page, then back
        page.click(f"#notes-list .note-item >> nth={i} >> .note-text"); page.wait_for_timeout(500)
        assert not page.evaluate(box)
    page.click("#notes-list .note-item >> nth=0 >> .note-edit")
    assert page.evaluate(box)
