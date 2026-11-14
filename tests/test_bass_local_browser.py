"""The local Bass server end to end in a real headless browser (Chromium, WebKit when installed), MOCK only: no network beyond 127.0.0.1, no key.
Opens http://127.0.0.1:PORT/#bassdev=<token>: the red MOCK banner, the Bass wizard Upload -> Review -> Build against the mock model, the credit chip
(500, then a real balance), a call that does not fit is refused, and a wrong token gets nothing."""
import json
import os
import threading

import pytest

from bass_support import ROOT
from alto.bass import mock_anthropic as M

sync = pytest.importorskip("playwright.sync_api")
import importlib.util  # noqa: E402

spec = importlib.util.spec_from_file_location("bass_local_server", ROOT / "tools" / "bass_local_server.py")
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)
NOTES = "Offer and acceptance. The mirror image rule. Consideration is a bargained-for exchange. Promissory estoppel protects reliance.\n"


@pytest.mark.parametrize("engine", ["chromium", "webkit"])
def test_the_local_server_runs_the_bass_wizard_in_a_browser(tmp_path, engine, monkeypatch):
    monkeypatch.setenv("ALTO_NO_NETWORK", "1")
    monkeypatch.delenv("ALTO_LIVE_ANTHROPIC", raising=False)
    monkeypatch.setenv("ALTO_BASS_LIVE_GO", str(tmp_path / "no-go"))
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    root, token, mock = tmp_path / "root", "tok-" + "z" * 24, M.MockAnthropic()
    proxy = S.build_proxy("own", root, port, token, False, mock=mock)
    site = S.build_site(root)
    srv = S.Server(port, proxy, site, False)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    notes = tmp_path / "notes.txt"
    notes.write_text(NOTES, "utf-8")
    bad = []

    def ok(name, cond, extra=None):
        if not cond:
            bad.append((name, extra))
    try:
        with sync.sync_playwright() as pw:
            try:
                browser = getattr(pw, engine).launch()
            except Exception as e:
                pytest.skip(f"{engine} is not available: {str(e)[:80]}")
            p = browser.new_page(viewport={"width": 1280, "height": 900})
            errors, foreign = [], []
            actions = []
            p.on("request", lambda r: actions.append(json.loads(r.post_data).get("action")) if r.method == "POST" and r.post_data else None)
            p.on("pageerror", lambda e: errors.append(str(e)))
            p.on("request", lambda r: foreign.append(r.url) if not r.url.startswith(("http://127.0.0.1", "data:", "blob:")) else None)
            step = ["start"]
            try:
              p.goto(f"http://127.0.0.1:{port}/#bassdev={token}")
              p.wait_for_function("typeof window._altoBassOpen === 'function'")
              p.wait_for_timeout(500)
              ok("MOCK banner", "MOCK: no real model" in p.evaluate("document.body.innerText"))
              ok("Bass pointed at this server", p.evaluate("window._ALTO_BASS_BASE") == f"http://127.0.0.1:{port}/bass")
              ok("Bass buttons appear (the gate answered)", p.evaluate("!document.documentElement.classList.contains('alto-bass-off')"))
              p.evaluate("window._altoBassOpen('wizard')")
              p.wait_for_selector("#bass-root .bs-chip", timeout=15000)
              ok("the chip starts at 500", "500" in p.inner_text("#bass-root .bs-chip"), p.inner_text("#bass-root .bs-chip"))
              p.set_input_files("#bs-file", str(notes))
              p.wait_for_timeout(300)
              mock.use(M.Scenario("plan", [M.Step(M.Reply([M.text("Here is the plan."), M.tool_use("propose_chips", {"title": "Contracts", "acts": [{"label": "Formation"}, {"label": "Remedies"}],
                                                                                                       "entities": [{"id": "offer", "name": "Offer"}], "fields": ["Rule"], "card_estimate": 6})])), M.Step(M.say("Confirm or tweak the plan."))]))
              p.click('[data-a="next1"]')
              p.wait_for_selector('[data-a="noticeok"]', timeout=10000)                  # the first-use notice
              p.click('[data-a="noticeok"]')
              p.wait_for_selector('[data-a="consent"]', timeout=20000)                   # Review: the chips
              ok("Review reached through the mock model", p.query_selector(".bs-title") is not None)
              after_propose = p.inner_text("#bass-root .bs-chip")
              ok("the chip moved to a real balance", "500" not in after_propose or "499" in after_propose, after_propose)
              p.check('[data-a="consent"]')
              mock.use(M.build("Contracts", {"title": "Contracts"}, [], []))
              p.click('[data-a="build"]')
              done = "/Ask me to change a card|Your timeline is built|credits used/i.test(document.querySelector('#bass-root').innerText)"
              p.wait_for_function("!!document.querySelector('[data-a=go]') || " + done, timeout=30000)
              if p.query_selector('[data-a="go"]'):
                  p.click('[data-a="go"]')
                  p.wait_for_function(done, timeout=30000)
              ok("Build ran on the mock", mock.message_requests != [])
              ok("no live request ever", all(r.get("path") == "/v1/messages" or "count_tokens" in r.get("path", "") for r in mock.requests))
              # a call that does not fit is refused with no model request
              from alto.bass.beta_ledger import pc_key
              period = proxy.cfg.period_id(proxy.clock())
              proxy.store.put(pc_key(period), {"period": period, "spent_mc": proxy.cfg.ceiling_mc, "reserved_mc": 0, "res": {}, "alerted": [], "spend_log": []})
              n = len(mock.message_requests)
              out = p.evaluate("window._altoBass.call('propose', {materials: [{name:'a.txt', kind:'notes', text:'x'.repeat(40)}]})")
              ok("a hold that does not fit is refused", out.get("ok") is False and out.get("code") == "beta_credits_used" and len(mock.message_requests) == n, out)
              # a wrong token gets nothing
              p2 = browser.new_page()
              p2.goto(f"http://127.0.0.1:{port}/#bassdev=wrong-token")
              p2.wait_for_function("typeof window._altoBassOpen === 'function'")
              before = len(mock.requests)
              out2 = p2.evaluate("window._altoBassOpen('wizard'), new Promise(r => setTimeout(() => window._altoBass.call('balance').then(r), 800))")
              ok("wrong token: nothing works", out2.get("ok") is False and len(mock.requests) == before, out2)
              ok("no request loop (the page asked a sane number of times)", len(actions) < 60, {x: actions.count(x) for x in set(actions)})
              ok("no errors, nothing off-box", not errors and not foreign, (errors, foreign))
            except Exception as e:                                            # say where it stopped and what the page showed, so a queue tail is enough to debug
                try:
                    shown = p.evaluate("(document.getElementById('bass-root') || document.body).innerText").replace("\n", " | ")[:500]
                except Exception:
                    shown = "?"
                import traceback
                bad.append(("stopped with " + repr(e)[:200], [l.strip() for l in traceback.format_exc().splitlines() if "test_bass_local_browser" in l][-2:], shown, errors[:3]))
            browser.close()
    finally:
        srv.shutdown()
        srv.server_close()
    if bad:
        print("BADINFO", json.dumps(bad, default=str))
    assert not bad, bad
