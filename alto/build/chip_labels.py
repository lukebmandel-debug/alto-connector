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
.alto-lbl-key:not(#_){display:flex;flex-wrap:wrap;gap:6px 16px;align-items:center;box-sizing:border-box;margin:12px 0 26px;padding:0;font-size:13px;line-height:1.3;color:var(--muted,inherit);max-width:100%;}
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
  function starFirst(a){ return a.slice().sort(function(x,y){ return (x===STAR?0:1)-(y===STAR?0:1); }); }
  function ordered(list){ var order=LEG.map(function(r){ return r.label; }); var seen=[]; list.forEach(function(l){ if(seen.indexOf(l)<0) seen.push(l); });
    return seen.sort(function(a,b){ if(a===STAR||b===STAR) return (a===STAR?0:1)-(b===STAR?0:1); var x=order.indexOf(a), y=order.indexOf(b); return (x<0?99:x)-(y<0?99:y); }); }
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
    used=ordered(used);
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
    set:function(k,id,tags,name){ BYID[k]=BYID[k]||{}; BYNAME[k]=BYNAME[k]||{}; var t=[]; (tags||[]).forEach(function(x){ x=clean(x); if(x&&t.indexOf(x)<0) t.push(x); }); t=starFirst(t.slice(0,2));
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
    ordered(LEG.map(function(r){ return r.label; })).forEach(function(l){ var r={label:l,meaning:means[l]}; var d=document.createElement('div'); d.className='lg'; var b=document.createElement('b'); b.textContent=r.label; var t=document.createElement('span'); t.textContent=r.meaning; d.appendChild(b); d.appendChild(t); s.appendChild(d); });
    body.insertBefore(s,body.firstChild);
  }
  /* the bubble: hover on a computer, a long press on a touch screen */
  var tip=null, hideT=0;
  function show(el){
    var tags=(el.getAttribute('data-lbl')||'').split(' ').filter(Boolean); if(!tags.length) return;
    if(!tip){ tip=document.createElement('div'); tip.id='alto-lbl-tip'; document.body.appendChild(tip); }
    tip.textContent='';
    var nm=el.getAttribute('data-tn'); if(nm){ var hd=document.createElement('div'); hd.style.fontWeight='600'; hd.style.marginBottom='4px'; hd.textContent=nm; tip.appendChild(hd); }
    var rows=ordered(LEG.map(function(r){ return r.label; }).concat(tags)).map(function(l){ return {label:l,meaning:means[l]||''}; });
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
    if not active(brief):
        return ""
    t = table(brief) or {"byId": {"char": {}, "env": {}, "theme": {}}, "byName": {"char": {}, "env": {}, "theme": {}}, "legend": []}
    return ("<style>" + _lean(CSS) + "</style><script>window._ALTO_CHIPLBL=" + json.dumps(t, separators=(",", ":")).replace("</", "<\\/") + ";"
            + _lean(JS) + "</script>\n")


# ── manual edit mode ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# The edit code rides in manual_edit's script only on a page that has labels or a legend, so every other page stays byte-identical to what it
# was before chip labels (the page budget is tight). A page gets its first label through the MCP tools (or a legend); from then on edit mode
# can add, change and clear labels and edit the legend.
FIELD_JS = "    // a chip's label (1-2 letters, chip_labels.py) and the page's legend of what each letter means\n    if((kind === 'c' || kind === 'env' || kind === 'theme') && p.length === 3 && p[2] === 'label'){\n      var RL = reg(kind), CL = window._altoChipLbl; if(!RL || !RL[id] || !CL) return null;\n      return {kind:'plain', get:function(){ return CL.get(kind, id).join(' '); },\n        set:function(v){ CL.set(kind, id, String(v || '').split(/\\s+/), txt(RL[id].name || '')); }};\n    }\n    if(kind === 'cl' && id === 'legend' && p.length === 2){\n      var CL2 = window._altoChipLbl; if(!CL2) return null;\n      return {kind:'list', get:function(){ return CL2.legend(); }, set:function(v){ CL2.setLegend(v || []); }};\n    }\n"
CALL_JS = "        if(kind !== 'n') decorateLabel(dc, kind, P.id);\n"
FN_JS = "  /* a chip's page: a button for its label and the page's legend (chip_labels.py) */\n  function legendText(L){ return (L || []).map(function(r){ return r.label + ' = ' + (r.meaning || ''); }).join('\\n'); }\n  function legendParse(t){ var out = [], seen = {};\n    String(t || '').split(/\\n|;/).forEach(function(ln){ var m = ln.match(/^\\s*([0-9A-Za-z]{1,2}|★)\\s*[=:\\-–]\\s*(.*)$/); if(!m) return; var l = m[1].toUpperCase(); if(seen[l]) return; seen[l] = 1; out.push({label: l, meaning: m[2].trim().slice(0, 60)}); });\n    return out.slice(0, 12); }\n  function decorateLabel(dc, kind, id){\n    var CL = window._altoChipLbl, hd = dc.querySelector('.detail-header'); if(!CL || !hd || dc.querySelector('.aed-lblbtn') || !field(kind + '|' + id + '|label')) return;\n    var b = document.createElement('button'); b.type = 'button'; b.className = 'aed-lblbtn'; var cur = CL.get(kind, id).join(' ');\n    b.textContent = cur ? 'Labels: ' + cur + ' — change' : '+ Add a label'; b.setAttribute('aria-label', 'Label and legend of this chip');\n    b.style.cssText = 'margin:8px 0 0;min-height:44px !important;height:44px !important;box-sizing:border-box;padding:0 14px;border-radius:12px;border:1px dashed currentColor;background:none;color:inherit;font:inherit;font-size:13px;cursor:pointer;display:block;';\n    b.addEventListener('click', function(e){ e.stopPropagation(); e.preventDefault();\n      askForm(b, 'Label this chip', [{k: 'label', l: 'Labels (up to two, apart by a space: O ★ — blank for none)', val: CL.get(kind, id).join(' ')},\n        {k: 'legend', l: 'What each letter means (one per line: H = history)', type: 'area', val: legendText(CL.legend())}], 'Save', function(v){\n        var l = String(v.label || '').split(/\\s+/).map(function(x){ return x === '\\u2605' ? x : x.replace(/[^0-9A-Za-z]/g, '').slice(0, 2).toUpperCase(); }).filter(function(x, i, a){ return x && a.indexOf(x) === i; }).slice(0, 2).sort(function(x, y){ return (x.charCodeAt(0) === 9733 ? 0 : 1) - (y.charCodeAt(0) === 9733 ? 0 : 1); }).join(' '), L = legendParse(v.legend), ch = [];\n        if(l !== CL.get(kind, id).join(' ')) ch.push([kind + '|' + id + '|label', l]);\n        if(JSON.stringify(L) !== JSON.stringify(CL.legend())) ch.push(['cl|legend', L]);\n        if(ch.length){ changes(ch); b.textContent = l ? 'Labels: ' + l + ' — change' : '+ Add a label'; toast(l ? 'Labelled ' + l + '. ⌘Z puts it back.' : 'Label changed. ⌘Z puts it back.'); } });\n    });\n    hd.parentNode.insertBefore(b, hd.nextSibling);\n  }\n"
_A_FIELD = "    if((kind === 'c' || kind === 'env' || kind === 'theme') && p.length === 3 && /^(name|role)$/.test(p[2])){"
_A_CALL = "        setF(dc.querySelector('.detail-role'), kind + '|' + P.id + '|' + (kind === 'n' ? 'tag' : 'role'));\n      }"
_A_FN = "  var decT = null;\n"


def active(brief) -> bool:
    return bool(table(brief)) or bool(brief.chip_legend)


def patch_manual(js: str, brief) -> str:
    """manual_edit's script with the label field, button and legend editor in it (only when the page has labels or a legend)."""
    if not active(brief) or _A_FIELD not in js or _A_CALL not in js or _A_FN not in js:
        return js
    js = js.replace(_A_FIELD, FIELD_JS + _A_FIELD, 1)
    js = js.replace(_A_CALL, _A_CALL[:-len("      }")] + CALL_JS + "      }", 1)
    return js.replace(_A_FN, FN_JS + _A_FN, 1)
