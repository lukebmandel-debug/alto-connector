"""Browser half of the fleet's sound tests (run by the QA kit's WebKit python; not collected by pytest): SOUND_JS alone in a blank page in WebKit and Chromium, the 1.9.99 sounds rendered
on an OfflineAudioContext (jet flyby, bomb whistle, missile launches, sonar ping, torpedo motor). Prints one RESULT json line."""
import json

from playwright.sync_api import sync_playwright

from alto.build.palace_sound import SOUND_JS

PAGE = "<!doctype html><html><body><script>" + SOUND_JS + "</script></body></html>"
PROBE = """async () => {
  const S = window._palSnd, SR = 44100, out = {};
  async function render(fn, secs){ const oc = new (window.OfflineAudioContext || window.webkitOfflineAudioContext)(1, SR*secs, SR); S.t(oc); fn(); const buf = await oc.startRendering(); return buf.getChannelData(0); }
  function stats(d){ let pk=0, nz=0, first=-1, i; for(i=0;i<d.length;i++){ const a=Math.abs(d[i]); if(a>pk) pk=a; if(a>.003){ nz++; if(first<0) first=i; } if(!(a<=1.5)) return {bad:true}; }
    let tail=0; for(i=d.length-SR*.25|0;i<d.length;i++) tail=Math.max(tail, Math.abs(d[i])); return {peak:pk, tail:tail, loud:nz/SR, first:first/SR}; }
  S.u(0, 0);
  out.jet     = stats(await render(() => S.jet(0, 3.4), 8));
  out.jets    = stats(await render(() => { S.jet(0, 3.4); S.jet(.43, 3.4); S.jet(.86, 3.4); S.jet(1.29, 3.4); }, 9));
  out.whistle = stats(await render(() => S.whistle(840), 3));
  out.rocket  = stats(await render(() => S.rocket(900), 4));
  out.ping    = stats(await render(() => S.ping(), 4));
  out.torpedo = stats(await render(() => S.torpedo(3), 6));
  out.run     = stats(await render(() => { S.ping(); S.torpedo(3); S.b(300, 0); }, 8));
  Object.defineProperty(document, 'hidden', {get: () => true, configurable: true});
  out.hidden  = stats(await render(() => { S.jet(0, 3); S.whistle(800); S.rocket(900); S.ping(); S.torpedo(2); }, 3));
  return out;
}"""
res = {}
with sync_playwright() as p:
    for name in ("webkit", "chromium"):
        b = p.webkit.launch() if name == "webkit" else p.chromium.launch(channel="chrome")
        pg = b.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.route("http://fleet99.test/", lambda route: route.fulfill(body=PAGE, content_type="text/html")); pg.goto("http://fleet99.test/")
        r = pg.evaluate(PROBE); r["errors"] = errs
        pg2 = b.new_page(); pg2.on("pageerror", lambda e: errs.append(str(e)))
        pg2.add_init_script("delete window.AudioContext; delete window.webkitAudioContext;")
        pg2.route("http://fleet99.test/", lambda route: route.fulfill(body=PAGE, content_type="text/html")); pg2.goto("http://fleet99.test/")
        r["noAudio"] = pg2.evaluate("() => { const S=window._palSnd; S.u(1,2); S.jet(0,3); S.whistle(800); S.rocket(900); S.ping(); S.torpedo(2); S.x(); return true; }")
        r["errors"] = errs
        res[name] = r; b.close()
print("RESULT " + json.dumps(res))
