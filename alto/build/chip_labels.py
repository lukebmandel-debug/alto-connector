"""Chip labels: a one- or two-letter badge on a chip (a case, a doctrine, a character), with a legend of what each letter means.

Luke, 2026-11-28: "a way to add labels in subchips for cases (although the user could add them to any subchip type)... one (or two letters at
most)... history cases labeled with an H... R... O". A label belongs to the chip (Entity.label / AxisValue.label), the legend to the page
(Brief.chip_legend [{label, meaning}]), so a chip wears its badge everywhere it shows: the card's footer glyphs, the nav and drawer buttons,
the chip rows of a detail page, a chip's own detail page.

One DOM layer does it for every format (Classic, Retro, Holographic, the horizontal timeline, the outline, a phone) because every format draws
the same chips: a chip either carries onclick="showDetail('kind','id')" or is a card glyph (.csym-btn characters, .esym-btn / .tsym-btn axis
values) named by its title. The badge is a real child at the end of the chip, in the chip's own colour, never laid over its text, and the
chip's own hit area (44pt on a phone) is the target. The meaning shows on hover (a bubble that lists the whole legend, the hovered letter
marked) and on a long press on a touch screen (the press that shows it does not also open the chip). The legend also heads the Filter panel.
"""
from __future__ import annotations

import json

CSS = r"""
.alto-lbl:not(#_){display:inline-flex;align-items:center;justify-content:center;box-sizing:border-box;min-width:1.45em;height:1.45em;padding:0 .3em;margin-left:.4em;
  border-radius:.8em;border:1px solid currentColor;font:700 .68em/1 system-ui,-apple-system,sans-serif;letter-spacing:.02em;text-transform:uppercase;
  vertical-align:middle;pointer-events:none;background:color-mix(in srgb,currentColor 14%,transparent);color:inherit;white-space:nowrap;flex:none;}
.csym-btn[data-lbl]:not(#_){width:auto !important;min-width:30px;padding:0 6px !important;display:inline-flex;align-items:center;justify-content:center;}
.csym-btn:not(#_) .alto-lbl,.esym-btn:not(#_) .alto-lbl,.tsym-btn:not(#_) .alto-lbl{margin-left:.3em;font-size:.6em;}
.alto-lbl.star:not(#_){color:var(--star,#c58a00);background:color-mix(in srgb,var(--star,#c58a00) 18%,transparent);text-transform:none;}
html.dark .alto-lbl.star:not(#_){--star:#f0c040;}
[data-lbl]{-webkit-touch-callout:none;}
.alto-lbl-key:not(#_){display:flex;flex-wrap:wrap;gap:6px 16px;align-items:center;box-sizing:border-box;margin:12px 0 24px;padding:0;font-size:13px;line-height:1.3;color:var(--muted,inherit);max-width:100%;}
.alto-lbl-key .lk{display:inline-flex;align-items:center;gap:0;}
.alto-lbl-key .alto-lbl{margin:0 .5em 0 0;font-size:.8em;color:var(--text,inherit);}
.alto-lbl-key .alto-lbl.star{color:var(--star,#c58a00);}
#alto-lbl-tip{position:fixed;z-index:100000;pointer-events:none;display:none;max-width:min(260px,calc(100vw - 40px));box-sizing:border-box;padding:7px 10px;border-radius:10px;
  background:var(--surface,#fff);color:var(--text,#222);border:1px solid var(--border,rgba(0,0,0,.2));box-shadow:0 8px 22px rgba(0,0,0,.25);font:12px/1.35 system-ui,-apple-system,sans-serif;}
#alto-lbl-tip div{display:flex;gap:7px;align-items:baseline;}
#alto-lbl-tip div+div{margin-top:2px;}
#alto-lbl-tip b{display:inline-block;min-width:1.7em;text-align:center;font-weight:700;border:1px solid currentColor;border-radius:.8em;padding:0 .3em;font-size:11px;opacity:.7;}
#alto-lbl-tip div.on{font-weight:600;}
#alto-lbl-tip div.on b{opacity:1;background:var(--text,#222);color:var(--surface,#fff);border-color:transparent;}
.alto-lbl-legend:not(#_){padding:2px 0 10px;font-size:12px;line-height:1.4;color:var(--text);}
.alto-lbl-legend .ef-h:not(#_){margin-bottom:5px;}
.alto-lbl-legend .lg{display:flex;gap:8px;align-items:baseline;margin-top:3px;}
.alto-lbl-legend .lg b{display:inline-block;min-width:1.8em;text-align:center;font-weight:700;border:1px solid currentColor;border-radius:.8em;padding:0 .3em;font-size:11px;}
html.dark #alto-lbl-tip{background:var(--surface,#1c1c22);}
"""

