"""Detail-page features first built by hand into the Torts preview (2026-09-26,
versions 2-13) and ported here so a rebuild keeps them: ALTO-001, 003, 004,
006, 008, 009, 010, 011, 012 and 013 in the engine issue log.

The general features (the back-to-previous-page control, the banner
clearance, auto-linking — builder._add_tail) go on every page. They were once
gated to outline and index pages because Terrarium's private page sat within a
kilobyte of the 1,000,000-byte cap; private pages are now stored gzipped (see
private_shell.MAX_PAGE_BYTES), so that gate is gone. What stays specific is
specific by nature: the outline pieces need an outline, the index pages need
a `hide_nav` axis.

Build-time pieces (source notes, citations, the autolink table) are plain
Python and cost nothing at runtime; the runtime pieces are JS strings in the
same style as blocks.py's glue.
"""
from __future__ import annotations

import json
import re
from urllib.parse import quote

from .brief import PROVENANCE, Section
from .sanitize import esc

# ── outline: a hub sits above its own children (ALTO-001) ───────────────────
# The engine hook (engine_patches: outline-hub-above-children) calls this from
# inside initLayout's resolver loop; layout.resolve() runs the same pass so the
# baseY hints already satisfy it. 90 = layout.HUB_DROP.
HUBS_ABOVE_GLUE = """
window._altoHubsAbove = function(pos, h){
  var par = (window._ALTO_OUTLINE||{}).parent || {}, moved = false;
  Object.keys(par).forEach(function(id){
    var p = par[id]; if(pos[p]==null || pos[id]==null) return;
    var need = pos[p]-(h[p]||0)/2 + 90 + (h[id]||0)/2;
    if(pos[id] < need-0.5){ pos[id] = need; moved = true; }
  });
  return moved;
};"""

# ── outline: a node's page names it (ALTO-004) ──────────────────────────────
# "Liable" appears under every concept, so a page titled only "Liable" says
# nothing. A title shared by several nodes is prefixed with its parent's.
NODE_NAME_GLUE = """
window._altoNodeName = function(n){
  var par = (window._ALTO_OUTLINE||{}).parent || {}, p = par[n.id];
  if(!p || NODES_SRC.filter(function(x){ return x.title===n.title; }).length < 2) return n.title;
  var pn = NODES_SRC.filter(function(x){ return x.id===p; })[0];
  return pn ? pn.title+': '+n.title : n.title;
};"""

# ── outline: an element's page as a tree (ALTO-003) ─────────────────────────
# Each concept the element touches, at its outline depth and number; under it,
# its outcome leaves — a leaf of a different kind (tag) from the concept that
# holds it, e.g. Liable / Not Liable under a Concept — with the cases decided
# each way. Replaces a flat list that mixed concepts with context-free
# "Liable" rows. Everything shown is the material's own titles and text.
ELEMENT_TREE = """
function _altoElementTree(members){
  var O = window._ALTO_OUTLINE || {}, num = O.num || {}, par = O.parent || {}, kids = O.kids || {};
  var byId = {}; NODES_SRC.forEach(function(n){ byId[n.id]=n; });
  var isM = {}; members.forEach(function(n){ isM[n.id]=1; });
  function isOut(n){ var p = byId[par[n.id]]; return !!(p && !(kids[n.id]||[]).length && n.tag && n.tag!==p.tag); }
  var rows = [], seen = {}, outs = {}, nOut = 0, outTag = '';
  members.forEach(function(n){
    if(isOut(n)){
      nOut++; outTag = outTag || n.tag;
      var p = par[n.id]; (outs[p]=outs[p]||[]).push(n);
      if(!seen[p]){ seen[p]=1; rows.push(byId[p]); }
    } else if(!seen[n.id]){ seen[n.id]=1; rows.push(n); }
  });
  var order = NODES_SRC.map(function(n){ return n.id; });
  rows.sort(function(a,b){ return order.indexOf(a.id)-order.indexOf(b.id); });
  var nCon = members.length-nOut, nn = String(_ALTO_NODE_NOUN||'Concept').toLowerCase(), ot = outTag.toLowerCase();
  var meta = '<div class="doc-meta">'+nCon+' '+nn+(nCon===1?'':'s')
    + (nOut ? ' &middot; '+nOut+' '+ot+(nOut===1?'':'s') : '') + '</div>';
  function depth(id){ return Math.max(0, String(num[id]||'').split('.').filter(Boolean).length-1); }
  return meta + rows.map(function(c){
    var faint = !isM[c.id];
    var h = '<div class="el-row" style="margin-left:'+(depth(c.id)*22)+'px'+(faint?';opacity:.7':'')+'">'
      + '<div><span class="el-num">'+(num[c.id]||'')+'</span>'
      + '<span class="alto-link el-title" data-sd-type="node" data-sd-id="'+c.id+'">'+(c.title||'')+'</span></div>'
      + (c.desc && !faint ? '<div class="doc-row-d">'+c.desc+'</div>' : '');
    (outs[c.id]||[]).forEach(function(o){
      var t = String(o.title||''), cls = /^liable$/i.test(t) ? 'el-liable' : /^not liable$/i.test(t) ? 'el-not' : '';
      var cases = (o.envs||[]).filter(function(e){ return ENVS[e]; }).map(function(e){
        return '<span class="alto-link" data-sd-type="env" data-sd-id="'+e+'">'+ENVS[e].name+'</span>'; }).join(', ');
      h += '<div class="el-out"><span class="alto-link el-verdict '+cls+'" data-sd-type="node" data-sd-id="'+o.id+'">'+t+'</span>'
        + (o.desc ? ' <span class="el-out-d">'+o.desc+'</span>' : '')
        + (cases ? '<div class="el-cases">'+cases+'</div>' : '') + '</div>';
    });
    return h + '</div>';
  }).join('');
}"""

