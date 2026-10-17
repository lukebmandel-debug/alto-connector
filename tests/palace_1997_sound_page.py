"""Page half of tests/test_palace_1997_sound.py: the real palace page (QA sandbox) in WebKit and Chromium. Arms the guns, fires, checks the speaker
button, the sound calls tied to the shots, that an AudioContext was made inside the click, and that Esc closes it. Prints one RESULT json line."""
import json
import sys

sys.path.insert(0, "/Users/lukemandel/Desktop/Alto Development/_qa/kit")
from qa_kit import Sandbox  # noqa: E402

SPY = """(()=>{ window.__acs=[]; window.__calls=[]; const A=window.AudioContext||window.webkitAudioContext; if(!A) return;
  const W=function(...a){ const c=new A(...a); c.__made=performance.now(); window.__acs.push(c); return c; }; W.prototype=A.prototype;
  window.AudioContext=W; window.webkitAudioContext=W; })()"""
HOOK = """(()=>{ const S=window._palSnd; ['u','f','b','x'].forEach(k=>{ const o=S[k]; S[k]=function(){ window.__calls.push([k,Math.round(performance.now()),[...arguments].map(v=>typeof v==='number'?Math.round(v):v)]); return o.apply(this,arguments); }; }); })()"""
GEOM = """(()=>{var g=document.querySelector('.pl-boat.bb').getBoundingClientRect(); var bx=g.x+g.width/2, by=g.y+g.height/2;
 var n=[...document.querySelectorAll('#world .node .nb3d')].map(e=>[e,e.getBoundingClientRect()]).filter(q=>q[1].width>0).sort((a,b)=>Math.hypot(a[1].x-bx,a[1].y-by)-Math.hypot(b[1].x-bx,b[1].y-by))[0][1];
 return [bx,by,n.x+n.width/2,n.y+n.height*.7]})()"""
STATE = """()=>({acs:window.__acs.map(c=>c.state), n:window.__acs.length, calls:window.__calls})"""

sb = Sandbox("snd97"); res = {}
for eng in ("webkit", "chromium"):
    with sb.browser(engine=eng, wait=5000) as pg:
        pg.evaluate("localStorage.removeItem('alto-palace-sound')")
        pg.add_init_script(SPY)
        pg.reload(wait_until="domcontentloaded"); pg.wait_for_timeout(5000)
        pg.mouse.click(171, 865); pg.wait_for_timeout(2500)
        pg.evaluate(HOOK)
        r = pg.evaluate(GEOM); out = {}
        pg.mouse.click(r[0], r[1]); pg.wait_for_timeout(500)                       # arm
        out["afterArm"] = pg.evaluate(STATE)
        out["bar"] = pg.evaluate("""()=>{ const s=document.querySelector('#pal-fxbar .fx-s'); return s?{label:s.getAttribute('aria-label'), kids:[...s.parentNode.children].map(c=>c.className).join('|'), vis:getComputedStyle(s.parentNode).display}:null; }""")
        pg.mouse.click(r[2], r[3])                                                 # fire
        pg.wait_for_timeout(3500)
        out["afterFire"] = pg.evaluate(STATE)
        pg.keyboard.press("Escape"); pg.wait_for_timeout(500)
        out["afterEsc"] = pg.evaluate(STATE)
        out["armedAfterEsc"] = pg.evaluate("document.documentElement.classList.contains('fx-armed')")
        # toggle off, re-arm: no new context; calls still harmless
        pg.mouse.click(r[0], r[1]); pg.wait_for_timeout(300)
        pg.click('#pal-fxbar .fx-s'); pg.wait_for_timeout(200)
        out["muted"] = pg.evaluate("()=>({ls:localStorage.getItem('alto-palace-sound'), lab:document.querySelector('#pal-fxbar .fx-s').getAttribute('aria-label'), armed:document.documentElement.classList.contains('fx-armed'), st:window.__acs.map(c=>c.state)})")
        pg.mouse.click(r[2], r[3]); pg.wait_for_timeout(2500)
        out["afterMutedFire"] = pg.evaluate("()=>window.__acs.map(c=>c.state)")
        out["errors"] = pg.errs
        res[eng] = out
print("RESULT " + json.dumps(res))
