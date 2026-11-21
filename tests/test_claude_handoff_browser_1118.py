"""The Claude handoff in real browsers (Board B-1118-CUTBASS part B): WebKit (Holo, Classic, Retro at d1440 and p390) and Chromium (Classic).
Local server, no network, a fake account. From edit mode on a detail page: "+ Add a section" > "Quiz" under "Or ask Claude to write one" copies
the prompt, opens Claude at its plain address in a new tab, saves the request under the owner's account, and says what to do next. Also the edit
pill's star, a card's star, the keyboard, the returning-user prompt and the connector update notice. Shots and the prompts: HANDOFF_SHOTS=<dir>."""
import os
import re
import sys
from pathlib import Path

import pytest

pw = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
import test_edit_pill_bass_1117 as PILL  # noqa: E402  (the page and the local server; its hook parts are not used here)

SHOTS = os.environ.get("HANDOFF_SHOTS", "")
UA = PILL.UA
FAKE = """(function(){ var store=null; window.__saved=[]; window.__opened=[]; window.__copied=[];
 var C={enabled:true, known:true, user:{uid:'u1', email:'tester@example.com'}, getEdits:function(){ return Promise.resolve(store); },
  putEdits:function(t,d){ store=JSON.parse(JSON.stringify(d)); return Promise.resolve(); }, watchEdits:function(){ return function(){}; },
  putRequest:function(c,d,exp){ window.__saved.push([c,d,exp]); return Promise.resolve(true); }, connectorState:function(){ return Promise.resolve(null); }};
 Object.defineProperty(window,'AltoCloud',{get:function(){return C;}, set:function(){}, configurable:true});
 window.open=function(u,t,f){ window.__opened.push([String(u),t,f]); return null; };
 try{ Object.defineProperty(navigator,'clipboard',{value:{writeText:function(t){ window.__copied.push(String(t)); return Promise.resolve(); }}, configurable:true}); }catch(e){} })();"""
CASES = [(s, t, w, h) for s, t in (("holo", "dark"), ("classic", "light"), ("retro", "dark")) for (w, h) in ((1440, 900), (390, 844))]
STATE = """() => { const el = document.getElementById('alto-handoff'), R = e => { const r = e.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom, r.width, r.height]; };
  if(!el) return null; const box = el.querySelector('.ah-box');
  return {title: el.querySelector('#ah-t').textContent, goal: el.querySelector('.ah-goal').textContent, steps: [...el.querySelectorAll('ol li')].map(e => e.textContent),
    text: el.querySelector('textarea').value, status: el.querySelector('.ah-st').textContent, role: box.getAttribute('role'), modal: box.getAttribute('aria-modal'),
    labelled: !!document.getElementById(box.getAttribute('aria-labelledby')), box: R(box), vw: innerWidth, vh: innerHeight,
    btns: [...el.querySelectorAll('.ah-b')].map(e => [e.textContent, R(e)[5], e.tagName, e.getAttribute('href'), e.getAttribute('rel'), e.getAttribute('target')]),
    focus: document.activeElement && document.activeElement.textContent, opened: window.__opened.slice(), copied: window.__copied.slice(), saved: window.__saved.slice(),
    url: location.href, scroll_x: document.documentElement.scrollWidth > innerWidth + 1}; }"""


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    import functools, http.server, socketserver, threading
    from alto.build import holo, retro
    root = tmp_path_factory.mktemp("handoff")
    (root / "on.html").write_text(PILL._page(), "utf-8")
    for m, fn in ((retro, retro.retro_asset), (holo, holo.holo_asset)):
        f = root / m.PATH.lstrip("/"); f.parent.mkdir(parents=True, exist_ok=True); f.write_text(fn()[1], encoding="utf-8")
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root)); h.log_message = lambda *a: None
    socketserver.TCPServer.allow_reuse_address = True
    srv = socketserver.TCPServer(("127.0.0.1", 0), h); threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def _open(b, server, w, h, style, theme, used=False):
    phone = w < 700
    ctx = b.new_context(viewport={"width": w, "height": h}, is_mobile=phone, has_touch=phone, user_agent=UA if phone else None, device_scale_factor=2 if phone else 1)
    ctx.add_init_script(FAKE + ";try{localStorage.setItem('alto-theme-v1','%s');%s}catch(e){}" % (theme, "localStorage.setItem('alto-claude-used','1')" if used else ""))
    pg = ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)) if "MIME type" not in str(e) else None)
    pg.goto(f"{server}/on.html", wait_until="domcontentloaded")
    pg.wait_for_function("typeof showDetail === 'function'", timeout=30000); pg.wait_for_timeout(1200)
    if style != "classic":
        pg.evaluate("window._altoStyle.set('%s');0" % style); pg.wait_for_timeout(1500)
    return ctx, pg, errs


