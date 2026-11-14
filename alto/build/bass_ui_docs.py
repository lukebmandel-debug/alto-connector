"""Bass UI: the Documents sheet (Luke's pick A, ORG notes/bass-documents-design-mock.html) and the "Using: Torts, 3 documents" line. Spliced into
the bundle's script at __DOCS__ (bass_ui._bundle), so it shares the bundle's door `call`, state `S` and helpers. Every change goes through
call('docs', {op, ...}): the proxy's library (alto/bass/documents.py) or, with no backend, the in-page simulator below (same ops, same silos).

  sheet      classes (each with its outlines and timelines), groups, "+ New class or group"; the chosen scope's files with a "Bass is using
             this" switch each, rename / move / delete under ⋯, a per-outline "Also use the <class> class documents" switch, Recently deleted
             (7 days) with Restore, the caps line ("3 of 20 files used") and the Anthropic line with the Privacy Policy link
  phone      one column: a scope picker on top, the files below (CSS only, nothing of the phone page is removed)
  using      in the edit panel and the wizard's upload step: which scope Bass reads, its documents as chips (the cross switches one off),
             "+ Add" opens the sheet; the scope rides on every spending call as scope_id (the proxy reads the documents itself)
Originals: when the page offers window.AltoCloud.putBassOriginal(path, file, type) (IT wires firebase-storage), the original is kept at the
path the proxy returns (storage.rules: owner only, listed only); without it Bass keeps the text only."""

