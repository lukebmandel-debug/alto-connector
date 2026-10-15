"""The Mind Palace's Index pages as the INSIDE of a landmark building.

In a Mind Palace the big Index lists (the Cases, a code, the Federal Rules ...) are
reached through a landmark building on the map (Art Museum, City Hall, Independence
Hall) or an Index chip. Instead of one long dumping-ground list, the page is the
building's lobby: a header with that landmark's little 3D art, and below it each
group (the unit / section its entries appear in) is a DEPARTMENT with its own glass
door, named, in the unit's colour, with a plaque counting its entries. A door is a
button (aria-expanded / aria-controls); it swings open in perspective with a light
spill (~450 ms; reduced motion: a plain crossfade) and the department's entries
unfold below it as the ordinary Index rows, so every link, "Appears in" link,
highlight, search hit and note keeps working.

Palace-only: `axis_index_glue()` patches the shared glue (detail_extras.AXIS_INDEX_GLUE)
only for a palace build; every other timeline gets the original glue byte for byte.
The landmark art is not copied: the palace map already holds each building's
`<symbol>` (palace_landmarks.py), and the header just `<use>`s it.
"""
from __future__ import annotations

from .detail_extras import AXIS_INDEX_GLUE
from .palace_landmarks import LANDMARK_CSS

# the landmark materials, for the header's art (the palace svg's rules are scoped to .pal-svg)
_VARS = "\n".join(ln.replace(".pal-svg{", ".pd-facade{") for ln in LANDMARK_CSS.splitlines()
                  if ln.strip().startswith((".pal-svg{", "html.dark .pal-svg{")))

