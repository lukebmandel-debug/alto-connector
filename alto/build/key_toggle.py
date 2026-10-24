"""The key of a horizontal timeline's lines, or of a Memory Palace's city.

A key is a toggle, not a panel that sits on the page: a round glass button like
the search / info / light-dark ones, floating at the top left of the page just
under the bars across the top, and the key opens beside it. Closed until asked
for; the choice is remembered per kind of key. Desktop only — a phone has no
room for one, and neither horizontal timelines nor Memory Palaces draw their key
there.

Both pages (lanes.py, palace.py) put KEY_CSS and KEY_JS in front of their own
and hand the panel they built to window._altoKeyToggle.
"""

KEY_CSS = """
  /* the key's toggle: the round glass of search / info / light-dark, top left, under the bars (--nav-bottom is the bars' real bottom) */
  #key-toggle{ position:fixed; z-index:310; left:30px; top:calc(var(--nav-bottom, 100px) + 14px); width:35px; height:35px; box-sizing:border-box; padding:0;
    border-radius:50%; display:flex; align-items:center; justify-content:center; cursor:pointer; color:var(--muted); touch-action:manipulation;
    background:var(--card-glass-bg, var(--surface));
    -webkit-backdrop-filter:blur(18px) saturate(190%) brightness(var(--card-glass-bright, 1)); backdrop-filter:blur(18px) saturate(190%) brightness(var(--card-glass-bright, 1));
    border:1px solid var(--card-glass-border, var(--border));
    box-shadow:0 10px 26px var(--node-rest-shadow), inset 0 0 0 0.5px var(--card-glass-rim); }
  #key-toggle:hover{ color:var(--text); border-color:var(--muted); }
  #key-toggle.active{ color:var(--accent, #6d5bd0); border-color:var(--accent, #6d5bd0); }
  #key-toggle svg{ display:block; }
  /* the key, opened: the glass of the other panels, just under its toggle */
  .key-pop{ position:fixed; z-index:309; left:30px; top:calc(var(--nav-bottom, 100px) + 14px + 35px + 10px); width:300px; max-width:calc(100vw - 80px);
    max-height:min(62vh, 560px); overflow:auto; box-sizing:border-box; padding:10px 12px 11px; border-radius:14px; display:none;
    font-size:12px; line-height:1.35; color:var(--text);
    background:var(--panel-glass-bg, var(--surface));
    -webkit-backdrop-filter:blur(30px) saturate(185%); backdrop-filter:blur(30px) saturate(185%);
    border:1px solid var(--card-glass-border, var(--border)); box-shadow:0 18px 48px var(--node-hover-shadow); }
  .key-pop.open{ display:block; }
  /* the text size: A- / A+ in the heading scale the whole panel from its top-left corner (a transform, so it stays put) */
  .key-pop{ transform-origin:0 0; transform:scale(var(--kp-s,1)); max-height:calc(min(62vh, 560px) / var(--kp-s,1)); }
  .key-pop .kp-sz{ margin-left:auto; display:inline-flex; gap:2px; letter-spacing:0; text-transform:none; }
  .key-pop .kp-sz button{ font:inherit; font-weight:700; line-height:1; min-width:24px; height:20px; padding:0 5px; border-radius:6px; cursor:pointer; color:var(--muted);
    background:transparent; border:1px solid color-mix(in srgb, var(--muted) 40%, transparent); }
  .key-pop .kp-sz button:hover:not(:disabled){ color:var(--text); border-color:var(--muted); }
  .key-pop .kp-sz button:disabled{ opacity:.35; cursor:default; }
  .key-pop .kp-sz .kp-sm{ font-size:10px; } .key-pop .kp-sz .kp-lg{ font-size:14px; }
  .key-pop h5{ margin:0 0 4px; font-size:11px; letter-spacing:.12em; text-transform:uppercase; color:var(--muted); display:flex; justify-content:space-between; gap:14px; }
  .key-pop h5 .kp-x{ cursor:pointer; letter-spacing:0; padding:0 2px; }
  .key-pop h5 .kp-x:hover{ color:var(--text); }
  html.mobile #key-toggle, html.mobile .key-pop, html.detail-open #key-toggle, html.detail-open .key-pop,
  html.printing #key-toggle, html.printing .key-pop{ display:none !important; }
"""

KEY_JS = r"""
(function(){
if(window._altoKeyToggle) return;
/* panel: the key's element (already built, with a <h5> heading); store: the localStorage key remembering whether it is open */
window._altoKeyToggle=function(panel, store, title){
  if(!panel || document.documentElement.classList.contains('mobile')) return null;
  var old=document.getElementById('key-toggle'); if(old) old.remove();
  panel.classList.add('key-pop');
  var b=document.createElement('button'); b.id='key-toggle'; b.type='button'; b.title=title||'Key'; b.setAttribute('aria-label', title||'Key'); b.setAttribute('aria-expanded','false');
  b.innerHTML='<svg viewBox="0 0 20 20" width="17" height="17" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" aria-hidden="true">'
    +'<circle cx="4.5" cy="5" r="1.3" fill="currentColor" stroke="none"/><path d="M8.5 5H17"/>'
    +'<circle cx="4.5" cy="10" r="1.3" fill="currentColor" stroke="none"/><path d="M8.5 10H17"/>'
    +'<circle cx="4.5" cy="15" r="1.3" fill="currentColor" stroke="none"/><path d="M8.5 15H14"/></svg>';
  function set(on, keep){
    panel.classList.toggle('open', !!on); b.classList.toggle('active', !!on); b.setAttribute('aria-expanded', on?'true':'false');
    if(!keep){ try{ localStorage.setItem(store, on?'1':'0'); }catch(e){} }
  }
  b.addEventListener('click', function(e){ e.stopPropagation(); set(!panel.classList.contains('open')); });
  var h=panel.querySelector('h5'); if(h){ var x=h.querySelector('span:last-child'); if(x){ x.className='kp-x'; x.textContent='✕'; x.setAttribute('role','button'); x.setAttribute('aria-label','Close');
    x.addEventListener('click', function(e){ e.stopPropagation(); set(false); }); } }
  var SIZES=[1,1.2,1.4,1.65], si=0; try{ si=Math.max(0,Math.min(SIZES.length-1, parseInt(localStorage.getItem('alto-key-size')||'0',10)||0)); }catch(e){}
  var sz=document.createElement('span'); sz.className='kp-sz'; sz.innerHTML='<button type="button" class="kp-sm" aria-label="Smaller text" title="Smaller text">A</button><button type="button" class="kp-lg" aria-label="Larger text" title="Larger text">A</button>';
  function size(i){ si=Math.max(0,Math.min(SIZES.length-1,i)); panel.style.setProperty('--kp-s', SIZES[si]); sz.querySelector('.kp-sm').disabled=si===0; sz.querySelector('.kp-lg').disabled=si===SIZES.length-1;
    try{ localStorage.setItem('alto-key-size', String(si)); }catch(e){} }
  sz.addEventListener('click', function(e){ e.stopPropagation(); var bt=e.target.closest('button'); if(bt) size(si+(bt.classList.contains('kp-lg')?1:-1)); });
  if(h){ var xx=h.querySelector('.kp-x'); h.insertBefore(sz, xx||null); } size(si);
  document.addEventListener('keydown', function(e){ if(e.key==='Escape' && panel.classList.contains('open') && !window._focusedNodeId) set(false); });
  document.body.appendChild(b); document.body.appendChild(panel);
  var was=false; try{ was=localStorage.getItem(store)==='1'; }catch(e){}
  set(was, true);
  return {button:b, panel:panel, set:set};
};
})();
"""
