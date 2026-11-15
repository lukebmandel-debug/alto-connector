"""Poison test for the hosted Bass bundle (STAMP-hosted row 3; Board B-1114-043000). SDK-free: a fake altoext (stdlib http.server) answers
EVERY action with HTML / JS / attribute-breaking / javascript: payloads in EVERY string and number field, in every status the UI branches on,
and the REAL pinned bundle (bass_hosted_ext.bundle()) opens every view and presses every button it draws. Headless WebKit, the site's own CSP
(script-src keeps 'unsafe-inline', the condition the stamp found the hole under). Nothing may run, and no element or attribute may be
injected. A control run with the bundle's three layers switched off proves the harness bites. No network, no key."""
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

pytest.importorskip("playwright.sync_api")

P = ['"><img src=x onerror=__hit()>', "'><svg onload=__hit()>", "<script>__hit()</script>", "javascript:__hit()",
     '" onmouseover="__hit()" x="', "' autofocus onfocus='__hit()' x='", "</textarea><img src=x onerror=__hit()>",
     '<a href="javascript:__hit()">x</a>', "1<img src=x onerror=__hit()>", "`><img src=x onerror=__hit()>", "x onmouseover=__hit() y"]
STATUSES = ["ok", "estimate", "error", "refused", "capped", "paused", "busy", "no_credits", "question", "off_topic", "stopped", P[0]]
CODES = [P[1], "promo_ended", "bass_off", "beta_credits_used", "terms_required", "drive_off", "beta_tester_daily", "upstream"]


def poisoned(i, status, code, numbers_too):
    c = iter(range(10_000))

    def s():
        return P[(i + next(c)) % len(P)]

    def n(v):
        return s() if numbers_too else v
    f = lambda k: {"id": s(), "name": s(), "type": s(), "bytes": n(2048), "added": s(), "use": True, "readable": True, "scope": s(),
                   "days_left": n(3), "deleted": True, "url": "javascript:__hit()", "href": "javascript:__hit()", "kind": s()}
    sc = lambda kind: {"id": s(), "kind": kind, "name": s(), "class_id": s(), "class_docs": True}
    return {"ok": status == "ok", "status": status, "code": code, "message": s(), "label": s(), "have_label": s(), "notice": s(),
            "estimate_credits": n(12), "short_by": n(4), "credits": n(42) if numbers_too else {"spent": 3, "left": 40}, "ack": s(),
            "cards": {"done": n(2), "total": n(5)}, "cards_in": n(5), "cards_out": n(6), "cards_done": n(1), "cards_total": n(5),
            "research": {"available": True, "on": False, "version": s(), "needs_optin": True, "text": s()},
            "chips": {"title": s(), "acts": [{"label": s()}, {"label": s()}], "entities": [{"id": s(), "name": s()}], "fields": [s(), s()],
                      "card_estimate": n(6)},
            "events": [{"event": "progress", "stage": n(2), "done": n(1), "total": n(4), "cards_done": n(1), "cards_total": n(4), "text": s(),
                        "message": s()}, {"event": "text", "text": s()}],
            "timeline_id": s(), "work_saved": True, "action_id": s(), "reply": s(), "text": s(), "question": s(), "options": [s(), s()],
            "scope": sc("class"), "scopes": [sc("class"), sc("outline"), sc("group"), sc("timeline")], "files": [f(0), f(1)],
            "deleted": [f(2)], "caps": {"files": n(2), "files_max": n(20), "bytes": n(10), "bytes_max": n(99)}, "chars": n(5),
            "chars_max": n(60000), "over": False, "available": True, "url": "javascript:__hit()", "link": "javascript:__hit()",
            "client_id": s(), "api_key": s(), "app_id": s(), "label_short": s(), "retryable": True, "beta": True}


PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>poison</title><script>
window.__hits=0; window.__hit=function(){ window.__hits++; }; window.__bad=[]; window.open=function(){ return null; };
window.AltoCloud={user:{uid:'u1',getIdToken:function(){ return Promise.resolve('tok'); }},known:true};
window.__altoExtUrl=location.origin+'/api';
addEventListener('load',function(){ new MutationObserver(function(ms){ ms.forEach(function(m){
  var chk=function(n){ if(n.nodeType!==1) return; var t=String(n.localName).toLowerCase();
    if(/^(img|iframe|script|object|embed|image|use|animate|set|foreignobject|base|meta|link|form|frame|video|audio|source|math)$/.test(t)) __bad.push('tag:'+t);
    for(var i=0;i<n.attributes.length;i++){ var a=n.attributes[i]; if(/^on/i.test(a.name)||/^(srcdoc|formaction|action|autofocus|xlink:href)$/i.test(a.name)) __bad.push('attr:'+a.name);
      if(/^(href|src)$/i.test(a.name)&&!/^(https?:\\/\\/|\\/(?![\\/\\\\])|#)/i.test(String(a.value).replace(/[\\u0000-\\u0020]/g,''))) __bad.push('url:'+a.value); }
    for(var c=n.firstChild;c;c=c.nextSibling) chk(c); };
  m.addedNodes.forEach(chk);
  if(m.type==='attributes'&&m.target.nodeType===1){ var nm=m.attributeName||''; if(/^on/i.test(nm)) __bad.push('attr:'+nm); } }); })
  .observe(document,{childList:true,subtree:true,attributes:true}); });
</script></head><body><div id="home">home</div><script src="/bundle.js"></script></body></html>"""

DRIVE = r"""
async function(){
  const sleep=t=>new Promise(r=>setTimeout(r,t)), B=window._altoBass, seen={text:0, views:0};
  const look=()=>{ const r=document.getElementById('bass-root'); if(r){ seen.views++; if(r.textContent.indexOf('__hit()')>=0) seen.text++; } };
  const press=async(n)=>{ for(let k=0;k<n;k++){ const bs=[...document.querySelectorAll('#bass-root [data-a]')].filter(b=>b.getAttribute('data-a')!=='close');
      if(!bs.length) break; const b=bs[k%bs.length]; try{ if(b.tagName==='SELECT'){ b.selectedIndex=b.options.length-1; b.dispatchEvent(new Event('change',{bubbles:true})); } else b.click(); }catch(e){}
      await sleep(60); look(); } };
  for(const m of ['wizard','panel','docs','embed','wizard']){ try{ B.open(m); }catch(e){} await sleep(250); look(); await press(18); }
  try{ B.open('wizard'); }catch(e){} await sleep(200);
  const ta=document.querySelector('#bass-root textarea'); if(ta){ ta.value='notes'; ta.dispatchEvent(new Event('input',{bubbles:true})); }
  for(const f of ['propose','build']) { try{ await B[f](); }catch(e){} await sleep(200); look(); await press(10); }
  for(const a of ['balance','estimate','propose','build','edit','chat','convert','make_study_plan','docs','drive','research','stop']){
    try{ await B.call(a,{op:'list'}, ()=>{}); }catch(e){} try{ B.open(a==='docs'?'docs':'panel'); }catch(e){} await sleep(120); look(); await press(6); }
  try{ B.openDocs('docs'); }catch(e){} await sleep(250); look(); await press(30);
  try{ await B.convert({tid:'t1'},'outline',{place:document.body,status:t=>{},confirm:()=>Promise.resolve(true),close:()=>{}}); }catch(e){}
  try{ B.open('panel'); }catch(e){} await sleep(200); const say=document.querySelector('#bass-root .bs-say');
  if(say){ say.value='hi'; const s=document.querySelector('#bass-root [data-a="send"]'); if(s) s.click(); } await sleep(400); look(); await press(10);
  return {hits: window.__hits, bad: window.__bad.slice(0,20), nbad: window.__bad.length, seen: seen};
}"""


class _Server:
    def __init__(self, bundle):
        from alto import publish_static as ps
        self.round = {"i": 0, "status": "ok", "code": CODES[0], "numbers": False}
        self.answers = 0
        csp = ps._csp("'none'")
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, ctype, body, extra=()):
                b = body.encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(b)))
                for k, v in extra:
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(b)

            def do_GET(self):
                if self.path.startswith("/bundle.js"):
                    return self._send(200, "text/javascript; charset=utf-8", bundle)
                return self._send(200, "text/html; charset=utf-8", PAGE, [("Content-Security-Policy", csp)])

            def do_POST(self):
                n = int(self.headers.get("Content-Length") or 0)
                self.rfile.read(n)
                r = outer.round
                outer.answers += 1
                r["i"] += 1
                return self._send(200, "application/json", json.dumps(poisoned(r["i"], r["status"], r["code"], r["numbers"])))

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = "http://127.0.0.1:%d/" % self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()


def _run(bundle, rounds):
    from playwright.sync_api import sync_playwright
    srv = _Server(bundle)
    out = []
    try:
        with sync_playwright() as pw:
            if not os.path.exists(pw.webkit.executable_path):
                pytest.skip("Playwright's WebKit is not installed here (set PLAYWRIGHT_BROWSERS_PATH); the stamp runs it")
            br = pw.webkit.launch()
            try:
                for status, code, numbers in rounds:
                    srv.round.update(status=status, code=code, numbers=numbers)
                    ctx = br.new_context()
                    pg = ctx.new_page()
                    dialogs = []
                    pg.on("dialog", lambda d: (dialogs.append(d.message), d.dismiss()))
                    pg.goto(srv.url)
                    pg.wait_for_function("!!window._altoBass", timeout=10000)
                    r = pg.evaluate(DRIVE)
                    r["dialogs"] = len(dialogs)
                    r["round"] = (status, code, numbers)
                    out.append(r)
                    ctx.close()
            finally:
                br.close()
    finally:
        srv.close()
    return out, srv.answers


ROUNDS = [(s, CODES[i % len(CODES)], i % 2 == 1) for i, s in enumerate(STATUSES)] + [("ok", c, True) for c in CODES]


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("ALTO_NO_NETWORK", "1")


def test_poisoned_answers_never_run_and_inject_nothing():
    from alto.build import bass_hosted_ext
    res, answers = _run(bass_hosted_ext.bundle(), ROUNDS)
    assert answers > 100                                                          # the bundle really asked, many times
    assert sum(r["seen"]["text"] for r in res) > 0                                # and drew poisoned values (as text)
    for r in res:
        assert r["hits"] == 0 and r["nbad"] == 0 and r["dialogs"] == 0, r


def test_the_poison_harness_bites_with_the_defences_off():
    """Control: the same harness against the bundle with its three layers removed (tame, clean, and the esc() on the Documents ids, as in
    e391fc69) sees injected code run. So a zero above means the defences held, not that the harness saw nothing."""
    from alto.build import bass_hosted_ext
    js = bass_hosted_ext.bundle()
    off = (js.replace("function tame(v,d){", "function tame(v,d){ return v;", 1).replace("function clean(n){", "function clean(n){ return;", 1)
             .replace("data-v=\"'+esc(f.id)+'\"", "data-v=\"'+f.id+'\""))
    assert off != js
    res, _ = _run(off, [("ok", CODES[0], False), ("ok", CODES[0], True)])
    assert sum(r["hits"] + r["nbad"] for r in res) > 0
