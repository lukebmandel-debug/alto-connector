"""Timeline search: one index, one ranking, one way of landing on a hit.

The engine's search box (desktop), the mobile pill and the mobile detail
page's FIND panel all used a single `indexOf(query)` over node text: a query
had to appear verbatim, case and restatement pages were not indexed at all,
twelve rows were the most anyone saw, and a hit on the timeline was a 1.7s
flash. This module replaces the core those three share (the engine's own
functions delegate to `window._altoSearch`, see engine_patches) and keeps
their look:

* Every place a word shows up is a result: the cards on the timeline and the
  pages (a node's details, each case / provision / element page, the
  overview). Whatever is named exactly what was typed comes first; then the
  strong matches, cards before pages; then the rest, cards before pages. A
  mention in a short section outranks one buried in a long one.
* Words match by prefix ("res" finds Res Ipsa Loquitur), by stem
  ("negligent" finds negligence), by alias ("Menlove"), and past one typo
  ("loquitor", "ispa") — typo matches only when nothing matches properly.
  Every query word must match; "v." and other filler words are ignored.
* A card hit flies to the card, enlarges it and rings it until it is no
  longer the enlarged card. A page hit opens the page with the matched words
  lit up for a few seconds.

MATCH_JS is shared with the homepage search (pages.py), so both rank alike.
"""
from __future__ import annotations

import json
import re

from .brief import Brief
from .sanitize import js_json

