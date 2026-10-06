"""Flash cards and quizzes in a real browser, Chromium AND WebKit (study.py,
study_edit.py): flipping and marking, grading and retaking without answers,
progress that survives a reload, the owner's editor with undo, adding a section,
and the account sync against a mock Firestore (never a real account).
Skipped where Playwright or a browser is missing."""
import copy
import functools
import http.server
import json
import re
import socketserver
import threading
from pathlib import Path

import pytest

pw = pytest.importorskip("playwright.sync_api")

from alto.build.builder import build_timeline, load_brief  # noqa: E402
from alto.build.reidentify import reidentify  # noqa: E402
from alto.cloud import SOURCE  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TID = "contracts-outline"
KEY = f"alto-hl-{TID}-st"
JS = SOURCE.read_text(encoding="utf-8")
ENGINES = ["chromium", "webkit"]

CARDS = {"label": "Elements", "cards": [
    {"id": "c1", "front": "What is an offer?", "back": "A manifestation of willingness to bargain."},
    {"id": "c2", "front": "What is acceptance?", "back": "Assent to the terms of the offer."},
    {"id": "c3", "front": "What is consideration?", "back": "A bargained-for exchange."}]}
QUIZ = {"label": "Formation quiz", "questions": [
    {"id": "q1", "q": "Which is judged by outward expression?", "choices": ["Assent", "Damages", "Venue"], "answer": 0,
     "explain": "Outward expression, not secret intent."},
    {"id": "q2", "q": "Which are elements?", "choices": ["Offer", "Acceptance", "Notary"], "answer": [0, 1]},
    {"id": "q3", "q": "Consideration is...", "choices": ["A gift", "A bargained-for exchange"], "answer": 1}]}


def _brief():
    d = json.loads((ROOT / "samples" / "outline_brief.json").read_text(encoding="utf-8"))
    d["nodes"][0]["sections"] += [{"h": "Flash cards", "t": "Flip through these.", "cards": copy.deepcopy(CARDS)},
                                  {"h": "Quiz", "t": "", "quiz": copy.deepcopy(QUIZ)}]
    return d


@pytest.fixture(scope="module")
def html():
    return build_timeline(*load_brief(_brief()))[0]


@pytest.fixture(scope="module")
def playwright_():
    with pw.sync_playwright() as p:
        yield p


def _launch(p, engine):
    try:
        return getattr(p, engine).launch()
    except Exception as e:
        pytest.skip(f"no {engine}: {e}")


@pytest.fixture(scope="module")
def url(tmp_path_factory, html):
    root = tmp_path_factory.mktemp("study")
    (root / "page.html").write_text(html, encoding="utf-8")
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    h.log_message = lambda *a: None
    socketserver.TCPServer.allow_reuse_address = True
    srv = socketserver.TCPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/page.html"
    srv.shutdown()


FAKE = """(function(){ var store=null;
 var C={enabled:true, known:true, user:{uid:'u1'}, getEdits:function(){ return Promise.resolve(store); },
  putEdits:function(t,d){ store=JSON.parse(JSON.stringify(d)); return Promise.resolve(); }, watchEdits:function(){ return function(){}; }};
 Object.defineProperty(window,'AltoCloud',{get:function(){return C;}, set:function(){}, configurable:true}); })();"""


def _open(b, url, viewport=None, edit=False, mobile=False, dark=False):
    ctx = b.new_context(viewport=viewport or {"width": 1400, "height": 900}, has_touch=mobile, is_mobile=mobile,
                        color_scheme="dark" if dark else "light")
    if edit:
        ctx.add_init_script(FAKE)
    pg = ctx.new_page()
    pg.errs = []
    pg.on("pageerror", lambda e: pg.errs.append(str(e)))
    pg.goto(url)
    pg.wait_for_timeout(1400)
    if dark:
        pg.evaluate("document.documentElement.classList.add('dark')")
    pg.evaluate("showDetail('node','formation')")
    pg.wait_for_timeout(800)
    return pg