def _quiz_from_edit_mode(pg, phone):
    """Edit mode on the detail page “Definiteness”. Desktop: + Add a section, then Quiz under "Or ask Claude to write one". A phone's edit mode
    has no + Add a section, so there it is the editing bar's star and "Add a quiz" in its list. -> the control to press."""
    pill = ".alto-edit-pill.in-page .aep-manual" if phone else ".alto-edit-pill:not(.in-page) .aep-manual"
    if phone:
        pg.evaluate("() => { const t = document.querySelector('.alto-edit-pill.in-page'); if(t) t.scrollIntoView({block: 'center'}); }"); pg.wait_for_timeout(400)
    pg.locator(pill).first.click(); pg.wait_for_timeout(900)
    if phone:
        pg.locator("#alto-edit-exit .ee-ask").click(); pg.wait_for_selector("#alto-handoff .ah-pick", timeout=5000); pg.wait_for_timeout(250)
        return pg.locator("#alto-handoff .ah-pick .ah-row", has_text="Add a quiz")
    pg.wait_for_selector("#detail-content .aed-add", state="attached", timeout=8000)
    add = pg.locator("#detail-content .aed-add").first
    add.scroll_into_view_if_needed(); pg.wait_for_timeout(200); add.click(); pg.wait_for_timeout(400)
    return pg.locator('#aed-kinds .aed-askrow button[data-ak="quiz"]')


ROWS = """(sel) => [...document.querySelectorAll(sel)].map(e => { const r = e.getBoundingClientRect();
  return [e.textContent, e.title, e.getAttribute('aria-label') || e.title, r.height, r.right <= innerWidth && r.left >= 0]; })"""


