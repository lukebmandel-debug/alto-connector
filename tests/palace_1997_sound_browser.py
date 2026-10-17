"""Browser half of tests/test_palace_1997_sound.py (run by the QA kit's WebKit python; not collected by pytest).
Loads SOUND_JS alone in a blank page in WebKit and Chromium, renders OfflineAudioContext buffers and prints one JSON line per engine."""
import json
import sys

from playwright.sync_api import sync_playwright

from alto.build.palace_sound import SOUND_JS

PAGE = "<!doctype html><html><body><script>" + SOUND_JS + "</script></body></html>"
PROBE = """async () => {
  const S = window._palSnd, SR = 44100, out = {};
  async function render(fn, secs){
    const oc = new (window.OfflineAudioContext || window.webkitOfflineAudioContext)(1, SR*secs, SR);
    S.t(oc); fn(); const buf = await oc.startRendering(); return buf.getChannelData(0);
  }
  function stats(d){ let pk=0, nz=0, first=-1, i; for(i=0;i<d.length;i++){ const a=Math.abs(d[i]); if(a>pk) pk=a; if(a>.003){ nz++; if(first<0) first=i; } if(!(a<=1.5)) return {bad:true}; }
    let tail=0; for(i=d.length-SR*.25|0;i<d.length;i++) tail=Math.max(tail, Math.abs(d[i]));
    return {peak:pk, tail:tail, loud:nz/SR, first:first/SR}; }
  S.u(0, 0);                                            // origin of the strike distances (no AudioContext is needed offline)
  out.one   = stats(await render(() => S.f(1000), 6));
  out.volley= stats(await render(() => { S.f(1000); S.f(900); S.f(1200); }, 6));
  out.near  = stats(await render(() => S.b(300, 0), 6));
  out.far   = stats(await render(() => S.b(6000, 0), 6));
  out.scream= stats(await render(() => S.sc(1), 4));
  out.all   = stats(await render(() => { S.f(1000); S.f(900); S.f(1200); S.b(300, 0); S.b(320, 10); S.b(280, 5); }, 6));
  Object.defineProperty(document, 'hidden', {get: () => true, configurable: true});     // a hidden tab: nothing is scheduled
  out.hidden = stats(await render(() => { S.f(1000); S.b(300, 0); }, 3));
  Object.defineProperty(document, 'hidden', {get: () => false, configurable: true});
  out.hasAC = !!(window.AudioContext || window.webkitAudioContext);
  return out;
}"""

URL = "http://snd97.test/"


def load(pg, html=PAGE):
    pg.route(URL, lambda route: route.fulfill(body=html, content_type="text/html"))
    pg.goto(URL)


res = {}
with sync_playwright() as p:
    for name in ("webkit", "chromium"):
        b = p.webkit.launch() if name == "webkit" else p.chromium.launch(channel="chrome")
        pg = b.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        load(pg)
        r = pg.evaluate(PROBE); r["errors"] = errs
        # no Web Audio at all: nothing throws
        pg2 = b.new_page(); pg2.on("pageerror", lambda e: errs.append(str(e)))
        pg2.add_init_script("delete window.AudioContext; delete window.webkitAudioContext;")
        load(pg2)
        r["noAudio"] = pg2.evaluate("() => { const S=window._palSnd; S.u(1,2); S.f(900); S.b(5,5); S.x(); const d=document.createElement('div'); d.innerHTML='<button class=fx-x></button>'; S.bar(d,true); S.bar(d,false); return S.on(); }")
        # the toggle: remembered, icon + label swap
        pg3 = b.new_page(); pg3.on("pageerror", lambda e: errs.append(str(e)))
        load(pg3, PAGE + "<div id=bar><span class=fx-t></span><button class=fx-x>x</button></div>")
        r["toggle"] = pg3.evaluate("""() => { const S=window._palSnd, bar=document.getElementById('bar'); let stopped=0; bar.addEventListener('click', ()=>stopped++);
          S.bar(bar, true); const s=bar.querySelector('.fx-s'), l0=s.getAttribute('aria-label'), h0=s.innerHTML; s.click();
          const l1=s.getAttribute('aria-label'), h1=s.innerHTML, st=localStorage.getItem('alto-palace-sound'), on1=S.on(); s.click();
          return {l0,l1,iconSwapped:h0!==h1,stored:st,on1,on2:S.on(),stored2:localStorage.getItem('alto-palace-sound'),barClicks:stopped,order:[...bar.children].map(c=>c.className).join('|')}; }""")
        pg3.reload(); pg3.evaluate("localStorage.setItem('alto-palace-sound','0')"); pg3.reload()
        r["offAfterReload"] = pg3.evaluate("() => window._palSnd.on()")
        res[name] = r; b.close()
print("RESULT " + json.dumps(res))