def _rec(pg):
    return pg.evaluate(f"JSON.parse(localStorage.getItem('{KEY}')||'null')")


@pytest.fixture(params=ENGINES)
def desk(request, playwright_, url):
    b = _launch(playwright_, request.param)
    pg = _open(b, url)
    yield pg
    assert not pg.errs, pg.errs
    b.close()


@pytest.fixture(params=ENGINES)
def phone(request, playwright_, url):
    b = _launch(playwright_, request.param)
    pg = _open(b, url, {"width": 390, "height": 844}, mobile=True)
    yield pg
    assert not pg.errs, pg.errs
    b.close()


@pytest.fixture(params=ENGINES)
def editor(request, playwright_, url):
    b = _launch(playwright_, request.param)
    pg = _open(b, url, edit=True)
    pg.click("#alto-edit-pill .aep-manual")
    pg.wait_for_timeout(700)
    yield pg
    assert not pg.errs, pg.errs
    b.close()


# ── the reader ──────────────────────────────────────────────────────────────

def test_cards_flip_mark_filter_shuffle_and_reset(desk):
    pg = desk
    c = pg.locator(".ast-cards")
    assert c.locator(".asc-count").inner_text() == "1 / 3"
    assert "What is an offer?" in c.locator(".asc-front .asc-tx").inner_text()
    c.locator(".asc-card").click(); pg.wait_for_timeout(650)
    assert "flip" in c.locator(".asc-card").get_attribute("class")
    c.locator(".asc-card").click(); pg.wait_for_timeout(650)
    assert "flip" not in c.locator(".asc-card").get_attribute("class")
    c.get_by_role("button", name="✓ Know it").click(); pg.wait_for_timeout(300)
    assert c.locator(".asc-count").inner_text() == "2 / 3"
    assert "What is acceptance?" in c.locator(".asc-front .asc-tx").inner_text()
    assert "flip" not in c.locator(".asc-card").get_attribute("class")           # the next card starts on its front
    pg.keyboard.press("Space"); pg.wait_for_timeout(650)                          # focus is on the card, not the button
    assert "flip" in c.locator(".asc-card").get_attribute("class")
    c.get_by_role("button", name="✗ Still learning").click(); pg.wait_for_timeout(300)
    r = _rec(pg)["s"]["n-formation-1"]["k"]
    assert r["c1"][0] == 1 and r["c2"][0] == 2
    assert "1 known · 1 still learning" in c.locator(".ast-meta").inner_text()
    c.get_by_role("button", name=re.compile("Only still learning")).click(); pg.wait_for_timeout(200)
    assert c.locator(".asc-count").inner_text() == "1 / 2"                        # not yet known: c2 and c3
    pg.keyboard.press("ArrowRight"); pg.wait_for_timeout(300)
    assert "What is consideration?" in c.locator(".asc-front .asc-tx").inner_text()
    pg.keyboard.press("ArrowLeft"); pg.wait_for_timeout(300)
    assert "What is acceptance?" in c.locator(".asc-front .asc-tx").inner_text()
    c.get_by_role("button", name="Shuffle").click(); pg.wait_for_timeout(200)
    assert "on" in c.get_by_role("button", name="Shuffle").get_attribute("class")
    c.get_by_role("button", name="Reset").click(); pg.wait_for_timeout(200)
    assert "0 known · 0 still learning" in c.locator(".ast-meta").inner_text()
    assert all(v[0] == 0 for v in _rec(pg)["s"]["n-formation-1"]["k"].values())


def test_marks_survive_a_reload(desk):
    pg = desk
    c = pg.locator(".ast-cards")
    c.get_by_role("button", name="✓ Know it").click(); pg.wait_for_timeout(200)
    pg.reload(); pg.wait_for_timeout(1400)
    pg.evaluate("showDetail('node','formation')"); pg.wait_for_timeout(800)
    assert "1 known" in pg.locator(".ast-cards .ast-meta").inner_text()