DOORS_CSS = _VARS + r"""
  /* the building's header: its art beside its name */
  .detail-header.pd-hdr{align-items:center;}
  .pd-facade{flex:none;width:236px;line-height:0;filter:drop-shadow(0 6px 10px rgba(20,26,55,.18));}
  .pd-facade svg{width:100%;height:auto;display:block;overflow:visible;--lz-line:var(--pd-hc,#667);--lz-door:var(--pd-hc,#667);}
  .pd-facade .pd-gen-f{fill:var(--surface);stroke:var(--pd-hc);stroke-width:1.4;}
  .pd-facade .pd-gen-d{fill:var(--pd-hc);opacity:.55;}
  .pd-facade .pd-gen-l{fill:none;stroke:var(--pd-hc);stroke-width:1.4;opacity:.7;}
  .pd-lead{font-size:14px;color:var(--muted);margin:10px 0 0;line-height:1.5;max-width:44em;}
  /* the lobby */
  .pd-bar{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:0 0 14px;}
  .pd-bar .pd-cnt{font-size:11px;letter-spacing:.22em;text-transform:uppercase;color:var(--muted);}
  .pd-all{font:inherit;font-size:12px;letter-spacing:.04em;padding:6px 14px;border-radius:999px;cursor:pointer;color:var(--text);
    background:var(--surface);border:1px solid var(--border);}
  .pd-all:hover,.pd-all:focus-visible{border-color:var(--pd-hc,var(--accent));}
  html.mobile .pd-all{display:none;}
  .pd-lobby{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:14px;align-items:start;margin-bottom:40px;}
  .detail-section.pd-dept{margin:0;min-width:0;}
  .pd-dept.open{grid-column:1/-1;}
  .pd-dept h3.pd-h{margin:0;padding:0;font-size:inherit;letter-spacing:normal;text-transform:none;color:inherit;font-weight:normal;}
  .pd-door{all:unset;box-sizing:border-box;display:flex;align-items:center;gap:16px;width:100%;padding:14px 16px;border-radius:16px;cursor:pointer;
    background:linear-gradient(135deg,color-mix(in srgb,var(--pd-c) 9%,var(--surface)),var(--surface));
    border:1px solid color-mix(in srgb,var(--pd-c) 38%,var(--border));border-left:4px solid var(--pd-c);
    box-shadow:0 1px 0 rgba(255,255,255,.5) inset,0 6px 16px -10px rgba(20,26,55,.35);transition:box-shadow .2s,transform .2s,background .2s;}
  html.dark .pd-door{box-shadow:0 1px 0 rgba(255,255,255,.05) inset,0 6px 16px -10px rgba(0,0,0,.6);}
  .pd-door:hover{transform:translateY(-1px);box-shadow:0 10px 22px -12px color-mix(in srgb,var(--pd-c) 60%,rgba(20,26,55,.4));}
  .pd-door:focus-visible{outline:2.5px solid var(--pd-c);outline-offset:3px;}
  .pd-dept.open .pd-door{background:linear-gradient(135deg,color-mix(in srgb,var(--pd-c) 18%,var(--surface)),var(--surface));}
  .pd-txt{flex:1;min-width:0;display:flex;flex-direction:column;gap:3px;}
  .pd-kick{font-size:10.5px;letter-spacing:.16em;text-transform:uppercase;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
  .pd-name{font-size:17px;font-weight:650;line-height:1.28;color:var(--text);overflow-wrap:anywhere;}
  .pd-plaque{align-self:flex-start;margin-top:5px;display:inline-flex;align-items:baseline;gap:5px;padding:3px 11px;border-radius:6px;
    font-size:12px;font-weight:700;letter-spacing:.03em;color:#4a3410;
    background:linear-gradient(180deg,#f3dfa6,#d2ae5d);border:1px solid #a8812f;box-shadow:0 1px 0 rgba(255,255,255,.6) inset,0 1px 2px rgba(60,40,0,.3);}
  html.dark .pd-plaque{color:#2a1e08;background:linear-gradient(180deg,#e7cd88,#b98f3c);border-color:#7d5d1d;}
  .pd-plaque b{font-size:14px;font-variant-numeric:tabular-nums;}
  .pd-chev{flex:none;width:18px;height:18px;color:var(--muted);transition:transform .3s;}
  .pd-dept.open .pd-chev{transform:rotate(180deg);}
  /* the door: a frame with light behind it, and a glass leaf that swings on its left hinge */
  .pd-art{position:relative;flex:none;width:52px;height:78px;perspective:240px;perspective-origin:30% 50%;}
  .pd-frame{position:absolute;inset:0;border-radius:9px 9px 2px 2px;border:2.5px solid var(--pd-c);box-sizing:border-box;overflow:hidden;
    background:linear-gradient(180deg,color-mix(in srgb,var(--pd-c) 30%,#1c2033),color-mix(in srgb,var(--pd-c) 16%,#10121c));
    transition:box-shadow .45s ease-out,background .45s ease-out;}
  .pd-frame::before{content:"";position:absolute;inset:0;opacity:0;transition:opacity .45s ease-out;
    background:radial-gradient(ellipse 90% 80% at 55% 100%,#fff6d6 0%,color-mix(in srgb,var(--pd-c) 30%,#ffeeb4) 55%,color-mix(in srgb,var(--pd-c) 45%,#fff) 100%);}
  .pd-leaf{position:absolute;left:2.5px;right:2.5px;top:2.5px;bottom:0;transform-origin:0 50%;border-radius:6px 6px 0 0;
    background:linear-gradient(135deg,rgba(255,255,255,.62) 0%,color-mix(in srgb,var(--pd-c) 26%,rgba(255,255,255,.38)) 42%,color-mix(in srgb,var(--pd-c) 40%,rgba(255,255,255,.22)) 100%);
    border:1.5px solid color-mix(in srgb,var(--pd-c) 80%,#fff);box-sizing:border-box;
    box-shadow:0 0 0 1px rgba(255,255,255,.35) inset;
    transition:transform .45s cubic-bezier(.16,.84,.3,1),opacity .45s ease-out;}
  html.dark .pd-leaf{background:linear-gradient(135deg,rgba(255,255,255,.34) 0%,color-mix(in srgb,var(--pd-c) 34%,rgba(40,44,66,.7)) 45%,color-mix(in srgb,var(--pd-c) 46%,rgba(30,33,50,.8)) 100%);}
  .pd-leaf i{position:absolute;display:block;}
  .pd-leaf .pd-m1{left:50%;top:6px;bottom:6px;width:1.5px;background:color-mix(in srgb,var(--pd-c) 70%,#fff);opacity:.7;}
  .pd-leaf .pd-m2{left:5px;right:5px;top:44%;height:1.5px;background:color-mix(in srgb,var(--pd-c) 70%,#fff);opacity:.7;}
  .pd-leaf .pd-kn{right:5px;top:56%;width:5px;height:5px;border-radius:50%;background:#e6c870;box-shadow:0 0 0 1px #a8812f;}
  .pd-art::after{content:"";position:absolute;left:8%;top:94%;width:190%;height:14px;opacity:0;pointer-events:none;
    background:linear-gradient(180deg,rgba(255,236,170,.7),rgba(255,236,170,0));clip-path:polygon(0 0,86% 0,100% 100%,18% 100%);transition:opacity .45s ease-out;}
  .pd-dept.open .pd-leaf{transform:rotateY(74deg);}
  .pd-dept.open .pd-frame{box-shadow:0 0 16px 2px color-mix(in srgb,var(--pd-c) 45%,rgba(255,226,140,.65));}
  .pd-dept.open .pd-frame::before,.pd-dept.open .pd-art::after{opacity:1;}
  /* the department: its entries unfold below the door */
  .pd-panel{display:grid;grid-template-rows:0fr;visibility:hidden;transition:grid-template-rows .36s ease-out .16s,visibility 0s linear .52s;}
  .pd-dept.open .pd-panel{grid-template-rows:1fr;visibility:visible;transition:grid-template-rows .36s ease-out .16s,visibility 0s;}
  .pd-dept.pd-now .pd-panel,.pd-dept.pd-now .pd-leaf,.pd-dept.pd-now .pd-frame,.pd-dept.pd-now .pd-frame::before,.pd-dept.pd-now .pd-art::after{transition:none !important;}
  .pd-panel-in{min-height:0;overflow:hidden;}
  .pd-body{margin:8px 2px 4px;padding:10px 16px 8px;border-radius:0 0 14px 14px;border-left:4px solid color-mix(in srgb,var(--pd-c) 60%,transparent);
    background:color-mix(in srgb,var(--pd-c) 4%,transparent);}
  .pd-body .pd-open{display:inline-block;margin:2px 0 6px;font-size:13px;}
  .pd-body .doc-row:last-child{border-bottom:0;}
  @media (prefers-reduced-motion:reduce){
    .pd-door,.pd-chev,.pd-frame,.pd-frame::before,.pd-art::after,.pd-panel,.pd-dept.open .pd-panel{transition:none !important;}
    .pd-leaf,.pd-dept.open .pd-leaf{transition:opacity .15s linear !important;}
    .pd-dept.open .pd-leaf{transform:none;opacity:0;}
  }
  /* phone: doors two to a row, each a tall card */
  html.mobile .detail-header.pd-hdr{flex-direction:column;align-items:flex-start;gap:14px;}
  html.mobile .pd-facade{width:min(220px,70vw);}
  html.mobile .pd-lobby{grid-template-columns:1fr 1fr;gap:10px;}
  html.mobile .pd-door{flex-direction:column;align-items:center;text-align:center;gap:10px;padding:14px 8px 12px;border-left-width:1px;border-top:4px solid var(--pd-c);}
  html.mobile .pd-txt{align-items:center;width:100%;}
  html.mobile .pd-name{font-size:14.5px;}
  html.mobile .pd-plaque{align-self:center;}
  html.mobile .pd-chev{display:none;}
  html.mobile .pd-dept.open .pd-door{flex-direction:row;text-align:left;padding:12px 14px;border-top-width:1px;border-left-width:4px;}
  html.mobile .pd-dept.open .pd-txt{align-items:flex-start;}
  html.mobile .pd-dept.open .pd-plaque{align-self:flex-start;}
  html.mobile .pd-body{padding:8px 10px 6px;}
"""

