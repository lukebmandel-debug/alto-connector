"""Portals that really go somewhere: an airport is a gateway to other cities (and to the Mind Palaces made there).

A portal (brief.palace.portals) pins itself to the stations it is reached from. Clicking the pin (or "Fly there" on its
card) now makes the trip: the camera goes to the station, a plane lifts off the pin, and the page becomes the airport —
a departures board of cities. A city that has a Mind Palace in the same account boards the traveller straight into it
(its `url`, a relative private link); a city without one says so and what to ask Claude for. Nothing is invented: the
board lists only the cities the portal names (`destinations`), and `set_up_palace` fills that list with the user's own
other palaces plus the cities Alto can build on request.

    destination = {"city": "New York", "code": "JFK", "timeline": "<timeline id>"?, "url": "../<key>/"?, "preset": true?}

check_portals (palace.py) keeps `code` and `destinations` as given and `kind` ('airport' when the name says so).
"""
from __future__ import annotations

# the cities an airport board offers when nothing else is known: (city, IATA code of its main airport, Alto has the city built in)
HUBS = [("New York City", "JFK", True), ("Boston", "BOS", True), ("Washington, D.C.", "DCA", True),
        ("Chicago", "ORD", False), ("Los Angeles", "LAX", False), ("London", "LHR", False), ("Paris", "CDG", False)]
CODES = {"philadelphia": "PHL", "new york city": "JFK", "new york": "JFK", "nyc": "JFK", "manhattan": "JFK", "boston": "BOS",
         "washington": "DCA", "washington, d.c.": "DCA", "washington dc": "DCA", "dc": "DCA", "chicago": "ORD",
         "los angeles": "LAX", "san francisco": "SFO", "london": "LHR", "paris": "CDG", "seattle": "SEA", "atlanta": "ATL",
         "miami": "MIA", "denver": "DEN", "houston": "IAH", "dallas": "DFW", "baltimore": "BWI", "pittsburgh": "PIT"}


def _key(city: str) -> str:
    return (city or "").strip().lower()


def code_for(city: str) -> str:
    return CODES.get(_key(city), "")


def default_destinations(place: str, own: list | None = None) -> list:
    """The board when the portal names none: the user's own palaces first, then the built-in cities (not this one)."""
    out, seen = [], {_key(place)}
    for d in own or []:
        k = _key(d.get("city"))
        if k and k not in seen:
            seen.add(k)
            out.append(dict(d))
    here = {"new york city": "new york", "washington, d.c.": "washington"}
    for city, code, preset in HUBS:
        k = here.get(_key(city), _key(city))
        if any(k in s or s in k for s in seen):
            continue
        out.append({"city": city, "code": code, **({"preset": True} if preset else {})})
    return out


def clean_destinations(items) -> list:
    out = []
    for d in items or []:
        if not isinstance(d, dict) or not str(d.get("city") or "").strip():
            continue
        e = {"city": str(d["city"]).strip(), "code": str(d.get("code") or code_for(d["city"])).strip().upper()[:4]}
        for k in ("timeline", "url"):
            if d.get(k):
                e[k] = str(d[k]).strip()
        if d.get("preset"):
            e["preset"] = True
        out.append(e)
    return out