@pytest.fixture(scope="module", params=["webkit", "chromium"])
def runs(request, server):
    out = {"engine": request.param, "cases": []}
    with pw.sync_playwright() as p:
        b = getattr(p, request.param).launch()
        for style, theme, w, h in (CASES if request.param == "webkit" else [c for c in CASES if c[0] == "classic"]):
            phone = w < 700
            ctx, pg, errs = _open(b, server, w, h, style, theme)
            c = {"case": [request.param, style, w], "errs": errs, "url0": pg.url}
            name = "%s-%s" % (style, "p390" if phone else "d1440")
            # the edit pill's star, on a detail page, before any editing
            pg.evaluate("showDetail('node','definiteness')"); pg.wait_for_timeout(900)
            star = ".alto-edit-pill.in-page .aep-claude" if phone else ".alto-edit-pill:not(.in-page) .aep-claude"
            pg.evaluate("s => { const e = document.querySelector(s); if(e) e.scrollIntoView({block: 'center'}); }", star); pg.wait_for_timeout(250)
            pg.locator(star).first.click(); pg.wait_for_selector("#alto-handoff", timeout=5000); pg.wait_for_timeout(250)
            c["star"] = pg.evaluate(STATE); pg.keyboard.press("Escape"); pg.wait_for_timeout(150)
            q = _quiz_from_edit_mode(pg, phone)
            c["ask_row"] = pg.evaluate(ROWS, "#alto-handoff .ah-pick .ah-row" if phone else "#aed-kinds .aed-askrow button")
            if SHOTS and request.param == "webkit":
                pg.screenshot(path=f"{SHOTS}/{name}-1-add-a-section-ask-claude.png")
            q.click(); pg.wait_for_selector("#alto-handoff", timeout=5000); pg.wait_for_timeout(350)
            c["sheet"] = pg.evaluate(STATE)
            if SHOTS and request.param == "webkit":
                pg.screenshot(path=f"{SHOTS}/{name}-2-copied-paste-into-claude.png")
            # keyboard: Tab stays inside, Escape closes and gives the focus back
            pg.keyboard.press("Tab"); pg.keyboard.press("Tab"); pg.keyboard.press("Tab"); pg.keyboard.press("Tab")
            c["trap"] = pg.evaluate("!!(document.activeElement && document.activeElement.closest('#alto-handoff'))")
            pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
            c["closed"] = pg.evaluate("!document.getElementById('alto-handoff')")
            # the editing bar's star: the same press while editing
            bar = pg.evaluate("""() => { const b = document.querySelector('#alto-edit-exit .ee-ask'); if(!b) return null; const r = b.getBoundingClientRect(), d = document.querySelector('#alto-edit-exit .ee-done').getBoundingClientRect();
              return [b.title, b.getAttribute('aria-label'), r.width, document.querySelector('#alto-edit-exit .ee-undo').getBoundingClientRect().width, r.left >= 0 && r.right <= innerWidth, d.left >= 0 && d.right <= innerWidth + .5]; }""")
            c["bar"] = bar
            pg.locator("#alto-edit-exit .ee-ask").click(); pg.wait_for_selector("#alto-handoff .ah-pick", timeout=5000); pg.wait_for_timeout(200)
            c["pick"] = pg.evaluate("[document.querySelector('#alto-handoff h2').textContent, document.activeElement.textContent, document.querySelector('#alto-handoff .ah-box').getAttribute('role')]")
            c["pick_rows"] = pg.evaluate(ROWS, "#alto-handoff .ah-pick .ah-row")
            pg.keyboard.press("Enter"); pg.wait_for_selector("#alto-handoff textarea", timeout=5000); pg.wait_for_timeout(250)      # the first row, by keyboard
            c["bar_star"] = pg.evaluate(STATE); pg.keyboard.press("Escape")
            out["cases"].append(c); ctx.close()
        # a card's own star (desktop, edit mode), and a returning user's prompt
        ctx, pg, errs = _open(b, server, 1440, 900, "classic", "light", used=True)
        pg.locator(".alto-edit-pill:not(.in-page) .aep-manual").first.click(); pg.wait_for_timeout(900)
        pg.locator("#node-definiteness .node-card").hover(); pg.wait_for_timeout(400)
        out["card_star"] = pg.evaluate("""() => { const b = document.querySelector('#node-definiteness .aed-cc [data-x="askc"]'); return b ? [b.title, b.getAttribute('data-g'), b.getAttribute('aria-label')] : null; }""")
        pg.locator('#node-definiteness .aed-cc [data-x="askc"]').click(); pg.wait_for_selector("#alto-handoff", timeout=5000); pg.wait_for_timeout(250)
        out["card"] = pg.evaluate(STATE); pg.keyboard.press("Escape")
        pg.evaluate("showDetail('node','definiteness')"); pg.wait_for_timeout(900)
        add = pg.locator("#detail-content .aed-add").first; add.scroll_into_view_if_needed(); add.click(); pg.wait_for_timeout(400)
        pg.locator('#aed-kinds .aed-askrow button[data-ak="quiz"]').click(); pg.wait_for_selector("#alto-handoff", timeout=5000); pg.wait_for_timeout(250)
        out["returning"] = pg.evaluate(STATE)
        if SHOTS and request.param == "webkit":
            pg.screenshot(path=f"{SHOTS}/returning-user-d1440.png")
        # the update notice: alto-cloud.js's own function, run here with this release's numbers
        from alto.cloud import emit_cloud_js
        js = emit_cloud_js({})
        note = js[js.index("const CONN_LATEST"):js.index("async function _connectorCheck")]
        pg.keyboard.press("Escape")
        pg.evaluate("s => { window.__note = new Function(s + '; return _connectorNote;')(); }", note)
        pg.evaluate("window.__note('1.9.100')"); pg.wait_for_timeout(200)
        out["note"] = pg.evaluate("""() => { const e = document.getElementById('alto-conn-note'); if(!e) return null; const r = e.getBoundingClientRect();
          return {text: e.textContent, role: e.getAttribute('role'), box: [r.left, r.top, r.right, r.bottom], vw: innerWidth, vh: innerHeight,
                  ctl: [...e.querySelectorAll('a,button')].map(x => [x.textContent, x.getBoundingClientRect().height, x.getAttribute('href'), x.getAttribute('rel')])}; }""")
        if SHOTS and request.param == "webkit":
            pg.screenshot(path=f"{SHOTS}/update-notice-d1440.png")
            pg.set_viewport_size({"width": 390, "height": 844}); pg.wait_for_timeout(300); pg.screenshot(path=f"{SHOTS}/update-notice-p390.png"); pg.set_viewport_size({"width": 1440, "height": 900})
        pg.locator("#alto-conn-note button").click(); pg.wait_for_timeout(150)
        pg.evaluate("window.__note('1.9.100')")
        out["note_dismissed"] = pg.evaluate("!document.getElementById('alto-conn-note')")
        pg.evaluate("window.__note('%s')" % __import__("alto.mcp_server", fromlist=["x"]).__version__)
        out["note_current"] = pg.evaluate("!document.getElementById('alto-conn-note')")
        ctx.close(); b.close()
    if SHOTS and request.param == "webkit":
        first = out["cases"][2]["sheet"]["text"]; back = out["returning"]["text"]
        Path(SHOTS, "prompt-first-timer.txt").write_text(first + "\n", "utf-8"); Path(SHOTS, "prompt-returning-user.txt").write_text(back + "\n", "utf-8")
    return out