ELEMENT_TREE_CSS = (
    "\n  .el-row{padding:10px 0 10px 12px;border-left:2px solid var(--border);margin-bottom:6px;line-height:1.6;}"
    "\n  .el-num{display:inline-block;min-width:3.4em;color:var(--muted);font-variant-numeric:tabular-nums;font-size:.9em;}"
    "\n  .el-title{font-weight:600;}"
    "\n  .el-out{margin:8px 0 0 3.4em;padding:6px 10px;border-radius:6px;"
    "background:color-mix(in srgb, var(--text) 4%, transparent);font-size:.94em;}"
    "\n  .el-verdict{font-weight:700;font-size:.82em;letter-spacing:.08em;text-transform:uppercase;}"
    "\n  .el-liable{color:#dc2626;} .el-not{color:#16a34a;}"
    "\n  html.dark .el-liable{color:#f87171;} html.dark .el-not{color:#4ade80;}"
    "\n  .el-out-d{opacity:.85;}"
    "\n  .el-cases{margin-top:4px;font-size:.92em;opacity:.95;}"
    "\n  html.mobile .el-out{margin-left:0;}")

# ── index pages for a big axis (ALTO-006) ───────────────────────────────────
# A hide_nav axis (a course's cases) has a page per value but no way in except
# a card chip. showDetail('index', 'env'|'theme') lists every value, grouped
# under the concept (outline) or band (linear) it is attached to, each linking
# to its page and to where it appears. _ALTO_AXES carries the labels, the
# optional source line and each value's citation, all built in Python.
AXIS_INDEX_GLUE = """
function showAxisIndex(kind){ window.showDetail('index', kind); }
function _altoAxisIndex(kind){
  var A = (window._ALTO_AXES||{})[kind]; if(!A) return;
  var reg = kind==='env' ? ENVS : THEMES, field = kind==='env' ? 'envs' : 'themes';
  var O = window._ALTO_OUTLINE, num = (O && O.num) || {}, par = (O && O.parent) || {};
  var byId = {}; NODES_SRC.forEach(function(n){ byId[n.id]=n; });
  // An outcome leaf files under the concept it belongs to; a linear page files by band.
  function home(n){
    if(!O){ var a = (typeof NODE_ACT!=='undefined' && NODE_ACT[n.id]!=null) ? NODE_ACT[n.id] : 0;
      return {id:'act-'+a, title:(PHASE_META[a]||{}).label||'', band:true}; }
    var p = byId[par[n.id]];
    return (p && !((O.kids||{})[n.id]||[]).length && n.tag && n.tag!==p.tag) ? p : n;
  }
  var groups = [], gi = {}, seen = {};
  NODES_SRC.forEach(function(n){
    (n[field]||[]).forEach(function(eid){
      if(!reg[eid]) return;
      var c = home(n);
      if(!gi.hasOwnProperty(c.id)){ gi[c.id]=groups.length; groups.push({c:c, rows:[], at:{}}); }
      var g = groups[gi[c.id]];
      if(!g.at.hasOwnProperty(eid)){ g.at[eid]=g.rows.length; g.rows.push({id:eid, via:[]}); }
      g.rows[g.at[eid]].via.push(n); seen[eid]=1;
    });
  });
  var loose = Object.keys(reg).filter(function(k){ return !seen[k]; });
  var color = kind==='env' ? 'var(--env-color)' : 'var(--theme-color)', cites = A.cites || {};
  function blurb(e){
    var ok = (e.sections||[]).filter(function(x){ return x && x.t && x.h!==A.citeH && x.h!=='Source notes'; });
    var s = ok[0];
    if((A.blurb||[]).length) s = ok.filter(function(x){ return A.blurb.indexOf(String(x.h).toLowerCase())>=0; })[0];
    if(!s) return '';
    var t = String(s.t).replace(/<[^>]+>/g,'');
    return t.length>220 ? t.slice(0,217).replace(/\\s+\\S*$/,'')+'\\u2026' : t;
  }
  function row(eid, via){
    var e = reg[eid], b = blurb(e);
    var links = (via||[]).map(function(n){
      var c = home(n), lab = (c!==n && !c.band) ? c.title+' \\u2014 '+n.title : n.title;
      return '<span class="alto-link" data-sd-type="node" data-sd-id="'+n.id+'">'+(num[n.id]?num[n.id]+' ':'')+lab+'</span>';
    }).join(' &middot; ');
    return '<div class="doc-row" style="cursor:default">'
      + '<span class="alto-link doc-row-t" data-sd-type="'+kind+'" data-sd-id="'+eid+'">'+e.name+'</span>'
      + (cites[eid] ? ' <span class="doc-row-tag">&middot; '+cites[eid]+'</span>' : '')
      + (b ? '<div class="doc-row-d">'+b+'</div>' : '')
      + (links ? '<div class="doc-row-d" style="margin-top:4px"><span class="doc-rel-lab">Appears in:</span> '+links+'</div>' : '')
      + '</div>';
  }
  var total = Object.keys(reg).length;
  var html = '<div class="detail-header"><div class="detail-symbol" style="color:'+color+'">'+A.sym+'</div><div>'
    + '<div class="detail-name" style="color:'+color+'">'+A.label+'</div>'
    + '<div class="detail-role">'+total+' '+A.unit+' &middot; in '+(O?'outline':'timeline')+' order</div>'
    + '<div class="detail-badge '+(kind==='env'?'badge-env':'badge-theme')+'">Index</div></div></div>';
  (A.top||[]).forEach(function(s){ html += '<div class="detail-section"><h3>'+s.h+'</h3><p>'+s.t+'</p></div>'; });
  groups.forEach(function(g){
    var head = g.c.band ? g.c.title
      : '<span class="alto-link" data-sd-type="node" data-sd-id="'+g.c.id+'">'+(num[g.c.id]?num[g.c.id]+' ':'')+g.c.title+'</span>';
    html += '<div class="detail-section"><h3>'+head+'</h3>' + g.rows.map(function(r){ return row(r.id, r.via); }).join('') + '</div>';
  });
  if(loose.length) html += '<div class="detail-section"><h3>Not yet attached to '+(O?'a concept':'anything')+'</h3>'
    + loose.map(function(k){ return row(k, []); }).join('') + '</div>';
  window._currentDetailType = null; window._currentDetailId = null; _currentNodeId = null;
  updateNodeNavBar(null, null);
  _closeAllPanels();
  var pill = document.getElementById('timeline-return-pill');
  if(pill){ pill.style.display = 'block'; if(typeof _updateReturnPillPos==='function') _updateReturnPillPos(); }
  document.getElementById('canvas').style.display = 'none';
  document.getElementById('detail-page').classList.add('visible');
  document.querySelectorAll('.nav-btn').forEach(function(b){ b.classList.toggle('active', b.getAttribute('data-axis-index')===kind); });
  document.getElementById('detail-content').innerHTML = html;
  document.getElementById('detail-page').scrollTop = 0;
}"""

