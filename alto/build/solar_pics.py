"""The System's picture panel (photos.py): a body that has pictures of the owner's own carries a small glowing tag from afar; as the
camera comes nearer a hologram panel rises from it, grows and turns to face the viewer, tethered to the body by a fine line (Luke,
2026-11-05: "7, i accept your recs": the rising panel, not "hand of god" and not the picture wrapped on the body).

The panel is flat HTML drawn over the 3D scene (no shader, no texture beyond the pictures' own small size, and it exists only for the body
the camera is nearest). It needs the scene's `window._altoSolar3D.screen(id)` (solar_3d.py: where a body is on screen, its radius in pixels).
Desktop only, in the 3D Star chart: a phone has no 3D System, a flat System shows the pictures in the plate beside an enlarged body (the tray of
photos.py, in the style the page is set to), and Reduce Motion stops the rising and the turning (the panel simply stands at its place).
Added to the hosted pictures script (it adds nothing to the page); a page without a System never runs it.
"""

CSS = r"""
#aph-hp{position:fixed;inset:0;z-index:62;pointer-events:none;perspective:900px;}
html:not(.sk-3d) #aph-hp,html.mobile #aph-hp{display:none;}
#aph-hp .hp-tag{position:absolute;width:20px;height:20px;margin:-10px 0 0 -10px;border:1px solid #4ff0e0;background:rgba(1,10,14,.78);color:#8ffcf2;font:700 10px/18px system-ui,sans-serif;text-align:center;
  box-shadow:0 0 10px rgba(79,240,224,.55);pointer-events:auto;cursor:pointer;padding:0;}
#aph-hp .hp-tag::before{content:'';position:absolute;inset:-5px;border:1px solid rgba(79,240,224,.35);animation:hp-ping 2.2s ease-out infinite;}
@keyframes hp-ping{from{transform:scale(.7);opacity:1;}to{transform:scale(1.5);opacity:0;}}
#aph-hp .hp-panel{position:absolute;left:0;top:0;transform-origin:0 50%;padding:8px;border:1px solid #4ff0e0;background:rgba(1,16,22,.82);color:#c9fffa;
  box-shadow:0 0 22px rgba(79,240,224,.42),inset 0 0 18px rgba(79,240,224,.12);will-change:transform,opacity;display:flex;flex-direction:column;gap:6px;}
#aph-hp .hp-panel::before{content:'';position:absolute;inset:0;pointer-events:none;background:repeating-linear-gradient(0deg,rgba(79,240,224,.06) 0 1px,transparent 1px 3px);}
#aph-hp .hp-panel button{display:block;position:relative;padding:0;border:1px solid rgba(79,240,224,.6);background:#010a0e;cursor:zoom-in;overflow:hidden;}
#aph-hp .hp-main{width:100%;aspect-ratio:4/3;}
#aph-hp .hp-main img,#aph-hp .hp-more img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;display:block;}
#aph-hp .hp-row{display:flex;gap:6px;}
#aph-hp .hp-more{flex:1 1 0;aspect-ratio:1;}
#aph-hp .hp-cap{font:11.5px/1.4 system-ui,sans-serif;letter-spacing:.04em;color:#8fc9c6;}
#aph-hp .hp-name{font:700 10px/1.2 system-ui,sans-serif;letter-spacing:.16em;text-transform:uppercase;color:#4ff0e0;}
#aph-hp .hp-tether{position:absolute;left:0;top:0;width:100%;height:100%;overflow:visible;pointer-events:none;}
#aph-hp .hp-tether line{stroke:#4ff0e0;stroke-width:1;stroke-dasharray:3 3;opacity:.8;}
html.printing #aph-hp{display:none;}
html.sk-3d .aph-tray{display:none !important;}
@media (prefers-reduced-motion:reduce){#aph-hp .hp-tag::before{animation:none;}}
"""

