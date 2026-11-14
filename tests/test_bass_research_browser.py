"""The opt-in sheet and the Conversation sharing row in a real headless browser, on the in-page simulator (no network, no key, no proxy):
Art's spec ORG/notes-art-bass-optin/SPEC-optin-step.md. Chromium, and WebKit when it is installed. ALTO_SHOTS=<dir> also writes the seven
acceptance shots (Classic light/dark, Retro; desktop 1280 and phone 390 / 360)."""
import os

import pytest

from bass_support import ROOT  # noqa: F401

PAGE = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{margin:0;font:14px -apple-system,system-ui,sans-serif;background:linear-gradient(135deg,#6c78c6,#c0788f 38%,#c9906f 62%,#5fa592);min-height:100vh}
html.dark{--surface:#14151f;--text:#ecebf5;--muted:#a3a3c2;--border:#3a3b52;--accent:#9aa6ff}html.dark body{background:#0b0c12}html.alto-retro body{background:#05070b}</style></head><body><script>__BUNDLE__</script></body></html>"""

sync = pytest.importorskip("playwright.sync_api")


@pytest.mark.parametrize("engine", ["chromium", "webkit"])
def test_the_optin_sheet_in_a_browser(tmp_path, engine, monkeypatch):
    monkeypatch.setenv("ALTO_BASS_UI", "1")
    from alto.build import bass_ui
    page = tmp_path / "page.html"
    page.write_text(PAGE.replace("__BUNDLE__", bass_ui.ASSET.replace("</script", "<\\/script")), "utf-8")
    shots = os.environ.get("ALTO_SHOTS", "")
    if shots:
        shots = os.path.join(shots, engine)
        os.makedirs(shots, exist_ok=True)
    bad = []

    def ok(name, cond, extra=None):
        if not cond:
            bad.append((name, extra))

    with sync.sync_playwright() as pw:
        try:
            browser = getattr(pw, engine).launch()
        except Exception as e:                                           # the browser is not installed here
            pytest.skip(f"{engine} is not available: {str(e)[:80]}")
        p = browser.new_page(viewport={"width": 1280, "height": 800})
        errors = []
        p.on("pageerror", lambda e: errors.append(str(e)))
        p.on("request", lambda r: errors.append("network: " + r.url) if not r.url.startswith("file:") else None)

        def go(state, w=1280, h=800, theme=None):
            p.set_viewport_size({"width": w, "height": h})
            p.goto("about:blank")
            p.goto(f"file://{page}#bass={state}")
            p.wait_for_function("window._altoBass")
            if theme:
                p.evaluate("t => document.documentElement.classList.add(t)", theme)
            p.evaluate("s => window._altoBass.dev(s, 'panel')", state)
            p.wait_for_timeout(250)

        def shot(name):
            if shots:
                p.screenshot(path=f"{shots}/{name}.png")

        def box(sel):
            return p.eval_on_selector(sel, "e => { const r = e.getBoundingClientRect(); return {x: r.x, y: r.y, w: r.width, h: r.height, r: r.right, b: r.bottom}; }")

        def sheet_open():
            return p.query_selector(".bs-share") is not None

        # 1. first-time sheet, desktop: focus on the title, no button focused, equal buttons, 44 px, centred, max 480
        go("share")
        ok("sheet opens", sheet_open())
        ok("focus starts on the title", p.evaluate("document.activeElement && document.activeElement.id") == "bs-sh")
        ok("no button preselected", p.evaluate("!document.activeElement || document.activeElement.tagName !== 'BUTTON'"))
        ok("one close x while the sheet is open", p.evaluate("getComputedStyle(document.querySelector('.bs-h [data-a=close]')).visibility") == "hidden")
        ok("paragraph 3 stays in the stamped order (one paragraph, no pinned split)", p.query_selector(".bs-promise") is None and "Bass works exactly the same if you say no. Nothing of your conversations is saved." in p.evaluate("document.querySelector('.bs-share').innerText").replace("\n", " "))
        no, yes = box('.bs-share [data-a="sharenot"].bs-sbtn'), box('.bs-share [data-a="shareyes"]')
        ok("equal size", abs(no["w"] - yes["w"]) <= 1 and abs(no["h"] - yes["h"]) <= 1, (no, yes))
        ok("44 px", no["h"] >= 44 and yes["h"] >= 44, (no, yes))
        ok("No thanks first (left)", no["x"] < yes["x"])
        inn = box(".bs-share .bs-sheet-in")
        ok("max 480", inn["w"] <= 481, inn)
        ok("nothing selected in the DOM", p.eval_on_selector_all(".bs-share input, .bs-share select, .bs-share [checked], .bs-share [aria-checked='true']", "a => a.length") == 0)
        shot("1-first-sheet-desktop")
        for _ in range(4):                                                    # Tab to No thanks (the x comes first)
            if p.evaluate("document.activeElement && document.activeElement.dataset.a === 'sharenot' && document.activeElement.classList.contains('bs-sbtn')"):
                break
            p.keyboard.press("Tab")
        if engine == "chromium":                                              # Safari/WebKit does not Tab to buttons by default (a system setting), so the ring is checked where Tab works
            ok("keyboard focus reaches No thanks with a 3 px ring", p.evaluate("(() => { const e = document.activeElement; return e && e.classList.contains('bs-sbtn') && parseFloat(getComputedStyle(e).outlineWidth) >= 3; })()"))
        shot("6-focus-first-button")
        # 2. Esc = No thanks: sheet gone, nothing on, toast
        p.keyboard.press("Escape")
        p.wait_for_timeout(200)
        ok("Esc closes the sheet as No thanks", not sheet_open() and p.evaluate("window._altoBass.state.share.on") is False)
        ok("toast says off", "Sharing is off." in p.evaluate("document.body.innerText"))
        shot("2-after-no-thanks")
        # 3. the x and a click outside also mean No thanks
        go("share")
        p.click('.bs-share [data-a="sharenot"].bs-shx')
        p.wait_for_timeout(150)
        ok("x closes as No thanks", not sheet_open())
        go("share")
        p.click('.bs-share', position={'x': 6, 'y': 6})                                    # the sheet's backdrop, outside the card
        p.wait_for_timeout(150)
        ok("click outside closes as No thanks", not sheet_open() and p.evaluate("window._altoBass.state.share.on") is False)
        # 4. Share: on, toast, row says On
        go("share")
        p.click('.bs-share [data-a="shareyes"]')
        p.wait_for_timeout(500)
        ok("Share turns it on", not sheet_open() and p.evaluate("window._altoBass.state.share.on") is True)
        ok("toast says on", "Sharing is on. You can turn it off in the Bass menu." in p.evaluate("document.body.innerText"))
        shot("3-after-share")
        # 5. the row: Off / On, Turn off withdraws at once, Turn on shows the same sheet
        go("share-on")
        t = p.evaluate("document.getElementById('bass-root').innerText")
        ok("row On", "Conversation sharing: On" in t and "Turn off" in t and "stops saving new conversations straight away; saved ones are deleted within 7 days" in t, t[-200:])
        shot("4-row-on")
        p.click('[data-a="sharetoggle"]')
        p.wait_for_timeout(500)
        ok("Turn off withdraws", p.evaluate("window._altoBass.state.share.on") is False and "Conversation sharing: Off" in p.evaluate("document.getElementById('bass-root').innerText"))
        shot("4-row-off")
        p.click('[data-a="sharetoggle"]')
        p.wait_for_timeout(250)
        ok("Turn on shows the sheet again, nothing on yet", sheet_open() and p.evaluate("window._altoBass.state.share.on") is False)
        shot("5-sheet-from-turn-on")
        # 6. dark and Retro
        for theme, nm in (("dark", "dark"), ("alto-retro", "retro")):
            go("share", theme=theme)
            ok(f"{nm}: sheet opens", sheet_open())
            ok(f"{nm}: equal buttons", abs(box('.bs-share [data-a="sharenot"].bs-sbtn')["h"] - box('.bs-share [data-a="shareyes"]')["h"]) <= 1)
            shot(f"1-first-sheet-{nm}")
        # 7. phone 390 and 360: a bottom sheet, stacked full-width buttons, 16 px gutters, no sideways scroll
        for w, hh in ((390, 760), (360, 640)):
            go("share", w=w, h=hh)
            no, yes = box('.bs-share [data-a="sharenot"].bs-sbtn'), box('.bs-share [data-a="shareyes"]')
            ok(f"{w}: stacked", yes["y"] > no["y"] and abs(no["w"] - yes["w"]) <= 1, (no, yes))
            ok(f"{w}: 16 px gutters", no["x"] >= 16 - 0.5 and w - no["r"] >= 16 - 0.5, (no, w))
            ok(f"{w}: 44 px", no["h"] >= 44 and yes["h"] >= 44)
            ok(f"{w}: sits at the bottom", hh - yes["b"] >= 0 and hh - yes["b"] <= 60, yes)
            ttl = box(".bs-share .bs-sht")
            ok(f"{w}: the title is reachable (not clipped above the sheet)", ttl["y"] >= 0, ttl)
            ok(f"{w}: no sideways scroll", p.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"))
            shot(f"7-phone-{w}")
        ok("no page errors, no network", not errors, errors)
        browser.close()
    assert not bad, bad
