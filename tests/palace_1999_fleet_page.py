"""Page half of tests/test_palace_1999_fleet.py: the real palace page of the fleet fixture sandbox (QA kit: _qa/fleet99/mkfix.py = the civ-pro palace with a carrier, a destroyer,
a submarine, a shore battery and an air base added) in WebKit and Chromium. Arms every toy, attacks a node building, checks what was drawn, which sounds were asked for, that the
building was brought down (palace_construct) with its crowd (palace_panic), and that Esc stands down. Prints one RESULT json line."""
import json
import sys

sys.path.insert(0, "/Users/lukemandel/Desktop/Alto Development/_qa/kit")
from qa_kit import Sandbox  # noqa: E402

SPY = """(()=>{ window.__calls=[]; const S=window._palSnd; ['u','f','b','jet','whistle','rocket','ping','torpedo'].forEach(k=>{ const o=S[k]; S[k]=function(){ window.__calls.push(k); return o.apply(this,arguments); }; }); })()"""
CLICK = """(a)=>{ const t=a[0]==='toy' ? document.querySelector('#palace-svg .wp[data-name="'+a[1]+'"]') : document.querySelector(a[1]); const s=document.querySelector('#palace-svg').getBoundingClientRect();
  t.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,clientX:s.x+s.width/2,clientY:s.y+s.height/2,view:window})); }"""
NODE = """(i)=>{ const n=[...document.querySelectorAll('#world .node[id^="node-"]')].filter(n=>n._nbS&&!n.classList.contains('pal-floor')&&n.querySelector(':scope > .nb3d'))[i]; return '#'+n.id+' > .nb3d'; }"""
STATE = """()=>({armed:document.documentElement.classList.contains('fx-armed'), bar:(document.querySelector('#pal-fxbar .fx-t')||{}).textContent, glow:[...document.querySelectorAll('.wp.armed')].map(g=>g.getAttribute('data-name')),
  con:window._palCon.active(), panic:window._palPanic.active(), calls:window.__calls.slice(), flights:window._palFleet.active(), errs:[]})"""
TOYS = """()=>[...document.querySelectorAll('#palace-svg .wp')].map(g=>({n:g.getAttribute('data-name'), w:g._w, kind:g.getAttribute('data-kind'), cls:g.getAttribute('class'), box:(()=>{const r=g.getBoundingClientRect(); return [Math.round(r.width),Math.round(r.height)]})()}))"""

sb = Sandbox("fleet99x"); res = {}
for eng in ("webkit", "chromium"):
    with sb.browser(engine=eng, device="desktop", wait=6000) as pg:
        out = {"toys": pg.evaluate(TOYS), "loaded": pg.evaluate("typeof window._palFleet"), "other": pg.evaluate("[...document.querySelectorAll('.pl-boat:not(.wp)')].map(g=>g.getAttribute('data-name'))"), "attacks": {}}
        pg.evaluate(SPY)
        for i, t in enumerate(out["toys"]):
            node = pg.evaluate(NODE, i)
            pg.evaluate("window.__calls.length=0; window._palFleet.last(0)")
            pg.evaluate(CLICK, ["toy", t["n"]]); pg.wait_for_timeout(250)
            armed = pg.evaluate(STATE)
            pg.evaluate("window._palFleet.last(0)")
            pg.evaluate(CLICK, ["node", node])
            pg.wait_for_timeout(9500)
            after = pg.evaluate(STATE)
            pg.keyboard.press("Escape"); pg.wait_for_timeout(300)
            down = pg.evaluate(STATE)
            out["attacks"][t["w"] + ":" + t["n"]] = {"armed": armed, "after": after, "down": down}
        out["errors"] = pg.errs
        out["console"] = [c for c in pg.cons if "404" not in c]
        res[eng] = out
print("RESULT " + json.dumps(res))
