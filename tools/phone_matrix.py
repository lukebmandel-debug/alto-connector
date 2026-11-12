#!/usr/bin/env python3
"""Phone shot matrix (chunk 1 of ORG/phone-ui-audit-1111.md, section 5): every format x style x phone size in headless WebKit, measured.

    ~/.local/share/alto/pw12/bin/python tools/phone_matrix.py <outdir> [key-substring,...] [--shots]

Writes <outdir>/metrics.json (one entry per cell, key "<page>-<style>-<size>") and, with --shots, <outdir>/shots/<key>.png.
Builds every page from the repo's own samples (no cloud, no network, no audio) and serves them from one 127.0.0.1 server together with the hosted
assets (palace_assets.find). Derived from ORG/sim-main/audit1111-webkit/shoot.py. WebKit emulation has no Safari bars and no safe areas, so only
layout faults are visible here (see tests/phone_matrix_known.json for what each row id needs)."""
import asyncio
import copy
import http.server
import json
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

PW12 = Path.home() / ".local/share/alto/pw12/lib/python3.12/site-packages"   # the Playwright venv; the repo venv has the engine deps but no Playwright


def _playwright():
    try:
        import playwright.async_api as m
    except ImportError:
        sys.path.append(str(PW12))
        import playwright.async_api as m
    return m


UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1")
STYLES = ["classic", "retro", "holo"]
# b874 / b812: a phone on its side with Safari's bars up, the page's visible box (chunk 5: 250 pt tall; the real box is 874 x 292 on the 402 pt phone, 250 is the least it leaves); only the pages
# the landscape rows measure (BONLY) are shot there
VPS = [("p402", 402, 874), ("l874", 874, 402), ("p375", 375, 812), ("l812", 812, 375), ("b874", 874, 250), ("b812", 812, 250)]
BONLY = ("tl-card", "ol-card", "ol-whole", "atlas", "home")
# (key, page file, query) -- the query is added to by ?style=
PAGES = [("tl-card", "timeline", "view=card"), ("tl-whole", "timeline", "view=whole"), ("ol-card", "outline-long", "view=card"),
         ("ol-whole", "outline-long", "view=whole"), ("lanes", "lanes", ""), ("system", "system", ""), ("home", "home", ""),
         ("atlas", "atlas", ""), ("city", "city", ""), ("blueprint", "blueprint", "")]
LONG = ["UNIT ONE — PERSONAL JURISDICTION, SERVICE OF PROCESS AND NOTICE UNDER RULE 4 AND THE LONG-ARM STATUTES",
        "UNIT TWO — THE DUTY OF REASONABLE CARE, BREACH, ACTUAL CAUSE, PROXIMATE CAUSE AND THE LIMITS OF LIABILITY IN NEGLIGENCE",
        "UNIT THREE — Remedies and the extraordinarily long list of every equitable and legal measure a court may award, restitution, reformation, rescission, specific performance, injunctions, declaratory relief and the rest"]

# loads the Retro / Holo hosted layer and seeds the page's own style key (one loader for every page; same as sim-fit-build.py)
LOADER = """<script>(function(){var s=(location.search.match(/[?&]style=(\\w+)/)||[])[1];if(!s)return;
function go(){var w=window;try{if(s==='retro'&&w._altoRetro)w._altoRetro.on();if(s==='holo'&&w._altoHolo)w._altoHolo.on();}catch(e){}}
function load(f,cb){var x=document.createElement('script');x.src=f;x.onload=cb;document.head.appendChild(x);}
try{var k=window._altoBg&&_altoBg.key; if(k){var sk=/-bg$/.test(k)?k.replace(/-bg$/,'-style'):k+'-style'; if(localStorage.getItem(sk)!==s) localStorage.setItem(sk,s);}}catch(e){}
var man=%s;load(man[s],function(){setTimeout(go,1500);});})();</script>"""