def test_no_script_errors_and_the_ask_rows_are_there_with_tips_and_names(runs):
    adds = ["Quiz", "Flash cards", "Decision tree", "Mini timeline", "Summary"]
    for c in runs["cases"]:
        assert c["errs"] == [], c
        phone = c["case"][2] < 700
        want = ["✦ Change this page", "✦ Add a quiz", "✦ Add flash cards", "✦ Add a decision tree", "✦ Add a mini timeline", "✦ Add a summary"]
        assert [r[0] for r in c["ask_row"]] == (want if phone else ["✦ " + a for a in adds]), (c["case"], c["ask_row"])
        assert [r[0] for r in c["pick_rows"]] == want and c["pick"] == ["Ask Claude about “Definiteness”", "✦ Change this page", "dialog"], (c["case"], c["pick"])
        for rows in (c["ask_row"], c["pick_rows"]):
            assert all(r[1] and r[4] for r in rows), rows                       # each has its tip and sits inside the window
        floor = 43.9 if phone else 35.9          # 44pt on a phone; a desktop page is drawn at the page's own zoom (44px in its own units)
        assert all(r[3] >= floor for r in c["pick_rows"]), (c["case"], c["pick_rows"])
        if phone:
            assert all(r[3] >= 43.9 for r in c["ask_row"]), (c["case"], c["ask_row"])


def test_the_quiz_press_names_the_action_the_detail_page_and_the_page(runs):
    for c in runs["cases"]:
        s = c["sheet"]
        assert s["goal"] == "Add a quiz to the detail page “Definiteness” in the Contracts outline.", (c["case"], s["goal"])
        assert s["text"].startswith("In Alto: " + s["goal"]) and "If the Alto connector isn't connected here yet" in s["text"]
        assert s["title"] == "Copied. Paste it into Claude." and "clipboard" in s["status"], (c["case"], s["title"])
        assert any("Paste into Claude" in x for x in s["steps"]) and any("new tab" in x for x in s["steps"])