# ── the matcher (no DOM) ─────────────────────────────────────────────────────
MATCH_JS = r"""
(function(){
  if(window._altoMatch) return;
  var STOP={v:1,vs:1,versus:1,the:1,of:1,a:1,an:1,and:1,'in':1,on:1,to:1,'for':1,at:1,by:1,sec:1,section:1,or:1,
            what:1,whats:1,is:1,are:1,was:1,were:1,who:1,how:1,does:1,'do':1,did:1,why:1,when:1,where:1,which:1,
            about:1,define:1,definition:1,explain:1,me:1,s:1};
  var SUF=['ational','ations','ation','ional','ments','ment','nesses','ness','ences','ence','ances','ance','ents','ent',
           'ings','ing','ities','ity','ably','able','ibly','ible','ively','ive','ously','ous','ies','ied','ers','er',
           'ed','es','ly','al','s'];
  function norm(s){
    s=String(s==null?'':s).toLowerCase();
    try{ s=s.normalize('NFD').replace(/[\u0300-\u036f]/g,''); }catch(e){}
    return s.replace(/[\u2018\u2019\u02bc`]/g,"'").replace(/&/g,' and ');
  }
  /* words of a text: letters/digits; "T.J." and "D.C." also give "tj"/"dc",
     "Russell-Vaughn" also "russellvaughn", "Hand's" also "hand" */
  function words(s){
    s=norm(s);
    var out=[], m, re=/[a-z0-9]+(?:['.\-][a-z0-9]+)*\.?/g;
    while((m=re.exec(s))){
      var w=m[0].replace(/\.$/,''), parts=w.split(/['.\-]/).filter(Boolean);
      parts.forEach(function(p){ out.push(p); });
      if(parts.length>1){
        if(/'/.test(w) && parts[parts.length-1]==='s') {}          // possessive: parts already hold the stem word
        else out.push(parts.join(''));
      }
    }
    return out;
  }
  function stem(w){
    if(w.length<=4 || /^\d/.test(w)) return w;
    for(var i=0;i<SUF.length;i++){
      var s=SUF[i];
      if(w.length-s.length>=4 && w.slice(-s.length)===s){
        w=(s==='ies'||s==='ied')?w.slice(0,-s.length)+'y':w.slice(0,-s.length); break;
      }
    }
    if(w.length>4 && /e$/.test(w)) w=w.slice(0,-1);
    return w;
  }
  /* optimal-string-alignment distance, stops early past `max` */
  function dist(a,b,max){
    var la=a.length, lb=b.length; if(Math.abs(la-lb)>max) return max+1;
    var prev2=null, prev=[], cur, i, j;
    for(j=0;j<=lb;j++) prev[j]=j;
    for(i=1;i<=la;i++){
      cur=[i]; var rowMin=i;
      for(j=1;j<=lb;j++){
        var c=a[i-1]===b[j-1]?0:1;
        var v=Math.min(prev[j]+1, cur[j-1]+1, prev[j-1]+c);
        if(prev2 && i>1 && j>1 && a[i-1]===b[j-2] && a[i-2]===b[j-1]) v=Math.min(v, prev2[j-2]+1);
        cur[j]=v; if(v<rowMin) rowMin=v;
      }
      if(rowMin>max) return max+1;
      prev2=prev; prev=cur;
    }
    return prev[lb];
  }
  /* how well query word q matches text word t: 1 exact \u2026 0 none */
  function wq(q,t,last){
    if(t===q) return 1;
    if(t.length>q.length && t.lastIndexOf(q,0)===0) return q.length>=3||last ? 0.92 : 0;
    var sq=stem(q), st=stem(t);
    if(sq===st) return 0.88;
    if(q.length>=4 && st.lastIndexOf(sq,0)===0) return 0.86;
    if(q.length<4) return 0;
    if(t.indexOf(q)>0) return 0.5;
    var tb=t.replace(/s$/,'');
    if(tb.length>=5 && tb.length*2>=q.length && q.length>tb.length && q.slice(-tb.length)===tb) return 0.7;   // "airplane" finds "planes"
    if(q[0]!==t[0] || t.length<4) return 0;                   // a typo keeps its first letter
    var max=q.length>=8?2:1;
    if(dist(q,t,max)<=max) return 0.62;
    if(t.length>q.length && dist(q,t.slice(0,q.length),1)<=1) return 0.56;   // typo while still typing
    return 0;
  }
  function query(q){
    var all=words(q), toks=all.filter(function(w){ return !STOP[w]; });
    if(!toks.length) toks=all;
    /* drop the joined forms words() adds, keep each typed word once */
    var seen={}, out=[];
    toks.forEach(function(w){ if(!seen[w]){ seen[w]=1; out.push(w); } });
    var raw=norm(q).replace(/\s+/g,' ').trim();
    return {raw:raw, toks:out, lit:/[^a-z0-9 ]/.test(raw)?raw:''};
  }
  /* item: {fields:[{w:weight, text, key?}]}; returns null or {score, exact, hits:{word:1}, field} */
  function score(Q,item,opt){
    if(!Q.toks.length) return null;
    /* a card's number ("1.4", "I.A.1") is only ever the whole query */
    var qnum=Q.raw.replace(/[.\s]+$/,'');
    for(var nf=0;nf<item.fields.length;nf++){
      var NF=item.fields[nf]; if(!NF.num) continue;
      var ns=norm(NF.text).split(/\s+/).map(function(x){ return x.replace(/\.+$/,''); });
      if(qnum && ns.indexOf(qnum)>=0) return {score:30, exact:true, hits:{}, field:nf, named:true, miss:0};
    }
    var total=0, exact=true, hits={}, fieldHits={}, miss=0, allow=(opt&&opt.allow)||0;
    for(var k=0;k<Q.toks.length;k++){
      /* a short word is only a prefix while it is the whole query ("pl" in
         "b < pl" is not "plaintiff") */
      var q=Q.toks[k], last=(k===Q.toks.length-1), best=0, bestQ=0, bestF=null, inF=0, bx=0, bxF=null;
      for(var f=0;f<item.fields.length;f++){
        var F=item.fields[f], here=0;
        if(F.num) continue;
        if(!F._w){
          F._w=words(F.text); if(F.ac) F._w=F._w.concat(acro(F.text));
          /* running text: a mention in a short section says more than one in a long one */
          F._ln=F.w<2 ? Math.pow(Math.min(1,60/Math.max(1,F._w.length)),0.3) : 1;
        }
        for(var i=0;i<F._w.length;i++){
          var t=F._w[i], m=wq(q,t,last); if(!m) continue;
          hits[t]=1; if(m>=0.85) here=1;
          var v=m*F.w*F._ln;
          if(v>best){ best=v; bestQ=m; bestF=f; }
          if(m>=0.85 && v>bx){ bx=v; bxF=f; }
        }
        inF+=here;
      }
      if(!best){ miss++; if(miss>allow) return null; continue; }
      /* a proper match anywhere beats a typo match anywhere */
      if(bx){ best=bx; bestQ=1; bestF=bxF; }
      /* found in several places on the page: a page about it, not a mention */
      if(inF>1 && item.body) total+=Math.min(1.2,0.35*(inF-1));
      if(bestQ<0.85) exact=false;
      total+=best; fieldHits[bestF]=(fieldHits[bestF]||0)+1;
    }
    /* several words: all of them in one place, better still side by side */
    if(Q.toks.length>1){
      var prox=0;
      item.fields.forEach(function(F){
        if(F.num || !F._w) return;
        var pos=Q.toks.map(function(q,k){ var ps=[]; for(var i=0;i<F._w.length;i++) if(wq(q,F._w[i],k===Q.toks.length-1)>=0.85) ps.push(i); return ps; });
        if(pos.some(function(p){ return !p.length; })) return;
        var near=pos[0].some(function(p0){
          var at=p0; for(var k=1;k<pos.length;k++){ var nx=pos[k].filter(function(p){ return p>at && p<=at+3; })[0]; if(nx===undefined) return false; at=nx; }
          return true; });
        prox=Math.max(prox, near?6:3);
      });
      total+=prox;
    }
    /* the whole query as a phrase, and at the start of the title */
    var title=item.fields[0], tn=norm(title&&title.text).replace(/[^a-z0-9]+/g,' ').trim(),
        qn=Q.toks.join(' ');
    var named=false;
    if(tn===qn){ total+=14; named=true; }
    else if(tn.lastIndexOf(qn,0)===0) total+=9;
    else if(Q.toks.length>1 && (' '+tn+' ').indexOf(' '+qn)>=0) total+=5;
    if(Q.lit && Q.lit.length>=3){
      for(var f2=0;f2<item.fields.length;f2++){
        var F2=item.fields[f2]; if(!F2._n) F2._n=norm(F2.text).replace(/\s+/g,' ');
        if(F2._n.indexOf(Q.lit)>=0){ total+=5; break; }
      }
    }
    (item.alias||[]).forEach(function(a){
      var an=norm(a).replace(/[^a-z0-9]+/g,' ').trim();
      if(an===qn){ total+=12; named=true; } else if(an.lastIndexOf(qn,0)===0) total+=7;
    });
    /* the field that carried most of the words is where the snippet comes from */
    var bf=0, bn=-1; Object.keys(fieldHits).forEach(function(f){ if(fieldHits[f]>bn){ bn=fieldHits[f]; bf=+f; } });
    if(miss){ exact=false; total*=0.6; }
    return {score:total, exact:exact, hits:hits, field:bf, named:named, miss:miss};
  }
  function acro(t){
    var ws=norm(t).replace(/\(.*?\)/g,' ').split(/[^a-z0-9]+/).filter(Boolean);
    if(ws.length<2) return [];
    var all=ws.map(function(w){ return w[0]; }).join(''), some=ws.filter(function(w){ return !STOP[w]; }).map(function(w){ return w[0]; }).join('');
    return some.length>=2 && some!==all ? [all,some] : [all];
  }
  function esc(s){ return String(s==null?'':s).replace(/[&<>"]/g,function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  /* does this text word light up for the query? */
  function lit(Q,w){
    var ws=words(w);
    for(var i=0;i<ws.length;i++) for(var k=0;k<Q.toks.length;k++) if(wq(Q.toks[k],ws[i],k===Q.toks.length-1)>=0.5) return true;
    return false;
  }
  /* text around the first lit word, every lit word marked */
  function snippet(text,Q,len){
    text=String(text||'').replace(/\s+/g,' ').trim(); len=len||130;
    var re=/[A-Za-z0-9\u00C0-\u024F]+(?:['.\-][A-Za-z0-9\u00C0-\u024F]+)*/g, m, spans=[];
    while((m=re.exec(text))){ if(lit(Q,m[0])) spans.push([m.index,m.index+m[0].length]); }
    if(!spans.length) return esc(text.slice(0,len))+(text.length>len?'\u2026':'');
    var s=Math.max(0,spans[0][0]-40); if(s>0){ var sp=text.lastIndexOf(' ',s); s=sp>0&&s-sp<12?sp+1:s; }
    var e=Math.min(text.length,s+len), out='', at=s;
    spans.forEach(function(p){ if(p[0]<at||p[1]>e) return; out+=esc(text.slice(at,p[0]))+'<mark>'+esc(text.slice(p[0],p[1]))+'</mark>'; at=p[1]; });
    out+=esc(text.slice(at,e));
    return (s>0?'\u2026':'')+out+(e<text.length?'\u2026':'');
  }
  /* the whole text, every lit word marked (the expanded search shows full text) */
  function hl(text,Q){
    text=String(text||'').replace(/\s+/g,' ').trim();
    var re=/[A-Za-z0-9\u00C0-\u024F]+(?:['.\-][A-Za-z0-9\u00C0-\u024F]+)*/g, m, out='', at=0;
    while((m=re.exec(text))){ if(lit(Q,m[0])){ out+=esc(text.slice(at,m.index))+'<mark>'+esc(m[0])+'</mark>'; at=m.index+m[0].length; } }
    return out+esc(text.slice(at));
  }
  window._altoMatch={norm:norm, words:words, stem:stem, dist:dist, wq:wq, query:query, score:score, snippet:snippet, lit:lit, esc:esc, hl:hl};
})();
"""

