"""Roman or arabic unit numbers, chosen per timeline (Luke, 2026-11-13: "let the user choose between roman numeral
units and numbered units").

Two choices, "roman" (I, II, III) and "numbers" (1, 2, 3). Never chosen, every format keeps the look it always had
(Roman band numerals on a timeline, arabic card and outline numbers); once chosen, every unit number in every format of
that timeline follows it. Only the unit level changes: "10.a.1" is "X.a.1" in Roman, the levels under it never change.

Where the choice comes from, newest first by its time (`t`, ms):
  * the page (Scene panel, desktop and phone): localStorage `alto-hl-{tid}-un` = {v, t}, synced with the owner's
    account like the background (alto-cloud.js: users/{uid}/tl/{tid} {un, unAt}, owner-only like the rest of that
    document);
  * the brief (MCP set_units(unit_numbers=...)): `unit_numbers` + `unit_numbers_at`, baked into the page;
  * a share link: the owner's choice, stamped into the shared copy when it is made or updated
    (`<script id="alto-un-owner">`, alto-cloud.js _sharePush). A share never reads or writes a choice of its own and its
    switch is shown read-only.

Every number is kept arabic in the page's data (NODE_ORDER_MAP, _ALTO_OUTLINE.num, PHASE_META's index), so editing,
renumbering and parsing are untouched; only what is shown is written the chosen way. Elements whose whole text is a
unit number or a path number (SEL) are rewritten in place when the choice changes and, while a choice is set, whenever
the page draws a new one (a MutationObserver, attached only once there is a choice: an unchosen page runs nothing).
Numbers inside longer text (search rows, detail pages, print, the palace's labels) are written at draw time through
window._altoP / window._altoU. The band numeral's collision box (timeline_template initLayout) is reserved for the
wider of its two spellings, so switching never moves a card."""
from __future__ import annotations

import json
import re

KEY_SUFFIX = "-un"
CHOICES = ("roman", "numbers")

# Whole-text unit numbers (.phase-numeral, .un-n) and path numbers (the rest).
# Card number labels (.node-order) are always arabic, whatever the choice (Luke 2026-11-24: "in nodes, the number label always uses the
# numeral version, not the roman numeral").
SEL = ".phase-numeral,.ol-num,.print-ol-num,.alto-lead-num,.el-num,.un-n,.un-p"

OWNER_EMPTY = '<script id="alto-un-owner">window._ALTO_UN_OWNER=null;</script>'
OWNER_BLOCK = re.compile(r'<script id="alto-un-owner">[\s\S]*?</script>')

