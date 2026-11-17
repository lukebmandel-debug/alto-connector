"""Edit with Bass: the panel and the `#bass-edit=<timeline id>` reader, appended to the hosted bundle (bass_hosted_ext.py), so they exist only for the
one allowlisted account the gate serves the bundle to. A timeline page, a share, a public page and the default build carry none of this.

How it behaves (v1.9.235, security tier):
  * The hash is untrusted. It is read once, cleared at once (history.replaceState), matched against the one timeline-id pattern and used only as an opaque
    id: it is never put in markup (every string below reaches the page through textContent, never innerHTML).
  * Nothing spends by itself. The page asks the server one free question, `edit_open` (does this account own that id?). Only if the answer is
    {ok:true} does the panel open; anything else (signed out, not the owner, an id that does not exist, a refusal, a failure) shows NOTHING at all.
    Preview changes and Apply are each ONE click of the user's. Apply charges nothing; the panel says so. If a preview has to be made again
    (expired, or the timeline changed), the panel says that a new preview uses credits again BEFORE the click.
  * The look is all in CSS (CSS) and one build function (panel): restyle without touching the calls.

The panel's calls: edit_open, balance, edit_preview, edit_apply, edit_undo (bass_edit_ui talks to the same function URL as the rest of the bundle)."""
from __future__ import annotations

import json

TID_PATTERN = r"^[a-z][a-z0-9-]{0,47}$"          # alto.build.brief.ID_RE, the one timeline-id shape

CSS = """
.be-root{position:fixed;inset:0;z-index:8900;display:flex;align-items:center;justify-content:center;padding:20px;background:rgba(10,12,24,.5);font:14px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
.be-win{box-sizing:border-box;width:min(560px,100%);max-height:calc(100vh - 40px);max-height:calc(100dvh - 40px);overflow:auto;border-radius:16px;padding:18px 18px 16px;background:var(--surface,#fff);color:var(--text,#161a2b);box-shadow:0 18px 60px rgba(0,0,0,.35)}
html.dark .be-win{background:#14182a;color:#f1f3fa}
.be-h{display:flex;align-items:center;gap:10px;margin:0 0 4px}
.be-g{width:22px;height:28px;color:#8b6cf0;flex:none}
.be-t{margin:0;font-size:18px;font-weight:650;flex:1;min-width:0}
.be-x{flex:none;width:44px;height:44px;margin:-8px -10px -8px 0;border:0;background:none;color:inherit;font:inherit;font-size:18px;cursor:pointer;border-radius:12px}
.be-sub{margin:0 0 12px;opacity:.72;font-size:13px;overflow-wrap:anywhere}
.be-l{display:block;margin:10px 0 4px;font-weight:600}
.be-ta{box-sizing:border-box;width:100%;min-height:96px;resize:vertical;border:1px solid rgba(128,128,150,.45);border-radius:10px;padding:9px 10px;font:inherit;background:transparent;color:inherit}
.be-f{display:flex;flex-wrap:wrap;gap:6px;margin:6px 0 0}
.be-fi{display:inline-flex;align-items:center;gap:6px;padding:4px 8px;border-radius:8px;background:rgba(128,128,150,.16);font-size:13px;max-width:100%;overflow-wrap:anywhere}
.be-fx{border:0;background:none;color:inherit;cursor:pointer;font:inherit;min-width:32px;min-height:32px}
.be-note{margin:8px 0 0;font-size:13px;opacity:.78}
.be-cr{margin:10px 0 0;font-size:13px;font-weight:600}
.be-box{margin:10px 0 0;padding:10px 12px;border-radius:10px;background:rgba(139,108,240,.12)}
.be-box h3{margin:0 0 4px;font-size:13px;font-weight:650}
.be-box ul{margin:0 0 6px;padding-left:18px}
.be-act{display:flex;flex-wrap:wrap;gap:8px;justify-content:flex-end;margin:14px 0 0}
.be-btn{min-height:44px;min-width:44px;padding:0 16px;border:1px solid rgba(128,128,150,.45);border-radius:12px;background:transparent;color:inherit;font:inherit;cursor:pointer}
.be-btn.pri{background:#5b3fc4;border-color:#5b3fc4;color:#fff;font-weight:600}
.be-btn[disabled]{opacity:.45;cursor:default}
.be-err{margin:10px 0 0;padding:9px 12px;border-radius:10px;background:rgba(220,60,60,.12)}
@media print{.be-root{display:none}}
"""