# ── the timeline's index, ranking and landing ───────────────────────────────
TIMELINE_SEARCH_JS = r"""
(function(){
  if(window._altoSearch) return;
  var M=window._altoMatch, CFG=window._ALTO_SEARCH||{aliases:{},kinds:{}};
  var INDEX=null;
  function strip(h){ var d=document.createElement('div'); d.innerHTML=String(h||''); return (d.textContent||'').replace(/\s+/g,' ').trim(); }
  function secs(list){ return (list||[]).filter(function(s){ return s&&s.t && !/^source notes$/i.test(s.h||''); }); }
  function kind(k){ return (CFG.kinds||{})[k]||k; }
  function build(){
    if(INDEX) return INDEX;
    INDEX=[];
    var src=(typeof NODES_SRC!=='undefined'&&NODES_SRC)||(typeof NODES!=='undefined'&&NODES)||[];
    var O=window._ALTO_OUTLINE||{}, titles={}, dup={};
    var order=(typeof NODE_ORDER!=='undefined'&&NODE_ORDER)||src.map(function(n){ return n.id; });
    var ordOf=function(id){ var i=order.indexOf(id); return i<0?9999:i; };
    src.forEach(function(n){ var t=(n.title||'').toLowerCase(); dup[t]=(dup[t]||0)+1; titles[n.id]=n.title||n.id; });
    var chipName=function(k,id){
      var T=k==='char'?(typeof CHARS!=='undefined'?CHARS:{}):k==='env'?(typeof ENVS!=='undefined'?ENVS:{}):(typeof THEMES!=='undefined'?THEMES:{});
      return (T[id]&&T[id].name)?strip(T[id].name):'';
    };
    src.forEach(function(n){
      if(!n||!n.id) return;
      var num=(typeof NODE_ORDER_MAP!=='undefined'&&NODE_ORDER_MAP[n.id])||'', onum=(O.num&&O.num[n.id])||'';
      var parent=(O.parent&&O.parent[n.id])||'';
      /* a title many cards share ("Liable") is shown with the card it sits under */
      var shown=(dup[(n.title||'').toLowerCase()]>1 && parent) ? titles[parent]+' \u203a '+n.title : (n.title||n.id);
      var unit=''; try{ if(typeof PHASE_META!=='undefined'&&typeof NODE_ACT!=='undefined'){ var a=PHASE_META[NODE_ACT[n.id]]; unit=a?strip(a.label):''; } }catch(e){}
      var chips=[];
      [['char',n.chars],['env',n.envs],['theme',n.themes]].forEach(function(p){
        (p[1]||[]).forEach(function(id){ var nm=chipName(p[0],id); if(nm) chips.push({k:p[0],id:id,name:nm}); });
      });
      var chipAlias=[]; chips.forEach(function(c){ ((CFG.aliases[c.k]||{})[c.id]||[]).forEach(function(a){ chipAlias.push(a); }); });
      /* the card: what it shows on the timeline */
      INDEX.push({group:0, target:'node', id:n.id, kind:n.tag||kind('node'), title:shown, ord:ordOf(n.id),
        fields:[{w:10,text:n.title||'',ac:1},{w:4,text:parent?titles[parent]:''},{w:7,text:num+' '+onum,num:1},
                {w:4,text:n.tag||''},{w:3.2,text:n.desc||'',key:'desc'},
                {w:3,text:chips.map(function(c){ return c.name; }).join(' \u00b7 '),key:'chips'},
                {w:2.6,text:chipAlias.join(' \u00b7 ')}],
        desc:n.desc||'', chips:chips, num:onum||num, unit:unit, parent:parent?titles[parent]:''});
      /* its page: everything written there beyond the card */
      var d=(typeof NODE_DETAILS!=='undefined'&&NODE_DETAILS[n.id])||{}, ss=secs(d.sections);
      if(ss.length){
        INDEX.push({group:1, target:'page', type:'node', id:n.id, kind:'Details', title:shown, ord:ordOf(n.id),
          fields:[{w:8,text:n.title||''}].concat(ss.map(function(s){ return {w:1.6,text:strip(s.t),h:strip(s.h)}; })).concat(ss.map(function(s){ return {w:4,text:strip(s.h),h:strip(s.h)}; })),
          body:true, num:onum||num, unit:unit, parent:parent?titles[parent]:''});
      }
    });
    [['char',typeof CHARS!=='undefined'?CHARS:null,typeof CHAR_PAGES!=='undefined'?CHAR_PAGES:{}],
     ['env',typeof ENVS!=='undefined'?ENVS:null,null],
     ['theme',typeof THEMES!=='undefined'?THEMES:null,null]].forEach(function(p){
      var T=p[1]; if(!T) return;
      Object.keys(T).forEach(function(id){
        var v=T[id]; if(!v||!v.name) return;
        var ss=secs((p[2]&&p[2][id]&&p[2][id].sections)||v.sections), al=(CFG.aliases[p[0]]||{})[id]||[];
        INDEX.push({group:1, target:'page', type:p[0], id:id, kind:kind(p[0]), title:strip(v.name), alias:al,
          fields:[{w:10,text:strip(v.name),ac:1},{w:9,text:al.join(' \u00b7 ')},{w:3,text:strip(v.role||'')},
                  {w:2.5,text:kind(p[0])+' '+((CFG.labels||{})[p[0]]||'')}]
            .concat(ss.map(function(s){ return {w:1.6,text:strip(s.t),h:strip(s.h)}; })),
          body:true, role:strip(v.role||'')});
      });
    });
    try{
      var inner=document.getElementById('summary-inner');
      if(inner){
        var sect='Overview';
        Array.prototype.forEach.call(inner.children, function(el){
          var st=el.getAttribute('style')||'';
          if(el.tagName==='H2' || /uppercase/.test(st)){ sect=(el.textContent||'').trim(); return; }
          var c=el.cloneNode(true);
          Array.prototype.forEach.call(c.querySelectorAll('.ov-node-btn'), function(b){ b.parentNode.removeChild(b); });
          var txt=(c.textContent||'').replace(/\s+/g,' ').trim();
          if(txt) INDEX.push({group:1, target:'overview', el:el, kind:'Overview', title:sect, fields:[{w:2,text:sect},{w:1.2,text:txt}], body:true});
        });
      }
    }catch(e){}
    return INDEX;
  }
  function search(q){
    var Q=M.query(q); if(!Q.toks.length || Q.raw.length<2) return [];
    var idx=build(), out=[];
    idx.forEach(function(r){
      var s=M.score(Q,r); if(!s) return;
      out.push({r:r, s:s, rank:s.score});
    });
    /* nothing has every word: offer what has all but one of them */
    if(!out.length && Q.toks.length>=2){
      idx.forEach(function(r){
        var s=M.score(Q,r,{allow:1}); if(!s) return;
        out.push({r:r, s:s, rank:s.score});
      });
    }
    /* a typo match is only offered when nothing matches properly */
    if(out.some(function(o){ return o.s.exact; })) out=out.filter(function(o){ return o.s.exact; });
    /* cards come before pages among the strong matches (at least 60% of the
       best), and before pages among the rest: a page named exactly what was
       typed still outranks cards that only mention it */
    var top=0; out.forEach(function(o){ if(o.s.score>top) top=o.s.score; });
    /* and whatever is named exactly what was typed comes first of all */
    out.forEach(function(o){ o.tier=o.s.named?-1:(o.s.score>=0.6*top?0:2)+o.r.group; });
    out.sort(function(a,b){ return a.tier-b.tier || b.s.score-a.s.score || (a.r.ord||0)-(b.r.ord||0) || (a.r.title||'').length-(b.r.title||'').length; });
    out=out.slice(0,60);
    out.forEach(function(o){ o.snip=snip(o,Q); o.r.text=o.snipText; o.q=q; o.r._q=q; });
    return out;
  }
  /* the snippet: for a card, what on the card matched (its summary, or which
     of its chips); for a page, the section the words were found in */
  function snip(o,Q){
    var r=o.r, F=r.fields[o.s.field]||r.fields[0];
    if(r.target==='node'){
      if(F.key==='chips' || (F!==r.fields[4] && o.s.field>=5)){
        var lit=r.chips.filter(function(c){ return M.lit(Q,c.name); }).concat(r.chips.filter(function(c){
          return ((CFG.aliases[c.k]||{})[c.id]||[]).some(function(a){ return M.lit(Q,a); }); }));
        if(lit.length){ var c=lit[0]; o.snipText=c.name; return M.esc(kind(c.k))+': '+M.snippet(c.name,Q); }
      }
      o.snipText=r.desc; return M.snippet(r.desc,Q);
    }
    if(r.target==='page'){
      if(!F.h || F.text===F.h){
        /* matched by name: the first section that mentions the words, else the first real one */
        var hs=r.fields.filter(function(f){ return f.h && f.text!==f.h; });
        F=hs.filter(function(f){ return M.snippet(f.text,Q).indexOf('<mark>')>=0; })[0]
          || hs.filter(function(f){ return f.text.length>=40; })[0] || hs[0] || F;
      }
      o.snipText=F.text;
      return (F.h?'<b>'+M.esc(F.h)+'</b> \u00b7 ':'')+M.snippet(F.text,Q);
    }
    o.snipText=r.fields[1].text; return M.snippet(r.fields[1].text,Q);
  }
  /* rows for any of the three search surfaces, with a heading per group */
  function rowsHtml(res,attr){
    if(big()) return res.map(function(o,i){ return richRow(o,attr,i); }).join('');
    var html='', g=-1;
    res.forEach(function(o,i){
      html+='<button type="button" class="search-result" '+attr+'="'+i+'"><span class="sr-kind">'+M.esc(o.r.kind)+'</span>'
          +'<span class="sr-title">'+M.esc(o.r.title)+'</span><span class="sr-snip">'+o.snip+'</span></button>';
    });
    return html;
  }
  /* the expanded desktop search: more of each hit (class set by the expand control) */
  function big(){ var h=document.documentElement; return h.classList.contains('sx-big') && !h.classList.contains('mobile'); }
  /* up to n sections of a page that mention the words, each with room to read */
  function passages(o,Q,n){
    var r=o.r, hs=r.fields.filter(function(f){ return f.h && f.text!==f.h && f.text; }), best=r.fields[o.s.field];
    var at=hs.indexOf(best); if(at>0){ hs.splice(at,1); hs.unshift(best); }
    var got=[];
    for(var i=0;i<hs.length && got.length<n && i<80;i++){
      var sn=M.snippet(hs[i].text,Q,360);
      if(sn.indexOf('<mark>')>=0) got.push('<span class="sr-pass"><b>'+M.hl(hs[i].h,Q)+'</b>'+sn+'</span>');
    }
    if(!got.length) hs.slice(0,2).forEach(function(f){ got.push('<span class="sr-pass"><b>'+M.hl(f.h,Q)+'</b>'+M.snippet(f.text,Q,300)+'</span>'); });
    return got.join('');
  }
  function richRow(o,attr,i){
    var r=o.r, Q=M.query(o.q||''), meta=[], body='';
    if(r.unit) meta.push(r.unit);
    if(r.target==='node'){
      if(r.parent) meta.push(r.parent);
      body='<span class="sr-full">'+M.hl(r.desc,Q)+'</span>';
      if(r.chips.length) body+='<span class="sr-chips">'+r.chips.map(function(c){
        return '<span class="sr-chip'+(M.lit(Q,c.name)?' lit':'')+'" title="'+M.esc(kind(c.k))+'">'+M.hl(c.name,Q)+'</span>'; }).join('')+'</span>';
    } else if(r.target==='page'){
      if(r.role) meta.push(r.role);
      body=passages(o,Q,4);
    } else {
      body='<span class="sr-full">'+M.snippet(r.fields[1].text,Q,700)+'</span>';
    }
    return '<button type="button" class="search-result sr-rich" '+attr+'="'+i+'"><span class="sr-head"><span class="sr-kind">'+M.esc(r.kind)+'</span>'
      +(r.num?'<span class="sr-num">'+M.esc(r.num)+'</span>':'')+'<span class="sr-title">'+M.hl(r.title,Q)+'</span></span>'
      +(meta.length?'<span class="sr-meta">'+meta.map(M.esc).join(' · ')+'</span>':'')+body+'</button>';
  }

  // ---- landing ----
  var _ring=null;
  function clearRing(){
    if(!_ring) return;
    var el=_ring; _ring=null;
    el.classList.remove('alto-found'); el.classList.add('alto-found-out');
    setTimeout(function(){ el.classList.remove('alto-found-out'); },450);
  }
  function ring(el){
    if(!el) return; clearRing();
    _ring=el; el.classList.remove('alto-found-out'); void el.offsetWidth; el.classList.add('alto-found');
  }
  function mobile(){ return document.documentElement.classList.contains('mobile'); }
  /* a card: enlarged where it sits, with a ring round it for as long as it is
     the enlarged card */
  function land(id){
    var node=document.getElementById('node-'+id); if(!node) return;
    var dp=document.getElementById('detail-page');
    if(dp && dp.classList.contains('visible') && typeof showTimeline==='function') showTimeline();
    if(mobile()){
      if(typeof window.featureNode==='function') window.featureNode(id,true);
      setTimeout(function(){ ring(document.getElementById('node-'+id)); },120);
      return;
    }
    if(typeof window.enterFocus==='function'){
      window.enterFocus(id);
      setTimeout(function(){ if(window._focusedNodeId===id) ring(node); },60);
    } else {
      node.scrollIntoView({block:'center',inline:'center'}); ring(node);
    }
  }
  /* a page: opened, the matched words lit for a few seconds */
  function lightUp(root,Q,scroller){
    if(!root) return;
    var tw=document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {acceptNode:function(t){
      var p=t.parentNode; if(!p || /^(SCRIPT|STYLE|MARK)$/.test(p.nodeName)) return NodeFilter.FILTER_REJECT;
      return /\S/.test(t.nodeValue)?NodeFilter.FILTER_ACCEPT:NodeFilter.FILTER_REJECT; }});
    var texts=[], t; while((t=tw.nextNode())) texts.push(t);
    var marks=[], re=/[A-Za-z0-9\u00C0-\u024F]+(?:['.\-][A-Za-z0-9\u00C0-\u024F]+)*/g;
    texts.forEach(function(tn){
      var s=tn.nodeValue, m, spans=[]; re.lastIndex=0;
      while((m=re.exec(s))){ if(M.lit(Q,m[0])) spans.push([m.index,m.index+m[0].length]); }
      if(!spans.length) return;
      var frag=document.createDocumentFragment(), at=0;
      spans.forEach(function(p){
        if(p[0]>at) frag.appendChild(document.createTextNode(s.slice(at,p[0])));
        var mk=document.createElement('mark'); mk.className='alto-sr-hit'; mk.textContent=s.slice(p[0],p[1]);
        frag.appendChild(mk); marks.push(mk); at=p[1];
      });
      if(at<s.length) frag.appendChild(document.createTextNode(s.slice(at)));
      tn.parentNode.replaceChild(frag,tn);
    });
    if(!marks.length) return;
    /* the first hit below the page's header, a third of the way down */
    var first=marks.filter(function(m){ return !m.closest('.detail-header'); })[0]||marks[0];
    try{
      if(scroller){
        var r=first.getBoundingClientRect(), sr=scroller.getBoundingClientRect();
        var y=scroller.scrollTop+(r.top-sr.top)-scroller.clientHeight/3;
        if(r.top-sr.top>scroller.clientHeight*0.6 || r.top<sr.top) scroller.scrollTo({top:Math.max(0,y),behavior:'smooth'});
      } else first.scrollIntoView({block:'center',behavior:'smooth'});
    }catch(e){}
    setTimeout(function(){ marks.forEach(function(m){ m.classList.add('fade'); }); },4200);
    setTimeout(function(){
      marks.forEach(function(m){
        var p=m.parentNode; if(!p) return;
        p.replaceChild(document.createTextNode(m.textContent),m); p.normalize();
      });
    },5600);
  }
  function go(o){
    var r=o.r||o, q=o.q||'', Q=M.query(q);
    var sw=document.getElementById('summary-wrap');
    var ovOpen=false; try{ ovOpen=(typeof summaryOpen!=='undefined'&&summaryOpen)||(sw&&sw.classList.contains('open')); }catch(e){}
    if(r.target!=='overview' && ovOpen && typeof toggleSummary==='function') toggleSummary();
    if(r.target==='node'){ setTimeout(function(){ land(r.id); }, ovOpen?260:30); return; }
    if(r.target==='page'){
      if(typeof showDetail==='function') showDetail(r.type, r.id);
      /* after the page's own post-render passes (auto-links, chips) */
      setTimeout(function(){
        lightUp(document.getElementById('detail-content'), Q, document.getElementById('detail-page'));
      },180);
      return;
    }
    if(r.target==='overview'){
      if(!ovOpen && typeof toggleSummary==='function') toggleSummary();
      setTimeout(function(){ lightUp(r.el,Q,null); },380);
    }
  }
  /* the ring goes when its card stops being the enlarged / featured one */
  document.addEventListener('keydown',function(e){ if(_ring && e.key==='Escape') clearRing(); },true);
  new MutationObserver(function(){
    if(!_ring) return;
    if(!mobile() && !_ring.classList.contains('focused')) clearRing();
  }).observe(document.documentElement,{subtree:true,attributes:true,attributeFilter:['class']});
  (function hook(){
    var fn=window.featureNode;
    if(typeof fn==='function' && !fn._altoRing){
      var w=function(id){ if(_ring && _ring.id!=='node-'+id) clearRing(); return fn.apply(this,arguments); };
      w._altoRing=true; for(var k in fn) if(Object.prototype.hasOwnProperty.call(fn,k)) w[k]=fn[k];
      window.featureNode=w; return;
    }
    if(!(fn && fn._altoRing)) setTimeout(hook,300);
  })();
  document.addEventListener('touchstart',function(e){
    if(!_ring || !mobile()) return;
    if(e.target.closest && (e.target.closest('#m-search')||e.target.closest('#m-search-results'))) return;
    setTimeout(clearRing,1200);
  },{passive:true,capture:true});

  window._altoSearch={build:build, search:search, go:go, land:land, rowsHtml:rowsHtml,
    snippet:function(text,q){ return M.snippet(text,M.query(q)); }};
})();
"""