AIRPORT_CSS = r"""
  /* the airport a portal opens: a glass scene over the board, a departures board of cities */
  #pal-airport{position:fixed;inset:0;z-index:420;display:none;align-items:center;justify-content:center;opacity:0;transition:opacity .55s ease;
    background:linear-gradient(180deg,color-mix(in srgb,var(--accent,#5b6cff) 28%,var(--bg,#f4f1ea)) 0%,var(--bg,#f4f1ea) 62%,color-mix(in srgb,var(--text,#222) 12%,var(--bg,#f4f1ea)) 100%);
    color:var(--text,#1b1d26);font-family:inherit;overflow:hidden;}
  #pal-airport.on{display:flex;} #pal-airport.show{opacity:1;}
  #pal-airport .pa-art{position:absolute;left:0;right:0;bottom:0;width:100%;height:46%;pointer-events:none;}
  #pal-airport .pa-art .a-gl{fill:color-mix(in srgb,var(--surface,#fff) 82%,transparent);stroke:var(--accent,#5b6cff);stroke-width:2;vector-effect:non-scaling-stroke;stroke-linejoin:round;}
  #pal-airport .pa-art .a-dk{fill:color-mix(in srgb,var(--accent,#5b6cff) 24%,var(--surface,#fff));stroke:var(--accent,#5b6cff);stroke-width:2;vector-effect:non-scaling-stroke;stroke-linejoin:round;}
  #pal-airport .pa-art .a-rw{fill:color-mix(in srgb,var(--text,#222) 22%,transparent);}
  #pal-airport .pa-art .a-ln{stroke:var(--surface,#fff);stroke-width:3;stroke-dasharray:22 26;fill:none;vector-effect:non-scaling-stroke;}
  #pal-airport .pa-art .a-pl{fill:var(--surface,#fff);stroke:var(--accent,#5b6cff);stroke-width:2;vector-effect:non-scaling-stroke;stroke-linejoin:round;}
  #pal-airport .pa-plane{position:absolute;left:-90px;top:15%;width:84px;height:84px;color:var(--accent,#5b6cff);opacity:0;pointer-events:none;}
  #pal-airport.show .pa-plane{animation:paFly 4.2s .35s ease-in-out infinite;}
  @keyframes paFly{0%{transform:translate(0,40px) rotate(-6deg);opacity:0}8%{opacity:.9}92%{opacity:.9}100%{transform:translate(calc(100vw + 180px),-60px) rotate(-6deg);opacity:0}}
  #pal-airport .pa-panel{position:relative;width:min(760px,92vw);max-height:84vh;display:flex;flex-direction:column;gap:14px;padding:22px 24px 18px;border-radius:22px;
    background:color-mix(in srgb,var(--surface,#fff) 90%,transparent);border:1px solid color-mix(in srgb,var(--text,#222) 14%,transparent);
    box-shadow:0 24px 70px rgba(0,0,0,.22);backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);transform:translateY(14px) scale(.985);transition:transform .55s cubic-bezier(.2,.8,.2,1);}
  #pal-airport.show .pa-panel{transform:none;}
  #pal-airport .pa-h{display:flex;align-items:center;gap:14px;flex-wrap:wrap;}
  #pal-airport .pa-code{font:800 30px/1 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.06em;padding:8px 12px;border-radius:12px;background:var(--accent,#5b6cff);color:#fff;}
  #pal-airport .pa-h b{display:block;font-size:19px;font-weight:700;line-height:1.2;}
  #pal-airport .pa-h small{display:block;font-size:12.5px;opacity:.7;margin-top:2px;}
  #pal-airport .pa-sub{font-size:12px;letter-spacing:.14em;text-transform:uppercase;opacity:.6;margin:2px 2px -4px;}
  #pal-airport .pa-board{display:flex;flex-direction:column;gap:6px;overflow:auto;padding:2px;}
  #pal-airport .pa-row{display:grid;grid-template-columns:62px 1fr auto;align-items:center;gap:12px;text-align:left;font:inherit;color:inherit;cursor:pointer;
    padding:11px 14px;border-radius:13px;border:1px solid color-mix(in srgb,var(--text,#222) 12%,transparent);background:color-mix(in srgb,var(--text,#222) 4%,transparent);}
  #pal-airport .pa-row:hover,#pal-airport .pa-row:focus-visible{background:color-mix(in srgb,var(--accent,#5b6cff) 14%,transparent);border-color:var(--accent,#5b6cff);outline:none;}
  #pal-airport .pa-row .c{font:700 17px/1 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.08em;}
  #pal-airport .pa-row .n{font-size:16px;font-weight:600;}
  #pal-airport .pa-row .n small{display:block;font-size:11.5px;font-weight:500;opacity:.65;margin-top:1px;}
  #pal-airport .pa-row .s{font-size:12px;font-weight:700;padding:5px 11px;border-radius:999px;white-space:nowrap;border:1px solid color-mix(in srgb,var(--text,#222) 22%,transparent);}
  #pal-airport .pa-row.go .s{background:var(--accent,#5b6cff);border-color:var(--accent,#5b6cff);color:#fff;}
  #pal-airport .pa-item{display:flex;flex-direction:column;gap:0;}
  #pal-airport .pa-item.open>.pa-row{border-bottom-left-radius:4px;border-bottom-right-radius:4px;border-color:var(--accent,#5b6cff);}
  #pal-airport .pa-row.boarding{background:color-mix(in srgb,var(--accent,#5b6cff) 20%,transparent);}
  #pal-airport .pa-row.boarding .s{animation:paBlink .5s steps(2) infinite;}
  @keyframes paBlink{50%{opacity:.35}}
  #pal-airport .pa-note{display:none;font-size:13px;line-height:1.45;padding:11px 14px 12px;margin-top:-1px;border:1px solid var(--accent,#5b6cff);border-top:0;border-radius:0 0 13px 13px;
    background:color-mix(in srgb,var(--accent,#5b6cff) 8%,var(--surface,#fff));}
  #pal-airport .pa-item.open .pa-note{display:block;}
  #pal-airport .pa-note p{margin:0 0 8px;}
  #pal-airport .pa-note code{display:block;margin:0 0 10px;padding:8px 10px;border-radius:8px;background:color-mix(in srgb,var(--text,#222) 9%,transparent);font:600 12.5px ui-monospace,Menlo,monospace;user-select:all;-webkit-user-select:all;cursor:text;}
  #pal-airport .pa-copy{font:inherit;font-weight:700;font-size:13px;padding:9px 16px;border-radius:999px;cursor:pointer;color:#fff;background:var(--accent,#5b6cff);border:1px solid var(--accent,#5b6cff);}
  #pal-airport .pa-copy:hover{filter:brightness(1.08);} #pal-airport .pa-copy.done{background:#2f8f5b;border-color:#2f8f5b;}
  #pal-airport .pa-note .pa-hint{display:inline-block;margin-left:10px;font-size:12px;opacity:.7;}
  #pal-airport .pa-foot{display:flex;justify-content:space-between;align-items:center;gap:10px;}
  #pal-airport .pa-back{font:inherit;font-weight:650;font-size:13.5px;padding:9px 16px;border-radius:999px;cursor:pointer;color:var(--text,#1b1d26);background:transparent;border:1px solid color-mix(in srgb,var(--text,#222) 26%,transparent);}
  #pal-airport .pa-back:hover{background:color-mix(in srgb,var(--text,#222) 8%,transparent);}
  #pal-airport .pa-via{font-size:12px;opacity:.6;}
  #pal-takeoff{position:fixed;z-index:419;left:0;top:0;width:46px;height:46px;pointer-events:none;color:var(--accent,#5b6cff);display:none;filter:drop-shadow(0 4px 6px rgba(0,0,0,.25));}
  html.printing #pal-airport,html.printing #pal-takeoff{display:none !important;}
  @media (prefers-reduced-motion: reduce){#pal-airport,#pal-airport .pa-panel{transition:none;} #pal-airport.show .pa-plane{animation:none;opacity:0;}}
"""

