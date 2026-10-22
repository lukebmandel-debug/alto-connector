"""Imported backgrounds: a picture of the user's own, added to their background library.

A page names a background by id and never carries its picture (a private page is one
Firestore document, private_shell.MAX_PAGE_BYTES). The built-in photographs are files
on the site (/bg/v{BG_V}/); an imported one is the account's own, so it lives where
the rest of the account does, under users/{uid} in Firestore (alto-cloud.js `bgLib`):

  users/{uid}/bglib/{id}   {e, t, del}   the library entry (JSON text, with a small
                                         thumbnail), when it last changed, removed?
  users/{uid}/bgimg/{id}   {d, type, t}  the picture: Bytes, resized and compressed
                                         in the browser to fit one document

and in the browser as the library (localStorage LIB_KEY, {id: entry}, read by the
page's head script before first paint) and the bytes (IndexedDB 'alto-bg-lib', an
ArrayBuffer per id: WebKit refuses to keep a Blob in a private window). An entry is
shaped like a photograph of the catalogue (backgrounds.client_catalog, k "p") plus
`u: 1`, so it is drawn by the same code, in every format and look that draws a photograph;
its picture is a blob: address made from the bytes.

Everything else is this file, LIB_JS, served from the site root (backgrounds.LIB_PATH)
and loaded by the page only when its picker opens or an imported background is in use:
the "Yours" section of the picker, the Import view (choose or drop a file, place and
zoom it in a preview the shape of the window, name it), resizing to EDGE px on the long
side and compressing to WebP (JPEG where the browser cannot write WebP) under MAX_BYTES,
the luminance measurements that tune the veil (a port of backgrounds.tune), rename and
remove (asked first), and every error explained in place with what to do about it.
Changing this file changes no page: the script is served no-cache, by a fixed name.
"""
from __future__ import annotations

import json

from .backgrounds import LIB_KEY, LIB_PATH

EDGE = 2560                 # the long side of a stored picture, at most
MAX_BYTES = 950_000         # what the picture's document may hold (Firestore: 1 MiB per document)
MAX_FILE = 60 * 1024 * 1024  # a file larger than this is refused before it is opened