HEAD_JS = r"""(function(){
  var K=__KEY__, B=__BRIEF__, SHARE=/^alto-hl-s-[a-km-np-z2-9]{22}-un$/.test(K), SEL=__SEL__, de=document.documentElement, mo=null, last='';
  var R=[[1000,'M'],[900,'CM'],[500,'D'],[400,'CD'],[100,'C'],[90,'XC'],[50,'L'],[40,'XL'],[10,'X'],[9,'IX'],[5,'V'],[4,'IV'],[1,'I']];
  function ok(o){ return !!o && (o.v==='roman' || o.v==='numbers') && typeof o.t==='number' && isFinite(o.t) && o.t>=0; }
  function newer(a, b){ return ok(a) ? (ok(b) && b.t>a.t ? b : a) : (ok(b) ? b : null); }
  function local(){ if(SHARE) return null; try{ return JSON.parse(localStorage.getItem(K)); }catch(e){ return null; } }
  function cur(){ var c=newer(B, SHARE ? window._ALTO_UN_OWNER : local()); return c ? c.v : ''; }
  function roman(n){ var s=''; R.forEach(function(p){ while(n>=p[0]){ s+=p[1]; n-=p[0]; } }); return s; }
  function deroman(s){ var n=0, i=0; R.forEach(function(p){ while(s.substr(i, p[1].length)===p[1]){ n+=p[0]; i+=p[1].length; } }); return i===s.length && roman(n)===s ? n : 0; }
  function u(n, d){ return (cur() || d)==='roman' ? roman(n) : String(n); }
  /* a text that starts with a unit number ("10", "X", "10.a.1", "X.a.1", "3.4-2"): its head written the chosen way; never chosen, as it is */
  var HEAD=/^(\s*)(\d+|[IVXLCDM]+)(?=$|[.\-\s])/;
  function p(s, d){ var m=cur() || d; return m ? to(s, m) : String(s==null ? '' : s); }
  function to(s, m){ s=String(s==null ? '' : s); var h=HEAD.exec(s); if(!h) return s; var n=/\d/.test(h[2]) ? +h[2] : deroman(h[2]); if(!n) return s;
    return h[1]+(m==='roman' ? roman(n) : String(n))+s.slice(h[0].length); }
  /* a number someone typed, back to the page's own arabic form: "X.a.1" / "x.a.1" -> "10.a.1" (a bare lower-case letter stays a letter) */
  function arabic(s){ s=String(s==null ? '' : s); var h=/^(\s*)([ivxlcdm]+)(?=$|[.\-\s])/i.exec(s); if(!h) return s;
    var up=h[2].toUpperCase(), n=deroman(up); if(!n || (h[2]!==up && h[0].length===s.length && cur()!=='roman')) return s; return h[1]+String(n)+s.slice(h[0].length); }
  function fix(e){ var t=e.textContent, v=p(t); if(v!==t && e.childElementCount===0) e.textContent=v; }
  function sweep(r){ (r || document).querySelectorAll && [].forEach.call((r || document).querySelectorAll(SEL), fix); }
  function watch(){ if(mo || typeof MutationObserver!=='function') return;
    mo=new MutationObserver(function(recs){ recs.forEach(function(rc){ var t=rc.target, e=t.nodeType===1 ? t : t.parentElement;
      if(e && e.closest){ var m=e.closest(SEL); if(m) fix(m); }
      if(rc.addedNodes) [].forEach.call(rc.addedNodes, function(a){ if(a.nodeType!==1) return; if(a.matches && a.matches(SEL)) fix(a); else if(a.firstElementChild) sweep(a); }); }); });
    mo.observe(de, {childList:true, subtree:true, characterData:true}); }
  function apply(){ var c=cur(); if(c) watch(); if(c===last) return; last=c; de.setAttribute('data-un', c); sweep();
    try{ window.dispatchEvent(new CustomEvent('alto-un-change', {detail:c})); }catch(e){} }
  function set(v){ if(SHARE || (v!=='roman' && v!=='numbers')) return false; try{ localStorage.setItem(K, JSON.stringify({v:v, t:Date.now()})); }catch(e){} apply(); return true; }
  /* the box a band numeral may take: the wider of its two spellings, so switching never moves a card (initLayout's collision check) */
  function wide(e){ var t=e.textContent, n=/\d/.test(t) ? +t : deroman(t), w=e.offsetWidth; if(!n) return w;
    [roman(n), String(n)].forEach(function(s){ if(s!==t){ e.textContent=s; w=Math.max(w, e.offsetWidth); } }); e.textContent=t; return w; }
  window._altoUN={key:K, share:SHARE, cur:cur, set:set, apply:apply, u:u, p:p, roman:roman, wide:wide, sweep:sweep, to:to, arabic:arabic};
  window._altoU=u; window._altoP=p;
  if(cur()){ last=cur(); de.setAttribute('data-un', last); watch(); }
  window.addEventListener('alto-un', apply);
  window.addEventListener('storage', function(e){ if(e && e.key===K) apply(); });
})();"""


def key_of(hl_key: str) -> str:
    return hl_key + KEY_SUFFIX


def _lean(text: str) -> str:
    text = re.sub(r"/\* .*?\*/", "", text, flags=re.S)
    return "\n".join(t for t in (ln.strip() for ln in text.split("\n")) if t and not t.startswith("//"))


def head_block(hl_key: str, brief) -> str:
    """The owner stamp (empty: a share's copy gets the owner's choice there) and the script, for <head>, ahead of every
    script that draws a number."""
    b = ({"v": brief.unit_numbers, "t": int(brief.unit_numbers_at or 0)}
         if getattr(brief, "unit_numbers", "") in CHOICES else None)
    js = (HEAD_JS.replace("__KEY__", json.dumps(key_of(hl_key))).replace("__BRIEF__", json.dumps(b))
          .replace("__SEL__", json.dumps(SEL)))
    return OWNER_EMPTY + '<script id="alto-un-head">' + _lean(js) + "</script>"


def stamp_owner(page_html: str, choice) -> str:
    """A share's copy carries the owner's choice ({v, t}, or None). Mirrors alto-cloud.js _unStamp."""
    ok = isinstance(choice, dict) and choice.get("v") in CHOICES and isinstance(choice.get("t"), (int, float)) \
        and choice["t"] >= 0
    js = "window._ALTO_UN_OWNER=" + (json.dumps({"v": choice["v"], "t": int(choice["t"])}) if ok else "null") + ";"
    return OWNER_BLOCK.sub(lambda _m: '<script id="alto-un-owner">' + js + "</script>", page_html, count=1)