JS = r"""
(function(){
  var D=window._ALTO_CHIPLBL; if(!D) return;
  var STAR='★', BYID=D.byId||{}, BYNAME=D.byName||{}, LEG=D.legend||[], means={};
  function setMeans(){ means={}; LEG.forEach(function(r){ means[r.label]=r.meaning||''; }); if(!means[STAR]) means[STAR]='critical case'; }
  setMeans();
  var KIND={'csym-btn':'char','esym-btn':'env','tsym-btn':'theme'};
  function tagsOf(el){
    var st=el.classList&&el.classList.contains('doc-row-t')&&el.getAttribute('data-sd-type');          /* a row of the page that lists a chip type's values */
    if(st) return (BYID[st]||{})[el.getAttribute('data-sd-id')]||[];
    var o=el.getAttribute&&el.getAttribute('onclick'), m=o&&o.match(/showDetail\('(\w+)','([^']+)'/);
    if(m){ return m[1]==='node'?[]:((BYID[m[1]]||{})[m[2]]||[]); }
    for(var c in KIND){ if(el.classList&&el.classList.contains(c)){ return (BYNAME[KIND[c]]||{})[el.getAttribute('data-tn')||el.getAttribute('title')||'']||[]; } }
    return [];
  }
  function badge(el,tags){
    var key=tags.join(' '), have=el.getAttribute('data-lbl');
    if(have===key&&el.querySelector(':scope>.alto-lbl')) return;
    el.querySelectorAll(':scope>.alto-lbl').forEach(function(x){ x.remove(); });
    tags.forEach(function(l){ var b=document.createElement('i'); b.className='alto-lbl'+(l===STAR?' star':''); b.textContent=l; b.setAttribute('aria-hidden','true'); el.appendChild(b); });
    el.setAttribute('data-lbl',key);
    var t=el.getAttribute('title'); if(t!=null&&!el.hasAttribute('data-tn')){ el.setAttribute('data-tn',t); el.removeAttribute('title'); }
    el.setAttribute('aria-label',(el.getAttribute('data-tn')||el.textContent.replace(/[^\w\s.’'&-]/g,'').trim())+', '+tags.map(function(l){ return l+(means[l]?' = '+means[l]:''); }).join(', '));
  }
  function scan(){
    document.querySelectorAll('[onclick*="showDetail(\'"],.csym-btn,.esym-btn,.tsym-btn,.doc-row-t[data-sd-type]').forEach(function(el){ var t=tagsOf(el); if(t.length) badge(el,t); });
    detailName(); legendInPanel(); pageKey();
  }
  /* a chip's own detail page: its name wears the badges too */
  function detailName(){
    var cur=D.current; if(!cur) return; var t=((BYID[cur[0]]||{})[cur[1]]||[]); var dp=document.getElementById('detail-page');
    if(!t.length||!dp||!dp.classList.contains('visible')) return; var n=dp.querySelector('.detail-name'); if(n&&!n.querySelector('.alto-lbl')) badge(n,t);
  }
  /* the page that lists a chip type's values: a compact key of the tags used on it */
  function pageKey(){
    var cur=D.current, dp=document.getElementById('detail-page'), dc=document.getElementById('detail-content'); if(!cur||cur[0]!=='index'||!dp||!dc||!dp.classList.contains('visible')) return;
    var used=[]; dc.querySelectorAll('[data-lbl]').forEach(function(e){ e.getAttribute('data-lbl').split(' ').forEach(function(l){ if(l&&used.indexOf(l)<0) used.push(l); }); });
    var old=dc.querySelector('.alto-lbl-key'), sig=used.join(' ');
    if(old&&old.getAttribute('data-sig')===sig) return; if(old) old.remove(); if(!used.length) return;
    var order=LEG.map(function(r){ return r.label; }); used.sort(function(a,b){ var x=order.indexOf(a), y=order.indexOf(b); return (x<0?99:x)-(y<0?99:y); });
    var k=document.createElement('div'); k.className='alto-lbl-key'; k.setAttribute('data-sig',sig);
    used.forEach(function(l){ var d=document.createElement('span'); d.className='lk'; var b=document.createElement('i'); b.className='alto-lbl'+(l===STAR?' star':''); b.textContent=l; d.appendChild(b); d.appendChild(document.createTextNode(means[l]||'')); k.appendChild(d); });
    var h=dc.querySelector('.detail-header'); if(h&&h.parentNode===dc) dc.insertBefore(k,h.nextSibling); else dc.insertBefore(k,dc.firstChild);
  }
  function clear(){ document.querySelectorAll('.alto-lbl-key').forEach(function(k){ k.remove(); });
    document.querySelectorAll('[data-lbl]').forEach(function(el){ el.querySelectorAll(':scope>.alto-lbl').forEach(function(b){ b.remove(); }); el.removeAttribute('data-lbl'); el.removeAttribute('aria-label');
      var t=el.getAttribute('data-tn'); if(t!=null){ el.setAttribute('title',t); el.removeAttribute('data-tn'); } }); }
  function refresh(){ hide(); clear(); scan(); }
  function clean(l){ l=String(l||'').trim(); if(l===STAR) return STAR; return l.replace(/[^0-9A-Za-z]/g,'').slice(0,2).toUpperCase(); }
  window._altoChipLbl={
    get:function(k,id){ return ((BYID[k]||{})[id]||[]).slice(); },
    set:function(k,id,tags,name){ BYID[k]=BYID[k]||{}; BYNAME[k]=BYNAME[k]||{}; var t=[]; (tags||[]).forEach(function(x){ x=clean(x); if(x&&t.indexOf(x)<0) t.push(x); }); t=t.slice(0,2);
      if(t.length){ BYID[k][id]=t; if(name) BYNAME[k][name]=t; } else { delete BYID[k][id]; if(name) delete BYNAME[k][name]; } refresh(); },
    legend:function(){ return LEG.map(function(r){ return {label:r.label,meaning:r.meaning}; }); },
    setLegend:function(v){ LEG=(v||[]).map(function(r){ return {label:r.label,meaning:r.meaning||''}; }); setMeans(); D.legend=LEG;
      document.querySelectorAll('.alto-lbl-legend').forEach(function(e){ e.remove(); }); refresh(); }
  };
  var _sd=window.showDetail;
  if(typeof _sd==='function'){ window.showDetail=function(k,id){ D.current=[k,id]; var r=_sd.apply(this,arguments); try{ scan(); }catch(e){} return r; }; }
  /* the legend heads the Filter panel */
  function legendInPanel(){
    var body=document.querySelector('#ef-panel .ef-body'); if(!body||!LEG.length||body.querySelector('.alto-lbl-legend')) return;
    var s=document.createElement('div'); s.className='alto-lbl-legend ef-sec'; var h=document.createElement('div'); h.className='ef-h'; h.textContent='Labels'; s.appendChild(h);
    LEG.forEach(function(r){ var d=document.createElement('div'); d.className='lg'; var b=document.createElement('b'); b.textContent=r.label; var t=document.createElement('span'); t.textContent=r.meaning; d.appendChild(b); d.appendChild(t); s.appendChild(d); });
    body.insertBefore(s,body.firstChild);
  }
  /* the bubble: hover on a computer, a long press on a touch screen */
  var tip=null, hideT=0;
  function show(el){
    var tags=(el.getAttribute('data-lbl')||'').split(' ').filter(Boolean); if(!tags.length) return;
    if(!tip){ tip=document.createElement('div'); tip.id='alto-lbl-tip'; document.body.appendChild(tip); }
    tip.textContent='';
    var nm=el.getAttribute('data-tn'); if(nm){ var hd=document.createElement('div'); hd.style.fontWeight='600'; hd.style.marginBottom='4px'; hd.textContent=nm; tip.appendChild(hd); }
    var rows=LEG.slice(); tags.forEach(function(l){ if(!rows.some(function(r){ return r.label===l; })) rows.push({label:l,meaning:means[l]||''}); });
    rows.forEach(function(r){ var d=document.createElement('div'); if(tags.indexOf(r.label)>=0) d.className='on'; var b=document.createElement('b'); b.textContent=r.label; d.appendChild(b);
      if(r.meaning){ var t=document.createElement('span'); t.textContent=r.meaning; d.appendChild(t); } tip.appendChild(d); });
    tip.style.display='block';
    var r=el.getBoundingClientRect(), w=tip.offsetWidth, h=tip.offsetHeight, x=Math.max(20,Math.min(window.innerWidth-w-20,r.left+r.width/2-w/2));
    var y=r.top-h-8; if(y<20) y=r.bottom+8;
    tip.style.left=x+'px'; tip.style.top=y+'px';
  }
  function hide(){ if(tip) tip.style.display='none'; clearTimeout(hideT); }
  document.addEventListener('mouseover',function(e){ var c=e.target.closest&&e.target.closest('[data-lbl]'); if(c&&!window._altoLblTouch) show(c); },true);
  document.addEventListener('mouseout',function(e){ var c=e.target.closest&&e.target.closest('[data-lbl]'); if(c) hide(); },true);
  var pressT=0, shown=false, sx=0, sy=0;
  document.addEventListener('touchstart',function(e){
    window._altoLblTouch=true; shown=false; clearTimeout(pressT);
    var c=e.target.closest&&e.target.closest('[data-lbl]'); if(!c||!e.touches[0]) return; sx=e.touches[0].clientX; sy=e.touches[0].clientY;
    pressT=setTimeout(function(){ shown=true; show(c); clearTimeout(hideT); hideT=setTimeout(hide,2600); },450);
  },{passive:true,capture:true});
  document.addEventListener('touchmove',function(e){ var t=e.touches[0]; if(t&&(Math.abs(t.clientX-sx)>8||Math.abs(t.clientY-sy)>8)){ clearTimeout(pressT); } },{passive:true,capture:true});
  document.addEventListener('touchend',function(){ clearTimeout(pressT); },{passive:true,capture:true});
  document.addEventListener('click',function(e){ if(shown){ shown=false; e.preventDefault(); e.stopPropagation(); e.stopImmediatePropagation(); } else if(tip&&tip.style.display==='block'&&window._altoLblTouch) hide(); },true);
  document.addEventListener('contextmenu',function(e){ if(e.target.closest&&e.target.closest('[data-lbl]')&&window._altoLblTouch) e.preventDefault(); },true);
  var q=0; new MutationObserver(function(){ if(q) return; q=requestAnimationFrame(function(){ q=0; scan(); }); }).observe(document.documentElement,{childList:true,subtree:true});
  scan();
})();
"""