DOCS_JS = r"""
/* ───────────────────────── Documents (bass_ui_docs.py) ───────────────────────── */
var DMAX=20, DAYS=7, DCH=60000;
var SIMLIB={scopes:{tor:{kind:'class',name:'Torts'},tol:{kind:'outline',name:'Torts outline',class_id:'tor',class_docs:true},tot:{kind:'timeline',name:'Torts timeline',class_id:'tor',class_docs:true},
  con:{kind:'class',name:'Contracts'},mid:{kind:'group',name:'Midterm prep'}},
 files:{d1:{scope:'tor',name:'Midterm 2, graded.pdf',type:'pdf',bytes:1258291,chars:18200,use:true,added:'2026-10-28T15:00:00Z'},
  d2:{scope:'tor',name:'Professor Lin, feedback.docx',type:'docx',bytes:86016,chars:5400,use:true,added:'2026-10-28T15:05:00Z'},
  d3:{scope:'tor',name:'Torts outline, fall.pdf',type:'pdf',bytes:624640,chars:31000,use:true,added:'2026-10-12T15:00:00Z'},
  d4:{scope:'con',name:'Contracts, weeks 1-6.pdf',type:'pdf',bytes:402000,chars:22000,use:true,added:'2026-10-02T15:00:00Z'},
  d5:{scope:'con',name:'Remedies notes.txt',type:'text',bytes:9100,chars:9100,use:true,added:'2026-10-20T15:00:00Z'},
  d6:{scope:'mid',name:'Practice exam 2024.pdf',type:'pdf',bytes:300000,chars:14000,use:true,added:'2026-10-25T15:00:00Z'},
  d7:{scope:'mid',name:'Study plan.md',type:'text',bytes:2100,chars:2100,use:true,added:'2026-10-26T15:00:00Z'}}, n:7};
var DMSG={docs_not_found:'That document or folder is not in your library.',docs_full:'Your library is full (20 files). Delete one first; deleted files count until they are gone for good after 7 days.',
 docs_too_long:'That file has more text than Bass can read at once (60,000 characters). Split it, or upload just the part you need.',docs_bad_name:'Please give it a name (up to 120 characters).',
 docs_over_limit:'Bass can read up to 60,000 characters of documents at a time. Switch off a document under Using, then try again.',docs_bad_request:'Bass could not read that request.',
 docs_picture:'Bass can keep pictures in your library but cannot read them yet, so it will not use this one.',upload_unsupported:'Bass can read PDF, Word (.docx) and plain-text files. Paste the text or upload one of those.',
 upload_too_big:'That file is too large for Bass. Try a smaller file, or paste the text.',
 drive_off:"Add from Drive isn't available right now.",drive_not_connected:'Connect Google Drive first, then choose your files.',drive_expired:'Your Google Drive connection ended. Choose your files again.',
 drive_bad_token:'Bass could not connect to Google Drive. Please try again.',drive_not_found:'Bass could not open that file from Drive. Choose it again.',
 drive_unsupported:'Bass can read Google Docs, PDF, Word (.docx) and plain-text files from Drive.',drive_unavailable:"Google Drive didn't answer. Please try again in a moment.",drive_cancel:'Google Drive could not be opened. Please try again.'};
function dno(c){ return {ok:false,status:'refused',code:c,message:DMSG[c]||DMSG.docs_bad_request,retryable:false}; }
function dnow(){ return SIM.now||Date.now(); }
function simActive(sid){ var L=SIMLIB, s=L.scopes[sid]; if(!s) return null; var homes=[sid]; if((s.kind==='outline'||s.kind==='timeline')&&s.class_docs&&L.scopes[s.class_id]) homes.push(s.class_id);
  var rows=[]; homes.forEach(function(h){ Object.keys(L.files).forEach(function(k){ var f=L.files[k]; if(f.scope===h&&f.use&&!f.deleted&&f.type!=='image') rows.push({id:k,name:f.name,chars:f.chars,from:h}); }); }); return rows; }
function simDocs(a){
  var L=SIMLIB, op=a.op, S_=L.scopes, F=L.files, f=a.doc_id&&F[a.doc_id], s=a.scope_id&&S_[a.scope_id];
  Object.keys(F).forEach(function(k){ if(F[k].deleted&&dnow()-Date.parse(F[k].deleted)>=DAYS*864e5) delete F[k]; });
  var ok={ok:true,status:'ok'}, live=f&&!f.deleted;
  if(op==='list'){ var fs=[],dl=[],by=0; Object.keys(F).forEach(function(k){ var x=F[k], r={id:k,scope:x.scope,name:x.name,type:x.type,bytes:x.bytes,chars:x.chars,use:x.use,added:x.added,readable:x.type!=='image'}; by+=x.bytes;
      if(x.deleted){ r.days_left=Math.max(1,Math.ceil((DAYS*864e5-(dnow()-Date.parse(x.deleted)))/864e5)); dl.push(r); } else fs.push(r); });
    return {ok:true,status:'ok',scopes:Object.keys(S_).map(function(k){ var o={id:k}; for(var p in S_[k]) o[p]=S_[k][p]; return o; }),files:fs,deleted:dl,caps:{files:Object.keys(F).length,files_max:DMAX,bytes:by,bytes_max:5e7,action_chars_max:DCH}}; }
  if(op==='using'){ if(!s) return dno('docs_not_found'); var rows=simActive(a.scope_id), ch=rows.reduce(function(t,r){ return t+r.chars; },0);
    return {ok:true,status:'ok',scope:{id:a.scope_id,kind:s.kind,name:s.name},files:rows,chars:ch,chars_max:DCH,over:ch>DCH,label:'Using: '+s.name+', '+rows.length+' document'+(rows.length===1?'':'s')}; }
  if(op==='add_scope'){ var nm=String(a.name||'').trim(); if(!nm||nm.length>120) return dno('docs_bad_name'); var id='s'+(++L.n), o={kind:a.kind,name:nm};
    if(a.kind==='outline'||a.kind==='timeline'){ if(a.class_id){ if(!S_[a.class_id]||S_[a.class_id].kind!=='class') return dno('docs_bad_request'); o.class_id=a.class_id; } o.class_docs=true; if(a.ref) o.ref=a.ref; }
    S_[id]=o; return {ok:true,status:'ok',scope:{id:id,kind:o.kind,name:o.name}}; }
  if(op==='rename_scope'){ if(!s) return dno('docs_not_found'); if(!String(a.name||'').trim()) return dno('docs_bad_name'); s.name=String(a.name).trim(); return ok; }
  if(op==='class_docs'){ if(!s) return dno('docs_not_found'); s.class_docs=!!a.on; return ok; }
  if(op==='remove_scope'){ if(!s) return dno('docs_not_found'); if(Object.keys(F).some(function(k){ return F[k].scope===a.scope_id; })||Object.keys(S_).some(function(k){ return S_[k].class_id===a.scope_id; })) return dno('docs_bad_request'); delete S_[a.scope_id]; return ok; }
  if(op==='add'){ if(!s) return dno('docs_not_found'); if(Object.keys(F).length>=DMAX) return dno('docs_full'); var nm2=String(a.name||''), ext=(nm2.match(/\.([a-z0-9]+)$/i)||[])[1]||'', ty=/^(pdf|docx)$/i.test(ext)?ext.toLowerCase():/^(txt|md|markdown|csv|text)$/i.test(ext)?'text':null;
    if(!ty) return dno('upload_unsupported'); var by2=a.file_b64?Math.floor(a.file_b64.length*3/4):String(a.text||'').length, ch2=ty==='image'?0:ty==='text'?String(a.text||'').length:Math.round(by2/40);
    if(ch2>DCH) return dno('docs_too_long'); var id2='f'+(++L.n); F[id2]={scope:a.scope_id,name:nm2,type:ty,bytes:by2,chars:ch2,use:ty!=='image',added:new Date(dnow()).toISOString()};
    var out={ok:true,status:'ok',file:{id:id2,scope:a.scope_id,name:nm2,type:ty,bytes:by2,chars:ch2,use:ty!=='image',readable:ty!=='image',path:'users/'+uid()+'/bass/'+id2}}; if(ty==='image') out.note=DMSG.docs_picture; return out; }
  if(op==='restore'){ if(!f||!f.deleted) return dno('docs_not_found'); delete f.deleted; return ok; }
  if(!live) return dno('docs_not_found');
  if(op==='rename'){ if(!String(a.name||'').trim()) return dno('docs_bad_name'); f.name=String(a.name).trim(); return ok; }
  if(op==='move'){ if(!s) return dno('docs_not_found'); f.scope=a.scope_id; return ok; }
  if(op==='use'){ if(a.on&&f.type==='image') return dno('docs_picture'); f.use=!!a.on; return ok; }
  if(op==='delete'){ f.deleted=new Date(dnow()).toISOString(); return {ok:true,status:'ok',recover_days:DAYS}; }
  return dno('docs_bad_request'); }

/* state: S.dk = the sheet {lib, sel, open:{class ids}, menu, newOpen, msg, busy}; S.scope = the scope Bass reads here; S.using = its "using" answer */
function dk(){ return S.dk||(S.dk={lib:null,sel:null,open:{},menu:null,newOpen:false,msg:null,busy:false,from:null}); }
function scopeKey(){ return 'alto-bass-scope-'+uid()+'-'+tidOf(); }
function scopeRead(){ try{ return localStorage.getItem(scopeKey())||null; }catch(e){ return null; } }
function scopeSave(id){ S.scope=id; try{ if(id) localStorage.setItem(scopeKey(),id); else localStorage.removeItem(scopeKey()); }catch(e){} }
function dLoad(){ var d=dk(); return call('docs',{op:'list'}).then(function(r){ if(!r||!r.ok){ d.msg=(r&&r.message)||DMSG.docs_bad_request; draw(); return; } d.lib=r;
  var ids=r.scopes.map(function(x){ return x.id; }); if(!d.sel||ids.indexOf(d.sel)<0) d.sel=(S.scope&&ids.indexOf(S.scope)>=0)?S.scope:(ids[0]||null);
  var cur=r.scopes.filter(function(x){ return x.id===d.sel; })[0]; if(cur&&cur.class_id) d.open[cur.class_id]=true; else if(cur&&cur.kind==='class') d.open[cur.id]=true;
  if(!S.scope){ var mine=r.scopes.filter(function(x){ return x.ref&&x.ref===tidOf(); })[0]; if(mine) S.scope=mine.id; }
  draw(); if(d.drv===undefined) driveConfig(); }); }
function usingLoad(){ var sid=S.scope||scopeRead(); if(!sid){ S.using=null; draw(); return Promise.resolve(); } S.scope=sid;
  return call('docs',{op:'using',scope_id:sid}).then(function(r){ if(r&&r.ok) S.using=r; else { S.using=null; if(r&&r.code==='docs_not_found') scopeSave(null); } draw(); }); }
function dOp(args,after){ var d=dk(); d.busy=true; d.msg=null; draw();
  return call('docs',args).then(function(r){ d.busy=false; if(!r||!r.ok){ d.msg=(r&&r.message)||DMSG.docs_bad_request; draw(); return r; } if(r.note) d.msg=r.note; if(after) after(r);
    return dLoad().then(function(){ if(S.scope) usingLoad(); return r; }); }); }
function openDocs(from){ var d=dk(); d.from=from||S.mode; d.menu=null; d.newOpen=false; d.msg=null; S.dopen=true; if(!root){ S.mode='docs'; mount(); } draw(); dLoad(); }
function closeDocs(){ S.dopen=false; if(S.mode==='docs'){ close(); return; } draw(); usingLoad(); }
function kb(n){ return n>=1048576?(Math.round(n/104857.6)/10)+' MB':Math.max(1,Math.round(n/1024))+' KB'; }
function dday(iso){ var t=new Date(iso); return isNaN(t)?'':['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][t.getUTCMonth()]+' '+t.getUTCDate(); }
function tag(t){ return {pdf:'PDF',docx:'DOC',text:'TXT',image:'IMG'}[t]||'FILE'; }
function scopesOf(lib,kind){ return lib.scopes.filter(function(x){ return x.kind===kind; }); }
function count(lib,sid){ return lib.files.filter(function(f){ return f.scope===sid; }).length; }
function sw(on,attrs,label,dis){ return '<button type="button" class="bs-sw'+(on?' on':'')+'" role="switch" aria-checked="'+(on?'true':'false')+'" '+attrs+(dis?' disabled':'')+' aria-label="'+esc(label)+'"><i></i></button>'; }
function navView(lib,sel){
  var d=dk(), h='<p class="bs-dk">Classes</p>';
  scopesOf(lib,'class').forEach(function(c){ var o=!!d.open[c.id], kids=lib.scopes.filter(function(x){ return x.class_id===c.id; }), n=count(lib,c.id);
    h+='<button type="button" class="bs-sc'+(sel===c.id?' sel':'')+'" data-a="d-sel" data-v="'+c.id+'" aria-expanded="'+o+'"><span class="bs-car" data-a="d-tog" data-v="'+c.id+'" aria-hidden="true">'+(o?'▾':'▸')+'</span><span class="bs-scn">'+esc(c.name)+'</span><span class="bs-n">'+n+'</span></button>';
    if(o) kids.forEach(function(k){ var own=count(lib,k.id); h+='<button type="button" class="bs-sc kid'+(sel===k.id?' sel':'')+'" data-a="d-sel" data-v="'+k.id+'"><span class="bs-scn">'+esc(k.name)+'</span><span class="bs-n">'+(own?own+' ':'')+(k.class_docs&&n?'+'+n:'')+'</span></button>'; }); });
  var g=scopesOf(lib,'group'); if(g.length){ h+='<p class="bs-dk">Groups</p>'; g.forEach(function(x){ h+='<button type="button" class="bs-sc'+(sel===x.id?' sel':'')+'" data-a="d-sel" data-v="'+x.id+'"><span class="bs-scn">'+esc(x.name)+'</span><span class="bs-n">'+count(lib,x.id)+'</span></button>'; }); }
  var loose=lib.scopes.filter(function(x){ return (x.kind==='outline'||x.kind==='timeline')&&!x.class_id; });
  if(loose.length){ h+='<p class="bs-dk">Outlines</p>'; loose.forEach(function(x){ h+='<button type="button" class="bs-sc'+(sel===x.id?' sel':'')+'" data-a="d-sel" data-v="'+x.id+'"><span class="bs-scn">'+esc(x.name)+'</span><span class="bs-n">'+count(lib,x.id)+'</span></button>'; }); }
  h+='<button type="button" class="bs-sc add" data-a="d-new">'+IC.plus+'<span class="bs-scn">New class or group</span></button>';
  if(d.newOpen) h+=newView(lib);
  return h; }
function newView(lib){ var cls=scopesOf(lib,'class');
  return '<div class="bs-dnew"><select class="bs-dsel bs-dnk" aria-label="Kind"><option value="class">Class</option><option value="group">Group</option>'
    +cls.map(function(c){ return '<option value="outline:'+c.id+'">Outline in '+esc(c.name)+'</option><option value="timeline:'+c.id+'">Timeline in '+esc(c.name)+'</option>'; }).join('')+'</select>'
    +'<div class="bs-inp"><input type="text" class="bs-dnn" maxlength="120" placeholder="Name, e.g. Evidence" aria-label="Name"></div><button type="button" class="bs-btn pri" data-a="d-newok">Add</button></div>'; }
function pickView(lib,sel){ var h='<select class="bs-dsel bs-dpick" data-a="d-pick" aria-label="Class or group">';
  lib.scopes.forEach(function(x){ var c=x.class_id&&lib.scopes.filter(function(y){ return y.id===x.class_id; })[0]; h+='<option value="'+x.id+'"'+(x.id===sel?' selected':'')+'>'+esc((c?c.name+' › ':'')+x.name)+' · '+(x.kind==='group'?'group':x.kind)+'</option>'; });
  return h+'</select>'; }
function mainView(lib,sel){
  var d=dk(), s=lib.scopes.filter(function(x){ return x.id===sel; })[0];
  if(!s) return '<div class="bs-dmain">'+(d.newOpen?'<div class="bs-dnewm">'+newView(lib)+'</div>':'')+'<h2 class="bs-t">Your documents</h2><p class="bs-hint">Make a class or a group on the left, then drop your files into it. Bass reads only the documents of the class or group you are working in.</p></div>';
  var c=s.class_id&&lib.scopes.filter(function(y){ return y.id===s.class_id; })[0], cn=c?count(lib,c.id):0;
  var why=s.kind==='class'?'Bass uses only these when you work in '+s.name+' and the outlines and timelines inside it. Other classes never see them.'
    :s.kind==='group'?'Bass uses only these when you pick '+s.name+'. Nothing else sees them.'
    :'Bass uses these only in this '+s.kind+(c&&s.class_docs?', plus the '+c.name+' class documents.':'.');
  var h='<div class="bs-dmain">'+pickView(lib,sel)+'<button type="button" class="bs-btn bs-dnewp" data-a="d-new">'+IC.plus+'New class or group</button>'+(d.newOpen?'<div class="bs-dnewm">'+newView(lib)+'</div>':'')+'<div class="bs-dt"><h2 class="bs-t">'+esc(s.name)+'</h2><button type="button" class="bs-ib" data-a="d-rsc" title="Rename" aria-label="Rename '+esc(s.name)+'">'+IC.pen+'</button></div><p class="bs-hint">'+esc(why)+'</p>';
  if(d.menu==='scope') h+='<div class="bs-dmenu"><div class="bs-inp"><input type="text" id="bs-dsn" maxlength="120" value="'+esc(s.name)+'" aria-label="New name"></div><button type="button" class="bs-btn pri" data-a="d-rscok">Save</button>'
    +(count(lib,s.id)||lib.scopes.some(function(x){ return x.class_id===s.id; })?'':'<button type="button" class="bs-btn" data-a="d-rmsc">Remove</button>')+'</div>';
  if(c) h+='<div class="bs-drow cls">'+IC.doc+'<div class="bs-dn"><b>Also use the '+esc(c.name)+' class documents</b><small>'+cn+' file'+(cn===1?'':'s')+' shared with every '+esc(c.name)+' outline and timeline</small></div>'+sw(s.class_docs,'data-a="d-cls" data-v="'+s.id+'"','Also use the '+c.name+' class documents')+'</div>';
  h+='<label class="bs-drop" data-drop="docs" for="bs-dfile">'+IC.up+'<b>Drop files here, or choose them</b><span>PDF, Word, text · '+lib.caps.files+' of '+lib.caps.files_max+' files used. Bass reads up to 60,000 characters of documents at a time.</span></label>'
    +'<input type="file" id="bs-dfile" multiple accept=".pdf,.docx,.txt,.md,.csv" style="display:none" aria-label="Choose files">';
  if(d.drv&&d.drv.available&&!phone()) h+='<button type="button" class="bs-btn bs-ddrive" data-a="d-drive"'+(d.busy?' disabled':'')+'>'+IC.doc+'Add from Drive</button><span class="bs-hint bs-ddh">Pick Google Docs, PDF or Word files. Bass sees only the files you pick.</span>';
  if(d.msg) h+='<div class="bs-alert">'+IC.warn+'<div><p>'+esc(d.msg)+'</p></div></div>';
  var mine=lib.files.filter(function(f){ return f.scope===sel; });
  if(!mine.length) h+='<p class="bs-hint">No documents here yet.</p>';
  mine.forEach(function(f){
    h+='<div class="bs-drow"><span class="bs-tag">'+tag(f.type)+'</span><div class="bs-dn"><b>'+esc(f.name)+'</b><small>'+kb(f.bytes)+' · added '+dday(f.added)+'</small></div>'
      +(f.readable?'<span class="bs-use'+(f.use?' on':'')+'">'+(f.use?'Bass is using this':'Not used')+'</span>'+sw(f.use,'data-a="d-use" data-v="'+f.id+'"','Bass is using '+f.name)
        :'<span class="bs-use">Bass can\'t read pictures yet</span>')
      +'<button type="button" class="bs-ib bs-more" data-a="d-menu" data-v="'+f.id+'" title="More" aria-label="More for '+esc(f.name)+'" aria-expanded="'+(d.menu===f.id)+'">⋯</button></div>';
    if(d.menu===f.id) h+='<div class="bs-dmenu"><div class="bs-inp"><input type="text" id="bs-dfn" maxlength="120" value="'+esc(f.name)+'" aria-label="Rename"></div><button type="button" class="bs-btn" data-a="d-ren" data-v="'+f.id+'">Rename</button>'
      +'<select class="bs-dsel" data-a="d-mv" data-v="'+f.id+'" aria-label="Move to"><option value="">Move to…</option>'+lib.scopes.filter(function(x){ return x.id!==sel; }).map(function(x){ return '<option value="'+x.id+'">'+esc(x.name)+'</option>'; }).join('')+'</select>'
      +'<button type="button" class="bs-btn bs-del" data-a="d-del" data-v="'+f.id+'">Delete</button></div>'; });
  var gone=lib.deleted;
  if(gone.length){ h+='<p class="bs-dk">Recently deleted</p>'; gone.forEach(function(f){ h+='<div class="bs-drow gone"><span class="bs-tag">'+tag(f.type)+'</span><div class="bs-dn"><b>'+esc(f.name)+'</b><small>Gone for good in '+f.days_left+' day'+(f.days_left===1?'':'s')+'</small></div><button type="button" class="bs-btn" data-a="d-res" data-v="'+f.id+'">Restore</button></div>'; }); }
  if(d.from&&d.from!=='docs') h+='<div class="bs-act" style="padding:4px 0 0"><span class="bs-sp"></span><button type="button" class="bs-btn pri" data-a="d-here" data-v="'+s.id+'">'+(S.scope===s.id?'Bass uses these here'+IC.check:'Use '+esc(s.name)+' here')+'</button></div>';
  return h+'</div>'; }
function docsSheet(){ var d=dk(), lib=d.lib;
  return '<div class="bs-dsheet" role="dialog" aria-modal="true" aria-label="Documents"><div class="bs-h">'+IC.doc+'<span class="bs-name">Documents</span><span class="bs-sp"></span>'+meter()
    +'<button type="button" class="bs-ib" data-a="d-close" title="Close" aria-label="Close documents">'+IC.x+'</button></div>'
    +(lib?'<div class="bs-dgrid"><nav class="bs-dnav" aria-label="Classes and groups">'+navView(lib,d.sel)+'</nav>'+mainView(lib,d.sel)+'</div>'
      :'<div class="bs-b">'+(d.msg?'<div class="bs-alert">'+IC.warn+'<div><p>'+esc(d.msg)+'</p></div></div>':'<p class="bs-hint">Opening your documents…</p>')+'</div>')
    +'<div class="bs-dfoot"><span>Bass uses AI and can make mistakes. The text of a document goes to Anthropic when Bass uses it. <a class="bs-link" href="'+esc(PRIVACY_URL)+'" target="_blank" rel="noopener">Privacy Policy</a></span><button type="button" class="bs-btn pri" data-a="d-close">Done</button></div></div>'; }
function usingView(){ var u=S.using;
  if(!u) return '<div class="bs-using"><button type="button" class="bs-ul" data-a="d-open">'+IC.doc+'<span>Using: no documents</span><b>Choose</b></button></div>';
  var h='<div class="bs-using"><button type="button" class="bs-ul" data-a="d-uexp" aria-expanded="'+!!S.uexp+'">'+IC.doc+'<span><b>Using:</b> '+esc(u.label.replace(/^Using: /,''))+'</span>'+(S.uexp?'▴':'▾')+'</button>';
  if(u.over) h+='<p class="bs-hint bs-warn">'+esc(DMSG.docs_over_limit)+'</p>';
  if(S.uexp){ h+='<div class="bs-wrap">'; u.files.forEach(function(f){ h+='<span class="bs-pill"><span>'+esc(f.name.replace(/\.[a-z0-9]+$/i,''))+'</span><button type="button" data-a="d-uoff" data-v="'+f.id+'" title="Stop using this here" aria-label="Stop using '+esc(f.name)+'">'+IC.x+'</button></span>'; });
    h+='<button type="button" class="bs-pill add" data-a="d-open" title="Add documents" aria-label="Add documents">'+IC.plus+'<span>Add</span></button></div>'; }
  return h+'</div>'; }
function addDocFiles(list){ var d=dk(), sid=d.sel; if(!sid) return;
  Array.prototype.forEach.call(list||[],function(f){ var n=f.name, isT=/\.(txt|md|markdown|csv)$/i.test(n)||/^text\//.test(f.type);
    if(!isT&&f.size>FMAX){ d.msg=DMSG.upload_too_big; draw(); return; }
    var r=new FileReader(); r.onload=function(){ var v=String(r.result||''), args={op:'add',scope_id:sid,name:n};
      if(isT) args.text=v.slice(0,DCH+1); else { var i=v.indexOf(','); args.file_b64=i>=0?v.slice(i+1):''; }
      dOp(args,function(res){ var put=window.AltoCloud&&window.AltoCloud.putBassOriginal; if(put&&res.file&&res.file.path){ try{ put(res.file.path,f,f.type||'application/octet-stream'); }catch(e){} } }); };
    if(isT) r.readAsText(f); else r.readAsDataURL(f); }); }
/* ── Add from Drive (alto/bass/drive.py; Luke L-1102-220150). Hidden on a phone and whenever the server has no Picker config. Google's Picker
   (scope drive.file ONLY: the app sees just the files this student picks) gives a short-lived token and the ids; the token lives in this
   function's variables only (never stored, never in the DOM or an address), goes to the server once, and is revoked as soon as the add is
   done. window._altoDrivePick(cfg) is the seam tests (and nothing else) replace: it must resolve {token, ids} or null. ── */
var driveLive=false;   /* true from the moment a token is sent until the server confirms it was revoked: sign-out revokes it first */
function phone(){ try{ return document.documentElement.classList.contains('mobile'); }catch(e){ return false; } }
function driveConfig(){ var d=dk(); d.drv=false; return call('drive',{op:'config'}).then(function(r){ d.drv=(r&&r.ok&&r.available)?r:false; draw(); }); }
/* The Picker runs on its own page (/drive-picker/, build/drive_picker_page.py), opened in a popup: only that path's CSP names Google's origins, so no
   Google script ever loads on this page. Messages are same-origin only, both ways; the popup hands back {token, ids} once and closes. */
function googlePick(c){
  return new Promise(function(res,rej){
    var o=location.origin; if(!o||o==='null') return rej(new Error('origin'));
    var w=window.open('/drive-picker/','alto-drive-picker','popup=yes,width=980,height=680'); if(!w) return rej(new Error('popup'));
    var fin=false, t=null;
    function end(v){ if(fin) return; fin=true; window.removeEventListener('message',on); if(t) clearInterval(t); res(v); }
    function on(e){ if(e.origin!==o||e.source!==w||!e.data) return;
      if(e.data.alto==='drive-ready') w.postMessage({alto:'drive-config',cfg:{client_id:c.client_id,api_key:c.api_key,app_id:c.app_id}},o);
      else if(e.data.alto==='drive-picked'){ var r=e.data.result; end(r&&typeof r.token==='string'&&Array.isArray(r.ids)?{token:r.token,ids:r.ids}:null); } }
    window.addEventListener('message',on);
    t=setInterval(function(){ try{ if(w.closed) end(null); }catch(x){ end(null); } },500);
  });
}
function driveFlow(p,sid){ var tok=p&&p.token; if(!p||!tok||!p.ids||!p.ids.length) return Promise.resolve(null); driveLive=true;
  return call('drive',{op:'connect',token:tok}).then(function(r){ tok=null; p.token=null; if(!r||!r.ok) return r;
    return call('drive',{op:'add',scope_id:sid,file_ids:p.ids.slice(0,5)}); })
   .then(function(r){ return call('drive',{op:'disconnect'}).then(function(x){ driveLive=!(x&&x.ok); return r; },function(){ return r; }); }); }
function drivePick(){ var d=dk(), c=d.drv, sid=d.sel; if(!c||!sid||d.busy||phone()) return; d.msg=null;
  var pick=window._altoDrivePick||googlePick;
  Promise.resolve().then(function(){ return pick(c); }).then(function(p){ if(!p) return; d.busy=true; draw(); return driveFlow(p,sid).then(function(r){ d.busy=false;
      if(r&&!r.ok) d.msg=r.message||DMSG[r.code]||DMSG.docs_bad_request; else if(r&&r.failed) d.msg=r.failed+' of the files could not be added.'; return dLoad().then(function(){ if(S.scope) usingLoad(); }); }); })
   .catch(function(){ d.busy=false; d.msg=DMSG.drive_cancel; draw(); }); }
function docsClick(t,a){
  var d=dk(), v=t.getAttribute('data-v');
  if(a==='d-open') openDocs();
  else if(a==='d-close') closeDocs();
  else if(a==='d-drive') drivePick();
  else if(a==='d-tog'){ d.open[v]=!d.open[v]; draw(); }
  else if(a==='d-sel'){ if(d.sel===v&&!d.open[v]) d.open[v]=true; d.sel=v; d.menu=null; d.msg=null; draw(); }
  else if(a==='d-pick'){ d.sel=t.value; d.menu=null; d.msg=null; draw(); }
  else if(a==='d-new'){ d.newOpen=!d.newOpen; draw(); var ns=root?root.querySelectorAll('.bs-dnn'):[]; for(var j=0;j<ns.length;j++){ if(ns[j].offsetParent){ ns[j].focus(); break; } } }
  else if(a==='d-newok'){ var box=t.closest('.bs-dnew'), k=(box.querySelector('.bs-dnk')||{}).value||'class', nm=((box.querySelector('.bs-dnn')||{}).value||'').trim(), p=k.split(':'), args={op:'add_scope',kind:p[0],name:nm};
    if(p[1]) args.class_id=p[1]; if(p[0]!=='class'&&p[0]!=='group'&&d.from&&d.from!=='docs'&&!S.scope) args.ref=tidOf();
    dOp(args,function(r){ d.newOpen=false; d.sel=r.scope.id; if(p[1]) d.open[p[1]]=true; }); }
  else if(a==='d-rsc'){ d.menu=d.menu==='scope'?null:'scope'; draw(); }
  else if(a==='d-rscok') dOp({op:'rename_scope',scope_id:d.sel,name:(root.querySelector('#bs-dsn')||{}).value},function(){ d.menu=null; });
  else if(a==='d-rmsc') dOp({op:'remove_scope',scope_id:d.sel},function(){ if(S.scope===d.sel) scopeSave(null); d.menu=null; d.sel=null; });
  else if(a==='d-cls') dOp({op:'class_docs',scope_id:v,on:t.getAttribute('aria-checked')!=='true'});
  else if(a==='d-use') dOp({op:'use',doc_id:v,on:t.getAttribute('aria-checked')!=='true'});
  else if(a==='d-menu'){ d.menu=d.menu===v?null:v; draw(); }
  else if(a==='d-ren') dOp({op:'rename',doc_id:v,name:(root.querySelector('#bs-dfn')||{}).value},function(){ d.menu=null; });
  else if(a==='d-mv'){ if(t.value) dOp({op:'move',doc_id:v,scope_id:t.value},function(){ d.menu=null; }); }
  else if(a==='d-del') dOp({op:'delete',doc_id:v},function(){ d.menu=null; });
  else if(a==='d-res') dOp({op:'restore',doc_id:v});
  else if(a==='d-here'){ scopeSave(v); draw(); usingLoad(); }
  else if(a==='d-uexp'){ S.uexp=!S.uexp; draw(); }
  else if(a==='d-uoff') call('docs',{op:'use',doc_id:v,on:false}).then(function(){ usingLoad(); });
}
function devDocs(name){ S.dopen=true; var d=dk(); d.from=S.mode; d.lib=null; d.menu=null; d.msg=null; d.newOpen=false;
  if(name==='docs-outline'){ d.sel='tol'; d.open.tor=true; } else if(name==='docs-deleted'){ SIMLIB.files.d3.deleted=new Date(dnow()-2*864e5).toISOString(); d.sel='tor'; d.open.tor=true; }
  else if(name==='docs-menu'){ d.sel='tor'; d.open.tor=true; d.menu='d2'; } else if(name==='docs-new'){ d.sel='tor'; d.open.tor=true; d.newOpen=true; } else { d.sel='tor'; d.open.tor=true; }
  return call('docs',{op:'list'}).then(function(r){ d.lib=r; draw(); }); }
"""