# sim1111g S8: the loader above seeds the key at the end of <body>, after Safari's first layout, so a first load (and every new Private tab) showed the
# Classic peach behind Safari's landscape toolbar on a Holo page. A reader's key is stored before the page loads; this puts the harness in the same state.
SEED = """<script>(function(){var s=(location.search.match(/[?&]style=(\\w+)/)||[])[1],k=window._altoBg&&_altoBg.key;if(!s||!k)return;
try{var sk=/-bg$/.test(k)?k.replace(/-bg$/,'-style'):k+'-style';if(localStorage.getItem(sk)!==s)localStorage.setItem(sk,s);}catch(e){}})();</script>"""


def build_pages():
    """-> ({page file: html}, {blueprint plan name: text}, {bart image name: bytes}). Pure builds, no network."""
    from alto.build import building_schema as bs, palace_assets
    from alto.build.builder import build_timeline, load_brief
    from alto.build.pages import build_home
    from alto import buildings
    from alto.buildings import pma_art

    def sample(name, **over):
        d = json.loads((ROOT / "samples" / f"{name}_brief.json").read_text(encoding="utf-8"))
        d["brief"].update(over)
        return d

    def html_of(d):
        b, n, c = load_brief(copy.deepcopy(d))
        return build_timeline(b, n, c)[0]

    man = {f: "/%s/%s" % (f, n) for f, n, _t in palace_assets.assets() if f in ("retro", "holo")}
    pages = {}

    def put(name, html):
        i = html.rfind("</body>")
        html = html[:i] + LOADER % json.dumps(man) + html[i:] if i >= 0 and man else html
        j = html.find('<script id="alto-shell-js">')          # the style key is there before the shell's <head> script reads it, as it is for a reader who chose the look
        pages[name] = html[:j] + SEED + html[j:] if j >= 0 else html

    put("timeline", html_of(sample("contracts")))
    d = sample("outline")
    for a, t in zip(d["brief"]["acts"], LONG):
        a["label"] = t
        a["short"] = t.title()
    put("outline-long", html_of(d))
    put("lanes", html_of(sample("lanes")))
    put("home", build_home([{"name": "Law school %d" % p, "pid": "p%d" % p, "courses": [
        {"title": "Civil Procedure %d.%d" % (p, c), "href": "outline.html", "sub": "%d units" % (c + 3), "courseId": "c%d%d" % (p, c), "units": []}
        for c in range(8)]} for p in range(12)]))
    d = sample("contracts", layout="solar", hub_look="stars")
    d["brief"]["mode"] = "outline"
    put("system", html_of(d))
    from test_world_palace import loaded as atlas_loaded
    from alto.build import world_plan as wp
    # Peru, the USA and Brazil: the Americas, as in the audit's atlas-world page (labels near the left edge, a wide map)
    put("atlas", build_timeline(*atlas_loaded(world={"places": {"erie": wp.resolve("Peru"), "pj": wp.resolve("United States"), "hanna": wp.resolve("Brazil")}}, palace_view="world"))[0])
    from test_palace_chrome import bundle
    put("city", html_of(bundle()))
    # Blueprint: the PMA plan, a walk-in at the first level (as tests/test_building_pma_render.py builds it)
    plan = buildings.load("pma")
    acts = [{"label": f"Part {i}", "color": c} for i, c in enumerate(("#7c5cff", "#e0813f", "#2f9e6b", "#d4509a"))]
    nodes = [{"id": f"n{i}", "act": i * 4 // 30, "title": f"Concept {i + 1}", "tag": "", "desc": "d"} for i in range(30)]
    b = {"title": "Walk", "timeline_id": "walk", "mode": "palace", "palace_view": "building", "columns": 5, "node_noun": "Room",
         "period_noun": "Wing", "acts": acts, "building": {"plan_z": bs.pack(plan), "plan_h": bs.plan_hash(plan), "mode": "room", "assign": {}}}
    put("blueprint", build_timeline(*load_brief({"brief": b, "nodes": nodes}))[0])
    pname, ptext = bs.hosted_json(plan)
    return pages, {pname: ptext}, dict(pma_art.files())


def serve(pages, plans, art):
    from alto.build import palace_assets

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            path = self.path.split("?")[0]
            name = path.strip("/")
            name = name[:-5] if name.endswith(".html") else name
            if name in pages:
                hit = ("text/html; charset=utf-8", pages[name].encode("utf-8"))
            elif path == "/alto-cloud.js":
                hit = ("text/javascript", b"")
            elif path.startswith("/bart/") and path[6:] in art:
                hit = ("image/jpeg", art[path[6:]])
            else:
                f = palace_assets.find(path, building_plans=plans)
                hit = (f[0], f[1].encode("utf-8")) if f else None
            body = hit[1] if hit else b"no"
            self.send_response(200 if hit else 404)
            self.send_header("Content-Type", hit[0] if hit else "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s


M = r"""() => {
 const vw=innerWidth, vh=innerHeight, out={vw,vh,sy:Math.round(scrollY),cls:document.documentElement.className.slice(0,200)};
 out.docW=document.documentElement.scrollWidth; out.bodyH=Math.round(document.body.getBoundingClientRect().height);
 const vis=e=>{if(e.closest('#summary-wrap:not(.open)')) return false; const c=getComputedStyle(e); if(c.display==='none'||c.visibility==='hidden'||+c.opacity<0.05) return false; const r=e.getBoundingClientRect(); return r.width>2&&r.height>2&&r.right>0&&r.bottom>0&&r.left<vw&&r.top<vh;};
 const nm=e=>(e.id?'#'+e.id:e.tagName.toLowerCase()+'.'+String(e.className&&e.className.baseVal!==undefined?e.className.baseVal:e.className).split(' ').slice(0,2).join('.'));
 const R=e=>{const r=e.getBoundingClientRect();return [Math.round(r.left),Math.round(r.top),Math.round(r.right),Math.round(r.bottom)]};
 const all=[...document.querySelectorAll('body *')];
 out.cut=[]; out.small=[]; out.clip=[]; out.spill=[]; out.kbd=[];
 const ctl=[];
 for(const e of all){ if(!vis(e)) continue; const c=getComputedStyle(e); const r=e.getBoundingClientRect();
   const isCtl=e.matches('button,[role=button],a[href],input,select,.drawer-btn,[onclick]');
   if(isCtl && !e.closest('#world') && !e.closest('svg')){ ctl.push(e);
     if((r.left<-1||r.right>vw+1||r.top<-1||r.bottom>vh+1) && out.cut.length<10) out.cut.push([nm(e),R(e)]);
     if((r.width<32||r.height<32) && out.small.length<10) out.small.push([nm(e),Math.round(r.width)+'x'+Math.round(r.height)]);
     if(/^(esc|c)$/i.test((e.textContent||'').trim()) && out.kbd.length<4) out.kbd.push([nm(e),e.textContent.trim()]);
   }
   const own=[...e.childNodes].some(n=>n.nodeType===3&&n.textContent.trim().length>2);
   if(own){ if(e.scrollWidth>e.clientWidth+2 && e.clientWidth>0 && c.display!=='inline'){ (c.overflowX==='visible'?out.spill:out.clip).length<8 && (c.overflowX==='visible'?out.spill:out.clip).push([nm(e),e.textContent.trim().slice(0,28),e.clientWidth,e.scrollWidth]); }
     else if(e.scrollHeight>e.clientHeight+3 && e.clientHeight>0 && c.display!=='inline' && c.overflowY==='visible' && out.spill.length<8) out.spill.push([nm(e),e.textContent.trim().slice(0,28),'h',e.clientHeight,e.scrollHeight]); }
 }
 out.nctl=ctl.length; out.overlap=[];
 for(let i=0;i<ctl.length;i++)for(let j=i+1;j<ctl.length;j++){const a=ctl[i],b=ctl[j]; if(a.contains(b)||b.contains(a)) continue; const x=a.getBoundingClientRect(),y=b.getBoundingClientRect();
   const w=Math.min(x.right,y.right)-Math.max(x.left,y.left),h=Math.min(x.bottom,y.bottom)-Math.max(x.top,y.top); if(w>4&&h>4&&out.overlap.length<8) out.overlap.push([nm(a),nm(b),Math.round(w)+'x'+Math.round(h)]);}
 out.cards=[...document.querySelectorAll('.node-card,.home-card,.course-card,.tile')].filter(vis).slice(0,40).map(R).filter(r=>r[0]<8||r[2]>vw-8).slice(0,6);
 // card titles split mid-word (W3): a short uppercase title whose rendered lines break inside one word
 out.split=[]; for(const e of document.querySelectorAll('.node-title,.node-card .t,[class*=title]')){ if(!vis(e)||out.split.length>=6) continue; const t=(e.textContent||'').trim(); const words=t.split(/\s+/);
   if(t.length>4 && t.length<48 && e.clientWidth>0 && e.getClientRects().length && e.scrollHeight>1.6*parseFloat(getComputedStyle(e).lineHeight||0) && words.some(w=>w.length>6)) { const r=document.createRange(); r.selectNodeContents(e); const rs=[...r.getClientRects()]; const lines=new Set(rs.map(x=>Math.round(x.top))).size; if(lines>words.length) out.split.push([nm(e),t.slice(0,30),lines,words.length]); } }
 // C1: the open card (the element holding the in-card unit label): its box and the lowest thing in it, against the screen's foot
 const ic=[...document.querySelectorAll('.in-card')].find(vis); out.cardBox=null; out.cardLow=null;
 if(ic){ const card=ic.closest('[id^=node-]')||ic.parentElement; out.cardBox=R(card); let low=0; for(const k of card.querySelectorAll('*')){ if(!vis(k)||k.closest('.ho-nt')) continue;      /* (Holo's border trace: strips 130 px longer than their edge, clipped by .ho-nt's overflow:hidden; never drawn past the card) */ const r=k.getBoundingClientRect(); if(r.top<vh) low=Math.max(low,Math.round(r.bottom)); } out.cardLow=low; }
 // F4/F5/F6: the Atlas's place tags and pins against the title bar and the screen; the tour bar
 const nb=document.getElementById('nav'); out.navBottom=nb&&vis(nb)?Math.round(nb.getBoundingClientRect().bottom):0;
 out.tags=[...document.querySelectorAll('.wp-tag')].filter(vis).map(R); out.pins=[...document.querySelectorAll('.wp-pin')].filter(vis).map(e=>{const r=e.getBoundingClientRect();return Math.round(Math.min(r.width,r.height))});
 const tb=document.querySelector('.wp-tour'); out.tour=tb&&vis(tb)?R(tb):null;
 // H1: what is on top of the page's header corners (a tile showing through means no backing)
 out.topAt=[40,vw-40].map(x=>{const e=document.elementFromPoint(x,12); return e?(e.closest('.course-tile')?'tile':e.id||e.tagName.toLowerCase()):null});
 // H2: the smallest tile action button
 out.tileBtn=Math.round(Math.min(999,...[...document.querySelectorAll('.tile-reports,.tile-share,.tile-download,.slab-share,.slab-download')].filter(vis).map(e=>{const r=e.getBoundingClientRect();return Math.min(r.width,r.height)})));
 // W4: the smallest card title as drawn (font size x the board's scale)
 let mp=0; for(const e of document.querySelectorAll('.node-title')){ if(!vis(e)||!e.offsetHeight) continue; const px=parseFloat(getComputedStyle(e).fontSize)*(e.getBoundingClientRect().height/e.offsetHeight); if(!mp||px<mp) mp=px; } out.titlePx=Math.round(mp*10)/10;
 // W2 / F5: what the header row (#nav, or the homepage's #title-bar) cuts or covers: a unit chip, card, place tag, pin or label straddling its foot or sitting under it, and (F5) what the Tour bar covers
 const hd=[document.getElementById('nav'),document.getElementById('title-bar')].filter(e=>e&&vis(e)&&e.getBoundingClientRect().height<120); out.hdrBottom=hd.length?Math.round(Math.max(...hd.map(e=>e.getBoundingClientRect().bottom))):0;
 const hdrEls=[...document.querySelectorAll('.phase-label-float,.node-card,.wp-tag,.wp-pin,.wp-lbl,.ix-pill,.ix-chip')].filter(e=>vis(e)&&!e.closest('#nav,#title-bar,#nav-drawer')&&!(document.documentElement.classList.contains('wpal-open')&&e.closest('#world')));
 out.cutByHeader=out.hdrBottom?hdrEls.filter(e=>e.getBoundingClientRect().top<out.hdrBottom-1).slice(0,6).map(e=>[nm(e),R(e)]):[];
 const tr=document.querySelector('.wp-tour'); const trr=tr&&vis(tr)?tr.getBoundingClientRect():null;
 out.tourHits=trr?hdrEls.filter(e=>{const r=e.getBoundingClientRect();return r.right>trr.left+2&&r.left<trr.right-2&&r.bottom>trr.top+2&&r.top<trr.bottom-2}).slice(0,6).map(e=>[nm(e),R(e)]):[];
 const f=id=>{const e=document.getElementById(id); return e&&vis(e)?R(e):null};
 out.key={nav:f('nav'),frame:f('sk-frame'),bg:f('page-bg'),canvas:f('canvas'),app:f('app'),lanesnav:f('lanes-nav'),menu:f('menu-btn')||f('drawer-btn')};
 const bg=document.getElementById('page-bg'); out.bgcss=bg?getComputedStyle(bg).backgroundImage.slice(0,60)+' | '+getComputedStyle(bg).backgroundColor:null;
 out.bodybg=getComputedStyle(document.body).backgroundColor+' / html '+getComputedStyle(document.documentElement).backgroundColor;
 const tc=document.querySelector('meta[name=theme-color]'); out.theme=tc?tc.content:null;
 // safe-area handling anywhere in the page's own CSS (E5)
 let sa=0; try{ for(const s of document.styleSheets){ let rs; try{rs=s.cssRules}catch(e){continue} for(const r of rs){ if(/safe-area-inset-(left|right)/.test(r.cssText)) sa++; } } }catch(e){}
 out.safeLR=sa;
 const nodes=[...document.querySelectorAll('.node-card,.node,[id^=node-]')].filter(vis); out.nnodes=nodes.length;
 return out; }"""


async def run(base, outdir, only, shots, concurrency=4):
    async_playwright = _playwright().async_playwright
    res = {}
    sem = asyncio.Semaphore(concurrency)

    async def one(b, vn, w, h, st):
        async with sem:
            ctx = await b.new_context(viewport={"width": w, "height": h}, device_scale_factor=3 if shots else 1, is_mobile=True, has_touch=True, user_agent=UA)
            for pn, page, q in PAGES:
                if vn[0] == "b" and pn not in BONLY:
                    continue
                key = f"{pn}-{st}-{vn}"
                if only and not any(o in key for o in only):
                    continue
                pg = await ctx.new_page()
                errs = []
                pg.on("pageerror", lambda e, errs=errs: errs.append(str(e)[:160]))
                qs = "&".join(x for x in (q, "" if st == "classic" else "style=" + st) if x)
                try:
                    await pg.goto(f"{base}/{page}.html" + ("?" + qs if qs else ""), wait_until="load", timeout=45000)
                    await pg.wait_for_timeout(3800 if st != "classic" else 2500)
                    if pn == "home":
                        await pg.evaluate("window.scrollTo(0, 420)")
                        await pg.wait_for_timeout(400)
                    m = await pg.evaluate(M)
                    m["errs"] = errs[:4]
                    if shots:
                        await pg.screenshot(path=f"{outdir}/shots/{key}.png")
                except Exception as e:
                    m = {"fail": str(e)[:200]}
                res[key] = m
                print(key, "ok" if "fail" not in m else m["fail"], flush=True)
                await pg.close()
            await ctx.close()

    async with async_playwright() as p:
        b = await p.webkit.launch()
        await asyncio.gather(*[one(b, vn, w, h, st) for vn, w, h in VPS for st in STYLES])
        await b.close()
    return res


def measure(outdir=None, only=None, shots=False):
    """Build, serve, shoot; -> the metrics dict (also written to <outdir>/metrics.json when outdir is given)."""
    pages, plans, art = build_pages()
    s = serve(pages, plans, art)
    try:
        if outdir:
            Path(outdir, "shots").mkdir(parents=True, exist_ok=True)
        res = asyncio.run(run(f"http://127.0.0.1:{s.server_address[1]}", outdir, only, shots))
    finally:
        s.shutdown()
    if outdir:
        Path(outdir, "metrics.json").write_text(json.dumps(res, indent=0), encoding="utf-8")
    return res


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    measure(args[0], args[1].split(",") if len(args) > 1 else None, "--shots" in sys.argv)
