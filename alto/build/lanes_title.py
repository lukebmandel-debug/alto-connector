"""The page's title on the horizontal timeline in Retro (Board B-1120-PICK267: option A).

Retro puts the name at the foot of a page (the cartouche, #sk-mark) and hides the top-row name (retro.py), but the horizontal
timeline's step bar has the bottom middle, so a Retro lanes page showed no title at all: only the crown's gold hairline. The name is
now set into that hairline, the rule breaking round the words. One line; an ellipsis when long, the full name on hover and as the
accessible name; 20px clear of the logo and wordmark; desktop-width lanes only (a phone has no .alto-lanes class and keeps its own
bar). Classic and Holographic keep the engine's name tab and are untouched."""

LT_CSS = r"""
  /* the page's name set into the Retro crown on a horizontal timeline (lanes_title.py) */
  #lt-t{display:none;}
  html.alto-retro.alto-lanes:not(.detail-open) #lt-t{display:flex;position:fixed;z-index:300;left:50%;top:20px;height:28px;transform:translateX(-50%);width:min(calc(100vw - 200px),760px);align-items:center;gap:16px;pointer-events:none;}
  html.alto-retro.alto-lanes:not(.detail-open) #sk-frame b{display:none;}
  html.alto-retro.alto-lanes #lt-t::before,html.alto-retro.alto-lanes #lt-t::after{content:"";flex:1 1 24px;height:1.5px;opacity:.7;background:linear-gradient(90deg,transparent,#d9ae55 70%);}
  html.alto-retro.alto-lanes #lt-t::after{background:linear-gradient(270deg,transparent,#d9ae55 70%);}
  html.alto-retro.alto-lanes #lt-t .lt-w{flex:0 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;pointer-events:auto;font-family:var(--rt-f);font-weight:400;font-size:14px;line-height:28px;letter-spacing:.4em;text-transform:uppercase;color:#d9ae55;}
  @media (max-width:760px){ html.alto-retro.alto-lanes:not(.detail-open) #lt-t{left:calc(70px / var(--alto-zoom,.8));right:calc(var(--lt-r,20px) / var(--alto-zoom,.8));width:auto;transform:none;} }   /* (the page is zoomed by --alto-zoom: insets in zoomed px) */
  @media (max-width:480px){ html.alto-retro.alto-lanes:not(.detail-open) #lt-t{gap:10px;}   /* a phone-width window: half the letter-spacing, the title takes the whole run from the logo to 20px short of the right edge */
    html.alto-retro.alto-lanes #lt-t::before,html.alto-retro.alto-lanes #lt-t::after{flex:1 1 10px;}
    html.alto-retro.alto-lanes #lt-t .lt-w{letter-spacing:.2em;font-size:13px;} }
  @media print{ #lt-t{display:none !important;} }
"""

LT_JS = r"""
(function(){
var de=document.documentElement;
if(!de.classList.contains('alto-lanes')) return;
var tt=document.getElementById('title-text'), box=document.createElement('div'), w=document.createElement('span');
box.id='lt-t'; box.setAttribute('role','heading'); box.setAttribute('aria-level','1'); w.className='lt-w'; box.appendChild(w); document.body.appendChild(box);
function clear(){ var b=document.querySelector('#title-bar .brand-word'), r=b && b.getBoundingClientRect(); box.style.setProperty('--lt-r', (r && r.width && r.left<innerWidth ? Math.max(20, innerWidth-r.left+20) : 20)+'px'); }
function paint(){ clear(); var s=String(tt ? tt.textContent : document.title).replace(/\s+/g,' ').trim(); w.textContent=s; box.setAttribute('aria-label', s); box.title=s; }
paint(); window.addEventListener('resize', clear);
if(tt && window.MutationObserver) new MutationObserver(paint).observe(tt,{childList:true,characterData:true,subtree:true});
})();
"""