def test_a_quiz_grades_and_a_blind_retake_hides_the_answers(desk):
    pg = desk
    q = pg.locator(".ast-quiz")
    assert "Not taken yet" in q.locator(".asq-sum").inner_text()
    q.locator('input[data-q=q1][data-c="0"]').check()                             # right
    q.locator('input[data-q=q2][data-c="0"]').check()                             # right, but misses Acceptance
    q.locator('input[data-q=q3][data-c="1"]').check()                             # right
    q.get_by_role("button", name="Submit answers").click(); pg.wait_for_timeout(300)
    assert "2 / 3" in q.locator(".asq-score").inner_text().replace("\n", " ")
    assert q.locator(".asq-q.right").count() == 2 and q.locator(".asq-q.wrong").count() == 1
    assert q.locator(".asq-ch.ok").count() >= 3 and "Outward expression" in q.inner_text()
    assert "Best 67%" in q.locator(".asq-sum").inner_text() and "1 attempt" in q.locator(".asq-sum").inner_text()
    # without answers: right / wrong and the score, never which choice or why
    q.get_by_role("button", name="Retake without answers").click(); pg.wait_for_timeout(200)
    assert q.locator('fieldset input:checked').count() == 0
    q.locator('input[data-q=q1][data-c="1"]').check()
    q.locator('input[data-q=q2][data-c="0"]').check(); q.locator('input[data-q=q2][data-c="1"]').check()
    q.locator('input[data-q=q3][data-c="0"]').check()
    q.get_by_role("button", name="Submit answers").click(); pg.wait_for_timeout(300)
    assert "1 / 3" in q.locator(".asq-score").inner_text().replace("\n", " ")
    assert q.locator(".asq-q.right").count() == 1 and q.locator(".asq-q.wrong").count() == 2
    assert q.locator(".asq-ch.ok").count() == 0 and q.locator(".asq-ex").count() == 0
    assert "Outward expression" not in q.inner_text()
    body = pg.evaluate("document.querySelector('.ast-quiz .ast-body').innerHTML")
    assert "Correct answer" not in body and "Not this one" not in body
    s = _rec(pg)["s"]["n-formation-2"]
    assert s["a"] == 2 and s["l"]["bl"] == 1 and s["l"]["s"] == 1 and s["b"]["s"] == 2      # best stays the better score
    # try again blind, then choose to see the answers
    q.get_by_role("button", name="Retake without answers").first.click(); pg.wait_for_timeout(200)
    q.get_by_role("button", name="Submit answers").click(); pg.wait_for_timeout(200)
    assert q.locator(".asq-q.wrong").count() == 3
    q.get_by_role("button", name="Show the answers").click(); pg.wait_for_timeout(200)
    assert q.locator(".asq-ch.ok").count() >= 4 and "Outward expression" in q.inner_text()


def test_the_quiz_scores_survive_a_reload(desk):
    pg = desk
    q = pg.locator(".ast-quiz")
    for qq, c in (("q1", 0), ("q3", 1)):
        q.locator(f'input[data-q={qq}][data-c="{c}"]').check()
    q.get_by_role("button", name="Submit answers").click(); pg.wait_for_timeout(200)
    pg.reload(); pg.wait_for_timeout(1400)
    pg.evaluate("showDetail('node','formation')"); pg.wait_for_timeout(800)
    assert "Best 67%" in pg.locator(".ast-quiz .asq-sum").inner_text()


def test_search_finds_the_words_of_a_quiz_and_cards(desk):
    pg = desk
    n = pg.evaluate("document.documentElement.innerHTML.indexOf('manifestation of willingness')")
    assert n > 0
    assert pg.evaluate("document.querySelectorAll('.ast-slot').length") == 0      # drawn, no slot left behind