# Links out of the page: source docs, casebook pages. Also used by provenance tags.
NOTE_LINK_CSS = (
    "\n  .note-link{color:inherit;text-decoration:underline;"
    "text-decoration-color:color-mix(in srgb, var(--accent) 55%, transparent);text-underline-offset:2px;}"
    "\n  .note-link:hover{color:var(--accent);}"
    "\n  .ns-item{display:block;position:relative;padding-left:1.1em;margin:0 0 .55em;line-height:1.75;}"
    "\n  .ns-item::before{content:\"\\2022\";position:absolute;left:0;color:var(--muted);}"
    "\n  .ns-src{font-size:.72em;letter-spacing:.06em;text-transform:uppercase;"
    "color:var(--muted);white-space:nowrap;margin-left:4px;}")

PROV_CSS = ("\n  .sec-prov{margin-left:8px;padding:1px 6px;border:1px solid var(--border);"
            "border-radius:8px;font-size:.85em;letter-spacing:.08em;opacity:.85;}")

# ── ← Back to <previous page> (ALTO-008) ────────────────────────────────────
# A link INSIDE a detail page that opens another detail page pushes the page
# it left; the control walks back one page at a time. Any other way of opening
# a page (nav bar, card, prev/next) or leaving the detail view clears the
# trail. Desktop: a segment in #desktop-banner-row beside Back to Overview;
# mobile: a floating pill. Must be the outermost showDetail wrapper, so it is
# emitted after every other one (end of body).
BACK_PREV = """<style id="alto-back-prev-css">
html:not(.mobile) #desktop-banner-row > .dbr-prev{ background:#2f5d3a; max-width:46vw; }
html:not(.mobile).dark #desktop-banner-row > .dbr-prev{ background:#1f3e2a; }
html:not(.mobile) #desktop-banner-row > .dbr-back:not([hidden]) + .dbr-prev{ border-left:1px solid rgba(255,255,255,.28); }
#alto-back-prev .bp-t{ overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
html.mobile #alto-back-prev{ position:fixed; left:50%; transform:translateX(-50%); bottom:calc(16px + env(safe-area-inset-bottom,0px));
  z-index:300; max-width:calc(100vw - 110px); display:flex; align-items:center; gap:6px; padding:10px 16px; border:0; border-radius:20px;
  background:#2f5d3a; color:#fff; font:14px Georgia,serif; box-shadow:0 6px 20px rgba(0,0,0,.28); }
html.mobile.dark #alto-back-prev{ background:#1f3e2a; }
html.mobile #alto-back-prev[hidden]{ display:none; }
html.printing #alto-back-prev{ display:none !important; }
</style>
<script id="alto-back-prev-js">
(function(){
  var root=document.documentElement, stack=[], fromDetail=false, goingBack=false;
  function mark(e){ var t=e.target; fromDetail=!!(t&&t.closest&&t.closest('#detail-content')); }
  document.addEventListener('mousedown', mark, true);
  document.addEventListener('touchstart', mark, true);
  document.addEventListener('click', function(e){ var t=e.target; if(t&&t.closest&&t.closest('#detail-content')) fromDetail=true; }, true);
  function btn(){
    var b=document.getElementById('alto-back-prev');
    if(b) return b;
    b=document.createElement('button'); b.id='alto-back-prev'; b.type='button'; b.setAttribute('hidden','');
    b.addEventListener('click', function(e){
      e.stopPropagation();
      var prev=stack.pop(); if(!prev) return;
      goingBack=true;
      try{ window.showDetail(prev.type, prev.id); }finally{ goingBack=false; }
    });
    var row=document.getElementById('desktop-banner-row');
    if(row && !root.classList.contains('mobile')){ b.className='dbr-seg dbr-prev'; row.appendChild(b); }
    else document.body.appendChild(b);
    return b;
  }
  function sync(){
    var b=btn(), top=stack[stack.length-1], dp=document.getElementById('detail-page');
    var open=dp && dp.classList.contains('visible');
    if(top && open){
      b.innerHTML='<span>&larr;</span><span class="bp-t">Back to '+top.title.replace(/[<&]/g,function(c){return c==='<'?'&lt;':'&amp;';})+'</span>';
      b.title='Back to '+top.title;
      b.removeAttribute('hidden');
    } else { b.setAttribute('hidden',''); if(!open) stack=[]; }
    var row=document.getElementById('desktop-banner-row');
    if(row && b.parentNode===row && !b.hasAttribute('hidden')) row.classList.add('active');
  }
  function current(){
    var dp=document.getElementById('detail-page'), nm=document.querySelector('#detail-content .detail-name');
    if(!dp || !dp.classList.contains('visible') || !nm || !window._altoPageNow) return null;
    return {type:window._altoPageNow.type, id:window._altoPageNow.id, title:(nm.textContent||'').trim()};
  }
  var prevFn=window.showDetail;
  window.showDetail=function(type,id){
    var was=current(), hop=fromDetail && !goingBack;
    fromDetail=false;
    var r=prevFn.apply(this, arguments);
    window._altoPageNow={type:type,id:id};
    if(!goingBack){
      if(hop && was && !(was.type===type && was.id===id)) stack.push(was);
      else if(!hop) stack=[];
    }
    try{ sync(); }catch(e){}
    return r;
  };
  var dp0=document.getElementById('detail-page');
  if(dp0) new MutationObserver(function(){ if(!dp0.classList.contains('visible')){ stack=[]; window._altoPageNow=null; } try{ sync(); }catch(e){} })
    .observe(dp0,{attributes:true,attributeFilter:['class']});
  // Other banner segments toggling must not collapse the row while this one shows.
  function watchRow(){
    var row=document.getElementById('desktop-banner-row'); if(!row){ return setTimeout(watchRow,300); }
    new MutationObserver(function(){ var b=document.getElementById('alto-back-prev');
      if(b && b.parentNode===row && !b.hasAttribute('hidden') && !row.classList.contains('active')) row.classList.add('active'); })
      .observe(row,{attributes:true,attributeFilter:['class']});
  }
  watchRow();
})();
</script>"""