SEARCH_CSS = """<style id="alto-search-css">
  .sr-group{padding:8px 12px 4px;font-size:10px;letter-spacing:.09em;text-transform:uppercase;
    color:var(--muted);font-weight:600;opacity:.85;}
  .sr-group:not(:first-child){border-top:1px solid var(--border);margin-top:4px;padding-top:10px;}
  .search-result .sr-snip b{font-weight:600;color:var(--text);opacity:.8;}
  #search-results{max-height:min(62vh,480px);overflow-y:auto;overscroll-behavior:contain;}
  /* a card search landed on: ringed while it is the enlarged / featured card */
  .node.alto-found .node-card{outline:3px solid var(--alto-found,#f5b83d);outline-offset:6px;
    animation:altoFoundIn .9s cubic-bezier(.2,.7,.3,1) both;}
  .node.alto-found-out .node-card{outline:3px solid transparent;outline-offset:10px;
    transition:outline-color .4s ease,outline-offset .4s ease;}
  @keyframes altoFoundIn{0%{outline-color:transparent;outline-offset:22px}
    55%{outline-color:var(--alto-found,#f5b83d);outline-offset:3px}100%{outline-offset:6px}}
  html.mobile .node.alto-found .node-card{outline-width:2.5px;outline-offset:-1px;animation:none;}
  mark.alto-sr-hit{background:rgba(245,184,61,.55);color:inherit;border-radius:3px;padding:0 1px;
    box-shadow:0 0 0 2px rgba(245,184,61,.35);transition:background-color 1.2s ease,box-shadow 1.2s ease;}
  mark.alto-sr-hit.fade{background:rgba(245,184,61,0);box-shadow:0 0 0 2px rgba(245,184,61,0);}
  @media (prefers-reduced-motion:reduce){ .node.alto-found .node-card{animation:none;} }
</style>"""