def test_the_phone_swipes_and_taps(phone):
    pg = phone
    c = pg.locator(".ast-cards")
    c.scroll_into_view_if_needed()
    box = c.locator(".asc-slide").bounding_box()
    y = box["y"] + box["height"] / 2
    # a swipe left: the next card (pointer events, as a touch makes them)
    pg.evaluate("""([x0,x1,y])=>{ var s=document.querySelector('.ast-cards .asc-slide');
      function ev(t,x){ s.dispatchEvent(new PointerEvent(t,{pointerType:'touch',clientX:x,clientY:y,bubbles:true})); }
      ev('pointerdown',x0); ev('pointerup',x1); }""", [box["x"] + box["width"] - 20, box["x"] + 20, y])
    pg.wait_for_timeout(300)
    assert c.locator(".asc-count").inner_text() == "2 / 3"
    c.locator(".asc-card").tap(); pg.wait_for_timeout(650)
    assert "flip" in c.locator(".asc-card").get_attribute("class")
    assert pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")


# ── the owner's editor ──────────────────────────────────────────────────────

def test_the_quiz_editor_edits_saves_and_undoes(editor):
    pg = editor
    btn = pg.locator(".ast-quiz .aed-st")
    assert btn.inner_text() == "✎ Edit quiz" and pg.locator(".ast-cards .aed-st").inner_text() == "✎ Edit cards"
    btn.click(); pg.wait_for_timeout(300)
    box = pg.locator("#aed-study")
    assert "Suggested: have Claude write this quiz from your notes" in box.inner_text()
    assert box.get_by_role("button", name="✦ Ask Claude to write it").count() == 1
    items = box.locator(".as-item")
    assert items.count() == 3
    items.nth(0).locator("textarea.as-q").fill("Which is judged objectively?")
    items.nth(0).get_by_role("button", name="+ Add a choice").click()
    items.nth(0).locator(".as-ci").nth(3).fill("Notice")
    items.nth(0).locator(".as-ch input[type=radio]").nth(3).check()               # the right one is now Notice
    items.nth(0).locator("textarea.as-x").fill("Because.")
    items.nth(2).get_by_role("button", name="Remove this question").click()      # remove question 3
    box.get_by_role("button", name="+ Add a question").click()
    new = box.locator(".as-item").nth(2)
    new.locator("textarea.as-q").fill("Is a gift consideration?")
    new.locator(".as-ci").nth(0).fill("Yes"); new.locator(".as-ci").nth(1).fill("No")
    new.locator(".as-ch input[type=radio]").nth(1).check()
    box.get_by_role("button", name="Save").click(); pg.wait_for_timeout(500)
    assert pg.locator("#aed-study").count() == 0
    q = pg.locator(".ast-quiz")
    assert q.locator(".asq-q").count() == 3 and "Which is judged objectively?" in q.inner_text() and "Is a gift consideration?" in q.inner_text()
    assert "Consideration is..." not in q.inner_text()
    ops = pg.evaluate("JSON.parse(localStorage.getItem(Object.keys(localStorage).filter(k=>k.indexOf('alto-ed-')===0)[0])).ops")
    op = ops["sd|n-formation-2|study"]
    assert op["v"]["n"][0]["a"] == 3 and op["v"]["n"][0]["x"] == "Because." and op["v"]["n"][2]["a"] == 1
    assert len(op["b"]) > 0 and op["b"] != "new"
    # the changed quiz grades the way it was edited
    q.locator('input[data-q=' + op["v"]["n"][0]["i"] + '][data-c="3"]').check()
    q.get_by_role("button", name="Submit answers").click(); pg.wait_for_timeout(200)
    assert q.locator(".asq-q.right").count() == 1
    # undo brings the old quiz back, redo the new one
    pg.click("#alto-edit-exit .ee-undo"); pg.wait_for_timeout(500)
    assert "Consideration is..." in pg.locator(".ast-quiz").inner_text()
    pg.click("#alto-edit-exit .ee-redo"); pg.wait_for_timeout(500)
    assert "Is a gift consideration?" in pg.locator(".ast-quiz").inner_text()