# ── banner row clears the page title (ALTO-009) ─────────────────────────────
# #desktop-banner-row is fixed at top:175px, centred, over the detail page. A
# long title ("Johnson v. Wills Memorial Hospital & Nursing Home") runs under
# it. When the row would sit on the header's text, drop it to just below that
# text, inside the header above its divider, growing the header's bottom
# padding if the gap is too small. Measures through html{zoom}; a no-op when
# nothing overlaps.
BANNER_CLEARANCE = """<script id="alto-banner-clearance">
(function(){
  var root=document.documentElement;
  function hdr(){ return document.querySelector('#detail-content .detail-header'); }
  function reset(row){ if(row) row.style.top=''; var h=hdr(); if(h && h._altoPad!=null){ h.style.paddingBottom=''; h._altoPad=null; } }
  function place(){
    var row=document.getElementById('desktop-banner-row');
    if(!row || root.classList.contains('mobile')) return;
    var dp=document.getElementById('detail-page'), h=hdr();
    if(!row.classList.contains('active') || !dp || !dp.classList.contains('visible') || !h){ reset(row); return; }
    row.style.top='';
    if(h._altoPad!=null){ h.style.paddingBottom=''; h._altoPad=null; }
    var rr=row.getBoundingClientRect(); if(!rr.height) return;
    var k=rr.height/(row.offsetHeight||rr.height);              // rect px per CSS px (html zoom)
    var texts=h.querySelectorAll('.detail-name,.detail-role,.detail-badge'), hit=false, bottom=-1e9;
    Array.prototype.forEach.call(texts,function(t){
      var r=t.getBoundingClientRect(); if(!r.height) return;
      var range=document.createRange(); range.selectNodeContents(t); var ir=range.getBoundingClientRect();
      var L=ir.width?ir.left:r.left, R=ir.width?ir.right:r.right;   // the text's ink, not its block
      bottom=Math.max(bottom,r.bottom);
      if(L<rr.right+6*k && R>rr.left-6*k && r.top<rr.bottom+4*k && r.bottom>rr.top-4*k) hit=true;
    });
    if(!hit) return;
    var gap=14*k, want=bottom+gap;
    var cur=parseFloat(getComputedStyle(row).top)||0;
    row.style.top=(cur+(want-rr.top)/k)+'px';
    var need=want+rr.height+gap-h.getBoundingClientRect().bottom;
    if(need>0){ var pad=parseFloat(getComputedStyle(h).paddingBottom)||0; h._altoPad=pad; h.style.paddingBottom=(pad+need/k)+'px'; }
  }
  window._altoPlaceBanner=place;
  function later(){ requestAnimationFrame(function(){ place(); requestAnimationFrame(place); }); }
  var prevFn=window.showDetail;
  window.showDetail=function(){ var r=prevFn.apply(this,arguments); later(); return r; };
  function wire(){
    var dp=document.getElementById('detail-page'), row=document.getElementById('desktop-banner-row');
    if(!dp || !row){ return setTimeout(wire,300); }
    dp.addEventListener('scroll', place, {passive:true});
    window.addEventListener('resize', later);
    new MutationObserver(later).observe(row,{attributes:true,childList:true,subtree:true,attributeFilter:['class','hidden']});
    new MutationObserver(later).observe(dp,{attributes:true,attributeFilter:['class']});
  }
  wire();
})();
</script>"""