AIRPORT_JS = r"""
(function(){
if(window._palAirport) return;
var E=null, root=null, openPo=null, esc=function(v){ return String(v==null?'':v).replace(/[&<>"]/g,function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); };
var PLANE='<svg viewBox="0 0 48 48" width="100%" height="100%" aria-hidden="true"><path fill="currentColor" d="M44 24c0-1.7-1.3-3-3-3H29.5L20 5h-4.2l5.2 16H10l-3-4H3.5l3 7-3 7H7l3-4h11l-5.2 16H20l9.500-16H41c1.700 0 3-1.300 3-3z"/></svg>';
function copyText(t, done){ function fb(){ var a=document.createElement('textarea'); a.value=t; a.setAttribute('readonly',''); a.style.cssText='position:fixed;left:-9999px;top:0;opacity:0'; document.body.appendChild(a); a.select(); a.setSelectionRange(0,t.length);
    var ok=false; try{ ok=document.execCommand('copy'); }catch(e){} a.remove(); done(ok); }
  if(navigator.clipboard && navigator.clipboard.writeText){ navigator.clipboard.writeText(t).then(function(){ done(true); }, fb); } else fb(); }
function reduced(){ return window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches; }
function art(){ return '<svg class="pa-art" viewBox="0 0 1200 300" preserveAspectRatio="xMidYMax slice" aria-hidden="true">'
  +'<rect class="a-rw" x="0" y="238" width="1200" height="62"/><path class="a-ln" d="M0 270H1200"/>'
  +'<path class="a-dk" d="M140 238V176h120v62zM300 238V150h150v88z"/><path class="a-gl" d="M470 238V120l60-24h300l60 24v118z"/>'
  +'<path class="a-dk" d="M560 120V84h220v36z"/><path class="a-gl" d="M870 238V160h170v78zM1060 238V190h100v48z"/>'
  +'<path class="a-dk" d="M1010 160V70h18v90zM996 70h46l-8-22h-30z"/>'
  +'<g class="a-pl" transform="translate(330 205) scale(2.3)"><path d="M44 24c0-1.700-1.300-3-3-3H29.500L20 5h-4.200l5.200 16H10l-3-4H3.500l3 7-3 7H7l3-4h11l-5.200 16H20l9.500-16H41c1.700 0 3-1.300 3-3z"/></g></svg>'; }
function build(po){
  var ds=po.destinations||[], code=po.code||'', place=(E&&E.P&&E.P.place)||'';
  var rows=ds.map(function(d,i){ var go=!!d.url, state=go?'Mind Palace ›':(d.preset?'Build it ›':'No palace yet'), ask=!go;
    var ask_txt='Set up a Mind Palace for '+d.city;
    return '<div class="pa-item" data-i="'+i+'"><button type="button" class="pa-row'+(go?' go':'')+'" data-i="'+i+'" aria-expanded="false"><span class="c">'+esc(d.code||'···')+'</span><span class="n">'+esc(d.city)
      +'<small>'+(go?'Your Mind Palace of this city':(d.preset?'Alto can draw this city for you':'Not built yet'))+'</small></span><span class="s">'+state+'</span></button>'
      +(ask?'<div class="pa-note"><p>There is no Mind Palace of '+esc(d.city)+' yet. Claude builds it from your own materials: copy this request and paste it to Claude.</p><code>'+esc(ask_txt)+'</code>'
        +'<button type="button" class="pa-copy" data-t="'+esc(ask_txt)+'">Copy request for Claude</button><span class="pa-hint" role="status"></span></div>':'')+'</div>'; }).join('');
  root.innerHTML='<div class="pa-plane">'+PLANE+'</div>'+art()
    +'<div class="pa-panel" role="document"><div class="pa-h"><span class="pa-code">'+esc(code||'AIR')+'</span><div><b>'+esc(po.name)+'</b><small>'+esc(place?('Leaving '+place+(po.via?' by '+po.via:'')):(po.via?'Reached by '+po.via:''))+'</small></div></div>'
    +'<div class="pa-sub">Departures</div><div class="pa-board">'+(rows||'<div class="pa-row"><span class="c">···</span><span class="n">No destinations yet<small>Add cities to this portal</small></span><span class="s"> </span></div>')+'</div>'
    +'<div class="pa-foot"><button type="button" class="pa-back">‹ Back to the city</button><span class="pa-via">Every city here is a door to its own Mind Palace.</span></div></div>';
}
function show(po){
  if(!root){ root=document.createElement('div'); root.id='pal-airport'; root.setAttribute('role','dialog'); root.setAttribute('aria-modal','true'); document.body.appendChild(root);
    root.addEventListener('click', function(e){
      if(e.target.closest('.pa-back')){ close(); return; }
      var cp=e.target.closest('.pa-copy'); if(cp){ var t=cp.getAttribute('data-t'), hint=cp.parentNode.querySelector('.pa-hint');
        copyText(t, function(ok){ cp.classList.toggle('done', ok); cp.textContent=ok?'Copied \u2713':'Select the words above and copy'; if(hint) hint.textContent=ok?'Now paste it into Claude.':'Your browser blocked copying.'; }); return; }
      var r=e.target.closest('.pa-row[data-i]'); if(!r || !openPo) return; var d=openPo.destinations[+r.getAttribute('data-i')]; if(!d) return;
      if(d.url){ r.classList.add('boarding'); var s=r.querySelector('.s'); if(s) s.textContent='Boarding…'; setTimeout(function(){ try{ window.location.href=d.url; }catch(x){ window.location.assign(d.url); } }, reduced()?0:700); }
      else { var it=r.closest('.pa-item'), on=!it.classList.contains('open');
        root.querySelectorAll('.pa-item.open').forEach(function(o){ o.classList.remove('open'); o.querySelector('.pa-row').setAttribute('aria-expanded','false'); });
        it.classList.toggle('open', on); r.setAttribute('aria-expanded', on?'true':'false'); if(on){ var b=it.querySelector('.pa-copy'); if(b) try{ b.focus({preventScroll:false}); }catch(x){} } } });
    window.addEventListener('keydown', function(e){ if(root.classList.contains('on') && e.key==='Escape'){ e.preventDefault(); e.stopImmediatePropagation(); close(); } }, true); }
  openPo=po; build(po); root.setAttribute('aria-label', po.name);
  root.classList.add('on'); void root.offsetWidth; root.classList.add('show');
  var f=root.querySelector('.pa-row'); if(f) try{ f.focus({preventScroll:true}); }catch(x){}
}
function close(){ if(!root) return; root.classList.remove('show'); setTimeout(function(){ root.classList.remove('on'); }, 560); openPo=null; }
/* the trip: to the station, the plane lifts off its pin, then the airport */
function go(po, pin, at){
  if(!po || !E) return; if(!po.destinations) po.destinations=[];
  var run=function(){
    var rect=pin&&pin.getBoundingClientRect?pin.getBoundingClientRect():null;
    if(reduced() || !rect || !rect.width){ show(po); return; }
    var t=document.getElementById('pal-takeoff'); if(!t){ t=document.createElement('div'); t.id='pal-takeoff'; t.innerHTML=PLANE; document.body.appendChild(t); }
    var x=rect.left+rect.width/2-23, y=rect.top+rect.height/2-23; t.style.display='block'; t.style.left=x+'px'; t.style.top=y+'px';
    var dx=Math.max(240, innerWidth*.42), dy=-Math.max(220, innerHeight*.38), a=t.animate([{transform:'translate(0,0) scale(.7) rotate(-18deg)',opacity:1},
      {transform:'translate('+(dx*.45)+'px,'+(dy*.2)+'px) scale(1.5) rotate(-26deg)',opacity:1,offset:.45},{transform:'translate('+dx+'px,'+dy+'px) scale(3) rotate(-30deg)',opacity:0}], {duration:900, easing:'cubic-bezier(.5,0,.3,1)'});
    setTimeout(function(){ show(po); }, 520); a.onfinish=function(){ t.style.display='none'; };
  };
  /* the camera goes to the station first (from a detail page or an enlarged building too), then lifts off */
  var s=at||po._at; if(s) E.fly(s.x, s.y, Math.max(.45, Math.min(E.Z(), 1.1)), function(){ setTimeout(run, 80); }); else run();
}
window._palAirport={init:function(e){ E=e; }, go:go, show:show, close:close, isOpen:function(){ return !!(root && root.classList.contains('on')); }};
})();
"""