# ── the page side ───────────────────────────────────────────────────────────
DOORS_JS = r"""
(function(){
var esc=function(s){ return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); };
var mem={}, seq=0;     /* which doors were open the last time each Index was shown */
function mob(){ return document.documentElement.classList.contains('mobile'); }
function dc(){ return document.getElementById('detail-content'); }
/* the building's art: the palace map already holds the symbol; a tasteful generic facade otherwise */
function facade(kind, A){
  var P=window._ALTO_PALACE||{}, L=((P.m||{}).landmarks||[]).filter(function(l){ return l.page==='index:'+kind; })[0], key=null, nm=A.label||'';
  if(window._palLm){ key=L?window._palLm.artKey(L.n):null; if(key==='gen') key=null; }
  var sym=key?document.querySelector('symbol[id^="lz-'+key+'-"]'):null;
  if(sym){ var vb=sym.getAttribute('viewBox').split(/\s+/).map(Number);
    return '<svg viewBox="'+vb.join(' ')+'" role="img" aria-label="'+esc(L.n)+'"><use href="#'+sym.id+'" x="'+vb[0]+'" y="'+vb[1]+'" width="'+vb[2]+'" height="'+vb[3]+'"/></svg>'; }
  var cols='', i; for(i=0;i<5;i++) cols+='<rect class="pd-gen-f" x="'+(34+i*22)+'" y="44" width="9" height="40" rx="2"/>';
  return '<svg viewBox="0 0 160 110" role="img" aria-label="'+esc(nm)+'"><path class="pd-gen-f" d="M18 44 80 12l62 32z"/><rect class="pd-gen-f" x="22" y="44" width="116" height="6"/>'
    +cols+'<path class="pd-gen-d" d="M70 84V66a10 10 0 0 1 20 0v18z"/><path class="pd-gen-l" d="M14 90h132M10 97h140"/></svg>';
}
function head(kind, A, total, color, base, outline){
  var unit=total===1?String(A.unit).replace(/s$/,''):A.unit;
  return '<div class="detail-header pd-hdr" style="--pd-hc:'+color+'"><div class="pd-facade" aria-hidden="false">'+facade(kind,A)+'</div><div>'
    +'<div class="detail-name" style="color:'+color+'">'+A.label+'</div>'
    +'<div class="detail-role">'+total+' '+unit+' &middot; in '+(outline?'outline':'timeline')+' order</div>'
    +'<div class="detail-badge '+(base==='env'?'badge-env':'badge-theme')+'">Index</div></div></div>';
}
var CHEV='<svg class="pd-chev" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 8l5 5 5-5"/></svg>';
function door(d, i, unit, ns){
  var pm=(d.act!=null && typeof PHASE_META!=='undefined')?PHASE_META[d.act]:null, col=pm&&pm.colorRaw?pm.colorRaw:'var(--accent,#6d5bd0)';
  var kick=pm?('Unit '+(pm.numeral||(d.act+1))+(pm.label&&!d.band?' \u00b7 '+pm.label:'')):'', id=ns+'-'+i;
  var u=d.n===1?String(unit).replace(/s$/,''):unit;
  var name=(d.num?d.num+' ':'')+d.title;
  return '<div class="detail-section pd-dept" id="'+id+'" data-pd="'+esc(d.id)+'" style="--pd-c:'+col+'">'
    +'<h3 class="pd-h"><button type="button" class="pd-door" id="'+id+'-b" aria-expanded="false" aria-controls="'+id+'-p">'
    +'<span class="pd-art" aria-hidden="true"><span class="pd-frame"></span><span class="pd-leaf"><i class="pd-m1"></i><i class="pd-m2"></i><i class="pd-kn"></i></span></span>'
    +'<span class="pd-txt">'+(kick?'<span class="pd-kick">'+esc(kick)+'</span>':'')+'<span class="pd-name">'+esc(name)+'</span>'
    +'<span class="pd-plaque"><b>'+d.n+'</b> '+esc(u)+'</span></span>'+CHEV+'</button></h3>'
    +'<div class="pd-panel" id="'+id+'-p" role="region" aria-labelledby="'+id+'-b"><div class="pd-panel-in"><div class="pd-body">'
    +(d.head?'<span class="pd-open">'+d.head+'</span><br>':'')+d.html+'</div></div></div></div>';
}
function lobby(kind, A, items){
  var ns='pd'+(++seq);
  return '<div class="pd-bar"><span class="pd-cnt">Lobby &middot; '+items.length+' department'+(items.length===1?'':'s')+'</span>'
    +'<button type="button" class="pd-all" aria-pressed="false">Open all</button></div>'
    +'<div class="pd-lobby" data-pd-kind="'+esc(kind)+'">'+items.map(function(d,i){ return door(d,i,A.unit,ns); }).join('')+'</div>';
}
function set(dept, on, instant){
  if(!dept || dept.classList.contains('open')===on) return;
  var b=dept.querySelector('.pd-door');
  if(instant){ dept.classList.add('pd-now'); }
  dept.classList.toggle('open', on); b.setAttribute('aria-expanded', on?'true':'false');
  if(instant){ void dept.offsetWidth; setTimeout(function(){ dept.classList.remove('pd-now'); }, 30); }
  var L=dept.parentNode, k=L&&L.getAttribute('data-pd-kind');
  if(k){ mem[k]=mem[k]||{}; mem[k][dept.getAttribute('data-pd')]=on?1:0; }
  var all=L&&L.parentNode&&L.parentNode.querySelector('.pd-all');
  if(all){ var n=L.querySelectorAll('.pd-dept'), o=L.querySelectorAll('.pd-dept.open'); all.textContent=o.length===n.length?'Close all':'Open all'; all.setAttribute('aria-pressed', o.length===n.length?'true':'false'); }
}
function toggle(dept){
  var on=!dept.classList.contains('open');
  if(on && mob()) Array.prototype.forEach.call(dept.parentNode.querySelectorAll('.pd-dept.open'), function(o){ if(o!==dept) set(o,false); });
  set(dept, on);
}
function reveal(id){
  var c=dc(); if(!c) return false; var dept=null, row=null, sid=String(id).replace(/"/g,'');
  var ds=c.querySelectorAll('.pd-dept');
  for(var i=0;i<ds.length && !dept;i++){ if(ds[i].getAttribute('data-pd')===sid) dept=ds[i]; }
  if(!dept){ var t=c.querySelector('.doc-row-t[data-sd-id="'+sid+'"]'); row=t&&t.closest('.doc-row'); dept=row&&row.closest('.pd-dept'); }
  if(!dept) return false;
  if(mob()) Array.prototype.forEach.call(dept.parentNode.querySelectorAll('.pd-dept.open'), function(o){ if(o!==dept) set(o,false,true); });
  set(dept, true);
  setTimeout(function(){ try{ (row||dept).scrollIntoView({block:'center',behavior:'smooth'}); }catch(e){} }, 420);
  return true;
}
function after(kind){
  var c=dc(); if(!c) return;
  if(!c._pd){ c._pd=1;
    c.addEventListener('click', function(e){
      var b=e.target.closest&&e.target.closest('.pd-door'); if(b){ e.preventDefault(); toggle(b.closest('.pd-dept')); return; }
      var a=e.target.closest&&e.target.closest('.pd-all'); if(!a) return;
      var L=c.querySelector('.pd-lobby'); if(!L) return; var ds=L.querySelectorAll('.pd-dept'), want=L.querySelectorAll('.pd-dept.open').length!==ds.length;
      Array.prototype.forEach.call(ds, function(d){ set(d, want); });
    });
    /* a search hit in a closed department opens its door and is scrolled to */
    new MutationObserver(function(ms){
      var hit=null;
      ms.forEach(function(m){ Array.prototype.forEach.call(m.addedNodes, function(n){
        var mk=n.nodeType===1 && (n.matches('mark.alto-sr-hit')?n:n.querySelector('mark.alto-sr-hit')); if(mk && !hit) hit=mk; }); });
      var d=hit&&hit.closest('.pd-dept'); if(!d || d.classList.contains('open')) return;
      set(d, true, true);
      setTimeout(function(){ try{ hit.scrollIntoView({block:'center',behavior:'smooth'}); }catch(e){} }, 60);
    }).observe(c, {childList:true, subtree:true});
  }
  var m=mem[kind]; if(!m) return;
  Array.prototype.forEach.call(c.querySelectorAll('.pd-dept'), function(d){ if(m[d.getAttribute('data-pd')]) set(d, true, true); });
}
window._palDoors={head:head, lobby:lobby, after:after, reveal:reveal, toggle:toggle};
})();
"""