# ── mentions in running text link to their page (ALTO-010) ─────────────────
# Walks the text of the open detail page and the Overview after each render
# and wraps every name in _ALTO_AUTOLINK.names (built below from the material:
# full names, generated short forms, authored aliases) and every "§ N"
# reference in _ALTO_AUTOLINK.sec. A § number several values share links only
# where the page itself points at one of them. Never links a page to itself;
# card bodies are left alone (a link would fight the card's own click).
AUTOLINK = """<script id="alto-autolink">
(function(){
  var L=window._ALTO_AUTOLINK; if(!L) return;
  var names=L.names||{}, sec=L.sec||{};
  var keys=Object.keys(names).sort(function(a,b){ return b.length-a.length; });
  var esc=function(t){ return t.replace(/[.*+?^${}()|[\\]\\\\]/g,'\\\\$&'); };
  var RE=keys.length ? new RegExp('(^|[^A-Za-z-])('+keys.map(esc).join('|')+')(?![A-Za-z])','g') : null;
  var SRE=/\\u00a7\\s?(\\d+[A-Z]?)(\\([a-z]\\))?(\\s*\\((?:2d|3d)\\))?/g;
  var SKIP='a,button,.alto-link,.hc-link,.ov-node-link,.char-chip,.note-link,[data-sd-id],[data-goto],h1,script,style,textarea,.detail-name,.ns-src';
  function texts(root, test){
    var w=document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null), out=[], t;
    while((t=w.nextNode())){ if(t.nodeValue && test(t.nodeValue) && t.parentElement && !t.parentElement.closest(SKIP)) out.push(t); }
    return out;
  }
  function wrap(tn, re, resolve){
    var v=tn.nodeValue, frag=document.createDocumentFragment(), last=0, m;
    re.lastIndex=0;
    while((m=re.exec(v))){
      var lead=m[1]&&re===RE?m[1].length:0, hit=resolve(m); if(!hit) continue;
      var start=m.index+lead, txt=re===RE?m[2]:m[0];
      frag.appendChild(document.createTextNode(v.slice(last,start)));
      var sp=document.createElement('span'); sp.className='alto-link autolink';
      sp.setAttribute('data-sd-type',hit[0]); sp.setAttribute('data-sd-id',hit[1]); sp.textContent=txt;
      frag.appendChild(sp); last=start+txt.length;
    }
    if(!last) return;
    frag.appendChild(document.createTextNode(v.slice(last)));
    tn.parentNode.replaceChild(frag, tn);
  }
  function link(root, selfId, near){
    if(!root) return;
    if(RE) texts(root, function(v){ RE.lastIndex=0; return RE.test(v); }).forEach(function(tn){
      wrap(tn, RE, function(m){ var h=names[m[2]]; return h && h[1]!==selfId ? h : null; });
    });
    texts(root, function(v){ return v.indexOf('\\u00a7')>=0; }).forEach(function(tn){
      wrap(tn, SRE, function(m){
        var ids=sec['\\u00a7'+m[1]]; if(!ids) return null;
        var id=ids.length===1 ? ids[0] : ids.filter(function(i){ return near[i]; })[0];
        return id && id!==selfId ? ['theme', id] : null;
      });
    });
  }
  // The theme values this page points at, for a § number several share.
  function nearOf(type, id){
    var near={}, NS=(typeof NODES_SRC!=='undefined')?NODES_SRC:[];
    NS.forEach(function(n){
      var on = type==='node' ? n.id===id : type==='char' ? (n.chars||[]).indexOf(id)>=0
        : type==='env' ? (n.envs||[]).indexOf(id)>=0 : type==='theme' ? (n.themes||[]).indexOf(id)>=0 : false;
      if(on) (n.themes||[]).forEach(function(t){ near[t]=1; });
    });
    return near;
  }
  var prev=window.showDetail;
  window.showDetail=function(type,id){
    var r=prev.apply(this, arguments);
    try{ link(document.getElementById('detail-content'), (type==='env'||type==='theme'||type==='char')?id:null, nearOf(type,id)); }catch(e){}
    return r;
  };
  function ov(){ if(L.ov===false) return; try{ link(document.getElementById('summary-inner'), null, {}); }catch(e){} }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', ov); else ov();
})();
</script>"""