def table(brief) -> dict:
    """{byId: {kind: {id: [tags]}}, byName: {kind: {name: [tags]}}, legend: [...]}; empty when no chip has a tag."""
    from .brief import tags_of
    by_id: dict = {"char": {}, "env": {}, "theme": {}}
    by_name: dict = {"char": {}, "env": {}, "theme": {}}
    for e in brief.entities:
        t = tags_of(e.label, e.labels)
        if t:
            by_id["char"][e.id] = t
            by_name["char"][e.name] = t
    for kind, ax in zip(("env", "theme"), brief.axes[:2]):
        for v in ax.values:
            t = tags_of(v.label, v.labels)
            if t:
                by_id[kind][v.id] = t
                by_name[kind][v.name] = t
    if not any(by_id.values()):
        return {}
    return {"byId": by_id, "byName": by_name, "legend": list(brief.chip_legend)}


def _lean(js: str) -> str:
    """The script with its comments and indentation taken out (the page is size-limited)."""
    import re
    js = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    return "\n".join(x.strip() for x in js.splitlines() if x.strip())


def block(brief) -> str:
    t = table(brief) or {"byId": {"char": {}, "env": {}, "theme": {}}, "byName": {"char": {}, "env": {}, "theme": {}}, "legend": []}
    return ("<style>" + _lean(CSS) + "</style><script>window._ALTO_CHIPLBL=" + json.dumps(t, separators=(",", ":")).replace("</", "<\\/") + ";"
            + _lean(JS) + "</script>\n")