def axis_index_glue() -> str:
    """AXIS_INDEX_GLUE with the Mind Palace's lobby hooked in (a palace build only)."""
    g = AXIS_INDEX_GLUE
    edits = [
        ("function showAxisIndex(kind){ window.showDetail('index', kind); }",
         "function showAxisIndex(kind, row){ window.showDetail('index', kind); if(row && window._palDoors) window._palDoors.reveal(row); }"),
        ("  (A.top||[]).forEach(function(s){",
         "  if(window._palDoors) html = window._palDoors.head(kind, A, total, color, base, !!O);\n  (A.top||[]).forEach(function(s){"),
        ("  groups.forEach(function(g){\n",
         "  if(window._palDoors){\n"
         "    var items = groups.map(function(g){\n"
         "      var head = g.c.band ? '' : '<span class=\"alto-link\" data-sd-type=\"node\" data-sd-id=\"'+g.c.id+'\">Open '+(num[g.c.id]?num[g.c.id]+' ':'')+g.c.title+' \\u203a</span>';\n"
         "      return {id:g.c.id, title:g.c.title, num:g.c.band?'':(num[g.c.id]||''), head:head, n:g.rows.length,\n"
         "        band:!!g.c.band, act:g.c.band ? +String(g.c.id).replace('act-','') : ((typeof NODE_ACT!=='undefined' && NODE_ACT[g.c.id]!=null) ? NODE_ACT[g.c.id] : null),\n"
         "        html:g.rows.map(function(r){ return row(r.id, r.via); }).join('')};\n"
         "    });\n"
         "    if(loose.length) items.push({id:'loose', title:'Not yet attached to '+(O?'a concept':'anything'), num:'', head:'', n:loose.length, act:null,\n"
         "      html:loose.map(function(k){ return row(k, []); }).join('')});\n"
         "    html += window._palDoors.lobby(kind, A, items);\n"
         "  } else {\n  groups.forEach(function(g){\n"),
        ("    + loose.map(function(k){ return row(k, []); }).join('') + '</div>';\n",
         "    + loose.map(function(k){ return row(k, []); }).join('') + '</div>';\n  }\n"),
        ("  document.getElementById('detail-content').innerHTML = html;\n",
         "  document.getElementById('detail-content').innerHTML = html;\n  if(window._palDoors) window._palDoors.after(kind);\n"),
    ]
    for old, new in edits:
        assert g.count(old) == 1, old
        g = g.replace(old, new)
    return g