_CORP_SUFFIX = re.compile(r",? (?:Inc|Co|Corp|Ry|Ltd|L\.?L\.?C|R\. ?Co)\.?$")
_V_RE = re.compile(r"^(.+?) v\. (.+)$")
_SEC_RE = re.compile(r"§\s?(\d+[A-Z]?)")


def autolink_table(b) -> dict:
    """{names: {text: [type, id]}, sec: {"§8A": [theme ids]}} from the material.

    Generated short forms: a case's name without a trailing corporate suffix,
    and the first party of "X v. Y" when no other value in the page shares
    it. Authored aliases win over generated ones. A generated form that is
    ambiguous is dropped rather than guessed."""
    names: dict = {}
    taken: dict = {}          # generated short form → owners (to drop collisions)
    on = set(b.autolink)
    families = [(k, vals) for k, vals in (
        ("env", b.axes[0].values if len(b.axes) > 0 else []),
        ("theme", b.axes[1].values if len(b.axes) > 1 else [])) if k in on]
    for kind, values in families:
        for v in values:
            full = v.name.strip()
            if len(full) >= 4:
                names[full] = [kind, v.id]
            forms = {}          # ordered: the page must build byte-identically
            short = _CORP_SUFFIX.sub("", full)
            if short != full:
                forms[short] = 1
            m = _V_RE.match(short)
            if m and kind == "env":
                first = re.sub(r"^(The|In re) ", "", m.group(1)).strip()
                if len(first) >= 4:
                    forms[first] = 1
            if full.startswith("The ") and len(full) > 8:
                forms[full[4:]] = 1
            for f in forms:
                taken.setdefault(f, set()).add((kind, v.id))
    # A surname that is also a party to some other case ("Williams" in both
    # "Williams v. Hays" and "Mohr v. Williams") names neither reliably.
    parties: dict = {}
    for kind, values in families:
        for v in values:
            m = _V_RE.match(_CORP_SUFFIX.sub("", v.name.strip()))
            if m:
                for side in (m.group(1), m.group(2)):
                    parties.setdefault(side.strip(), set()).add(v.id)
    for f, owners in taken.items():
        others = parties.get(f, set()) - {o[1] for o in owners}
        if len(owners) == 1 and f not in names and not others:
            names[f] = list(next(iter(owners)))
    for kind, values in families:
        for v in values:
            for a in v.aliases:
                names[a.strip()] = [kind, v.id]
    if "char" in on:
        # A character by full name, and by a first or last name no other
        # character shares ("Ada" for Ada Reyes; not a surname two characters
        # carry — an alias settles that one).
        parts: dict = {}
        for e in b.entities:
            words = e.name.split()
            if len(words) > 1:
                for w in (words[0], words[-1]):
                    parts.setdefault(w, set()).add(e.id)
        for e in b.entities:
            if len(e.name.strip()) >= 3:
                names[e.name.strip()] = ["char", e.id]
        for w, owners in parts.items():
            if len(owners) == 1 and len(w) >= 3 and w not in names:
                names[w] = ["char", next(iter(owners))]
        for e in b.entities:
            for a in e.aliases:
                names[a.strip()] = ["char", e.id]
    # A name of a kind that is NOT linked, but contains a linked one
    # ("Hale House", a setting, holds "Hale", a character), is matched whole
    # and left alone, so its first word does not link to the wrong page.
    others = [e.name for e in b.entities] if "char" not in on else []
    for k, ax in (("env", b.axes[0] if len(b.axes) > 0 else None),
                  ("theme", b.axes[1] if len(b.axes) > 1 else None)):
        if ax and k not in on:
            others += [v.name for v in ax.values]
    for o in others:
        o = o.strip()
        if o not in names and any(re.search(r"(?<![A-Za-z])" + re.escape(n)
                                            + r"(?![A-Za-z])", o) for n in names):
            names[o] = None
    sec: dict = {}
    for v in (dict(families).get("theme") or []):
        for k in dict.fromkeys(_SEC_RE.findall(v.name)):
            sec.setdefault("§" + k, []).append(v.id)
    # Names are escaped text by now (sanitize ran); the walker sees decoded
    # text, so match on the decoded form.
    import html as _h
    return {"names": {_h.unescape(k): v for k, v in names.items()}, "sec": sec,
            "ov": b.autolink_overview}