LIB_JS = r"""(function(){
  var B=window._altoBg; if(!B || window._altoBgLib) return;
  var root=document.documentElement, LK=__LIBKEY__, DBN='alto-bg-lib', EDGE=__EDGE__, MAXB=__MAXB__, MAXF=__MAXF__;
  var U=window._altoBgU=window._altoBgU||{}, tried={}, pulled=null, sec=null, view=null, mng=null;

  // ── the account (alto-cloud.js); a share is a frame, whose page has it in the parent ──
  function cloudWin(){ try{ if(window.AltoCloud) return window; if(parent!==window && parent.AltoCloud) return parent; }catch(e){} return null; }
  function AC(){ var w=cloudWin(), c=w && w.AltoCloud; return c && c.enabled && c.bgLib ? c : null; }
  function authed(){
    var c=AC(), w=cloudWin(); if(!c) return Promise.reject(new Error('not-configured'));
    if(c.known) return c.user ? Promise.resolve(c) : Promise.reject(new Error('signed-out'));
    return new Promise(function(res, rej){
      var to=setTimeout(function(){ rej(new Error('signed-out')); }, 15000);
      w.addEventListener('alto-auth', function f(){ w.removeEventListener('alto-auth', f); clearTimeout(to); c.user ? res(c) : rej(new Error('signed-out')); });
    });
  }
  function within(p, ms){ return Promise.race([p, new Promise(function(_, rej){ setTimeout(function(){ rej(new Error('timeout')); }, ms); })]); }

  // ── this browser's copies: the library (localStorage) and the pictures (IndexedDB) ──
  function readLib(){ try{ return JSON.parse(localStorage.getItem(LK)||'{}')||{}; }catch(e){ return {}; } }
  function writeLib(L){ localStorage.setItem(LK, JSON.stringify(L)); B.apply(B.read()); redraw(); }
  function idbDo(mode, f){
    return new Promise(function(res, rej){
      var q=indexedDB.open(DBN, 1);
      q.onupgradeneeded=function(){ q.result.createObjectStore('img'); };
      q.onerror=function(){ rej(q.error); };
      q.onsuccess=function(){
        var db=q.result, tx=db.transaction('img', mode), r=f(tx.objectStore('img'));
        tx.oncomplete=function(){ db.close(); res(r && r.result); };
        tx.onerror=tx.onabort=function(){ db.close(); rej(tx.error); };
      };
    });
  }
  function idbGet(id){ return idbDo('readonly', function(s){ return s.get(id); }); }
  function idbPut(id, v){ return idbDo('readwrite', function(s){ return s.put(v, id); }); }
  function idbDel(id){ return idbDo('readwrite', function(s){ return s.delete(id); }).catch(function(){}); }
  function forget(id){ idbDel(id); if(U[id]){ try{ URL.revokeObjectURL(U[id]); }catch(e){} delete U[id]; } }

  // An imported picture on screen: this browser's copy, else the account's (kept here for next time).
  function load(id){
    if(U[id] || tried[id]) return; tried[id]=1;
    idbGet(id).catch(function(){ return null; }).then(function(v){
      if(v && v.buf) return v;
      return authed().then(function(c){ return c.bgLib.bytes(id); }).then(function(r){
        if(!r) return null;
        var u8=r.bytes, v2={buf:u8.buffer.slice(u8.byteOffset, u8.byteOffset+u8.byteLength), type:r.type};
        idbPut(id, v2).catch(function(){});
        return v2;
      });
    }).then(function(v){
      if(!v) return;
      U[id]=URL.createObjectURL(new Blob([v.buf], {type:v.type})); B.apply(B.read());
    }).catch(function(){ delete tried[id]; });        // offline or signed out: its colour stays, and a later sign-in tries again
  }

  // The account's library is the truth: what it lists comes here, what it removed goes (with its picture).
  function pull(){
    if(pulled) return pulled;
    var t0=Date.now();
    pulled=authed().then(function(c){ return within(c.bgLib.list(), 20000); }).then(function(rows){
      var L=readLib(), N={};
      rows.forEach(function(r){ if(r.del || !r.e) return; try{ var e=JSON.parse(r.e); if(e && e.k==='p'){ e.t=r.t; N[r.id]=e; } }catch(x){} });
      Object.keys(L).forEach(function(id){ if(!N[id] && (L[id].t||0)>=t0) N[id]=L[id]; });     // imported here a moment ago
      Object.keys(L).forEach(function(id){ if(!N[id]) forget(id); });
      if(JSON.stringify(N)!==JSON.stringify(L)) writeLib(N);
      return N;
    });
    pulled.catch(function(){ pulled=null; });
    return pulled;
  }
  (function(){ var w=cloudWin(); if(w) w.addEventListener('alto-auth', function(){ pulled=null; tried={}; pull().catch(function(){}); B.apply(B.read()); }); })();

  // ── what an import is: the luminance the veil is tuned from (backgrounds.tune, in the browser) ──
  function cl(v, lo, hi){ return Math.max(lo, Math.min(hi, v)); }
  function hex(c){ return '#'+c.map(function(v){ return ('0'+Math.round(cl(v,0,255)).toString(16)).slice(-2); }).join(''); }
  function rgbOf(h){ var n=parseInt(h.slice(1),16); return [n>>16&255, n>>8&255, n&255]; }
  function mixc(a, b, t){ return [0,1,2].map(function(i){ return a[i]*(1-t)+b[i]*t; }); }
  function tune(p, dark){
    var b, v, veil, m, h, lo;
    if(dark){
      b=p.L50<=.30 ? 1 : Math.max(.55, .30/p.L50); m=p.L50*b; h=p.L90*b;
      v=cl(Math.max((m-.15)/Math.max(m-.04,.01), (h-.34)/Math.max(h-.04,.01), 0), .20, .70); veil=[8,10,18];
    } else {
      b=p.L50>=.55 ? 1 : Math.min(2, .55/Math.max(p.L50,.06)); m=Math.min(1,p.L50*b); lo=Math.min(1,p.L10*b);
      v=cl(Math.max((.70-m)/(.97-m), (.52-lo)/(.97-lo), 0), .10, .70); veil=[247,249,253];
    }
    function lift(c){ return rgbOf(c).map(function(x){ return Math.min(255, x*b); }); }
    return {b:+b.toFixed(2), v:+v.toFixed(2), q:hex(mixc(lift(p.mean), veil, v)), s:hex(mixc(lift(p.top), veil, v)), a:hex(lift(p.top))};
  }
  // L10/L50/L90 of a small (so, softened) copy, its mean colour, and the colour of its top edge
  function measure(cv){
    var w=48, h=Math.max(8, Math.round(48*cv.height/cv.width)), s=document.createElement('canvas'); s.width=w; s.height=h;
    var x=s.getContext('2d'); x.drawImage(cv, 0, 0, w, h);
    var d=x.getImageData(0, 0, w, h).data, L=[], sum=[0,0,0], top=[0,0,0], tn=0, rows=Math.max(1, Math.round(h*.08));
    for(var i=0, p=0; i<d.length; i+=4, p++){
      L.push((.299*d[i]+.587*d[i+1]+.114*d[i+2])/255); sum[0]+=d[i]; sum[1]+=d[i+1]; sum[2]+=d[i+2];
      if(Math.floor(p/w)<rows){ top[0]+=d[i]; top[1]+=d[i+1]; top[2]+=d[i+2]; tn++; }
    }
    L.sort(function(a,b){ return a-b; }); var n=L.length, q=function(f){ return L[Math.min(n-1, Math.floor(f*n))]; };
    return {L10:q(.1), L50:q(.5), L90:q(.9), mean:hex(sum.map(function(v){ return v/n; })), top:hex(top.map(function(v){ return v/tn; }))};
  }
  function toBlob(cv, type, q){ return new Promise(function(res){ cv.toBlob(function(b){ res(b); }, type, q); }); }
  // WebP where the browser can write it (Safari writes PNG when asked, so the answer is checked), else JPEG;
  // quality, then size, stepped down until the picture fits its document
  function encode(cv){
    var type='image/webp', qs=[.85,.78,.70,.62], i=0;
    function step(){
      return toBlob(cv, type, qs[i]).then(function(b){
        if(!b) throw new Error('encode');
        if(b.type!==type){ if(type==='image/jpeg') throw new Error('encode'); type='image/jpeg'; i=0; return step(); }
        if(b.size<=MAXB) return b;
        if(++i<qs.length) return step();
        var c2=document.createElement('canvas'); c2.width=Math.round(cv.width*.8); c2.height=Math.round(cv.height*.8);
        if(c2.width<320) throw new Error('too-large');
        c2.getContext('2d').drawImage(cv, 0, 0, c2.width, c2.height); cv=c2; i=0; return step();
      });
    }
    return step().then(function(b){ return {blob:b, w:cv.width, h:cv.height}; });
  }
  function rid(){ var a='abcdefghijklmnopqrstuvwxyz0123456789', s=''; var r=new Uint8Array(10); (window.crypto||{getRandomValues:function(x){ for(var i=0;i<x.length;i++) x[i]=Math.random()*256; return x; }}).getRandomValues(r); for(var i=0;i<10;i++) s+=a[r[i]%36]; return 'u:'+s; }
  function clean(n){ return String(n||'').replace(/[\u0000-\u001f\u2028\u2029]/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 60); }

  // ── the look ──
  var CSS=[
    // the style row (Classic | Retro): two halves of one pill, the chosen one filled
    '#bg-panel .bg-seg{display:flex;width:100%;border:1px solid var(--border);border-radius:9px;overflow:hidden;}',
    '#bg-panel .bg-segb{flex:1;font:inherit;font-size:12px;height:30px;border:0;background:transparent;color:var(--text);cursor:pointer;}',
    '#bg-panel .bg-segb+.bg-segb{border-left:1px solid var(--border);}',
    '#bg-panel .bg-segb.on{background:var(--accent,#6d5bd0);color:#fff;font-weight:600;}',
    'html.alto-retro #bg-panel .bg-seg{border-radius:0;border-color:rgba(217,174,85,.6);} html.alto-retro #bg-panel .bg-segb{font-family:"Avenir Next","Futura",system-ui,sans-serif;text-transform:uppercase;letter-spacing:.2em;font-size:11px;}',
    'html.alto-retro #bg-panel .bg-segb.on{background:#d9ae55;color:#000;}',
    '#bg-panel .bg-tile.bg-mine .bg-more{position:absolute;top:4px;right:4px;width:22px;height:22px;border-radius:50%;display:flex;align-items:center;justify-content:center;',
    ' font-size:13px;line-height:1;color:#fff;background:rgba(0,0,0,.45);opacity:0;transition:opacity .15s;cursor:pointer;}',
    '#bg-panel .bg-tile.bg-mine:hover .bg-more,#bg-panel .bg-tile.bg-mine:focus-within .bg-more,html.mobile #bg-panel .bg-more,#bg-panel .bg-tile.bg-mine.active .bg-more{opacity:1;}',
    '@media (hover:none){#bg-panel .bg-more{opacity:1 !important;}}',
    '#bg-panel .bg-tile.bg-add{background:var(--card-glass-bg,var(--surface));color:var(--text);display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;',
    ' border:1.5px dashed var(--muted);box-shadow:none;}',
    '#bg-panel .bg-tile.bg-add .bg-name{position:static;background:none;text-shadow:none;color:var(--text);padding:0;text-align:center;font-size:10.5px;}',
    '#bg-panel .bg-tile.bg-add svg{opacity:.8;}',
    '#bg-panel.bg-drop{outline:2px dashed var(--accent,#6d5bd0);outline-offset:-6px;}',
    '#bg-panel.bg-importing .bg-body>:not(.bg-imp){display:none !important;}',
    '#bg-panel.bg-importing .bg-foot,#bg-panel [hidden]{display:none !important;}',
    '#bg-panel .bg-imp{display:flex;flex-direction:column;gap:10px;font-size:12px;line-height:1.45;}',
    'html.mobile #bg-panel .bg-imp{padding:0 16px;}',
    '#bg-panel .bg-imp-top{display:flex;align-items:center;gap:8px;font-weight:600;font-size:12.5px;}',
    '#bg-panel .bg-btn{font:inherit;font-size:12px;padding:6px 12px;border-radius:999px;cursor:pointer;color:var(--text);background:var(--card-glass-bg,var(--surface));',
    ' border:1px solid var(--card-glass-border,var(--border));}',
    '#bg-panel .bg-btn:hover{border-color:var(--muted);}',
    '#bg-panel .bg-btn.bg-go{background:var(--accent,#6d5bd0);border-color:var(--accent,#6d5bd0);color:#fff;font-weight:600;}',
    '#bg-panel .bg-btn[disabled]{opacity:.5;cursor:default;}',
    '#bg-panel .bg-zone{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;text-align:center;padding:26px 14px;border-radius:12px;',
    ' border:1.5px dashed var(--muted);color:var(--muted);}',
    '#bg-panel .bg-zone b{color:var(--text);font-weight:600;}',
    '#bg-panel .bg-zone input{display:none;}',
    '#bg-panel .bg-fr{position:relative;width:100%;overflow:hidden;border-radius:10px;background:#000;cursor:grab;touch-action:none;box-shadow:0 0 0 1px var(--border);}',
    '#bg-panel .bg-fr.drag{cursor:grabbing;}',
    '#bg-panel .bg-fr img{position:absolute;max-width:none;user-select:none;-webkit-user-select:none;pointer-events:none;}',
    '#bg-panel .bg-fr .bg-vl{position:absolute;inset:0;pointer-events:none;}',
    '#bg-panel .bg-fr .bg-hint{position:absolute;left:8px;bottom:8px;font-size:10.5px;color:#fff;background:rgba(0,0,0,.5);padding:2px 8px;border-radius:999px;pointer-events:none;}',
    '#bg-panel .bg-row{display:flex;align-items:center;gap:8px;}',
    '#bg-panel .bg-row input[type=range]{flex:1;}',
    '#bg-panel .bg-in{flex:1;min-width:0;font:inherit;font-size:12.5px;padding:6px 9px;border-radius:8px;color:var(--text);background:var(--surface);border:1px solid var(--border);}',
    '#bg-panel .bg-err{padding:8px 10px;border-radius:9px;color:var(--text);background:color-mix(in srgb,#e5484d 14%,transparent);border:1px solid color-mix(in srgb,#e5484d 45%,transparent);}',
    '#bg-panel .bg-err .bg-btn{margin-top:6px;}',
    '#bg-panel .bg-note{color:var(--muted);font-size:11px;}',
    '#bg-panel .bg-mng{margin-top:8px;padding:9px 10px;border-radius:10px;font-size:12px;line-height:1.45;background:var(--card-glass-bg,var(--surface));border:1px solid var(--card-glass-border,var(--border));}',
    '#bg-panel .bg-mng .bg-row{margin-top:7px;flex-wrap:wrap;}',
    '#bg-panel .bg-foot .bg-lnk{background:none;border:0;padding:0;font:inherit;color:inherit;text-decoration:underline;cursor:pointer;}'
  ].join('\n');
  function style(){ if(document.getElementById('alto-bglib-css')) return; var s=document.createElement('style'); s.id='alto-bglib-css'; s.textContent=CSS; (document.head||root).appendChild(s); }
  function el(tag, cls, txt){ var e=document.createElement(tag); if(cls) e.className=cls; if(txt!=null) e.textContent=txt; return e; }
  function btn(txt, cls, f){ var b=el('button', 'bg-btn'+(cls ? ' '+cls : ''), txt); b.type='button'; b.addEventListener('click', function(e){ e.stopPropagation(); f(e); }); return b; }
  var PLUS='<svg viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10 13V4M6.5 7.5L10 4l3.5 3.5"/><path d="M3.5 12.5v2.5a1.5 1.5 0 0 0 1.5 1.5h10a1.5 1.5 0 0 0 1.5-1.5v-2.5"/></svg>';

  // ── what went wrong, and what to do about it ──
  function why(e, ctx){
    var m=String(e && (e.code || e.message) || e || '');
    if(!navigator.onLine || /offline|unavailable|network/i.test(m)) return {t:"You're offline, so your account can't be reached. Connect to the internet, then "+(ctx||'try again')+'.'};
    if(/not-configured/.test(m)) return {t:"This page isn't connected to an Alto account, so there's nowhere private to keep a picture. Open this timeline from your Alto homepage and import it there."};
    if(/signed-out|unauthenticated/.test(m)) return {t:'Sign in to keep your own backgrounds. They are saved privately in your account, so every device of yours has them.', signIn:true};
    if(/timeout|deadline/i.test(m)) return {t:"Your account didn't answer in time. Check your connection, then "+(ctx||'try again')+'.'};
    if(/permission/i.test(m)) return {t:'Your account refused the change. Sign out and back in (account menu), then '+(ctx||'try again')+'.', signIn:true};
    if(/too-large/.test(m)) return {t:"This picture doesn't get small enough to keep, even shrunk. Try a different picture, or crop this one tighter with Zoom."};
    if(/QuotaExceeded|quota/i.test(m)) return {t:"This browser's storage for Alto is full. Remove a background you no longer use, then "+(ctx||'try again')+'.'};
    return {t:'Something went wrong ('+m.slice(0,120)+'). '+(ctx ? 'Please '+ctx+'.' : 'Please try again.')};
  }
  function errBox(host, w){
    var b=el('div', 'bg-err'); b.setAttribute('role', 'alert'); b.appendChild(el('div', null, w.t));
    if(w.signIn){ var c=AC(); if(c && c.signIn) b.appendChild(btn('Sign in', 'bg-go', function(){ try{ c.signIn(); }catch(e){} })); }
    host.textContent=''; host.appendChild(b); host.hidden=false;
  }

  // ── the picker's "Yours" section ──
  function picker(s){ sec=s; style(); styles(); drop(); redraw(); pull().catch(function(){}); }
  // the page's style, Classic | Retro (retro.py): a timeline's head script keeps the choice (window._altoStyle); its row heads the picker
  function styles(){
    var S=window._altoStyle, ui=B.ui; if(!S || !ui || document.getElementById('bg-style')) return;
    var row=el('div', 'bg-sec'), seg=el('div', 'bg-seg'); row.id='bg-style'; seg.setAttribute('role', 'group'); seg.setAttribute('aria-label', 'Style');
    function mark(){ var c=S.get(); [].forEach.call(seg.children, function(b){ var on=b.getAttribute('data-sty')===c; b.classList.toggle('on', on); b.setAttribute('aria-pressed', on ? 'true' : 'false'); }); }
    [['classic', 'Classic'], ['retro', 'Retro']].forEach(function(v){
      var b=el('button', 'bg-segb', v[1]); b.type='button'; b.setAttribute('data-sty', v[0]);
      b.title=v[0]==='retro' ? 'Retro: black and gold, like a vintage space poster' : 'Classic: Alto\u2019s own look, with the background below';
      b.addEventListener('click', function(e){ e.stopPropagation(); S.set(v[0]); mark(); }); seg.appendChild(b); });
    row.appendChild(el('div', 'bg-h', 'Style')); row.appendChild(seg); ui.body.insertBefore(row, ui.body.firstChild); mark();
  }
  function order(L){ return Object.keys(L).sort(function(a, b){ return (L[b].c||0)-(L[a].c||0); }); }
  function redraw(){
    var ui=B.ui; if(!sec || !ui) return;
    for(var i=ui.tiles.length-1; i>=0; i--) if(ui.tiles[i]._yours) ui.tiles.splice(i, 1);
    var L=readLib(); sec.textContent='';
    sec.appendChild(el('div', 'bg-h', 'Yours'));
    var g=el('div', 'bg-grid'), add=el('button', 'bg-tile bg-add'); add.type='button'; add.innerHTML=PLUS; add.appendChild(el('span', 'bg-name', 'Import'));
    add.setAttribute('aria-label', 'Import a background of your own'); add.title='Import a picture (JPG, PNG, WebP or HEIC), or drop one here';
    add.addEventListener('click', function(e){ e.stopPropagation(); openImport(); });
    g.appendChild(add);
    order(L).forEach(function(id){
      var t=ui.tile(id, L[id]); t._yours=1; t.classList.add('bg-mine');
      var m=el('span', 'bg-more', '\u22ef'); m.setAttribute('role', 'button'); m.setAttribute('aria-label', 'Rename or remove '+L[id].n); m.title='Rename or remove';
      m.addEventListener('click', function(e){ e.stopPropagation(); e.preventDefault(); manage(id); });
      t.appendChild(m); g.appendChild(t);
    });
    sec.appendChild(g);
    mng=el('div', 'bg-mng'); mng.hidden=true; sec.appendChild(mng);
    ui.mark();
  }
  // the credit line of an imported background in use
  function credit(id, foot){
    var L=readLib(), e=L[id]; if(!e) return;
    foot.textContent=e.n+' \u2014 your own picture, private to your account \u00b7 ';
    var r=el('button', 'bg-lnk', 'Rename'); r.type='button'; r.addEventListener('click', function(ev){ ev.stopPropagation(); manage(id, 'rename'); });
    var x=el('button', 'bg-lnk', 'Remove'); x.type='button'; x.addEventListener('click', function(ev){ ev.stopPropagation(); manage(id, 'remove'); });
    foot.appendChild(r); foot.appendChild(document.createTextNode(' \u00b7 ')); foot.appendChild(x);
  }
  // rename or remove one of the account's own (a built-in has no such controls); removing is asked first
  function manage(id, what){
    var e=readLib()[id]; if(!e || !mng) return;
    mng.hidden=false; mng.textContent='';
    var note=el('div', 'bg-note'); note.hidden=true;
    function done(){ mng.hidden=true; mng.textContent=''; }
    if(what==='remove'){
      mng.appendChild(el('div', null, 'Remove \u201c'+e.n+'\u201d from your backgrounds? It goes from every device of yours, and any timeline using it goes back to the Alto wallpaper.'));
      var row=el('div', 'bg-row'), yes=btn('Remove', 'bg-go', function(){
        yes.disabled=true; note.hidden=false; note.className='bg-note'; note.textContent='Removing\u2026';
        authed().then(function(c){ return within(c.bgLib.remove(id), 20000); }).then(function(){
          var L=readLib(); delete L[id]; forget(id); done(); writeLib(L);
        }).catch(function(err){ yes.disabled=false; errBox(note, why(err, 'press Remove again')); });
      });
      row.appendChild(yes); row.appendChild(btn('Keep it', '', done)); mng.appendChild(row); mng.appendChild(note);
      mng.scrollIntoView && mng.scrollIntoView({block:'nearest'});
      return;
    }
    if(what!=='rename'){
      mng.appendChild(el('div', null, e.n));
      var r0=el('div', 'bg-row'); r0.appendChild(btn('Rename', '', function(){ manage(id, 'rename'); })); r0.appendChild(btn('Remove\u2026', '', function(){ manage(id, 'remove'); }));
      r0.appendChild(btn('Close', '', done)); mng.appendChild(r0);
      mng.scrollIntoView && mng.scrollIntoView({block:'nearest'});
      return;
    }
    var row2=el('div', 'bg-row'), inp=el('input', 'bg-in'); inp.type='text'; inp.value=e.n; inp.maxLength=60; inp.setAttribute('aria-label', 'Name');
    function save(){
      var n=clean(inp.value); if(!n){ inp.focus(); return; }
      if(n===e.n){ done(); return; }
      var e2=JSON.parse(JSON.stringify(e)); e2.n=n; e2.l.n=n; e2.d.n=n; e2.t=Date.now();
      sv.disabled=true; note.hidden=false; note.textContent='Saving\u2026';
      authed().then(function(c){ return within(c.bgLib.rename(id, e2), 20000); }).then(function(){
        var L=readLib(); if(L[id]){ L[id]=e2; } done(); writeLib(L);
      }).catch(function(err){ sv.disabled=false; errBox(note, why(err, 'press Save again')); });
    }
    inp.addEventListener('keydown', function(ev){ ev.stopPropagation(); if(ev.key==='Enter') save(); if(ev.key==='Escape') done(); });
    var sv=btn('Save', 'bg-go', save);
    row2.appendChild(inp); row2.appendChild(sv); row2.appendChild(btn('Cancel', '', done));
    mng.appendChild(el('div', null, 'Rename this background')); mng.appendChild(row2); mng.appendChild(note);
    setTimeout(function(){ try{ inp.focus(); inp.select(); }catch(x){} }, 30);
  }

  // drop a picture anywhere on the open picker
  function drop(){
    var p=B.ui && B.ui.panel; if(!p || p._bgDrop) return; p._bgDrop=1;
    function files(e){ var t=e.dataTransfer; return t && [].indexOf.call(t.types||[], 'Files')>=0; }
    p.addEventListener('dragover', function(e){ if(!files(e)) return; e.preventDefault(); e.dataTransfer.dropEffect='copy'; p.classList.add('bg-drop'); });
    p.addEventListener('dragleave', function(e){ if(e.target===p) p.classList.remove('bg-drop'); });
    p.addEventListener('drop', function(e){
      if(!files(e)) return; e.preventDefault(); p.classList.remove('bg-drop');
      var f=e.dataTransfer.files && e.dataTransfer.files[0]; if(f) openImport(f);
    });
  }

  // ── the Import view, in place of the picker's tiles ──
  function closeImport(){
    var ui=B.ui; if(view && view.parentNode) view.parentNode.removeChild(view); view=null;
    if(ui && ui.panel) ui.panel.classList.remove('bg-importing');
    if(src && src.url){ try{ URL.revokeObjectURL(src.url); }catch(e){} } src=null;
  }
  var src=null;
  function openImport(file){
    var ui=B.ui; if(!ui) return; style(); closeImport();
    view=el('div', 'bg-imp'); ui.panel.classList.add('bg-importing'); ui.body.insertBefore(view, ui.body.firstChild); ui.body.scrollTop=0;
    var top=el('div', 'bg-imp-top'); top.appendChild(btn('\u2190 Back', '', closeImport)); top.appendChild(el('span', null, 'Import a background')); view.appendChild(top);
    var msg=el('div'); msg.hidden=true;
    var zone=el('label', 'bg-zone'), inp=el('input'); inp.type='file';
    inp.accept='image/jpeg,image/png,image/webp,image/heic,image/heif,.jpg,.jpeg,.png,.webp,.heic,.heif';
    zone.innerHTML=PLUS.replace(/18/g, '26'); zone.appendChild(el('b', null, 'Choose a picture')); zone.appendChild(el('span', null, 'or drop one here'));
    zone.appendChild(el('span', 'bg-note', 'JPG, PNG, WebP or HEIC. It is kept privately in your account and stays on every device of yours.'));
    zone.appendChild(inp);
    inp.addEventListener('change', function(){ var f=inp.files && inp.files[0]; inp.value=''; if(f) take(f, view, msg, zone); });
    view.appendChild(zone); view.appendChild(msg);
    var c=AC();
    if(!c) errBox(msg, why(new Error('not-configured')));
    else if(c.known && !c.user) errBox(msg, why(new Error('signed-out')));
    if(file) take(file, view, msg, zone);
  }
  function isHeic(f){ return /hei[cf]/i.test(f.type||'') || /\.hei[cf]$/i.test(f.name||''); }
  function take(f, host, msg, zone){
    msg.hidden=true;
    var mb=(f.size/1048576).toFixed(f.size<10485760 ? 1 : 0);
    if(f.size>MAXF){ errBox(msg, {t:'That file is '+mb+' MB; Alto opens pictures up to '+Math.round(MAXF/1048576)+' MB. Choose a smaller copy of it (on a Mac, Preview \u2192 File \u2192 Export makes one).'}); return; }
    var ok=/^image\/(jpeg|pjpeg|png|webp|heic|heif|avif)$/i.test(f.type||'') || /\.(jpe?g|png|webp|hei[cf]|avif)$/i.test(f.name||'');
    if(!ok){ var ext=((f.name||'').match(/\.([a-z0-9]+)$/i)||[])[1]; errBox(msg, {t:'\u201c'+(f.name||'That file')+'\u201d is '+(ext ? 'a .'+ext.toLowerCase()+' file' : 'not a picture')+', which Alto can\u2019t use as a background. Choose a JPG, PNG, WebP or HEIC picture.'}); return; }
    var url=URL.createObjectURL(f), im=new Image();
    im.onload=function(){
      if(!im.naturalWidth){ im.onerror(); return; }
      if(src && src.url && src.url!==url){ try{ URL.revokeObjectURL(src.url); }catch(e){} }
      src={im:im, url:url, w:im.naturalWidth, h:im.naturalHeight, name:clean((f.name||'').replace(/\.[a-z0-9]+$/i, '').replace(/[_-]+/g, ' ')) || 'My background'};
      editor(host, msg, zone);
    };
    im.onerror=function(){
      try{ URL.revokeObjectURL(url); }catch(e){}
      errBox(msg, {t: isHeic(f)
        ? 'This browser can\u2019t open HEIC photos. Import it from Safari, which can, or save the photo as JPEG first (in Photos: File \u2192 Export).'
        : '\u201c'+(f.name||'That file')+'\u201d couldn\u2019t be opened as a picture; it may be damaged or not really an image. Try another, or save it again as JPG.'});
    };
    im.src=url;
  }
  // place it: drag to choose what sits in the middle of the window, zoom to crop in, name it, save
  function editor(host, msg, zone){
    zone.hidden=true;
    var old=host.querySelector('.bg-ed'); if(old) old.parentNode.removeChild(old);
    var ed=el('div', 'bg-ed'); ed.style.cssText='display:flex;flex-direction:column;gap:10px;';
    var fr=el('div', 'bg-fr'), im=el('img'), vl=el('div', 'bg-vl'); im.src=src.url; im.alt=''; im.draggable=false;
    var hint=el('span', 'bg-hint', 'Drag to place'); fr.appendChild(im); fr.appendChild(vl); fr.appendChild(hint);
    // the shape of the open window under the top bars, so what is shown is what the timeline will show
    var bars=0; ['title-bar','nav'].forEach(function(i){ var e=document.getElementById(i); if(e){ var q=e.getBoundingClientRect(); if(q.height>0 && q.bottom>bars) bars=q.bottom; } });
    var ar=cl(window.innerWidth/Math.max(120, window.innerHeight-bars), .45, 2.6);
    fr.style.aspectRatio=String(ar.toFixed(3));
    var st={fx:.5, fy:.5, z:1}, stats=null;
    try{ var mc=document.createElement('canvas'); mc.width=96; mc.height=Math.max(8, Math.round(96*src.h/src.w)); mc.getContext('2d').drawImage(src.im, 0, 0, mc.width, mc.height); stats=measure(mc); }catch(e){}
    function look(){
      if(!stats) return; var t=tune(stats, root.classList.contains('dark'));
      im.style.filter='brightness('+t.b+') blur(1px) saturate(1.15)';
      vl.style.background=(root.classList.contains('dark') ? 'rgba(8,10,18,' : 'rgba(247,249,253,')+t.v+')';
    }
    function draw(){
      var W=fr.clientWidth, H=fr.clientHeight; if(!W || !H) return;
      var s=Math.max(W/src.w, H/src.h)*st.z, iw=src.w*s, ih=src.h*s;
      st.fx=cl(st.fx, W/2/iw, 1-W/2/iw); st.fy=cl(st.fy, H/2/ih, 1-H/2/ih);
      im.style.width=iw+'px'; im.style.height=ih+'px';
      im.style.left=Math.min(0, Math.max(W-iw, W/2-st.fx*iw))+'px'; im.style.top=Math.min(0, Math.max(H-ih, H/2-st.fy*ih))+'px';
      st.iw=iw; st.ih=ih;
    }
    var drag=null;
    fr.addEventListener('pointerdown', function(e){ drag={x:e.clientX, y:e.clientY}; fr.classList.add('drag'); hint.hidden=true; try{ fr.setPointerCapture(e.pointerId); }catch(x){} e.preventDefault(); });
    fr.addEventListener('pointermove', function(e){ if(!drag) return; st.fx-=(e.clientX-drag.x)/st.iw; st.fy-=(e.clientY-drag.y)/st.ih; drag={x:e.clientX, y:e.clientY}; draw(); });
    function up(){ drag=null; fr.classList.remove('drag'); }
    fr.addEventListener('pointerup', up); fr.addEventListener('pointercancel', up);
    fr.addEventListener('wheel', function(e){ e.preventDefault(); e.stopPropagation(); st.z=cl(st.z*(e.deltaY<0 ? 1.06 : 1/1.06), 1, 4); zr.value=st.z; draw(); }, {passive:false});
    var zrow=el('div', 'bg-row'), zr=el('input'); zr.type='range'; zr.min='1'; zr.max='4'; zr.step='0.01'; zr.value='1'; zr.setAttribute('aria-label', 'Zoom');
    zr.addEventListener('input', function(){ st.z=+zr.value; draw(); });
    zrow.appendChild(el('span', 'bg-note', 'Zoom')); zrow.appendChild(zr);
    var nrow=el('div', 'bg-row'), nm=el('input', 'bg-in'); nm.type='text'; nm.maxLength=60; nm.value=src.name; nm.setAttribute('aria-label', 'Name');
    nm.addEventListener('keydown', function(e){ e.stopPropagation(); if(e.key==='Enter') save(); });
    nrow.appendChild(el('span', 'bg-note', 'Name')); nrow.appendChild(nm);
    var small=Math.max(src.w, src.h)<1200 ? el('div', 'bg-note', 'This picture is small ('+src.w+' \u00d7 '+src.h+'), so it may look soft behind a large window.') : null;
    var arow=el('div', 'bg-row'), go=btn('Save and use', 'bg-go', save), again=btn('Choose another', '', function(){ ed.parentNode.removeChild(ed); zone.hidden=false; msg.hidden=true; });
    arow.appendChild(go); arow.appendChild(again);
    var note=el('div', 'bg-note'); note.hidden=true;
    ed.appendChild(fr); ed.appendChild(zrow); ed.appendChild(nrow); if(small) ed.appendChild(small); ed.appendChild(arow); ed.appendChild(note);
    host.appendChild(ed); host.appendChild(msg);
    look(); requestAnimationFrame(draw); setTimeout(draw, 60);
    new MutationObserver(function(){ if(view) look(); }).observe(root, {attributes:true, attributeFilter:['class']});
    function save(){
      msg.hidden=true;
      if(!navigator.onLine){ errBox(msg, why(new Error('offline'), 'press Save and use again \u2014 your picture is still here')); return; }
      go.disabled=true; again.disabled=true; note.hidden=false; note.textContent='Preparing your picture\u2026';
      var name=clean(nm.value)||src.name, z=st.z, cw=src.w/z, ch=src.h/z;
      var cx=cl(st.fx*src.w-cw/2, 0, src.w-cw), cy=cl(st.fy*src.h-ch/2, 0, src.h-ch);
      var fx=cl((st.fx*src.w-cx)/cw, 0, 1), fy=cl((st.fy*src.h-cy)/ch, 0, 1);
      var k=Math.min(1, EDGE/Math.max(cw, ch)), cv=document.createElement('canvas'); cv.width=Math.max(1, Math.round(cw*k)); cv.height=Math.max(1, Math.round(ch*k));
      var id=rid(), now=Date.now(), entry, out;
      Promise.resolve().then(function(){
        var x=cv.getContext('2d'); x.imageSmoothingQuality='high'; x.drawImage(src.im, cx, cy, cw, ch, 0, 0, cv.width, cv.height);
        return encode(cv);
      }).then(function(o){
        out=o; var p=measure(cv);
        // the tile: 240px wide, cut around the chosen middle
        var tw=240, th=150, tc=document.createElement('canvas'); tc.width=tw; tc.height=th;
        var s=Math.max(tw/cv.width, th/cv.height), iw=cv.width*s, ih=cv.height*s;
        tc.getContext('2d').drawImage(cv, cl(tw/2-fx*iw, tw-iw, 0), cl(th/2-fy*ih, th-ih, 0), iw, ih);
        var thumb=tc.toDataURL('image/jpeg', .72);
        function side(dark){ var t=tune(p, dark); return {n:name, f:'', w:o.w, h:o.h, x:+fx.toFixed(3), y:+fy.toFixed(3), by:'', lic:'', u:'', m:p.mean, b:t.b, v:t.v, q:t.q, s:t.s, a:t.a}; }
        entry={g:'Yours', k:'p', u:1, n:name, c:now, t:now, th:thumb, l:side(false), d:side(true)};
        note.textContent='Saving to your account\u2026';
        return o.blob.arrayBuffer ? o.blob.arrayBuffer() : new Response(o.blob).arrayBuffer();
      }).then(function(buf){
        out.buf=buf;
        return authed().then(function(c){ return within(c.bgLib.put(id, entry, new Uint8Array(buf), out.blob.type), 45000); });
      }).then(function(){
        // this browser's copy before anything else: a reload straight after must find it here
        return idbPut(id, {buf:out.buf, type:out.blob.type}).catch(function(){});
      }).then(function(){
        U[id]=URL.createObjectURL(out.blob);
        var L=readLib(); L[id]=entry;
        try{ localStorage.setItem(LK, JSON.stringify(L)); }catch(e){}
        closeImport(); B.choose(id); redraw();
      }).catch(function(err){
        go.disabled=false; again.disabled=false; note.hidden=true;
        errBox(msg, why(err, 'press Save and use again'));
      });
    }
  }

  window._altoBgLib={load:load, pull:pull, picker:picker, credit:credit, manage:manage, open:openImport, tune:tune, measure:measure};
  pull().catch(function(){});
})();"""


def lib_js() -> str:
    """The hosted script, as the site serves it at backgrounds.LIB_PATH."""
    return (LIB_JS.replace("__LIBKEY__", json.dumps(LIB_KEY)).replace("__EDGE__", str(EDGE))
            .replace("__MAXB__", str(MAX_BYTES)).replace("__MAXF__", str(MAX_FILE)))


def site_file() -> tuple[str, str]:
    """(path under the site root, text) for publish_static."""
    return LIB_PATH.lstrip("/"), lib_js()