def test_the_editor_checks_what_it_saves(editor):
    pg = editor
    pg.locator(".ast-quiz .aed-st").click(); pg.wait_for_timeout(200)
    box = pg.locator("#aed-study")
    box.locator(".as-item").nth(0).locator("textarea.as-q").fill("")
    box.get_by_role("button", name="Save").click()
    assert "needs its question" in box.locator(".as-err").inner_text()
    assert pg.locator("#aed-study").count() == 1
    box.locator(".as-item").nth(0).locator("textarea.as-q").fill("Back again?")
    box.locator(".as-item").nth(0).locator(".as-ci").nth(1).fill("Assent")                  # repeats choice A
    box.get_by_role("button", name="Save").click()
    assert "repeats a choice" in box.locator(".as-err").inner_text()
    box.get_by_role("button", name="Cancel").click(); pg.wait_for_timeout(200)
    assert pg.locator("#aed-study").count() == 0
    assert "Which is judged by outward expression?" in pg.locator(".ast-quiz").inner_text()


def test_escape_and_arrows_in_the_editor_stay_in_the_editor(editor):
    pg = editor
    pg.locator(".ast-quiz .aed-st").click(); pg.wait_for_timeout(200)
    here = pg.evaluate("window._currentDetailId")
    pg.locator("#aed-study .as-name input").focus()
    pg.keyboard.press("ArrowRight"); pg.keyboard.press("ArrowLeft"); pg.keyboard.press("Space"); pg.wait_for_timeout(300)
    assert pg.evaluate("window._currentDetailId") == here and "flip" not in pg.locator(".ast-cards .asc-card").get_attribute("class")
    pg.keyboard.press("Escape"); pg.wait_for_timeout(300)
    assert pg.locator("#aed-study").count() == 0
    assert pg.evaluate("window._currentDetailId") == here and pg.evaluate("document.getElementById('detail-page').classList.contains('visible')")
    pg.keyboard.press("Escape"); pg.wait_for_timeout(300)                      # the engine's own Escape is back
    assert not pg.evaluate("document.getElementById('detail-page').classList.contains('visible')")


def test_the_cards_editor_and_ask_claude(editor):
    pg = editor
    pg.evaluate("window._altoAskClaude = function(t){ window.__asked = t; }")
    pg.locator(".ast-cards .aed-st").click(); pg.wait_for_timeout(200)
    box = pg.locator("#aed-study")
    items = box.locator(".as-item")
    assert items.count() == 3
    items.nth(0).get_by_role("button", name="Move down").click()                            # swap the first two
    items = box.locator(".as-item")
    assert items.nth(0).locator("textarea.as-q").input_value() == "What is acceptance?"
    box.get_by_role("button", name="✦ Ask Claude to write it").click()
    asked = pg.evaluate("window.__asked")
    assert "flash cards" in asked and "ONLY my own material" in asked and "add_nodes" in asked and "Formation" in asked
    box.locator(".as-opt input").check()
    box.get_by_role("button", name="Save").click(); pg.wait_for_timeout(400)
    ops = pg.evaluate("JSON.parse(localStorage.getItem(Object.keys(localStorage).filter(k=>k.indexOf('alto-ed-')===0)[0])).ops")
    v = ops["sd|n-formation-1|study"]["v"]
    assert [x["i"] for x in v["n"]] == ["c2", "c1", "c3"] and v["sh"] is True
    assert "What is acceptance?" in pg.locator(".ast-cards .asc-front .asc-tx").inner_text() or v["sh"]