# ── the expanded desktop search (timeline and homepage) ─────────────────────
# A control in the search box grows the results into a large centred panel with
# bigger type and more of each hit (rowsHtml / richRow above; the homepage's
# own row below). The choice is remembered in localStorage. Desktop only.
_SX_CSS_SRC = """<style id="alto-sx-css">
#sx-toggle{display:none;flex:0 0 auto;align-items:center;justify-content:center;gap:7px;height:26px;min-width:26px;margin:0 6px 0 0;
  padding:0 5px;border:1px solid transparent;border-radius:8px;background:transparent;color:var(--muted);cursor:pointer;font:inherit;}
#sx-toggle:hover,#sx-toggle:focus-visible{color:var(--text);border-color:var(--muted);outline:none;}
#sx-toggle svg{width:15px;height:15px;display:block;}
#sx-toggle .sx-i-shrink,html.sx-big #sx-toggle .sx-i-grow{display:none;}
html.sx-big #sx-toggle .sx-i-shrink{display:block;}
#search-btn.expanded #sx-toggle{display:flex;}
.sx-hint{display:none;font-size:11.5px;color:var(--muted);white-space:nowrap;}
#sx-scrim{display:none;}
.search-result.sx-active{background:var(--btn-hover-bg);}
@media (min-width:641px){
html:not(.mobile).sx-big.sx-open #sx-scrim{display:block;position:fixed;inset:0;z-index:599;background:rgba(16,18,32,.30);}
html.dark:not(.mobile).sx-big.sx-open #sx-scrim{background:rgba(0,0,0,.48);}
/* sizes are true pixels: --sx-k undoes the page zoom, --sx-w/--sx-h are the viewport in the page's own px (set by the script) */
html:not(.mobile).sx-big #search-btn.expanded{position:fixed;
  width:min(@960,calc(var(--sx-w,1200px) * .84));top:max(@64,calc(var(--sx-h,800px) * .08));right:auto !important;bottom:auto !important;
  height:@58;border-radius:@16;z-index:600 !important;transition:none;}
html:not(.mobile).sx-big #search-btn.expanded,html:not(.mobile).sx-big #search-btn.expanded #search-results{background:rgba(251,251,255,.985);}
html.dark:not(.mobile).sx-big #search-btn.expanded,html.dark:not(.mobile).sx-big #search-btn.expanded #search-results{background:rgba(21,23,35,.985);}
html:not(.mobile).sx-big #search-btn.expanded #search-glyph{flex:0 0 @58;width:@58;height:@58;}
html:not(.mobile).sx-big #search-btn.expanded #search-glyph svg{width:@23;height:@23;}
html:not(.mobile).sx-big #search-btn.expanded #search-input{font-size:@20;padding-right:@12;}
html:not(.mobile).sx-big #search-btn.expanded .sx-hint{display:inline;margin-right:@12;font-size:@11.5;}
html:not(.mobile).sx-big #sx-toggle{height:@32;min-width:@32;margin-right:@12;border-radius:@8;}
html:not(.mobile).sx-big #sx-toggle svg{width:@18;height:@18;}
html:not(.mobile).sx-big #search-btn.expanded #search-results{position:absolute;left:0;right:auto;top:calc(100% + @8);bottom:auto;width:100%;
  max-height:min(calc(var(--sx-h,800px) - max(@64,calc(var(--sx-h,800px) * .08)) - @94),calc(var(--sx-h,800px) * .8 - @66));padding:@8;border-radius:@16;}
html:not(.mobile).sx-big .search-empty{font-size:@15;padding:@18;}
html:not(.mobile).sx-big .search-result{padding:@14 @18;border-radius:@12;}
html:not(.mobile).sx-big .search-result + .search-result{box-shadow:0 -1px 0 var(--border);}
html:not(.mobile).sx-big .search-result:hover,html:not(.mobile).sx-big .search-result.sx-active{background:var(--btn-hover-bg);box-shadow:none;}
html:not(.mobile).sx-big .search-result:hover + .search-result,html:not(.mobile).sx-big .search-result.sx-active + .search-result{box-shadow:none;}
.sr-rich .sr-head{display:flex;align-items:baseline;gap:@10;flex-wrap:wrap;}
.sr-rich .sr-kind{font-size:@10;margin-right:0;}
.sr-rich .sr-num{font-size:@13;color:var(--muted);font-variant-numeric:tabular-nums;}
.sr-rich .sr-title{font-size:@18;font-weight:600;line-height:1.3;}
.sr-rich .sr-meta{display:block;font-size:@12.5;color:var(--muted);margin-top:@3;}
.sr-rich .sr-full{display:block;font-size:@14.5;line-height:1.65;color:var(--text);opacity:.9;margin-top:@9;}
.sr-rich .sr-chips{display:flex;flex-wrap:wrap;gap:@6;margin-top:@10;}
.sr-rich .sr-chip{font-size:@11.5;border:1px solid var(--border);border-radius:999px;padding:@2 @10;color:var(--muted);}
.sr-rich .sr-chip.lit{color:var(--text);border-color:var(--muted);}
.sr-rich .sr-pass{display:block;margin-top:@10;padding-left:@13;border-left:2px solid var(--border);font-size:@14;line-height:1.65;color:var(--text);opacity:.9;}
.sr-rich .sr-pass b{display:block;font-size:@11;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);font-weight:600;margin-bottom:@2;opacity:1;}
html:not(.mobile).sx-big .search-result mark{background:rgba(167,139,250,.38);}
}
html.mobile #sx-toggle,html.mobile #sx-scrim,html.mobile .sx-hint{display:none !important;}
/* the homepage never carries .mobile; its phone layout is this media query, and a phone has no expanded panel */
@media (max-width:640px){#sx-toggle,#sx-scrim,.sx-hint{display:none !important;}}
</style>"""
# "@14.5" = 14.5 px at the viewer's true size, whatever the page zoom is
SX_CSS = re.sub(r"@(\d+(?:\.\d+)?)", r"calc(\1px * var(--sx-k,1))", _SX_CSS_SRC)