# ── build-time sections: citations and source notes (ALTO-011/012/013) ──────

def _chapter_num(ch: str) -> str:
    m = re.search(r"\d+", ch or "")
    return m.group(0) if m else ""


def cite_html(ax, v, short: bool) -> str:
    """A value's citation as page text, linked when the axis has a cite_link
    and the chapter has a known section. "" when the value has no cite."""
    c = v.cite or {}
    if not c:
        return ""
    if c.get("note") and not c.get("p"):
        return (c.get("short") or c["note"]) if short else c["note"]
    page = c.get("p", "")
    label = f"p. {page}"
    tl = ax.cite_link or {}
    if tl.get("url") and page:
        num = _chapter_num(c.get("ch", ""))
        secs = tl.get("sections") or {}
        if "{sec}" not in tl["url"] or num in secs:
            url = (tl["url"].replace("{sec}", quote(str(secs.get(num, "")), safe=""))
                   .replace("{p}", quote(str(page), safe="")))
            label = (f'<a class="note-link" href="{esc(url)}" target="_blank" '
                     f'rel="noopener">{label}</a>')
    ch = c.get("ch", "")
    if short:
        n = _chapter_num(ch)
        return (f"Ch. {n}, {label}" if n else label)
    return f"{ch}, {label}" if ch else label


