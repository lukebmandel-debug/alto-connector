import os,sys,contextlib; sys.path.insert(0,"/Users/lukemandel/Desktop/Alto Development/_qa/kit")
from qa_kit import Sandbox, FAKE
OUT=os.environ.get("RIDE_OUT","/tmp")
FAKE_ROAM="""(function(){ var a=false, calls=[]; var r=window._palRide.roam; window.__rc=calls;
 r.enter=function(x,y,h,o){ calls.push(['enter',x,y,h,o&&o.from]); a=true; var d=document.getElementById('fake-ride')||document.createElement('div'); d.id='fake-ride'; d.style.cssText='position:fixed;inset:0;z-index:399;background:linear-gradient(#7fa6d6,#c9d6df 55%,#5b5f66 55%);'; document.body.appendChild(d); return true; };
 r.exit=function(stay){ calls.push(['exit',!!stay]); a=false; var d=document.getElementById('fake-ride'); if(d) d.remove(); };
 r.active=function(){ return a; }; })()"""
@contextlib.contextmanager
def page(eng='webkit', dpr=1, dark=False, reduced=False, wait=4000, sb="ride95ui"):
    from playwright.sync_api import sync_playwright
    s=Sandbox(sb)
    with s.serve() as url, sync_playwright() as p:
        b=p.webkit.launch() if eng=='webkit' else p.chromium.launch(channel="chrome")
        ctx=b.new_context(viewport={"width":1400,"height":900}, device_scale_factor=dpr, reduced_motion='reduce' if reduced else 'no-preference', color_scheme='dark' if dark else 'light')
        ctx.add_init_script(FAKE); pg=ctx.new_page(); pg.errs=[]; pg.on("pageerror", lambda e: pg.errs.append(str(e)))
        pg.on("console", lambda m: pg.errs.append('console:'+m.text) if m.type=='error' else None)
        pg.goto(url, wait_until="domcontentloaded", timeout=120000); pg.wait_for_timeout(wait)
        pg.evaluate("d=>document.documentElement.classList.toggle('dark',d)", dark); pg.wait_for_timeout(600)
        try: yield pg
        finally: b.close()