SX_JS = r"""
(function(){
  var root=document.documentElement;
  if(root.classList.contains('mobile') || window._altoSX) return;
  var btn=document.getElementById('search-btn'), input=document.getElementById('search-input'), res=document.getElementById('search-results');
  if(!btn||!input||!res) return;
  var KEY='alto-search-big', on=false, act=-1, ZV='--alto-'+'zoom';   /* the timeline's page zoom; the homepage has none */
  try{ on=localStorage.getItem(KEY)==='1'; }catch(e){}
  /* A phone never gets the large panel (the homepage's phone layout is a media query, not .mobile): the saved choice is
     kept for the desktop, but nothing of it applies here, so the pill and its list stay the phone's own. */
  function phone(){ return window.innerWidth<=640; }
  function big(){ return on && !phone(); }
  var tg=document.createElement('button'); tg.type='button'; tg.id='sx-toggle';
  tg.innerHTML='<span class="sx-hint">↑↓ move · Enter open · Esc shrink</span>'
    +'<svg class="sx-i-grow" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M9.5 2H14v4.5M14 2L9 7M6.5 14H2V9.5M2 14l5-5"/></svg>'
    +'<svg class="sx-i-shrink" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M14 6.5H9.5V2M9.5 6.5L14 2M2 9.5h4.5V14M6.5 9.5L2 14"/></svg>';
  btn.insertBefore(tg,res);
  var scrim=document.createElement('div'); scrim.id='sx-scrim'; document.body.appendChild(scrim);
  /* the viewport in the page's own px (the timeline runs at a zoom; vw/vh differ per engine) */
  function fit(){
    var z=parseFloat(getComputedStyle(root).getPropertyValue(ZV))||1, st=root.style;
    st.setProperty('--sx-k',String(1/z)); st.setProperty('--sx-w',(window.innerWidth/z)+'px'); st.setProperty('--sx-h',(window.innerHeight/z)+'px');
  }
  /* the page's own control alignment pins the box with inline !important right/left, so
     the centring is set the same way (and handed back when the box shrinks or closes) */
  var placed=false;
  function place(){
    if(big() && btn.classList.contains('expanded')){
      var z=parseFloat(getComputedStyle(root).getPropertyValue(ZV))||1, w=window.innerWidth/z, bw=Math.min(960/z,w*.84);
      var v=((w-bw)/2)+'px'; placed=true;
      if(btn.style.getPropertyValue('left')!==v || btn.style.getPropertyPriority('left')!=='important') btn.style.setProperty('left',v,'important');
    } else if(placed){ placed=false; btn.style.setProperty('left','auto','important'); }
  }
  fit(); window.addEventListener('resize',function(){ fit(); root.classList.toggle('sx-big',big()); setTimeout(place,0); });
  function label(){ var t=on?'Collapse search':'Expand search'; tg.title=t; tg.setAttribute('aria-label',t); tg.setAttribute('aria-pressed',on?'true':'false'); }
  function render(){ var f=window._altoSearchRender||window._homeSearchRender, v=input.value; if(f && v.trim().length>=2) f(v); }
  var pref=on;   /* the saved choice; Esc shrinks for now without changing it */
  function set(v,temp){
    on=!!v; root.classList.toggle('sx-big',big()); label(); act=-1;
    if(!temp){ pref=on; try{ localStorage.setItem(KEY,on?'1':'0'); }catch(e){} }
    place(); render(); try{ input.focus({preventScroll:true}); }catch(e){}
  }
  root.classList.toggle('sx-big',big()); label();
  tg.addEventListener('click',function(e){ e.stopPropagation(); set(!on); });
  new MutationObserver(function(){
    var open=btn.classList.contains('expanded');
    if(!open && on!==pref){ on=pref; root.classList.toggle('sx-big',big()); label(); }
    fit(); place(); root.classList.toggle('sx-open',open); })
    .observe(btn,{attributes:true,attributeFilter:['class','style']});
  new MutationObserver(function(){ act=-1; }).observe(res,{childList:true});
  function rows(){ return res.querySelectorAll('.search-result'); }
  function mark(i){
    var rs=rows(); if(!rs.length) return;
    if(act>=0 && rs[act]) rs[act].classList.remove('sx-active');
    act=(i+rs.length)%rs.length; rs[act].classList.add('sx-active');
    try{ rs[act].scrollIntoView({block:'nearest'}); }catch(e){}
  }
  btn.addEventListener('keydown',function(e){
    if(!btn.classList.contains('expanded')) return;
    if(e.key==='ArrowDown'||e.key==='ArrowUp'){ e.preventDefault(); mark(act<0?(e.key==='ArrowDown'?0:-1):act+(e.key==='ArrowDown'?1:-1)); }
    else if(e.key==='Enter' && act>=0){ var rs=rows(); if(rs[act]){ e.preventDefault(); e.stopPropagation(); rs[act].click(); } }
    else if(e.key==='Escape' && big()){ e.preventDefault(); e.stopPropagation(); set(false,true); }
  },true);
  function collapse(){ if(big() && btn.classList.contains('expanded')){ set(false,true); return true; } return false; }
  window._altoSXCollapse=collapse;
  window._altoSX={big:big, set:set, collapse:collapse};
})();
"""