JS = r"""
  /* ── the System's rising panel (solar_pics.py) ── */
  (function(){
    var layer=null, tags={}, panel=null, panId=null, rafH=0, mq=window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)');
    function S3(){ var p=window._altoSolar3D; return p && p.on && p.screen && p.on() && !root.classList.contains('mobile') ? p : null; }
    function ids(){ var c=C(); return Object.keys(c).filter(function(k){ return (c[k]||[]).length; }); }
    function ensure(){ if(layer) return; layer=el('div'); layer.id='aph-hp'; document.body.appendChild(layer); }
    function sm(a, b, x){ var t=Math.max(0, Math.min(1, (x-a)/(b-a))); return t*t*(3-2*t); }
    function drop(){ if(panel && panel.parentNode) panel.parentNode.removeChild(panel); panel=null; panId=null; }
    function build(id, pics){
      var p=el('div','hp-panel'); p.setAttribute('role','group'); p.setAttribute('aria-label','Pictures of this body');
      var n=document.querySelector('#node-'+id+' .node-title'); p.appendChild(el('div','hp-name',(n && n.textContent) || 'Pictures'));
      var b=el('button','hp-main'); b.type='button'; b.setAttribute('aria-label',(pics[0].a||pics[0].c||'Picture')+' — open large');
      var im=el('img'); im.alt=pics[0].a||pics[0].c||''; b.appendChild(im); paint(im,null,pics[0].r,'th'); b.addEventListener('click', function(e){ e.stopPropagation(); lightbox(pics, 0); }); p.appendChild(b);
      if(pics[0].c) p.appendChild(el('div','hp-cap',pics[0].c));
      if(pics.length>1){ var row=el('div','hp-row'); pics.slice(1,4).forEach(function(it, j){ var m=el('button','hp-more'); m.type='button'; m.setAttribute('aria-label',(it.a||it.c||'Picture')+' — open large');
        var i2=el('img'); i2.alt=it.a||it.c||''; m.appendChild(i2); paint(i2,null,it.r,'th'); m.addEventListener('click', function(e){ e.stopPropagation(); lightbox(pics, j+1); }); row.appendChild(m); }); p.appendChild(row); }
      var NS='http://www.w3.org/2000/svg', sv=document.createElementNS(NS,'svg'); sv.setAttribute('class','hp-tether'); var ln=document.createElementNS(NS,'line'); sv.appendChild(ln); p._ln=ln; p._sv=sv;
      ['mousedown','pointerdown','wheel','dblclick'].forEach(function(t){ p.addEventListener(t, function(e){ e.stopPropagation(); }); });
      return p;
    }
    function frame(){
      rafH=0; var p3=S3(); var L=p3 ? ids() : [];
      if(!p3 || !L.length){ if(layer) layer.style.display='none'; drop(); return; }       // loop ends; the class watcher below starts it again
      ensure(); layer.style.display='';
      var focus=window._focusedNodeId, best=null, bestR=0, vw=window.innerWidth, vh=window.innerHeight, seen={};
      L.forEach(function(id){
        var q=p3.screen(id); var t=tags[id];
        var vis=q && q.fa>.3 && q.x>-40 && q.x<vw+40 && q.y>-40 && q.y<vh+40 && q.r>=1.5;
        if(!vis){ if(t) t.style.display='none'; return; }
        seen[id]=1;
        if(!t){ t=tags[id]=el('button','hp-tag'); t.type='button'; t.setAttribute('aria-label','This body has pictures'); layer.appendChild(t);
          t.addEventListener('click', function(e){ e.stopPropagation(); var f=window.enterFocus; if(f) f(id); }); }
        var n=(C()[id]||[]).length; if(t.textContent!==String(n)) t.textContent=n>1 ? String(n) : '▣';
        t.style.display=''; t.style.left=Math.round(q.x+q.r+10)+'px'; t.style.top=Math.round(q.y-q.r-8)+'px'; t.style.opacity=String(1-sm(60,110,q.r));
        var big=id===focus ? q.r+60 : q.r; if(big>bestR){ best=id; bestR=big; }
        t._q=q;
      });
      Object.keys(tags).forEach(function(k){ if(!seen[k] && tags[k].style.display!=='none') tags[k].style.display='none'; });
      var q=best && p3.screen(best), t2=0;
      if(q && best===focus){ var fc=document.querySelector('#node-'+focus+' .node-card'), rr=fc && fc.getBoundingClientRect();     // an enlarged body: clear of the disc the engine shows
        if(rr && rr.width) q={x:rr.left+rr.width/2, y:rr.top+rr.height/2, r:rr.width/2*1.18, fa:1}; t2=1; }
      else if(q) t2=sm(34, 120, q.r);
      if(!best || t2<=.02){ drop(); }
      else {
        if(panId!==best){ drop(); panel=build(best, C()[best]); panId=best; layer.appendChild(panel); layer.insertBefore(panel._sv, panel); }
        var w=Math.round(150+130*t2), x=q.x+q.r+34, left=false;
        if(x+w+20>vw){ x=q.x-q.r-34-w; left=true; }
        panel.style.width=w+'px';
        var h=panel.offsetHeight, y=Math.max(70, Math.min(vh-h-70, q.y-h/2));
        var reduce=mq && mq.matches, rise=reduce ? 0 : (1-t2), turn=reduce ? 0 : rise*(left ? 62 : -62);
        panel.style.transformOrigin=left ? '100% 50%' : '0 50%';
        panel.style.transform='translate('+Math.round(x)+'px,'+Math.round(y+rise*46)+'px) rotateY('+turn.toFixed(1)+'deg) scale('+(.62+.38*t2).toFixed(3)+')';
        panel.style.opacity=String(Math.min(1, t2*1.4)); panel.style.pointerEvents=t2>.55 ? 'auto' : 'none';
        var ex=left ? x+w : x, ey=y+h/2+rise*46;
        var ang=Math.atan2(ey-q.y, ex-q.x); panel._ln.setAttribute('x1', (q.x+Math.cos(ang)*q.r).toFixed(1)); panel._ln.setAttribute('y1', (q.y+Math.sin(ang)*q.r).toFixed(1));
        panel._ln.setAttribute('x2', ex.toFixed(1)); panel._ln.setAttribute('y2', ey.toFixed(1)); panel._sv.style.opacity=String(Math.min(1, t2*1.6));
        if(tags[best]) tags[best].style.display='none';
      }
      rafH=requestAnimationFrame(frame);
    }
    function kick(){ if(!rafH && S3() && ids().length) rafH=requestAnimationFrame(frame); }
    API.holo=kick;
    new MutationObserver(kick).observe(root, {attributes:true, attributeFilter:['class']});
    setInterval(kick, 1000);
    kick();
  })();
"""
