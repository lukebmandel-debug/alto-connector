"""Bass UI: the bundle's script (see bass_ui.py): the wizard (Upload, Review, Build, Edit), the edit panel, the credits meter, the estimate prompt and
every state, over ONE door `call(action, args, onEvent)`. The door is the in-page SIMULATOR until `window._ALTO_BASS_BASE` names a URL: then it POSTs
{action, args} there and reads one JSON result (docs/bass-api.md on the alto-bass branch is the contract; the simulator's keys, states and flow are
copied from its real samples). No network, no key, no Anthropic call here."""

JS = r"""
(function(){
'use strict';
if(window._altoBass) return;
var D=document, R=D.documentElement;
var FMAX=5000000;                              /* a file over this is not sent (the proxy's own cap, upload_max_file_bytes) */
var DISC='Bass uses AI and can make mistakes. Check your cards.';
var BASE=window._ALTO_BASS_BASE||null;           /* the one switch: a URL = the real backend, null = the simulator below */
var BETA=__BETA__;                                /* the beta (bass_ui.BETA): credits are a free allowance, nothing is sold, no price is shown */
var OUT={bass_off:1,terms_required:1,beta_credits_used:1,beta_tester_daily:1,beta_daily_full:1};   /* the server says no call can go out now: nothing is sent until the next open */
var GLC='__GL_MARK__', GLR='__GL_RETRO__', GLS='__GL_SMALL__';
var IC={
 x:'<svg class="bs-i" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg>',
 check:'<svg class="bs-i" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4.5 4.5L19 7"/></svg>',
 back:'<svg class="bs-i" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M15 5l-7 7 7 7"/></svg>',
 plus:'<svg class="bs-i" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>',
 coin:'<svg class="bs-i" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><circle cx="12" cy="12" r="9"/><path d="M12 7v10M9.5 9.5h4a1.7 1.7 0 010 3.4h-3a1.7 1.7 0 000 3.4h4.3" stroke-linecap="round"/></svg>',
 send:'<svg class="bs-i" viewBox="0 0 24 24" fill="currentColor"><path d="M3 11.5L21 3l-6.5 18-3-7.5z"/></svg>',
 up:'<svg class="bs-i" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 16V5M7 10l5-5 5 5M5 20h14"/></svg>',
 doc:'<svg class="bs-i" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4"/></svg>',
 pause:'<svg class="bs-i" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="5" width="4" height="14" rx="1"/><rect x="14" y="5" width="4" height="14" rx="1"/></svg>',
 clock:'<svg class="bs-i" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
 stop:'<svg class="bs-i" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M6 6l12 12"/></svg>',
 warn:'<svg class="bs-i" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l10 18H2z"/><path d="M12 10v5M12 18v.5"/></svg>',
 pen:'<svg class="bs-i" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20l1-4L16 5l3 3L8 19z"/></svg>'
};
function glyph(s){ return '<span class="bs-gw" style="display:inline-flex;--s:'+s+'px">'+GLC.replace('<svg','<svg class="bs-g bs-gc"')+GLR.replace('<svg','<svg class="bs-g bs-gr"')+'</span>'; }
function esc(s){ return String(s==null?'':s).replace(/[&<>"]/g,function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
function wait(ms){ return new Promise(function(r){ setTimeout(r,ms); }); }
function fl(n){ return Math.floor(n+1e-9); }
function lab(n){ var f=fl(n); return f+' credit'+(f===1?'':'s'); }
function usd(n){ return '$'+(n/100).toFixed(2); }
function about(n){ return n<=1?'less than 1 credit':'about '+Math.max(1,Math.round(n))+' credits'; }
function balLab(n){ return BETA?'Beta credits remaining: '+fl(n):lab(n); }

/* ───────────────────────── the simulator: the real door's keys, states and flow, scripted ───────────────────────── */
var SIM={calls:0, acks:{}, bal:142, n:0, force:null, hold:false, stopReq:false, cards:61, delay:1};
var CH0={title:'Civil Procedure',acts:[{label:'Jurisdiction'},{label:'Pleading'},{label:'Discovery'}],
  entities:[{id:'pennoyer',name:'Pennoyer v. Neff'},{id:'erie',name:'Erie v. Tompkins'},{id:'twombly',name:'Twombly'}],fields:['Holding','Rule','Date'],card_estimate:61};
var CODES={rate_limited:'Bass is busy right now. Nothing was charged. Please try again in a minute.',
 bass_paused:'Bass is taking a short break. Nothing was charged. Please try again later.',
 refused:'Bass could not help with that request. Nothing was charged.',
 upstream:'Something went wrong on our side. Nothing was charged. Please try again.',
 no_credits:'You are out of credits. Your work so far is saved.',
 action_cap:'This step reached its credit limit and was stopped. Your work so far is saved.',
 stopped:'Stopped. Your work so far is saved.',
 consent_required:'Please confirm you want Bass to build only from your own materials.'};
var OFF='I can only help with building and editing your timelines and outlines in Alto. Tell me what you would like to add or change.';
function aid(){ SIM.n++; return 'act_'+('000'+SIM.n).slice(-4); }
function R_(status,code,message,x){
  var r={ok:status==='ok',status:status,code:code||null,message:message,action_id:null,work_saved:false,credits:null,retryable:false,events:[]};
  for(var k in x) r[k]=x[k]; return r; }
function crd(spent,refunded){ return {spent:spent,refunded:refunded||0,balance:SIM.bal,label:lab(SIM.bal)}; }
function estOf(cards){ return SIM.force==='estimate'?150:Math.round(cards*1.2); }
function simCall(action,a,on){
  on=on||function(){}; SIM.calls++;
  var f=SIM.force;
  return wait(160*SIM.delay).then(function(){
    if(action==='balance') return {ok:true,status:'ok',credits:SIM.bal,label:lab(SIM.bal),available:f!=='paused',ack:SIM.acks[uid()]||null};
    if(action==='ack_notice'){ SIM.acks[uid()]=String(a.version||''); return {ok:true,status:'ok',ack:SIM.acks[uid()]}; }
    if(action==='stop'){ SIM.stopReq=true; return {ok:true,status:'ok'}; }
    if(action==='research'){ var rs=SIM.research||(SIM.research={available:false,on:false,version:'sim',needs_optin:false}); if(a.op==='optin'&&rs.available){ rs.on=true; rs.needs_optin=false; } if(a.op==='withdraw') rs.on=false; return {ok:true,status:'ok',code:null,message:'',research:JSON.parse(JSON.stringify(rs))}; }
    if(f==='paused') return R_('paused','bass_paused',CODES.bass_paused,{});
    if(f==='busy') return R_('busy','rate_limited',CODES.rate_limited,{retryable:true});
    if(f==='error') return R_('error','upstream',CODES.upstream,{retryable:true});
    if(f==='refused') return R_('refused','refused',CODES.refused,{});
    if(action==='estimate'){ var e=a.kind==='edit'?1:estOf(CH0.card_estimate);
      return {ok:true,status:'ok',kind:a.kind,credits_text:about(e),estimate_credits:e,show_prompt:e>20,have:SIM.bal,have_label:lab(SIM.bal),short_by:Math.max(0,Math.ceil(e-SIM.bal))}; }
    if(action==='propose') return wait(900*SIM.delay).then(function(){
      var id=aid(), tiny=(a.materials||[]).every(function(m){ return !m.name||/^scrap/i.test(m.name); })||f==='question';
      SIM.bal-=0.01; var base={code:null,action_id:id,work_saved:false,credits:crd(0.01),retryable:false,events:[{event:'start',action_id:id,kind:'propose'}]};
      if(tiny){ var q=R_('ok',null,'Which course is this for, and which weeks should it cover?',base); q.chips=null; return q; }
      var ch=JSON.parse(JSON.stringify(CH0)), nm=((a.materials||[])[0]||{}).name;
      if(nm&&!/^(civ pro outline)/i.test(nm)) ch.title=nm.replace(/\.[a-z0-9]+$/i,'').replace(/[_-]+/g,' ').replace(/\b[a-z]/g,function(c){ return c.toUpperCase(); }).slice(0,60);
      var r=R_('ok',null,'Here is my plan.',base); r.chips=ch; return r; });
    if(action==='build'){
      if(!a.consent) return R_('error','consent_required',CODES.consent_required,{});
      var n=(a.chips&&a.chips.card_estimate)||SIM.cards, est=estOf(n);
      if(est>20&&!a.accepted) return {ok:false,status:'estimate',kind:'build',credits_text:about(est),estimate_credits:est,show_prompt:true,have:SIM.bal,have_label:lab(SIM.bal),
        short_by:Math.max(0,Math.ceil(est-SIM.bal)),message:'This will use about '+est+' credits.',work_saved:false,credits:crd(0),events:[],code:null,retryable:false,action_id:null};
      return simBuild(n,est,on); }
    if(action==='convert'){
      if(!a.consent) return R_('error','consent_required',CODES.consent_required,{});
      var cv=200;
      if(!a.accepted) return {ok:false,status:'estimate',kind:'convert',credits_text:about(cv),estimate_credits:cv,show_prompt:true,have:SIM.bal,have_label:lab(SIM.bal),
        short_by:Math.max(0,Math.ceil(cv-SIM.bal)),message:'This will use about '+cv+' credits.',work_saved:false,credits:crd(0),events:[],code:null,retryable:false,action_id:null,cards_in:SIM.cards};
      SIM.bal-=cv/2; var cr=R_('ok',null,'Done.',{action_id:aid(),work_saved:true,credits:crd(cv/2),retryable:false,events:[]});
      cr.timeline_id='sim-converted'; cr.cards_in=cr.cards_out=SIM.cards; cr.to=a.target; return cr; }
    if(action==='edit'){
      var id2=aid(), txt=String(a.text||'');
      var off=f==='offtopic'||/\b(poem|python|javascript|recipe|weather|joke|homework|stock|crypto|song|essay about)\b/i.test(txt);
      var ev=[{event:'start',action_id:id2,kind:'edit'}];
      if(off) return R_('off_topic',null,OFF,{action_id:id2,credits:crd(0),events:ev.concat([{event:'result',action_id:id2,status:'off_topic',message:OFF}])});
      if(f==='nocredits') return R_('no_credits','no_credits',CODES.no_credits,{action_id:id2,work_saved:true,credits:crd(0)});
      if(f==='capped') return R_('capped','action_cap',CODES.action_cap,{action_id:id2,work_saved:true,credits:crd(2.4)});
      var spent=Math.round((0.17+txt.length*0.03)*100)/100; SIM.bal=Math.max(0,SIM.bal-spent);
      var msg=/add|new|create/i.test(txt)?'Added 1 card. Check it reads right.':/link|connect/i.test(txt)?'Linked the two cards.':/rename|title|change|fix|edit/i.test(txt)?'Done: I made that change.':'Done. Check the card reads right.';
      on(ev[0]); on({event:'progress',action_id:id2,step:'cards',label:'Writing cards',detail:'cards 1',ok:true,cards_done:1,cards_total:null,spent_credits:spent});
      return wait(700*SIM.delay).then(function(){ return {ok:true,status:'ok',code:null,message:msg,action_id:id2,work_saved:true,credits:crd(spent),retryable:false,events:ev,timeline_id:a.timeline_id||'current',changed:true}; }); }
    return R_('error','bad_input','Bass could not read that request. Nothing was charged.',{});
  });
}
function simBuild(n,est,on){
  var id=aid(), evs=[], stop=false; SIM.stopReq=false;
  var spent=0, out=function(e){ evs.push(e); on(e); };
  out({event:'start',action_id:id,kind:'build'});
  function prog(step,label,detail,done,sp){ spent=sp; out({event:'progress',action_id:id,step:step,label:label,detail:detail||'',ok:true,cards_done:done,cards_total:n,spent_credits:Math.round(sp*100)/100}); }
  var cap=SIM.force==='nocredits'||SIM.force==='capped'||SIM.force==='stopped';
  var lim=SIM.force==='nocredits'?38:(SIM.force==='capped'?38:n);
  var plan=[['setup','Setting up your timeline','',0,.04],['consent','Checking your materials','',0,.08],['chips','Adding your chips','',0,.12]];
  var done=0, tot=est*0.92;
  var p=Promise.resolve();
  plan.forEach(function(s){ p=p.then(function(){ return stop?0:wait(380*SIM.delay).then(function(){ prog(s[0],s[1],s[2],s[3],tot*s[4]); }); }); });
  var batches=[]; for(var k=9;k<=n+8;k+=9) batches.push(Math.min(k,n));
  batches.forEach(function(b){ p=p.then(function(){
    if(SIM.stopReq){ stop=true; return; } if(stop) return;
    if(b>lim){ stop=true; return; }
    return wait(520*SIM.delay).then(function(){ done=b; prog('cards','Writing cards','cards '+b+' of '+n,b,tot*(.12+.6*b/n)); }); }); });
  if(SIM.force==='build'||SIM.hold){ return p.then(function(){ return new Promise(function(){}); }); }   /* held mid-build for a screenshot: never settles */
  return p.then(function(){
    if(stop||cap&&lim<n){
      var st=SIM.force==='nocredits'?['no_credits','no_credits']:SIM.force==='capped'?['capped','action_cap']:['stopped','stopped'];
      if(SIM.stopReq) st=['stopped','stopped'];
      SIM.bal=Math.max(0,SIM.bal-spent);
      var r=R_(st[0],st[1],CODES[st[1]],{action_id:id,work_saved:true,credits:crd(spent),events:evs,timeline_id:'civil-procedure',cards:{done:done,total:n}});
      out({event:'result',action_id:id,status:st[0],message:r.message}); return r; }
    return wait(380*SIM.delay).then(function(){ prog('links','Linking cards','',n,tot*.8); return wait(380*SIM.delay); })
      .then(function(){ prog('build','Building your page','',n,tot*.9); return wait(380*SIM.delay); })
      .then(function(){ prog('work','Checking the result','',n,tot);
        SIM.bal=Math.max(0,SIM.bal-tot);
        var r=R_('ok',null,'Your timeline is built.',{action_id:id,work_saved:true,credits:crd(tot),events:evs,timeline_id:'civil-procedure',cards:{done:n,total:n}});
        out({event:'result',action_id:id,status:'ok',message:r.message}); return r; }); });
}

/* ───────────────────────── the one door ───────────────────────── */
function token(){ try{ var u=window.AltoCloud&&window.AltoCloud.user; return Promise.resolve(u&&u.getIdToken?u.getIdToken():null); }catch(e){ return Promise.resolve(null); } }
function gate(ok){ R.classList.toggle('alto-bass-off',!ok); try{ var u=window.AltoCloud&&window.AltoCloud.user; if(u&&u.uid) localStorage.setItem('alto-bass-ok-'+u.uid,JSON.stringify({ok:ok,t:Date.now()})); }catch(e){} }
function note(j){ if(!BETA||!j||!OUT[j.code]) return j;
  S.out={status:j.code==='bass_off'?'off':j.code==='beta_credits_used'?'no_credits':j.status==='paused'?'paused':'capped',code:j.code,message:j.message||'',work:!!j.work_saved,cards:j.cards||null};
  if(j.code==='bass_off') gate(false);
  if(j.code==='beta_credits_used') setBal(0);                                        /* used up: the chip reads 0 now, not the last balance (daily-limit codes keep it) */
  return j; }
function outR(){ var o=S.out; return R_(o.status==='off'?'paused':o.status,o.code,o.message,{}); }
function call(action,args,on){
  if(BETA&&S.out&&action!=='balance'&&action!=='stop') return Promise.resolve(outR());       /* used up / not on the list: nothing goes out */
  if(!BASE&&action==='drive') return wait(40*SIM.delay).then(function(){ SIM.calls++; return (args&&args.op==='config')?{ok:true,status:'ok',available:false}:{ok:false,status:'refused',code:'drive_off',message:DMSG.drive_off,retryable:false}; });     /* the simulator never reaches Google */
  if(!BASE) return (action==='docs'?wait(60*SIM.delay).then(function(){ SIM.calls++; return simDocs(args||{}); }):simCall(action,args||{},on)).then(note);
  return token().then(function(t){
    if(!t) return R_('paused','signin','Please sign in to use Bass.',{});
    return fetch(BASE,{method:'POST',headers:{'content-type':'application/json','authorization':'Bearer '+t},body:JSON.stringify({action:action,args:args||{}})})
      .then(function(r){ return r.json().then(function(j){ return r.ok?j:R_('error',r.status===401?'signin':'upstream',(j&&j.message)||'Something went wrong on our side. Nothing was charged.',{retryable:r.status!==401}); }); })
      .then(function(j){ (j.events||[]).forEach(function(e){ if(on) on(e); }); if(action==='balance'&&j.ok) gate(true); return note(j); }); })
    .catch(function(){ return R_('error','connection','Bass could not be reached. Nothing was charged. Please try again.',{retryable:true}); });
}

/* ───────────────────────── state ───────────────────────── */
var S={out:null,ack:null,notice:null,share:null,sharesheet:false,emb:false,fmt:null,place:'philadelphia',mode:null,step:1,files:[],paste:'',chips:null,consent:false,msg:'',alert:null,est:null,prog:null,running:false,bal:null,log:[],tid:null,typing:false,q:null};
var NOTICE_V='__NOTICE_V__', PRIVACY_URL='__PRIVACY_URL__';
var NOTICE_TEXT='Bass uses AI (Claude, by Anthropic). What you submit is sent to Anthropic to produce the result. AI can be wrong.';
function uid(){ try{ var c=window.AltoCloud; return (c&&c.user&&(c.user.uid||c.user.id))||'anon'; }catch(e){ return 'anon'; } }
function ackRead(){ try{ return localStorage.getItem('alto-bass-ack-'+uid())||null; }catch(e){ return null; } }
function acked(){ return (S.ack||ackRead())===NOTICE_V; }
var root=null, RUN=0;
var PLACES=[['philadelphia','Philadelphia'],['nyc','New York'],['boston','Boston'],['dc','Washington'],['chicago','Chicago'],['la','Los Angeles']];
function kindNow(){ return (typeof ntKind!=='undefined'&&ntKind)||'outline'; }
function isCity(){ return kindNow()==='palace'; }                            /* RUN: a reply that arrives after the window was closed or reopened is dropped */
function setBal(b){ if(typeof b!=='number') return; S.bal=b;
  try{ localStorage.setItem('alto-bass-bal',String(fl(b))); }catch(e){}
  var h=D.querySelector('.bt-bal'); if(h) h.textContent=balLab(b); var m=root&&root.querySelector('.bs-chip'); if(m) m.outerHTML=meter(); var e=root&&root.querySelector('.bs-bal'); if(e) e.textContent=balLab(b); }
function meter(){ if(S.bal==null) return ''; if(BETA) return '<span class="bs-chip" title="'+balLab(S.bal)+'"><span class="bs-coin">'+IC.coin+'</span>'+balLab(S.bal)+'</span>';
  return '<span class="bs-chip" title="Credits: '+fl(S.bal)+' (about '+usd(fl(S.bal)*1)+')"><span class="bs-coin">'+IC.coin+'</span>'+fl(S.bal)+'</span>'; }
function toast(t){ var e=D.createElement('div'); e.className='bs-toast bs-root-toast'; e.textContent=t; D.body.appendChild(e); setTimeout(function(){ e.remove(); },3200); }

/* ───────────────────────── views ───────────────────────── */
function head(title){ if(S.emb) return '<div class="bs-eh"><span class="bs-bal" title="'+(S.bal==null?'':BETA?balLab(S.bal):'Credits: '+fl(S.bal))+'">'+(S.bal==null?'':balLab(S.bal))+'</span></div>';
  return '<div class="bs-h">'+glyph(20)+'<span class="bs-name">'+esc(title||'Bass')+'</span><span class="bs-sp"></span>'+meter()+(S.mode==='panel'?'':'<button type="button" class="bs-ib" data-a="d-open" title="Documents" aria-label="Documents">'+IC.doc+'</button>')+'<button type="button" class="bs-ib" data-a="close" title="Close" aria-label="Close">'+IC.x+'</button></div>'; }
function foot(){ return (typeof shareRow==='function'?shareRow():'')+'<div class="bs-f">'+DISC+'</div>'; }
function dots(){ var N=S.emb?5:4, at=S.step+(S.emb?1:0), nm=S.emb?['Format','Upload','Review','Build','Edit']:['Upload','Review','Build','Edit']; var h='<div class="bs-dots" role="img" aria-label="Step '+at+' of '+N+'">'; for(var i=1;i<=N;i++){ h+='<i class="'+(i<=at?'on':'')+'" title="'+nm[i-1]+'"></i>'+(i<N?'<u></u>':''); } return h+'<span>'+at+' of '+N+'</span></div>'; }
function fmtView(){ var k=D.querySelector('#nt-modal > .nt-kinds'); if(!k) return '';
  var h=k.outerHTML; D.querySelectorAll('#nt-modal > .nt-modes').forEach(function(m){ h+=m.outerHTML; });
  return h.replace(/<small([^>]*)>([^<]*)<\/small>/g,function(_,a,t){ return '<small'+a+'>'+t.replace(/Claude/g,'Bass')+'</small>'; }); }
function placeView(){ var h='<div class="bs-wrap">'; PLACES.forEach(function(p){ var on=S.place===p[0]; h+='<button type="button" class="bs-pill pl '+(on?'pl-on':'pl-off')+'" data-a="place" data-v="'+p[0]+'" aria-pressed="'+on+'" title="'+(on?'Click to clear':'Build this city')+'"><i class="bs-dot p"></i><span>'+p[1]+'</span>'+(on?IC.x:'')+'</button>'; }); return h+'</div>'; }
function pillsOf(kind,list,cls){ var h='<div class="bs-wrap">'; list.forEach(function(t,i){
  h+='<span class="bs-pill" title="Click the cross to remove"><i class="bs-dot '+cls+'"></i><span>'+esc(t)+'</span><button type="button" data-a="rm" data-k="'+kind+'" data-i="'+i+'" title="Remove" aria-label="Remove '+esc(t)+'">'+IC.x+'</button></span>'; });
  return h+'<button type="button" class="bs-pill add" data-a="add" data-k="'+kind+'" title="Add one" aria-label="Add one">'+IC.plus+'</button></div>'; }
function alertView(a){
  var ic={no_credits:IC.coin,capped:IC.coin,busy:IC.clock,paused:IC.pause,stopped:IC.stop,refused:IC.warn,error:IC.warn,estimate:IC.coin}[a.status]||IC.warn;
  var ttl={no_credits:'Out of credits',capped:'Credit limit reached',busy:'Bass is busy',paused:'Bass is paused',stopped:'Stopped',refused:'Bass could not help',error:'Something went wrong'}[a.status]||'Bass';
  var body={busy:'Nothing was used. Try again in a moment.',paused:'Your timelines still open, study and share as usual.'}[a.status]||esc(a.message||'');
  if(BETA&&a.code==='bass_off'){ ttl='Bass is for beta testers'; body='Bass is open to invited beta testers only. Your timelines still open, study and share as usual.'; }
  else if(BETA&&a.status==='no_credits'){ ttl='Beta credits used up'; body='Your Bass beta credits are used up. Thank you for testing Bass!'+(a.work||a.cards?'<br><span style="color:var(--bs-mut)">'+(a.cards?a.cards.done+' of '+a.cards.total+' cards are built. ':'')+'Your work so far is saved.</span>':''); }
  else if(BETA&&a.code==='terms_required'){ ttl='Beta Terms'; body=esc(a.message||'Please accept the Beta Terms to use Bass. Sign in again to see the box.'); }   /* no paywall, no button */
  else if(BETA&&OUT[a.code]&&a.message) body=esc(a.message);                          /* today's limits: the server's own words */
  else if(a.status==='no_credits') body='Your credits ran out. Your work is saved.<br><span style="color:var(--bs-mut)">'+(a.cards?a.cards.done+' of '+a.cards.total+' cards are built. ':'')+'Add credits to finish.</span>';
  var h='<div class="bs-alert">'+ic+'<div><b>'+ttl+'</b><p>'+body+'</p></div></div>';
  if(a.cards&&a.cards.total) h+='<div class="bs-bar" role="progressbar" aria-valuenow="'+a.cards.done+'" aria-valuemax="'+a.cards.total+'"><b style="width:'+Math.round(100*a.cards.done/a.cards.total)+'%"></b></div>';
  return h;
}
function alertActs(a){
  var h='';
  if(!BETA&&a.status==='no_credits') h+='<button type="button" class="bs-btn pri" data-a="addcr" title="Credits cannot be bought yet">Add credits</button>';
  if(BETA&&S.out) return h;                                                             /* nothing to retry until the next open */
  if(a.retryable||a.status==='busy') h+='<button type="button" class="bs-btn pri" data-a="retry" title="Try again">Try again</button>';
  if(a.status==='stopped'||a.status==='capped'||a.status==='refused'||a.status==='error') h+=(S.mode==='wizard'&&S.step===3?'<button type="button" class="bs-btn" data-a="to2">'+IC.back+'Back</button>':'');
  return h;
}
function noticeView(){ return '<div class="bs-sheet" role="dialog" aria-modal="true" aria-labelledby="bs-nt"><div class="bs-sheet-in"><h2 class="bs-t" id="bs-nt">Before you use Bass</h2>'
  +'<p class="bs-np">'+esc(NOTICE_TEXT)+'</p><p class="bs-np"><a class="bs-link" href="'+esc(PRIVACY_URL)+'" target="_blank" rel="noopener">Privacy Policy</a></p>'
  +'<div class="bs-nact"><button type="button" class="bs-btn" data-a="notnow">Not now</button><button type="button" class="bs-btn pri" data-a="noticeok">OK, continue'+IC.check+'</button></div></div></div>'; }
function ask(fn,text){ S.notice={fn:fn,text:text==null?null:text}; draw(); }
function noticeEnd(){ var n=S.notice; S.notice=null; draw(); var i=root&&root.querySelector('.bs-say'); if(n&&n.text!=null&&i) i.value=n.text; return n; }
function noticeOk(){ if(!S.notice) return; S.ack=NOTICE_V; try{ localStorage.setItem('alto-bass-ack-'+uid(),NOTICE_V); }catch(e){} if(!BASE) call('ack_notice',{version:NOTICE_V}); var n=noticeEnd();   /* the proxy has no ack action: the ack lives in this browser */ if(n&&n.fn) n.fn(); }
function notNow(){ if(S.notice) noticeEnd(); }
/* Conversation sharing (opt-in; Art's spec ORG/notes-art-bass-optin/SPEC-optin-step.md): one sheet, asked once, two equal buttons, No thanks first, nothing selected,
   Esc / the x / a click outside = No thanks. Nothing is saved until Share is pressed; the server (research action) holds the record and the version. */
var SHARE_UNTIL='15 February 2027';                         /* ONE place for the retention date: it moves with Privacy/Terms Version 1.0, needs Luke's yes, and the version string changes with it */
var SHARE_L1="If you say yes, we save what you type to Bass and Bass's replies (not the files you add). Luke Mandel and people he asks to help, including AI tools, may read them to improve Bass.";
var SHARE_L2="We remove your account ID before anyone reads them, but we can't catch everything, so please don't type other people's private information. We keep them until "+SHARE_UNTIL+".";
var SHARE_SPLIT=false;                                     /* false = the stamped order: paragraph 3 stays ONE paragraph in the scrolling text. true (needs Strategy/IT's written OK of the new reading order) pins its first sentence above the buttons */
var SHARE_L3A='Bass works exactly the same if you say no.';          /* L3 split in two for layout only: A is pinned above the buttons, A + ' ' + B is Strategy's stamped string, word for word */
var SHARE_L3B='Nothing of your conversations is saved. You can stop any time: Bass menu, then Conversation sharing. Saving stops at once and what we saved is deleted within 7 days.';
var SHARE_URL=PRIVACY_URL;                                  /* the Privacy Policy page (no #fragment: the published 1.0 has no anchor for the section "Bass conversations you share") */
function shareNoKey(){ return 'alto-bass-share-no-'+uid(); }
function shareDeclined(v){ try{ return localStorage.getItem(shareNoKey())===String(v); }catch(e){ return false; } }
function shareView(){ return '<div class="bs-sheet bs-share" role="dialog" aria-modal="true" aria-labelledby="bs-sh"><div class="bs-sheet-in">'
  +'<button type="button" class="bs-ib bs-shx" data-a="sharenot" title="No thanks" aria-label="No thanks">'+IC.x+'</button>'
  +'<h2 class="bs-t bs-sht" id="bs-sh" tabindex="-1">Help improve Bass?</h2>'
  +'<p class="bs-np">'+esc(SHARE_L1)+'</p><p class="bs-np">'+esc(SHARE_L2)+'</p><p class="bs-np">'+esc(SHARE_SPLIT?SHARE_L3B:SHARE_L3A+' '+SHARE_L3B)+'</p>'
  +'<p class="bs-np"><a class="bs-link" href="'+esc(SHARE_URL)+'" target="_blank" rel="noopener">Read the details</a></p>'
  +'<div class="bs-nact bs-sact">'+(SHARE_SPLIT?'<p class="bs-np bs-promise">'+esc(SHARE_L3A)+'</p>':'')+'<div class="bs-sbtns"><button type="button" class="bs-btn bs-sbtn" data-a="sharenot">No thanks</button><button type="button" class="bs-btn bs-sbtn bs-syes" data-a="shareyes">Share my conversations</button></div></div></div></div>'; }
function shareRow(){ var s=S.share; if(!s||s.available!==true||S.sharesheet) return ''; var on=s.on===true;
  return '<div class="bs-shr"><span class="bs-shl">Conversation sharing: <b>'+(on?'On':'Off')+'</b></span><button type="button" class="bs-btn bs-sbtn" data-a="sharetoggle">'+(on?'Turn off':'Turn on')+'</button>'
    +(on?'<span class="bs-shn">Turning it off stops saving new conversations straight away; saved ones are deleted within 7 days.</span>':'')+'</div>'; }
function shareApply(s){ if(!s||typeof s!=='object') return; S.share=s;
  if(s.available===true&&s.needs_optin===true&&!shareDeclined(s.version)&&!S.notice) S.sharesheet=true; }
function shareNo(){ var v=S.share&&S.share.version; S.sharesheet=false; try{ if(v!=null) localStorage.setItem(shareNoKey(),String(v)); }catch(e){} draw(); toast('Sharing is off.'); }
function shareYes(){ var v=S.share&&S.share.version; if(v==null){ S.sharesheet=false; draw(); return; }
  call('research',{op:'optin',agree:true,version:v}).then(function(r){ S.sharesheet=false;
    if(r&&r.ok&&r.research){ S.share=Object.assign({},S.share,r.research,{available:true,needs_optin:false}); toast('Sharing is on. You can turn it off in the Bass menu.'); }
    else toast('That did not go through, so nothing changed.'); draw(); }); }
function shareToggle(){ var s=S.share; if(!s) return;
  if(s.on===true) call('research',{op:'withdraw'}).then(function(r){ if(r&&r.ok){ S.share=Object.assign({},S.share,{on:false,needs_optin:false}); toast('Sharing is off.'); } else toast('That did not go through, so nothing changed.'); draw(); });
  else { S.sharesheet=true; draw(); } }          /* turning on shows the same sheet: the user re-confirms, no one-tap enable */
function chat(){ var h=(S.mode==='panel'?usingView():'')+((S.log.length||S.typing)?'<div class="bs-log" role="log" aria-live="polite">':'');
  S.log.forEach(function(m){ h+='<div class="bs-msg '+m.r+'">'+esc(m.t)+(m.s?'<small>'+esc(m.s)+'</small>':'')+'</div>'; });
  if(S.typing) h+='<div class="bs-msg a bs-typing" aria-label="Bass is working"><i></i><i></i><i></i></div>';
  if(S.log.length||S.typing) h+='</div>';
  if(S.alert) h+=alertView(S.alert);
  return h; }
function inputRow(){ return '<div class="bs-inp"><input type="text" class="bs-say" placeholder="Ask Bass to change this timeline" aria-label="Ask Bass to change this timeline" maxlength="600"><button type="button" class="bs-ib" data-a="send" title="Send" aria-label="Send">'+IC.send+'</button></div>'; }

function bodyWizard(){
  var st=S.step, b='', a='';
  if(S.alert){ b=alertView(S.alert); a=alertActs(S.alert); return [b,a]; }
  if(st===0){
    b='<div>'+dots()+'</div><h2 class="bs-t">Pick a format</h2>'+fmtView()+'<p class="bs-hint">'+(BETA?'A build usually uses about 40 to 150 of your free beta credits. You see the estimate before anything runs.':'A build usually uses about 40 to 150 credits (about $0.40 to $1.50). You see the exact estimate before anything runs.')+'</p>';
    a='<button type="button" class="bs-btn" data-a="cancel">Cancel</button><span class="bs-sp"></span><button type="button" class="bs-btn pri" data-a="next0">Next'+IC.check+'</button>';
  } else if(st===1){
    b='<div>'+dots()+'</div><h2 class="bs-t">Add your materials</h2>'+usingView()+'<label class="bs-drop" data-drop="1" for="bs-file">'+IC.up+'<b>Drop PDFs or notes here</b><span>or tap to choose files</span></label>'
     +'<input type="file" id="bs-file" multiple accept=".pdf,.txt,.md,.doc,.docx,.rtf,.html" style="display:none" aria-label="Choose files">';
    S.files.forEach(function(f,i){ b+='<div class="bs-row">'+IC.doc+'<span class="bs-sp">'+esc(f.name)+'</span><button type="button" class="bs-ib" data-a="rmf" data-i="'+i+'" title="Remove" aria-label="Remove '+esc(f.name)+'">'+IC.x+'</button></div>'; });
    b+='<div class="bs-grp bs-pg"><label class="bs-lbl" for="bs-paste">Or paste your notes</label><textarea id="bs-paste" class="bs-paste" rows="5" maxlength="200000" placeholder="Paste or type your notes here. Bass writes only from what you add." aria-label="Paste your notes">'+esc(S.paste||'')+'</textarea></div>';
    a=(S.emb?'<button type="button" class="bs-btn" data-a="to0">'+IC.back+'Back</button>':'')+'<span class="bs-sp"></span><button type="button" class="bs-btn pri" data-a="next1"'+(S.files.length||pasted()||(S.using&&S.using.files.length)?'':' disabled')+'>Next'+IC.check+'</button>';
  } else if(st===2){
    if(S.running){ b='<div>'+dots()+'</div><div class="bs-alert">'+IC.clock+'<div><b>Reading your materials</b><p>This takes a moment.</p></div></div>'; a=''; }
    else if(!S.chips){ b='<div>'+dots()+'</div><h2 class="bs-t">One question</h2><div class="bs-msg a">'+esc(S.q||'Tell me a little more about these materials.')+'</div><div class="bs-inp"><input type="text" class="bs-say" placeholder="Your answer" aria-label="Your answer"><button type="button" class="bs-ib" data-a="ans" title="Send" aria-label="Send">'+IC.send+'</button></div>';
      a='<button type="button" class="bs-btn" data-a="to1">'+IC.back+'Back</button>'; }
    else { var c=S.chips;
      b='<div>'+dots()+'</div><h2 class="bs-t">Review what Bass found</h2>'
       +'<div class="bs-grp"><p class="bs-lbl">Title</p><div class="bs-inp"><input type="text" class="bs-title" value="'+esc(c.title)+'" aria-label="Title" maxlength="80">'+IC.pen+'</div></div>'
       +'<div class="bs-grp"><p class="bs-lbl">Acts</p>'+pillsOf('acts',c.acts.map(function(x){ return x.label; }),'')+'</div>'
       +'<div class="bs-grp"><p class="bs-lbl">Entities</p>'+pillsOf('entities',c.entities.map(function(x){ return x.name; }),'b')+'</div>'
       +(S.emb&&isCity()?'<div class="bs-grp"><p class="bs-lbl">Place</p>'+placeView()+'</div>':'')
       +'<div class="bs-grp"><p class="bs-lbl">Card fields</p>'+pillsOf('fields',c.fields,'g')+'</div>'
       +'<label class="bs-ckr"><input type="checkbox" class="bs-ck" data-a="consent"'+(S.consent?' checked':'')+'><span>Build only from my own materials. I have the right to use them.</span></label>';
      a='<button type="button" class="bs-btn" data-a="to1">'+IC.back+'Back</button><span class="bs-sp"></span><button type="button" class="bs-btn pri" data-a="build"'+(S.consent&&c.acts.length?'':' disabled')+'>Looks right'+IC.check+'</button>'; }
  } else if(st===3){
    if(S.est&&!S.running){ var e=S.est, short=e.short_by>0;
      b='<div>'+dots()+'</div><div class="bs-alert">'+IC.coin+'<div><b>This build will use '+esc(e.credits_text)+'</b><p>'+(BETA
        ?'You have '+(S.bal==null?esc(e.have_label):fl(S.bal))+' beta credits remaining'+(short?', so this build is bigger than what is left. Try fewer materials. Nothing was charged':'')
        :'That is about '+usd(e.estimate_credits)+'. You have '+esc(e.have_label)+(short?', so '+e.short_by+' more '+(e.short_by===1?'is':'are')+' needed':''))+'.</p></div></div>';
      a='<button type="button" class="bs-btn" data-a="to2">Cancel</button>'+(short?(BETA?'':'<button type="button" class="bs-btn pri" data-a="addcr" title="Credits cannot be bought yet">Add credits</button>'):'<button type="button" class="bs-btn pri" data-a="go">Continue'+IC.check+'</button>'); }
    else { var p=S.prog||{stage:0,label:'',detail:'',done:0,total:0}, names=['Read your materials','Structured acts and entities','Placing cards','Linked and laid out'];
      b='<div>'+dots()+'</div><h2 class="bs-t">Building your timeline</h2>';
      names.forEach(function(n,i){ var cls=i<p.stage?'done':i===p.stage?'cur':'', t=n+(i===2&&p.total&&i<=p.stage?', '+p.done+' of '+p.total:'');
        b+='<div class="bs-step '+cls+'"><i>'+(i<p.stage?IC.check:(i+1))+'</i>'+esc(t)+'</div>'; });
      b+='<div class="bs-bar" role="progressbar" aria-valuenow="'+(p.total?p.done:0)+'" aria-valuemax="'+(p.total||100)+'"><b style="width:'+(p.total?Math.round(100*p.done/p.total):4)+'%"></b></div>';
      a='<span class="bs-sp"></span><button type="button" class="bs-btn" data-a="stop" title="Stop and keep what is built">'+IC.stop+'Stop</button>'; }
  } else {
    b='<div>'+dots()+'</div><h2 class="bs-t">Your timeline is built</h2>'+chat(); a='';
  }
  return [b,a+(st===4?'':'')];
}
function draw(){
  if(!root) return; var keep=root.querySelector('.bs-say,.bs-title,.bs-paste'), val=keep?keep.value:null, cls=keep?keep.className:null, ae=D.activeElement;
  var inner;
  var dsh=S.dopen?docsSheet():'';
  if(S.mode==='docs'){
    inner='<div class="bs-scrim" data-scrim="1">'+dsh+'</div>'; dsh='';
  } else if(S.emb){
    var we=bodyWizard(), edE=S.step===4&&!S.alert;
    var sh=S.notice?noticeView():S.sharesheet?shareView():'';
    inner='<div class="bs-ew'+(S.notice?' bs-nw':'')+'">'+head()+'<div class="bs-b">'+we[0]+'</div>'+(edE?'<div class="bs-act" style="padding-bottom:10px;display:block">'+inputRow()+'</div>':(we[1]?'<div class="bs-act">'+we[1]+'</div>':''))+foot()+sh+dsh+'</div>';
  } else if(S.mode==='wizard'){
    var w=bodyWizard(), edit=S.step===4&&!S.alert;
    inner='<div class="bs-scrim" data-scrim="1"><div class="bs-win" role="dialog" aria-modal="true" aria-label="Bass">'+head('Bass')+'<div class="bs-b">'+w[0]+'</div>'
      +(edit?'<div class="bs-act" style="padding-bottom:10px;display:block">'+inputRow()+'</div>':(w[1]?'<div class="bs-act">'+w[1]+'</div>':''))+foot()+(S.notice?noticeView():S.sharesheet?shareView():'')+'</div></div>';
  } else {
    inner='<div class="bs-panel" role="dialog" aria-label="Bass">'+head('Bass')+'<div class="bs-b">'+chat()+'</div><div class="bs-act" style="display:block;padding-bottom:10px">'
      +(S.alert&&alertActs(S.alert)?'<div class="bs-act" style="padding:0 0 8px">'+alertActs(S.alert)+'</div>':'')+inputRow()+'</div>'+foot()+(S.notice?noticeView():S.sharesheet?shareView():'')+'</div>';
  }
  if(dsh&&!S.emb) inner+='<div class="bs-scrim bs-dscrim">'+dsh+'</div>';     /* over the panel or the wizard: the sheet needs the room */
  root.innerHTML=inner;
  var lg=root.querySelector('.bs-log'); if(lg) lg.scrollTop=lg.scrollHeight;
  if(keep&&val!=null&&ae===keep){ var k=root.querySelector('.'+cls.split(' ')[0]); if(k){ k.value=val; k.focus(); } }
  if(S.notice){ var okb=root.querySelector('[data-a="noticeok"]'); if(okb&&okb.focus) okb.focus(); }
  else if(S.sharesheet){ var sht=root.querySelector('#bs-sh'); if(sht&&sht.focus) sht.focus(); }       /* focus starts on the title, never on a button */
  var fi=root.querySelector('#bs-file'); if(fi) fi.addEventListener('change',function(){ addFiles(fi.files); fi.value=''; });
  var pst=root.querySelector('#bs-paste'); if(pst) pst.addEventListener('input',function(){ S.paste=pst.value; var nx=root.querySelector('[data-a="next1"]'); if(nx) nx.disabled=!(S.files.length||pasted()||(S.using&&S.using.files.length)); });
  var dfi=root.querySelector('#bs-dfile'); if(dfi) dfi.addEventListener('change',function(){ addDocFiles(dfi.files); dfi.value=''; });
  root.classList.toggle('bs-sharing',!!S.sharesheet);                                  /* one close x while the sheet is open: the sheet's (= No thanks) */
  root.setAttribute('data-step',S.mode==='wizard'?String(S.step):'panel'); root.classList.toggle('bs-emb',!!S.emb);
}
function addFiles(list){ Array.prototype.forEach.call(list||[],function(f){ var n=f.name;
  var isT=/\.(txt|md|markdown|csv|html?|rtf)$/i.test(n)||/^text\//.test(f.type), m={name:n,kind:'notes',text:'',size:f.size,needs_extraction:!isT};
  S.files.push(m); if(isT){ var r=new FileReader(); r.onload=function(){ m.text=String(r.result||'').slice(0,200000); m.needs_extraction=false; }; r.readAsText(f); }
  else if(/\.(pdf|docx)$/i.test(n)&&f.size<=FMAX){ var r2=new FileReader(); r2.onload=function(){ var u=String(r2.result||''), i=u.indexOf(','); if(i>=0) m.file_b64=u.slice(i+1); }; r2.readAsDataURL(f); } }); draw(); }   /* the proxy turns a PDF / .docx into text */
function pasted(){ return String(S.paste||'').trim(); }
function mats(){ var m=S.files.map(matOf), p=pasted(); if(p) m.push({name:'pasted-notes.txt',kind:'notes',text:p}); return m; }   /* pasted text is a text material like a .txt file */
function matOf(f){ var o={name:f.name,kind:f.kind,text:f.text}; if(f.file_b64) o.file_b64=f.file_b64; else if(f.needs_extraction) o.needs_extraction=true; return o; }

/* ───────────────────────── actions ───────────────────────── */
function applyBal(r){ if(r&&r.credits&&typeof r.credits.balance==='number') setBal(r.credits.balance); }
function failed(r){ S.alert={status:r.status,code:r.code,message:r.message,retryable:r.retryable,cards:r.cards||null,work:r.work_saved}; S.running=false; S.typing=false; draw(); }
function doPropose(extra){
  if(!acked()){ ask(function(){ doPropose(extra); }); return; }
  var my=RUN; S.running=true; S.alert=null; S.step=2; draw();
  var ms=mats(); if(extra) ms.push({name:'answer.txt',kind:'notes',text:extra});
  call('propose',{materials:ms,format:S.emb?kindNow():undefined,scope_id:S.scope||undefined}).then(function(r){ if(my!==RUN) return; applyBal(r); S.running=false;
    if(r.status!=='ok') return failed(r);
    if(r.chips){ S.chips=r.chips; S.q=null; } else { S.chips=null; S.q=r.message; } draw(); }); }
function doBuild(accepted){
  if(!acked()){ ask(function(){ doBuild(accepted); }); return; }
  var my=RUN; S.alert=null; S.step=3; S.running=!!accepted; if(accepted) S.prog={stage:0,done:0,total:S.chips.card_estimate||0}; S.est=null; draw();
  var st={setup:0,consent:0,chips:1,cards:2,links:3,layout:3,build:3,look:3,work:3};
  call('build',{format:S.emb?kindNow():undefined,place:S.emb&&isCity()?(S.place||undefined):undefined,chips:S.chips,materials:mats(),consent:true,accepted:!!accepted,scope_id:S.scope||undefined},function(e){
    if(my!==RUN) return; if(e.event==='progress'){ S.prog={stage:st[e.step]||0,done:e.cards_done||0,total:e.cards_total||(S.prog&&S.prog.total)||0}; if(S.step===3) draw(); } })
  .then(function(r){ if(my!==RUN) return; applyBal(r); S.running=false;
    if(r.status==='estimate'){ S.est=r; return draw(); }
    if(r.status!=='ok') return failed(r);
    S.tid=r.timeline_id; S.step=4; S.log=[{r:'a',t:'Your timeline is built. Ask me to change a card, an act or a link.',s:about(r.credits?r.credits.spent:0)+' used'}]; draw(); }); }
function doSend(){
  var my=RUN, inp=root.querySelector('.bs-say'); if(!inp) return; var t=inp.value.trim(); if(!t||S.typing) return;
  if(!acked()){ ask(function(){ var i=root&&root.querySelector('.bs-say'); if(i) i.value=t; doSend(); },t); return; }
  inp.value='';
  S.log.push({r:'u',t:t}); S.typing=true; S.alert=null; draw();
  call('edit',{timeline_id:S.tid||tidOf(),text:t,scope_id:S.scope||undefined}).then(function(r){ if(my!==RUN) return; applyBal(r); S.typing=false;
    if(r.status==='ok'||r.status==='off_topic'){ var sp=r.credits?r.credits.spent:0; S.log.push({r:'a',t:r.message,s:r.status==='ok'?(sp<1?'less than 1 credit':'About '+Math.round(sp)+' credits'):''}); draw(); if(r.changed&&window._altoBassChanged) window._altoBassChanged(r); return; }
    failed(r); }); }
/* "Turn into another format..." on the homepage (the sheet in home_template.html hands us the file, the format and its ui):
   estimate, a confirm that says it adds nothing, then the conversion; the counts come back from the server's own check. */
function doConvert(pg,fmt,ui){
  if(!acked()){ ui.status('Bass shows a short notice before its first use. Open Bass from the New timeline window, read it once, then come back.'); return Promise.resolve(); }
  var tid=pg&&pg.tid; if(!tid){ ui.status('Bass cannot find this timeline\u2019s cards.'); return Promise.resolve(); }
  var a={timeline_id:tid,target:fmt,consent:true};
  return call('convert',{timeline_id:tid,target:fmt,consent:true,accepted:false}).then(function(r){
    applyBal(r);
    if(r.status!=='estimate'){ ui.status(r.message||'Did not work. Nothing was charged.'); return; }
    var cr=r.estimate_credits||'';
    return ui.confirm('Bass will make a new timeline from this one\u2019s own '+(r.cards_in||'')+' cards and add nothing. About '+cr+' credits. Go on?','Make it (about '+cr+' credits)').then(function(yes){
      if(!yes) return;
      ui.status('Working\u2026');
      return call('convert',{timeline_id:tid,target:fmt,consent:true,accepted:true},function(e){ if(e.event==='progress'&&e.cards_total) ui.status('Making the cards: '+(e.cards_done||0)+' of '+e.cards_total); }).then(function(x){
        applyBal(x);
        if(x.ok&&x.timeline_id){ ui.status('Done: '+x.cards_in+' cards in, '+x.cards_out+' out. It is a new timeline in this project; the original is unchanged.'); if(window._altoBassChanged) window._altoBassChanged(x); }
        else ui.status(x.message||'Did not work. Nothing was saved.'); }); }); }); }
function tidOf(){ var s=D.querySelector('script[data-tid]'); return (s&&s.getAttribute('data-tid'))||S.tid||'current'; }
function onClick(e){
  var nk=e.target.closest&&e.target.closest('.nt-kind,.nt-mode');
  if(nk&&root&&root.contains(nk)){ if(nk.classList.contains('nt-kind')) ntPick(nk.dataset.kind); else ntMode(nk.closest('.nt-modes').dataset.for,nk.dataset.mode); return; }
  if(e.target.classList&&e.target.classList.contains('bs-share')){ shareNo(); return; }          /* a click on the sheet's own backdrop (outside the card) = No thanks */
  var t=e.target.closest('[data-a],[data-scrim]'); if(!t) return;
  if(t.hasAttribute('data-scrim')){ if(e.target===t){ if(S.sharesheet) shareNo(); else close(); } return; }
  var a=t.getAttribute('data-a');
  if(a.indexOf('d-')===0){ if(t.tagName!=='SELECT') docsClick(t,a); return; }
  if(a==='sharenot') shareNo();
  else if(a==='shareyes') shareYes();
  else if(a==='sharetoggle') shareToggle();
  else if(a==='close') close();
  else if(a==='rmf'){ S.files.splice(+t.getAttribute('data-i'),1); draw(); }
  else if(a==='next0'){ S.step=1; draw(); }
  else if(a==='to0'){ S.step=0; S.alert=null; draw(); }
  else if(a==='cancel'){ if(typeof ntClose==='function') ntClose(); }
  else if(a==='place'){ var v=t.getAttribute('data-v'); S.place=S.place===v?null:v; draw(); }
  else if(a==='next1') doPropose();
  else if(a==='to1'){ S.step=1; S.alert=null; S.chips=null; draw(); }
  else if(a==='to2'){ S.step=2; S.alert=null; S.est=null; draw(); }
  else if(a==='rm'){ var k=t.getAttribute('data-k'); S.chips[k].splice(+t.getAttribute('data-i'),1); draw(); }
  else if(a==='add'){ var k2=t.getAttribute('data-k'), sp=D.createElement('span'); sp.className='bs-pill'; sp.innerHTML='<input type="text" maxlength="40" aria-label="New name">'; t.replaceWith(sp);
    var inp=sp.firstChild; inp.focus(); var fin=function(){ var v=inp.value.trim(); if(v){ if(k2==='acts') S.chips.acts.push({label:v}); else if(k2==='entities') S.chips.entities.push({id:v.toLowerCase().replace(/\W+/g,'-'),name:v}); else S.chips.fields.push(v); } draw(); };
    inp.addEventListener('keydown',function(ev){ if(ev.key==='Enter'){ ev.preventDefault(); inp.onblur=null; fin(); } else if(ev.key==='Escape'){ ev.stopPropagation(); inp.onblur=null; draw(); } }); inp.onblur=fin; }
  else if(a==='consent'){ S.consent=t.checked; draw(); }
  else if(a==='build'){ S.chips.title=(root.querySelector('.bs-title')||{value:S.chips.title}).value||S.chips.title; doBuild(false); }
  else if(a==='go') doBuild(true);
  else if(a==='noticeok') noticeOk();
  else if(a==='notnow') notNow();
  else if(a==='stop') call('stop',{});
  else if(a==='retry'){ S.alert=null; if(S.mode==='wizard'&&S.step===3) doBuild(true); else if(S.mode==='wizard'&&S.step===2) doPropose(); else { var lu=S.log.filter(function(m){ return m.r==='u'; }).pop(); if(lu){ S.log.pop(); root.querySelector('.bs-say').value=lu.t; doSend(); } else draw(); } }
  else if(a==='addcr'&&!BETA) toast('Buying credits opens later. Your work is saved.');
  else if(a==='send') doSend();
  else if(a==='ans'){ var v=(root.querySelector('.bs-say')||{}).value; if(v&&v.trim()) doPropose(v.trim()); }
}
function onKey(e){
  if(S.emb) { if(e.key==='Enter'&&e.target.classList&&e.target.classList.contains('bs-say')){ e.preventDefault(); var an=root&&root.querySelector('[data-a="ans"]'); if(an) an.click(); else doSend(); } return; }
  if(e.key==='Escape'&&root){ e.stopPropagation(); if(S.notice) notNow(); else if(S.sharesheet) shareNo(); else if(S.dopen) closeDocs(); else close(); return; }
  if(e.key==='Enter'&&e.target.classList&&e.target.classList.contains('bs-say')){ e.preventDefault(); var ans=root.querySelector('[data-a="ans"]'); if(ans) ans.click(); else doSend(); }
}
function close(){ if(root){ root.remove(); root=null; D.removeEventListener('keydown',onKey,true); } }
function mount(){ close(); RUN++; root=D.createElement('div'); root.className='bs-root'+(S.emb?' bs-emb':''); root.id='bass-root'; (S.emb&&D.getElementById('nt-bass')||D.body).appendChild(root);
  root.addEventListener('click',onClick); root.addEventListener('change',function(e){ if(e.target.matches('[data-a="consent"]')) onClick({target:e.target}); else if(e.target.matches('select[data-a^="d-"]')) docsClick(e.target,e.target.getAttribute('data-a')); });
  root.addEventListener('dragover',function(e){ var d=e.target.closest('[data-drop]'); if(d){ e.preventDefault(); d.classList.add('over'); } });
  root.addEventListener('dragleave',function(e){ var d=e.target.closest('[data-drop]'); if(d) d.classList.remove('over'); });
  root.addEventListener('drop',function(e){ var d=e.target.closest('[data-drop]'); if(d){ e.preventDefault(); d.classList.remove('over'); (d.getAttribute('data-drop')==='docs'?addDocFiles:addFiles)(e.dataTransfer&&e.dataTransfer.files); } });
  D.addEventListener('keydown',onKey,true); }

/* ───────────────────────── every state, on demand: #bass=<name> or _altoBass.dev(name) ───────────────────────── */
var DEMO_FILES=[{name:'Civ Pro outline.pdf',kind:'notes',text:'',size:204800,needs_extraction:true},{name:'Week 3 notes.txt',kind:'notes',text:'Erie, Twombly',size:3100}];
var CHAT0=[{r:'u',t:'add the Erie holding from my notes'},{r:'a',t:'Added 1 card to Erie.',s:'About 6 credits'},{r:'u',t:'link it to Pennoyer'}];
function dev(name,mode){
  name=String(name||'').toLowerCase().replace(/^#?bass=?/,''); S.out=null; SIM.force=null; SIM.hold=false; SIM.delay=1;
  var emb=mode==='embed'; var wiz=emb||/^(home|upload|review|estimate|build|built|format)$/.test(name)||(mode==='wizard'&&!/^(edit|offtopic|live)$/.test(name));
  S.emb=emb; S.place='philadelphia'; S.mode=wiz?'wizard':'panel'; S.alert=null; S.est=null; S.prog=null; S.running=false; S.typing=false; S.consent=false; S.log=CHAT0.slice(); S.step=1; S.files=DEMO_FILES.slice(); S.paste=''; S.chips=JSON.parse(JSON.stringify(CH0));
  S.dopen=false; S.dk=null; S.uexp=false; S.using=null; S.scope=null; S.sharesheet=false; S.share=null;
  var dn=/^docs/.test(name); if(dn&&!mode){ S.mode='docs'; }
  if(S.bal==null) S.bal=142; mount(); setBal(142);
  if(dn||name==='using'){ if(dn&&!mode){ S.mode='docs'; draw(); } if(name==='using'){ S.scope='tol'; S.uexp=true; S.log=CHAT0.slice(); usingLoad(); } else devDocs(name); return; }
  var cardsAlert={ret:{status:'no_credits',cards:{done:38,total:61}}};
  switch(name){
    case 'share': SIM.research={available:true,on:false,version:'sim',needs_optin:true}; S.share=Object.assign({},SIM.research); S.sharesheet=true; break;
    case 'share-on': SIM.research={available:true,on:true,version:'sim',needs_optin:false}; S.share=Object.assign({},SIM.research); break;
    case 'share-off': SIM.research={available:true,on:false,version:'sim',needs_optin:false}; S.share=Object.assign({},SIM.research); break;
    case 'format': S.step=0; break;
    case 'upload': S.step=1; break;
    case 'review': S.step=2; break;
    case 'estimate': S.mode='wizard'; S.step=3; S.est={credits_text:'about 150 credits',estimate_credits:150,have_label:'142 credits',short_by:8}; break;
    case 'build': S.mode='wizard'; S.step=3; S.running=true; S.prog={stage:2,done:38,total:61}; break;
    case 'built': S.mode='wizard'; S.step=4; S.log=[{r:'a',t:'Your timeline is built. Ask me to change a card, an act or a link.',s:'About 73 credits used'}]; break;
    case 'edit': S.log=CHAT0.concat([]); break;
    case 'offtopic': S.log=[{r:'u',t:'write me a python script'},{r:'a',t:'I can only help with your timeline. Try asking about a card, an act or a link.'}]; break;
    case 'nocredits': case 'outofcredits': S.log=[]; S.alert={status:'no_credits',cards:{done:38,total:61},work:true}; if(S.mode==='wizard') S.step=3; break;
    case 'busy': S.log=[]; S.alert={status:'busy',retryable:true}; break;
    case 'paused': S.log=[]; S.alert={status:'paused'}; break;
    case 'refused': S.log=[]; S.alert={status:'refused',message:CODES.refused}; break;
    case 'capped': S.log=[]; S.alert={status:'capped',message:CODES.action_cap,cards:{done:38,total:61}}; break;
    case 'error': S.log=[]; S.alert={status:'error',message:CODES.upstream,retryable:true}; break;
    case 'stopped': S.log=[]; S.alert={status:'stopped',message:CODES.stopped,cards:{done:38,total:61}}; break;
    case 'live': S.log=CHAT0.concat([]); break;
    default: if(name!=='home'&&name!=='') { S.mode=wiz?'wizard':'panel'; }
  }
  if(name==='home'||name===''){ S.mode='wizard'; S.step=emb?0:1; S.files=[]; S.paste=''; S.chips=null; S.log=[]; }
  if(S.mode==='panel'&&!/^(live|edit|offtopic)$/.test(name)&&!S.alert&&name!=='') S.log=[];
  if(S.mode==='panel'&&name===''){ S.log=[{r:'a',t:'Ask me to change a card, an act or a link in this timeline.'}]; }
  if(/^(busy|paused|error|refused|capped|nocredits|outofcredits|offtopic|stopped|estimate|build|question)$/.test(name)) SIM.force={nocredits:'nocredits',outofcredits:'nocredits',offtopic:'offtopic'}[name]||name;
  if(name==='live') SIM.force=null;
  draw();
}
function open(mode){
  var h=(location.hash.match(/bass=([a-z-]+)/i)||[])[1];
  if(h){ dev(h,mode); return; }
  S.dopen=false; S.using=null; S.uexp=false; S.scope=null;
  if(mode==='docs'){ S.emb=false; S.out=null; S.mode='docs'; mount(); openDocs('docs'); call('balance').then(function(r){ if(r&&typeof r.credits==='number') setBal(r.credits); }); return; }
  S.emb=mode==='embed'; S.place='philadelphia'; S.mode=(mode==='wizard'||S.emb)?'wizard':'panel'; S.alert=null; S.est=null; S.running=false; S.typing=false; S.consent=false; S.step=S.emb?0:1; S.files=[]; S.paste=''; S.chips=null;
  S.log=S.mode==='panel'?[{r:'a',t:'Ask me to change a card, an act or a link in this timeline.'}]:[];
  S.out=null; mount(); if(S.bal==null&&!BASE) S.bal=SIM.bal;   /* with a real backend the chip stays blank until its first answer: never the simulator's number */
  draw(); S.scope=scopeRead(); usingLoad(); call('balance').then(function(r){ if(r&&typeof r.ack==='string'&&r.ack) S.ack=r.ack; if(typeof r.credits==='number'){ SIM.bal=BASE?r.credits:SIM.bal; setBal(r.credits); }
    if(S.out){ S.alert={status:S.out.status==='off'?'paused':S.out.status,code:S.out.code,message:S.out.message}; if(S.mode==='wizard'&&!S.emb) S.step=1; } else if(r&&r.research) shareApply(r.research); draw(); });
  var f=root.querySelector('button.bs-btn.pri,.bs-say'); }
function leave(){ if(root){ root.remove(); root=null; D.removeEventListener('keydown',onKey,true); } S.emb=false; }
__DOCS__
window._altoBass={convert:doConvert,share:{no:shareNo,yes:shareYes,toggle:shareToggle},open:open,openDocs:openDocs,drive:{flow:driveFlow,pick:drivePick,popup:googlePick},close:close,leave:leave,dev:dev,propose:doPropose,build:doBuild,ok:noticeOk,notNow:notNow,NOTICE_TEXT:NOTICE_TEXT,NOTICE_V:NOTICE_V,sim:SIM,call:call,state:S,version:'ui-2'};
/* Signing out revokes a Drive token that is still live (a flow whose last disconnect did not get through): the server's sign_out line
   (alto/bass/beta_guard.py) is the same disconnect. After sign-out there is no ID token to ask with, so it goes first; 2.5 s at most, then sign-out proceeds. */
(function(){ try{ var c=window.AltoCloud; if(!BASE||!c||c._bassSO||typeof c.signOut!=='function') return; var so=c.signOut; c._bassSO=1;
  c.signOut=function(){ var self=this, a=arguments, go=function(){ return so.apply(self,a); }; if(!driveLive) return go();
    return Promise.race([call('drive',{op:'disconnect'}),new Promise(function(r){ setTimeout(r,2500); })]).then(function(x){ if(x&&x.ok) driveLive=false; return go(); },go); }; }catch(e){} })();
})();
"""