# The switch in the Scene panel (backgrounds.UI_JS draws the panel; this adds its first row). A share shows it
# read-only, with the owner's choice lit.
PANEL_CSS = """
#bg-panel #bg-units{ display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:0 12px; min-height:44px; }
#bg-panel #bg-units .bg-h{ margin:0; }
html:not(.alto-retro):not(.sk-retro):not(.alto-holo) #bg-panel :is(#bg-units,#bg-style) .bg-h{ color:var(--text); }
#bg-panel #bg-units .bg-solar-seg{ display:inline-grid; grid-template-columns:repeat(2, 44px); width:auto; flex:0 0 auto; }
#bg-panel #bg-units .bg-solar-seg .bg-segb{ height:30px; padding:0; font-family:"Times New Roman",Times,serif; font-variant-numeric:lining-nums; font-feature-settings:"lnum" 1; font-size:14px; letter-spacing:.04em; line-height:1; }
/* the panel that holds only the style picker and this row hugs them: no air under the row (the scroll-edge fade and padding are for long lists) */
html:is(.alto-retro,.sk-retro) #bg-panel #bg-units .bg-segb.on{ background:#d9ae55; color:#000 !important; }   /* Retro's dark ink on gold, like its selected floor-bar pill (white on gold was 2.07:1) */
#bg-panel.bg-only #bg-units{ margin-bottom:0; }
#bg-panel.bg-only .bg-body::after{ display:none; }
html:not(.mobile) #bg-panel.bg-only .bg-body{ padding-bottom:0; -webkit-mask-image:none; mask-image:none; }
@media (max-width:640px), (pointer:coarse){ #bg-panel #bg-units .bg-solar-seg .bg-segb{ height:44px; } }
#bg-panel #bg-units .bg-segb[disabled]{ cursor:default; }
#bg-panel #bg-units .bg-segb[disabled]:not(.on){ opacity:.55; }
#bg-panel #bg-units .bg-un-note{ flex:0 0 100%; font-size:11px; line-height:1.4; color:var(--muted); margin:6px 2px 0; }
"""

PANEL_JS = r"""(function(){
  var U=window._altoUN; if(!U) return;
  function mark(row){ var c=U.cur() || 'roman';   /* nothing chosen: show the effective default, III, and store nothing */
    [].forEach.call(row.querySelectorAll('.bg-segb'), function(b){ var on=b.getAttribute('data-un')===c;
    b.classList.toggle('on', on); b.setAttribute('aria-pressed', on ? 'true' : 'false'); if(window._altoOnAcc) window._altoOnAcc(b); }); }
  function add(){
    var p=document.getElementById('bg-panel'), body=p && p.querySelector('.bg-body'); if(!body) return;
    var row=document.getElementById('bg-units');
    if(!row){
      row=document.createElement('div'); row.className='bg-sec'; row.id='bg-units';
      var h=document.createElement('div'); h.className='bg-h'; h.textContent='Unit numbers'; row.appendChild(h);
      var seg=document.createElement('div'); seg.className='bg-solar-seg'; seg.setAttribute('role', 'group'); seg.setAttribute('aria-label', 'Unit numbers');
      [['roman', 'III', 'Roman'], ['numbers', '3', 'Plain']].forEach(function(o){
        var b=document.createElement('button'); b.type='button'; b.className='bg-segb'; b.setAttribute('data-un', o[0]); b.textContent=o[1];
        b.setAttribute('aria-label', 'Unit numbers: '+o[2]); b.title=o[2];
        if(U.share){ b.disabled=true; b.title=o[2]+' (set by the owner of this timeline)'; }
        else b.addEventListener('click', function(e){ e.stopPropagation(); U.set(o[0]); mark(row); });
        seg.appendChild(b); });
      row.appendChild(seg);
      if(U.share){ var n=document.createElement('div'); n.className='bg-un-note'; n.textContent='Set by the owner of this timeline.'; row.appendChild(n); }
    }
    var st=document.getElementById('bg-style'), a=body.querySelector('.bg-auto'), after=(st && st.parentNode===body) ? st : (a && a.parentNode===body ? a : null);
    if(row.parentNode!==body || row.previousSibling!==after) body.insertBefore(row, after ? after.nextSibling : body.firstChild);
    mark(row);
  }
  function hook(){
    var p=document.getElementById('bg-panel'); if(!p){ return false; }
    new MutationObserver(function(){ if(p.classList.contains('open')) add(); }).observe(p, {attributes:true, attributeFilter:['class']});
    var b=p.querySelector('.bg-body'); if(b) new MutationObserver(function(){ if(p.classList.contains('open')) add(); }).observe(b, {childList:true});
    window.addEventListener('alto-un-change', function(){ var r=document.getElementById('bg-units'); if(r) mark(r); });
    return true; }
  var n=0; (function go(){ if(!hook() && ++n<80) setTimeout(go, 250); })();
})();"""


def panel_block() -> str:
    return ('<style id="alto-un-css">' + re.sub(r"\s+", " ", PANEL_CSS).strip() + "</style>"
            '<script id="alto-un-ui">' + _lean(PANEL_JS) + "</script>")