def test_one_press_copies_opens_claude_bare_and_saves_under_the_owners_account(runs):
    for c in runs["cases"]:
        s = c["sheet"]
        assert s["opened"][-1] == ["https://claude.ai/new", "_blank", "noopener,noreferrer"] and len(s["opened"]) == 2, (c["case"], s["opened"])
        assert all(o[0] == "https://claude.ai/new" for o in s["opened"])
        assert s["copied"][-1] == s["text"]
        code, doc, exp = s["saved"][-1]
        assert re.fullmatch(r"[a-f0-9]{32}", code) and ("request code " + code) in s["text"]
        assert doc["detailId"] == "definiteness" and doc["tid"] and doc["action"] == "Add a quiz" and doc["page"] == "Contracts" and doc["fmt"] == "outline"
        assert doc["tid"] not in s["text"] and "definiteness" not in s["text"]                   # the ids are in the account only
        assert s["url"] == c["url0"]                                                              # this page's own address never changed
        assert code not in s["url"]


def test_the_sheet_is_a_dialog_inside_the_window_with_big_enough_buttons(runs):
    for c in runs["cases"]:
        s = c["sheet"]
        assert s["role"] == "dialog" and s["modal"] == "true" and s["labelled"] and not s["scroll_x"]
        l, t, r, b = s["box"][:4]
        assert l >= 0 and t >= 0 and r <= s["vw"] + .5 and b <= s["vh"] + .5, (c["case"], s["box"])
        assert [x[0] for x in s["btns"]] == ["Copy again", "Open Claude", "Done"] and all(x[1] >= (43.9 if c["case"][2] < 700 else 35.9) for x in s["btns"]), s["btns"]
        assert s["btns"][1][2:] == ["A", "https://claude.ai/new", "noopener noreferrer", "_blank"]
        assert s["focus"] == "Done" and c["trap"] and c["closed"], c["case"]


def test_the_pills_star_and_the_editing_bars_star_name_the_detail_page_they_are_on(runs):
    for c in runs["cases"]:
        for k in ("star", "bar_star"):
            s = c[k]
            assert s["goal"] == "Edit the detail page “Definiteness” in the Contracts outline.", (c["case"], k, s["goal"])
            assert s["opened"][-1] == ["https://claude.ai/new", "_blank", "noopener,noreferrer"]
        assert len(c["star"]["saved"]) == 1 and len(c["bar_star"]["saved"]) == 3
        title, name, w, undo_w, inside, done_inside = c["bar"]
        assert title and name == "Ask Claude about this page" and inside and done_inside, (c["case"], c["bar"])
        assert w >= undo_w - .5, (c["case"], c["bar"])          # the bar's own button size; on a phone its hit area reaches 44pt like Undo and Redo (manual_edit.py .ee-h::before)


def test_a_cards_star_names_the_card(runs):
    assert runs["card_star"] == ["Ask Claude to change this card", "✦", "Ask Claude to change this card"]
    assert runs["card"]["goal"] == "Change the card “Definiteness” in the Contracts outline."
    assert runs["card"]["saved"][-1][1]["targetId"] == "definiteness"


def test_a_returning_users_prompt_drops_the_install_steps(runs):
    first, back = runs["cases"][0]["sheet"]["text"], runs["returning"]["text"]
    assert "install" in first and "install" not in back.lower() and "alto-get" not in back
    assert back.startswith("In Alto: Add a quiz to the detail page “Definiteness” in the Contracts outline. Call Alto's get_pending_request with my request code ")


def test_the_update_notice_shows_says_how_and_can_be_dismissed(runs):
    n = runs["note"]
    assert n and n["role"] == "status" and "Update your Alto connector" in n["text"] and "Yours is 1.9.100" in n["text"]
    assert "alto-get.web.app" in n["text"] and "restart Claude" in n["text"]
    assert [c[0] for c in n["ctl"]] == ["Get the update", "Dismiss"] and all(c[1] >= 35.9 for c in n["ctl"])      # min-height:44px in the page's own units (the text test pins it)
    assert n["ctl"][0][2:] == ["https://alto-get.web.app", "noopener noreferrer"]
    l, t, r, b = n["box"]
    assert l >= 0 and r <= n["vw"] and b <= n["vh"]
    assert runs["note_dismissed"] and runs["note_current"]