def test_a_new_quiz_section_is_added_and_recommends_claude(editor):
    pg = editor
    pg.locator(".aed-add").click(); pg.wait_for_timeout(200)
    k = pg.locator("#aed-kinds")
    assert "best written by Claude" in k.inner_text()
    k.locator('button[data-k="quiz"]').click(); pg.wait_for_timeout(500)
    box = pg.locator("#aed-study")
    assert "New quiz" in box.inner_text() and "only from your own materials" in box.inner_text()
    assert box.locator(".as-claude.big").count() == 1
    box.locator("textarea.as-q").first.fill("Is an offer revocable?")
    box.locator(".as-ci").nth(0).fill("Usually"); box.locator(".as-ci").nth(1).fill("Never")
    box.get_by_role("button", name="Save").click(); pg.wait_for_timeout(700)
    assert pg.locator(".ast-quiz").count() == 2
    ops = pg.evaluate("JSON.parse(localStorage.getItem(Object.keys(localStorage).filter(k=>k.indexOf('alto-ed-')===0)[0])).ops")
    keys = [k for k in ops if k.startswith("sd|n-formation-new-")]
    assert len(keys) == 1 and ops[keys[0]]["b"] == "new" and ops[keys[0]]["v"]["n"][0]["q"] == "Is an offer revocable?"
    assert pg.locator(".ast-quiz").nth(1).locator(".aed-st").count() == 1                    # the new one is editable too


def test_cancelling_a_new_flash_card_section_takes_it_back(editor):
    pg = editor
    before = pg.locator(".detail-section").count()
    pg.locator(".aed-add").click(); pg.wait_for_timeout(200)
    pg.locator('#aed-kinds button[data-k="cards"]').click(); pg.wait_for_timeout(500)
    assert pg.locator("#aed-study").count() == 1 and pg.locator(".ast-cards").count() == 2
    pg.get_by_role("button", name="Cancel").click(); pg.wait_for_timeout(600)
    assert pg.locator("#aed-study").count() == 0 and pg.locator(".ast-cards").count() == 1
    assert pg.locator(".detail-section").count() == before


def test_the_editor_button_is_not_on_a_phone_or_outside_edit_mode(desk):
    assert desk.locator(".aed-st").count() == 0


# ── dark mode and the phone, looked at ──────────────────────────────────────

@pytest.mark.parametrize("engine", ENGINES)
def test_dark_and_phone_render_without_overflow(engine, playwright_, url):
    b = _launch(playwright_, engine)
    try:
        for vp, mobile, dark in (({"width": 1400, "height": 900}, False, True), ({"width": 390, "height": 844}, True, True),
                                 ({"width": 390, "height": 844}, True, False)):
            pg = _open(b, url, vp, mobile=mobile, dark=dark)
            assert pg.evaluate("document.querySelector('.ast-cards').scrollWidth <= document.querySelector('.ast-cards').clientWidth + 1")
            assert pg.evaluate("document.querySelector('.ast-quiz').scrollWidth <= document.querySelector('.ast-quiz').clientWidth + 1")
            assert not pg.errs
            pg.context.close()
    finally:
        b.close()


# ── the account: a second device, newest wins ───────────────────────────────

FAKE_APP = "export const initializeApp = c => ({c});"
FAKE_AUTH = """
export const getAuth = a => { const o = {currentUser: null}; window.__auth = o; return o; };
export class GoogleAuthProvider {}
export const signInWithPopup = async () => {}, signInWithRedirect = async () => {}, getRedirectResult = async () => null, signOut = async () => {};
export const browserLocalPersistence = {}, setPersistence = async () => {};
export const onAuthStateChanged = (auth, cb) => { const u = {uid: 'U1', displayName: 'T', email: 't@example.com', photoURL: ''}; auth.currentUser = u; setTimeout(() => cb(u), 30); return () => {}; };
"""
FAKE_FS = """
const call = (op, a) => window.__fs(op, a);
export const getFirestore = () => ({});
export const doc = (db, ...p) => ({path: p.join('/')});
export const collection = (db, ...p) => ({path: p.join('/'), col: true});
export const serverTimestamp = () => 1;
export class Bytes { static fromUint8Array(a){ return a; } }
const snap = (path, data) => ({id: path.split('/').pop(), exists: () => data != null, data: () => data, metadata: {hasPendingWrites: false}, forEach(){}});
export const setDoc = async (ref, data, opts) => { await call('set', {path: ref.path, data: JSON.parse(JSON.stringify(data)), merge: !!(opts && opts.merge)}); };
export const getDoc = async ref => snap(ref.path, await call('get', ref.path));
export const getDocs = async () => ({docs: [], forEach(){}});
export const deleteDoc = async () => {};
export const onSnapshot = (ref, cb) => {
  let last, dead = false;
  const tick = async () => { if(dead) return;
    if(ref.col){ if(last === undefined){ last = 0; cb({forEach(){}, docs: [], metadata: {hasPendingWrites: false}}); } }
    else { const d = await call('get', ref.path), s = JSON.stringify(d); if(s !== last){ last = s; cb(snap(ref.path, d)); } }
    setTimeout(tick, 120); };
  tick(); return () => { dead = true; };
};
"""