def cite_heading(ax) -> str:
    return esc((ax.cite_link or {}).get("label") or "Citation")


def source_section(ids, docs_by_id) -> "Section | None":
    """"Source notes": the documents a page was built from, linked when the
    manifest gave a url. Google Docs can deep-link only to headings and
    bookmarks, so a document-level link is the reliable default."""
    items = []
    for sid in dict.fromkeys(ids or []):
        d = docs_by_id.get(sid)
        if not d:
            continue
        name = d["name"]
        items.append(
            f'<span class="ns-item"><a class="note-link" href="{esc(d["url"])}" '
            f'target="_blank" rel="noopener">{name}</a></span>' if d.get("url")
            else f'<span class="ns-item">{name}</span>')
    return Section(h="Source notes", t="".join(items)) if items else None


def prov_heading(s) -> str:
    """A section heading with its provenance tag (ALTO-014)."""
    if not s.prov or (s.h or "").strip().lower() == PROVENANCE[s.prov].lower():
        return s.h
    return f'{s.h}<span class="sec-prov">{PROVENANCE[s.prov]}</span>'


def outline_overview(b, nodes) -> str:
    """ALTO-005: an outline build with no authored overview gets one assembled
    from the outline itself — a heading per band, and under it each concept of
    the first two levels, linked, with its own one-line description. Nothing is
    written that the nodes do not already say. Emitted in the same deep-link
    form sanitize produces, so the Overview's link upgrader handles it."""
    kids: dict = {}
    for n in nodes:
        if n.parent:
            kids.setdefault(n.parent, []).append(n)

    def chip(n):
        return (f'<span class="ov-node-link">{n.title}<button class="ov-node-btn" '
                f"onclick=\"showDetail('node','{n.id}')\"></button></span>")

    out = ["<h2>Overview</h2>"]
    for i, a in enumerate(b.acts):
        roots = [n for n in nodes if n.act == i and not n.parent]
        if not roots:
            continue
        out.append(f"<h2>{a.short or a.label}</h2>")
        for r in roots:
            line = chip(r) + (f" — {r.desc}" if r.desc else "")
            out.append(f"<p>{line}</p>")
            for c in kids.get(r.id, []):
                sub = kids.get(c.id, [])
                tail = ""
                if sub:
                    tail = " Covers " + ", ".join(chip(s) for s in sub) + "."
                out.append(f"<p>{chip(c)}{(' — ' + c.desc) if c.desc else ''}{tail}</p>")
    return "\n".join(out)


def axes_config(b, index_axes) -> str:
    """window._ALTO_AXES for the index pages: label, glyph, source line, and
    each value's short citation."""
    docs = {d["id"]: d for d in b.source_docs}
    cfg = {}
    for kind, ax in index_axes:
        src = source_section(ax.sources, docs)
        top = [{"h": s.h, "t": s.t} for s in ax.index_sections if s.t]
        if src:
            top.append({"h": "Source", "t": src.t})
        cfg[kind] = {
            "label": ax.label,
            "unit": (ax.singular or ax.label).lower() + ("" if (ax.singular or "").endswith("s") else "s"),
            "sym": "&#9670;" if kind == "env" else "&#167;",
            "top": top,
            "blurb": [h.lower() for h in ax.index_blurb],
            "citeH": cite_heading(ax),
            "cites": {v.id: cite_html(ax, v, True) for v in ax.values if v.cite},
        }
    return ("\nwindow._ALTO_AXES=" + json.dumps(cfg, ensure_ascii=False)
            .replace("</", "<\\/") + ";")