# the homepage's own result row, expanded: full text with the matched words lit
HOME_ROW_JS = r"""
window._altoSXHomeRow=function(r,q){
  var M=window._altoMatch, Q=M.query(q||'');
  return '<span class="sr-head"><span class="sr-kind">'+M.esc(r.kind)+'</span><span class="sr-title">'+M.hl(r.title,Q)+'</span></span>'
    +(r.proj?'<span class="sr-meta">'+M.esc(r.proj)+'</span>':'')
    +(r.text?'<span class="sr-full">'+M.hl(r.text,Q)+'</span>':'');
};
"""


def sx_block(extra: str = "") -> str:
    """CSS + script for the expand control (after the page's own search)."""
    return SX_CSS + "\n<script id=\"alto-sx\">" + extra + SX_JS + "</script>\n"


def search_config(b: Brief) -> str:
    """What the index needs that the page does not already carry: every
    entity / axis value's aliases, and what to call each kind of page."""
    aliases = {"char": {e.id: list(e.aliases) for e in b.entities if e.aliases}}
    for k, i in (("env", 0), ("theme", 1)):
        ax = b.axes[i] if len(b.axes) > i else None
        aliases[k] = ({v.id: list(v.aliases) for v in ax.values if getattr(v, "aliases", None)}
                      if ax else {})
    kinds = {"node": b.node_noun, "char": b.entity_axis_singular}
    if len(b.axes) > 0:
        kinds["env"] = b.axes[0].singular
    if len(b.axes) > 1:
        kinds["theme"] = b.axes[1].singular
    labels = {"char": b.entity_axis_label}
    for k, i in (("env", 0), ("theme", 1)):
        if len(b.axes) > i:
            labels[k] = b.axes[i].label
    cfg = {"aliases": aliases, "kinds": kinds, "labels": labels}
    return ("<script>window._ALTO_SEARCH="
            + js_json(cfg) + ";</script>\n"
            + SEARCH_CSS + "\n<script id=\"alto-search-core\">" + MATCH_JS
            + TIMELINE_SEARCH_JS + "</script>\n" + sx_block())