class Cloud:
    def __init__(self):
        self.docs, self.lock = {}, threading.Lock()

    def op(self, source, a):
        with self.lock:
            if source == "get":
                return self.docs.get(a)
            cur = dict(self.docs.get(a["path"]) or {}) if a["merge"] else {}
            cur.update(a["data"]); self.docs[a["path"]] = cur
            return None


def _device(browser, html, cloud, tid=TID):
    ctx = browser.new_context(viewport={"width": 1400, "height": 900})
    js = JS.replace('apiKey:            ""', 'apiKey: "test"').replace('projectId:         ""', 'projectId: "test"')
    mods = {"app": FAKE_APP, "auth": FAKE_AUTH, "firestore": FAKE_FS}

    def route(r):
        u = r.request.url
        if "gstatic.com/firebasejs" in u:
            name = re.search(r"firebase-(\w+)\.js", u).group(1)
            return r.fulfill(body=mods[name], content_type="application/javascript")
        if u.endswith("/alto-cloud.js"):
            return r.fulfill(body=js, content_type="application/javascript")
        if "/p.html" in u:
            return r.fulfill(body=html, content_type="text/html")
        return r.fulfill(status=404, body="")
    ctx.route("**/*", route)
    ctx.expose_binding("__fs_py", lambda src, op, a: cloud.op(op, a))
    ctx.add_init_script("window.__fs = (op, a) => window.__fs_py(op, a);")
    pg = ctx.new_page()
    pg.goto(f"http://alto.test/p.html?course={tid}"); pg.wait_for_timeout(1500)
    pg.evaluate("showDetail('node','formation')"); pg.wait_for_timeout(700)
    return pg


def _mark(pg, state_btn):
    pg.locator(".ast-cards").get_by_role("button", name=state_btn).click(); pg.wait_for_timeout(200)