# One literal glyph (the bass clef's small cut): replaced as ONE single-quoted literal, like every other markup in the bundle.
_JS = r"""(function(){
'use strict';
var d=document, W=window;
if(d.__altoBassEdit) return; d.__altoBassEdit=1;
var BASE=W._ALTO_BASS_BASE||'', TID=/__TID__/, KEY='bass-edit=', root=null, S=null, FMAX=5000000;
function str(v,n){ return typeof v==='string'?v.slice(0,n||400):''; }
function num(v){ v=+v; return isFinite(v)?v:0; }
function token(){ try{ var u=W.AltoCloud&&W.AltoCloud.user; return Promise.resolve(u&&u.getIdToken?u.getIdToken():null); }catch(e){ return Promise.resolve(null); } }
/* the one door: a parsed object, or null on ANY failure (no message to show, nothing to learn from a failure) */
function call(action,args){
  if(!BASE) return Promise.resolve(null);
  return token().then(function(t){ if(!t) return null;
    return fetch(BASE,{method:'POST',mode:'cors',credentials:'omit',cache:'no-store',referrerPolicy:'no-referrer',
      headers:{'content-type':'application/json','authorization':'Bearer '+t},body:JSON.stringify({action:action,args:args||{}})})
      .then(function(r){ return r.ok?r.json():null; }).then(function(j){ return (j&&typeof j==='object'&&!Array.isArray(j))?j:null; }); })
    .catch(function(){ return null; });
}
function el(tag,cls,text){ var e=d.createElement(tag); if(cls) e.className=cls; if(text!=null) e.textContent=text; return e; }
function btn(label,cls,fn){ var b=el('button','be-btn'+(cls?' '+cls:''),label); b.type='button'; b.addEventListener('click',fn); return b; }
function close(){ if(root){ root.remove(); root=null; d.removeEventListener('keydown',onKey,true); } S=null; }
function onKey(e){ if(e.key==='Escape'&&root){ e.stopPropagation(); close(); } }
function credits(r){ var c=r&&r.credits; return (c&&typeof c==='object'&&typeof c.balance==='number')?Math.floor(c.balance):(typeof c==='number'?Math.floor(c):null); }
function lab(n){ return n+' credit'+(n===1?'':'s'); }
function list(h,items,more){ if(!items||!items.length) return null; var b=el('div'); b.appendChild(el('h3',null,h)); var u=el('ul');
  items.slice(0,12).forEach(function(t){ u.appendChild(el('li',null,str(t,120))); }); if(more>items.length) u.appendChild(el('li',null,'and '+(more-items.length)+' more')); b.appendChild(u); return b; }

function mat(f){ var o={name:f.name,kind:'notes',text:f.text||''}; if(f.file_b64) o.file_b64=f.file_b64; else if(f.needs) o.needs_extraction=true; return o; }
function addFiles(list){ Array.prototype.forEach.call(list||[],function(f){ var n=str(f.name,120), isT=/\.(txt|md|markdown|csv|html?|rtf)$/i.test(n)||/^text\//.test(f.type), m={name:n,text:'',needs:!isT};
  S.files.push(m); if(isT){ var r=new FileReader(); r.onload=function(){ m.text=String(r.result||'').slice(0,200000); m.needs=false; }; r.readAsText(f); }
  else if(/\.(pdf|docx)$/i.test(n)&&f.size<=FMAX){ var r2=new FileReader(); r2.onload=function(){ var u=String(r2.result||''), i=u.indexOf(','); if(i>=0) m.file_b64=u.slice(i+1); }; r2.readAsDataURL(f); } }); draw(); }

function frame(){ var w=el('div','be-win'); w.setAttribute('role','dialog'); w.setAttribute('aria-modal','true'); w.setAttribute('aria-label','Edit with Bass');
  var h=el('div','be-h'), g=el('span','be-g'); g.innerHTML=__GLYPH__; h.appendChild(g); h.appendChild(el('h2','be-t','Edit with Bass')); var xb=el('button','be-x','\u2715'); xb.type='button'; xb.setAttribute('aria-label','Close'); xb.addEventListener('click',close); h.appendChild(xb); w.appendChild(h);
  w.appendChild(el('p','be-sub','Editing: '+S.title)); return w; }

function draw(){
  if(!root||!S) return; var keep=root.querySelector('.be-ta'); if(keep) S.text=keep.value;
  while(root.firstChild) root.removeChild(root.firstChild);
  var w=frame(), act=el('div','be-act'); root.appendChild(w);
  if(S.stage==='form'){
    w.appendChild(el('label','be-l','What should change?')).setAttribute('for','be-ta');
    var ta=el('textarea','be-ta'); ta.id='be-ta'; ta.maxLength=4000; ta.value=S.text||''; ta.placeholder='For example: add a card about consideration, and link it to the offer card.';
    ta.addEventListener('input',function(){ S.text=ta.value; go.disabled=!S.text.trim()||S.busy; }); w.appendChild(ta);
    w.appendChild(el('label','be-l','Files (optional)')).setAttribute('for','be-file');
    var fi=el('input'); fi.type='file'; fi.id='be-file'; fi.multiple=true; fi.accept='.pdf,.txt,.md,.doc,.docx,.rtf,.html'; fi.addEventListener('change',function(){ addFiles(fi.files); }); w.appendChild(fi);
    var fl=el('div','be-f'); S.files.forEach(function(f,i){ var c=el('span','be-fi',f.name), x=el('button','be-fx','✕'); x.type='button'; x.setAttribute('aria-label','Remove '+f.name);
      x.addEventListener('click',function(){ S.files.splice(i,1); draw(); }); c.appendChild(x); fl.appendChild(c); }); w.appendChild(fl);
    w.appendChild(el('p','be-cr',S.bal==null?'':'Credits remaining: '+S.bal));
    w.appendChild(el('p','be-note',S.again?'Making this preview again uses credits again. Applying it is free.':'Previewing uses some of your credits. Applying a preview is free, and you can undo it.'));
    if(S.err) w.appendChild(el('div','be-err',S.err));
    var go=btn(S.busy?'Working…':'Preview changes','pri',preview); go.disabled=!(S.text||'').trim()||!!S.busy;
    act.appendChild(btn('Cancel','',close)); act.appendChild(go);
  } else if(S.stage==='preview'){
    var r=S.result||{}, sm=r.summary||{}, c=sm.counts||{};
    w.appendChild(el('p','be-l','Here is what Bass would change'));
    var box=el('div','be-box'); [list('Added',sm.added,num(c.added)),list('Changed',sm.changed,num(c.changed)),list('Removed',sm.removed,num(c.removed))].forEach(function(x){ if(x) box.appendChild(x); });
    if(r.message) box.appendChild(el('p','be-note',str(r.message,600))); w.appendChild(box);
    var sp=r.credits&&r.credits.spent; w.appendChild(el('p','be-cr',(typeof sp==='number'?'This preview used '+lab(Math.round(sp))+'. ':'')+'Applying it uses no more credits.'));
    w.appendChild(el('p','be-note','Your timeline has not changed yet. This preview is kept for '+Math.round(num(r.expires_in)/60||15)+' minutes. If it runs out, previewing again uses credits again.'));
    if(S.err) w.appendChild(el('div','be-err',S.err));
    var ap=btn(S.busy?'Working…':'Apply','pri',apply); ap.disabled=!!S.busy;
    act.appendChild(btn('Discard','',function(){ S.stage='form'; S.again=false; S.err=''; S.result=null; draw(); })); act.appendChild(ap);
  } else if(S.stage==='done'){
    w.appendChild(el('div','be-box',str(S.msg,300)));
    if(S.canUndo) w.appendChild(el('p','be-note','Changed your mind? Undo puts your timeline back exactly as it was.'));
    if(S.err) w.appendChild(el('div','be-err',S.err));
    if(S.canUndo){ var un=btn(S.busy?'Working…':'Undo','',undo); un.disabled=!!S.busy; act.appendChild(un); }
    act.appendChild(btn('Close','pri',close));
  }
  w.appendChild(act);
  var f=w.querySelector('.be-ta,.be-btn.pri'); if(f&&f.focus&&!keep) try{ f.focus(); }catch(e){}
}
function why(r,fallback){ return r?(str(r.message,400)||fallback):'Bass could not be reached. Nothing was charged. Please try again.'; }
function preview(){
  if(S.busy||!(S.text||'').trim()) return; S.busy=true; S.err=''; draw();
  var my=S; call('edit_preview',{timeline_id:S.tid,text:S.text.trim(),materials:S.files.length?S.files.map(mat):undefined}).then(function(r){
    if(S!==my) return; S.busy=false; var b=credits(r); if(b!=null) S.bal=b;
    if(r&&r.ok===true&&r.changed===true&&typeof r.preview_id==='string'){ S.result=r; S.pid=r.preview_id; S.stage='preview'; }
    else if(r&&r.ok===true){ S.err=str(r.message,300)||'Bass found nothing to change.'; }
    else S.err=why(r,'Bass could not make that preview.');
    draw(); }); }
function apply(){
  if(S.busy||!S.pid) return; S.busy=true; S.err=''; draw();
  var my=S; call('edit_apply',{timeline_id:S.tid,preview_id:S.pid}).then(function(r){
    if(S!==my) return; S.busy=false; var b=credits(r); if(b!=null) S.bal=b;
    if(r&&r.ok===true){ S.stage='done'; S.msg=str(r.message,300)||'Your timeline was changed.'; S.canUndo=r.applied===true&&r.can_undo===true; S.pid=null; }
    else if(r&&(r.code==='edit_preview_gone'||r.code==='edit_stale')){ S.stage='form'; S.again=true; S.pid=null; S.result=null; S.err=why(r,''); }
    else S.err=why(r,'Bass could not save that change. Nothing was charged.');
    draw(); }); }
function undo(){
  if(S.busy) return; S.busy=true; S.err=''; draw();
  var my=S; call('edit_undo',{timeline_id:S.tid}).then(function(r){
    if(S!==my) return; S.busy=false;
    if(r&&r.ok===true){ S.msg=str(r.message,300)||'Your timeline is back the way it was.'; S.canUndo=false; } else S.err=why(r,'Bass could not undo that. Please try again.');
    draw(); }); }

function open(tid,title,can){
  close(); S={tid:tid,title:str(title,120),stage:'form',text:'',files:[],bal:null,busy:false,err:'',again:false,canUndo:false};
  root=el('div','be-root'); root.id='bass-edit-root'; root.addEventListener('click',function(e){ if(e.target===root) close(); });
  d.body.appendChild(root); d.addEventListener('keydown',onKey,true); draw();
  var my=S; call('balance',{}).then(function(r){ var b=credits(r); if(S===my&&b!=null){ S.bal=b; draw(); } });
}
/* the page's own entry: ask the one free question, and open ONLY on a clear yes */
function enter(tid){ if(!TID.test(tid)) return;
  call('edit_open',{timeline_id:tid}).then(function(r){ if(r&&r.ok===true&&r.status==='ok'&&typeof r.title==='string') open(tid,r.title,r.can_undo===true); }); }
W._altoBassEdit={open:enter};
/* #bass-edit=<id>: read once, cleared at once, only a well-formed id is used, never rendered */
(function(){ var h=''; try{ h=String(location.hash||''); }catch(e){}
  if(h.indexOf('#'+KEY)!==0) return;
  try{ history.replaceState(null,'',location.pathname+location.search); }catch(e){}
  var v=h.slice(KEY.length+1); if(TID.test(v)) enter(v); })();
})();
"""


def js(glyph_small: str) -> str:
    """The panel script with the one glyph literal and the one id pattern put in."""
    assert "'" not in glyph_small and "\\" not in glyph_small and "\n" not in glyph_small
    return _JS.replace("__TID__", TID_PATTERN).replace("__GLYPH__", "'" + glyph_small + "'")


def css_js() -> str:
    """The panel's style, as the script that adds it once."""
    return "(function(){var d=document;if(d.getElementById('alto-bass-edit-css'))return;var s=d.createElement('style');s.id='alto-bass-edit-css';s.textContent=" + json.dumps(" ".join(CSS.split())) + ";d.head.appendChild(s);})();\n"