DOCS_CSS = r"""
.bs-dsheet{pointer-events:auto;position:absolute;inset:0;z-index:5;background:var(--bs-bg);display:flex;flex-direction:column;min-height:0}
.bs-scrim>.bs-dsheet{position:relative;inset:auto;width:820px;max-width:100%;height:min(620px,100%);border:1px solid var(--bs-bd);border-radius:calc(var(--bs-rad) + 6px);box-shadow:var(--bs-shadow);overflow:hidden}
.bs-panel .bs-dsheet,.bs-win .bs-dsheet{border-radius:inherit}
.bs-dgrid{flex:1;min-height:0;display:grid;grid-template-columns:230px 1fr}
.bs-dnav{border-right:1px solid var(--bs-bd);padding:8px;overflow:auto;display:flex;flex-direction:column;gap:2px}
.bs-dk{font-size:10.5px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--bs-mut);margin:12px 10px 4px}
.bs-dnav .bs-dk:first-child{margin-top:4px}
.bs-sc{display:flex;align-items:center;gap:8px;min-height:44px;padding:8px 10px;border-radius:var(--bs-rad);border:0;background:none;color:var(--bs-ink);font:inherit;font-size:14px;text-align:left;cursor:pointer;width:100%}
.bs-sc.kid{padding-left:30px;font-size:13px;min-height:40px}
.bs-sc.sel{background:color-mix(in srgb,var(--bs-dis) 16%,transparent);color:color-mix(in srgb,var(--bs-dis) 70%,var(--bs-ink));font-weight:700}
.bs-sc.add{color:var(--bs-dis);font-weight:600}
.bs-sc:focus-visible{outline:2px solid var(--bs-acc);outline-offset:-2px}
.bs-scn{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.bs-car{width:14px;color:var(--bs-mut)}
.bs-n{font-size:12px;color:var(--bs-mut);font-weight:500}
.bs-dnew{display:flex;flex-direction:column;gap:6px;padding:6px 4px}
.bs-dsel{min-height:36px;border:1px solid var(--bs-bd);border-radius:var(--bs-rad);background:var(--bs-glass);color:var(--bs-ink);font:inherit;font-size:13px;padding:0 8px;max-width:100%}
.bs-dpick,.bs-dnewp,.bs-dnewm{display:none}
.bs-dmain{padding:14px 16px;overflow:auto;display:flex;flex-direction:column;gap:10px;min-width:0}
.bs-dt{display:flex;align-items:center;gap:6px}
.bs-hint{margin:0;color:var(--bs-mut);font-size:12.5px}
.bs-hint.bs-warn{color:#b3261e}
.bs-drow{display:flex;align-items:center;gap:10px;padding:9px 10px;border:1px solid var(--bs-bd);border-radius:var(--bs-rad);background:var(--bs-glass);min-height:56px;flex-shrink:0}   /* a row is a flex child of the scrolling column: never squeeze it below its content */
.bs-drow.cls{border-style:dashed}
.bs-drow.gone{opacity:.8}
.bs-tag{flex:none;width:34px;height:42px;border-radius:6px;border:1px solid var(--bs-bd);display:grid;place-items:center;font-size:10px;font-weight:700;letter-spacing:.04em;color:var(--bs-dis)}
html.dark:not(.alto-retro) .bs-tag{color:#b9a9ff}   /* Art: the PDF/DOC tag is too dim in Classic dark */
.bs-dn{flex:1;min-width:0;display:flex;flex-direction:column}
.bs-dn b{font-weight:650;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.bs-dn small{color:var(--bs-mut);font-size:12px}
.bs-use{font-size:12px;color:var(--bs-mut);white-space:nowrap}
.bs-use.on{color:color-mix(in srgb,#2a9a50 72%,var(--bs-ink));font-weight:650}    /* darker on light, lighter on dark */
.bs-sw{flex:none;width:40px;height:24px;border-radius:99px;border:0;background:var(--bs-bd);position:relative;cursor:pointer;padding:0}
.bs-sw i{position:absolute;left:3px;top:3px;width:18px;height:18px;border-radius:50%;background:#fff;transition:left .15s}
.bs-sw.on{background:var(--bs-dis)}.bs-sw.on i{left:19px}
.bs-sw:focus-visible{outline:2px solid var(--bs-acc);outline-offset:2px}
.bs-sw[disabled]{opacity:.45;cursor:default}
html.alto-retro .bs-sw,html.alto-retro .bs-sw i,html.alto-retro .bs-tag{border-radius:0}
html.alto-retro .bs-sw.on i{background:#000}
.bs-more{font-weight:900;border-color:var(--bs-bd)}
.bs-dmenu{display:flex;flex-wrap:wrap;gap:6px;align-items:center;padding:0 4px 4px 44px}
.bs-dmenu .bs-inp{flex:1 1 200px;width:auto}
.bs-del{color:#b3261e}
.bs-dsheet .bs-btn,.bs-dsheet .bs-ib{min-height:36px;min-width:36px}
.bs-dfoot{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:9px 14px;border-top:1px solid var(--bs-bd);font-size:12px;color:var(--bs-mut)}
.bs-using{display:flex;flex-direction:column;gap:6px}
.bs-ul{display:flex;align-items:center;gap:7px;min-height:36px;padding:4px 10px;border:1px solid var(--bs-bd);border-radius:var(--bs-rad);background:var(--bs-glass);color:var(--bs-ink);font:inherit;font-size:12.5px;cursor:pointer;text-align:left}
.bs-ul span{flex:1}.bs-ul b{font-weight:650}.bs-ul>b{color:var(--bs-dis)}
.bs-pill.add{gap:4px;padding:0 10px;color:var(--bs-dis);cursor:pointer;font:inherit;font-size:12px}
@media (max-width:640px){
  .bs-scrim>.bs-dsheet{height:100%;border-radius:calc(var(--bs-rad) + 4px)}
  .bs-dgrid{grid-template-columns:1fr}
  .bs-dnav{display:none}
  .bs-dpick{display:block;width:100%;min-height:44px;font-size:15px}
  .bs-dnewp{display:inline-flex;align-self:flex-start;min-height:44px}
  .bs-dnewm{display:block}
  .bs-drow{display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;column-gap:10px;row-gap:4px}
  .bs-drow .bs-dn{min-width:0}
  .bs-drow:not(.cls):not(.gone) .bs-more{grid-column:3;grid-row:1;justify-self:center}
  .bs-drow .bs-use{grid-column:1/3;grid-row:2;padding-left:44px}
  .bs-drow:not(.cls) .bs-sw{grid-column:3;grid-row:2;justify-self:center}
  .bs-dpick{-webkit-appearance:none;appearance:none;height:44px;box-sizing:border-box;padding:0 34px 0 12px;background-image:linear-gradient(45deg,transparent 50%,currentColor 50%),linear-gradient(135deg,currentColor 50%,transparent 50%);background-position:calc(100% - 19px) 19px,calc(100% - 14px) 19px;background-size:5px 5px,5px 5px;background-repeat:no-repeat}
  .bs-dmenu{padding-left:0}
  .bs-dfoot{flex-wrap:wrap}
  .bs-dsheet .bs-btn,.bs-dsheet .bs-ib{min-height:44px;min-width:44px}
  .bs-sw{width:52px;height:32px}.bs-sw i{width:26px;height:26px}.bs-sw.on i{left:23px}
  .bs-sw:before{content:"";position:absolute;inset:-6px -4px}
}
"""