@pytest.mark.parametrize("engine", ENGINES)
def test_progress_follows_the_account_and_the_newest_mark_wins(engine, playwright_, html):
    b = _launch(playwright_, engine)
    cloud = Cloud()
    try:
        a = _device(b, html, cloud)
        assert a.evaluate("!!(window.AltoCloud && AltoCloud.user)")
        _mark(a, "✓ Know it")                                                              # c1 known
        q = a.locator(".ast-quiz")
        q.locator('input[data-q=q1][data-c="0"]').check(); q.locator('input[data-q=q3][data-c="1"]').check()
        q.get_by_role("button", name="Submit answers").click(); a.wait_for_timeout(1800)
        doc = cloud.docs[f"users/U1/tl/{TID}"]
        st = json.loads(doc["study"])
        assert st["s"]["n-formation-1"]["k"]["c1"][0] == 1
        assert st["s"]["n-formation-2"]["b"]["s"] == 2 and st["s"]["n-formation-2"]["a"] == 1
        assert "highlights" in doc                                                         # the notes layer syncs beside it, untouched
        # a second device gets it
        d2 = _device(b, html, cloud)
        d2.wait_for_timeout(1500)
        assert json.loads(d2.evaluate(f"localStorage.getItem('{KEY}')"))["s"]["n-formation-1"]["k"]["c1"][0] == 1
        assert "1 known" in d2.locator(".ast-cards .ast-meta").inner_text()
        assert "Best 67%" in d2.locator(".ast-quiz .asq-sum").inner_text()
        # device 2 marks c2 later, and takes the quiz again with a worse score: A sees the mark, the best stays
        d2.locator(".ast-cards .asc-nav").nth(1).click(); d2.wait_for_timeout(200)                # on to the second card
        _mark(d2, "✗ Still learning")
        q2 = d2.locator(".ast-quiz")
        q2.locator('input[data-q=q1][data-c="1"]').check()
        q2.get_by_role("button", name="Submit answers").click(); d2.wait_for_timeout(1800)
        a.wait_for_timeout(1800)
        ra = json.loads(a.evaluate(f"localStorage.getItem('{KEY}')"))["s"]
        assert ra["n-formation-1"]["k"]["c1"][0] == 1 and ra["n-formation-1"]["k"]["c2"][0] == 2     # both devices' marks
        assert ra["n-formation-2"]["a"] == 2 and ra["n-formation-2"]["b"]["s"] == 2 and ra["n-formation-2"]["l"]["s"] == 0
        assert "2 attempts" in a.locator(".ast-quiz .asq-sum").inner_text()
        assert "1 known · 1 still learning" in a.locator(".ast-cards .ast-meta").inner_text()
        # an older copy never overwrites a newer one; a reset travels
        old = {"v": 1, "s": {"n-formation-1": {"k": {"c1": [2, 5]}, "m": 5}}}
        a.evaluate("(o)=>localStorage.setItem('%s', JSON.stringify(o))" % KEY, old); a.wait_for_timeout(1800)
        assert json.loads(cloud.docs[f"users/U1/tl/{TID}"]["study"])["s"]["n-formation-1"]["k"]["c1"][0] == 1
        a.locator(".ast-cards").get_by_role("button", name="Reset").click(); a.wait_for_timeout(1800)
        d2.wait_for_timeout(1800)
        assert "0 known · 0 still learning" in d2.locator(".ast-cards .ast-meta").inner_text()
    finally:
        b.close()


@pytest.mark.parametrize("engine", ENGINES)
def test_a_share_viewer_keeps_their_own_progress(engine, playwright_, html):
    b = _launch(playwright_, engine)
    cloud = Cloud()
    try:
        owner = _device(b, html, cloud)
        _mark(owner, "✓ Know it"); owner.wait_for_timeout(1800)
        shared = reidentify(html, "abcDEF123")
        assert "KEY = 'alto-hl-s-abcDEF123-st'" in shared and f"alto-hl-{TID}-st" not in shared
        viewer = _device(b, shared, cloud, tid="s-abcDEF123")
        assert "0 known" in viewer.locator(".ast-cards .ast-meta").inner_text()            # not the owner's marks
        _mark(viewer, "✗ Still learning"); viewer.wait_for_timeout(1800)
        assert json.loads(cloud.docs[f"users/U1/tl/{TID}"]["study"])["s"]["n-formation-1"]["k"]["c1"][0] == 1
        assert "c1" in json.loads(cloud.docs["users/U1/tl/s-abcDEF123"]["study"])["s"]["n-formation-1"]["k"]
    finally:
        b.close()


def test_the_cloud_layer_syncs_study_beside_the_notes():
    assert "let ST_KEY = TID ? `alto-hl-${TID}-st` : null;" in JS
    assert "k === ST_KEY" in JS                                                            # the Storage.prototype hook (Safari)
    assert "ST_KEY = `alto-hl-${tid}-st`" in JS                                            # setTid (the private shell)
    assert "alto-study-sync" in JS and "mergeStudy" in JS
