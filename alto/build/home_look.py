"""The homepage's look (item 15, Luke's answers 1C 2B 3B 4C 5C 6A 7A 8A; Art's spec ORG/notes-art-homepage-spec.md).

What this builds, on top of home_template.html (which is frozen, so everything is spliced in by pages.build_home):
  Q2B  the big faded format symbol stays, and the title is kept clear of it (a reserved zone beside it, never under it);
  Q3B  the strip across a card is the timeline's own unit colours: one equal segment per unit, at most seven, a single
       unit solid, none known = one segment in the format's accent; in the dark theme the same hues a tenth dimmer;
  Q7A  a phone shows the cards two to a row (three on a tablet), smaller: the title, the symbol and the same buttons;
  Q8A  the Classic | Retro switch: the page keeps the choice (backgrounds.head_block(..., retro=True)) and the Retro look
       for this page is retro.HOME_CSS, carried by the hosted Retro script like every other format's.
Left as they were: the card buttons and the ⋯ (Q1C), the corner controls on a computer (Q4C), the New timeline / project
flow (Q5C). Q6A (a bin icon) is held and not built.
"""
from __future__ import annotations

# the accent a card's strip wears when its units are not known (a timeline whose colours never reached the account yet)
FMT_ACCENT = {"timeline": "#4a9eff", "lanes": "#e8a87c", "outline": "#a78bfa", "system": "#fbbf24",
              "palace": "#10b981", "building": "#f472b6", "world": "#7dd3fc"}

# ── the strip (Q3B): replaces the template's unitStrip and the static tiles' inline strip ──
UNIT_STRIP_OLD = """function unitStrip(units){
  const u = (units && units.length) ? units : [null,null,null,null,null,null,null];
  return u.map(c => '<span' + (c && /^#[0-9a-fA-F]{3,8}$/.test(c)
    ? ' style="background:' + c + '"' : '') + '></span>').join('');
}"""
UNIT_STRIP_NEW = """const HOME_FMT_ACCENT = %s;
function unitStrip(units, fmt){
  // one equal segment per unit, in unit order, at most seven; none known = one segment in the format's accent
  const ok = (units || []).filter(c => c && /^#[0-9a-fA-F]{3,8}$/.test(c)).slice(0, 7);
  const u = ok.length ? ok : [HOME_FMT_ACCENT[fmt] || HOME_FMT_ACCENT.timeline];
  return u.map(c => '<span style="background:' + c + '"></span>').join('');
}""" % __import__("json").dumps(FMT_ACCENT)
STATIC_STRIP_OLD = """    const strip = (c.units || [null,null,null,null,null,null,null])
      .map(u => '<span' + (u ? ' style="background:'+u+'"' : '') + '></span>').join('');"""
STATIC_STRIP_NEW = "    const strip = unitStrip(c.units, c.fmt);"

# ── Classic CSS: appended after the template's own rules ──
_CLASSIC = """
/* Q2B: the title keeps clear of the big faded symbol: the symbol's box (132px, turned 6 degrees, 12px past the right edge) and a 12px gap are reserved */
@media (min-width:901px){
  .course-tile:not(.new-tile) .tile-title{ margin-right:115px; overflow-wrap:anywhere; }
  .course-tile.has-more .tile-title{ padding-right:0; }
}
html.dark .tile-emblem{ opacity:.22; }
/* Q3B: the strip is the timeline's own colours; in the dark theme the same hues a tenth dimmer */
html.dark .course-tile .unit-strip{ filter:brightness(.9); }
/* Q7A: two cards to a row on a phone, three on a tablet; a card is smaller: title top left, the symbol bottom right, the buttons along the bottom */
@media (max-width:900px){
  .course-tile{ --em:88px; min-height:132px; display:flex; flex-direction:column; }
  .course-grid{ grid-template-columns:repeat(3, minmax(0, 1fr)); gap:12px; }
  .project-slab{ padding:30px 22px 32px; }
  #projects-wrap{ padding-left:16px; padding-right:16px; }
  .course-tile .tile-body{ flex:1; padding:12px 14px 0; }
  .course-tile .tile-title{ font-size:16px; line-height:1.2; margin-bottom:6px; overflow-wrap:normal; }
  /* the card's ⋯ sits beside the first line only: a float keeps that line short and lets the rest run full width */
  .course-tile.has-more .tile-title{ padding-right:0; }
  .course-tile.has-more .tile-title::before{ content:''; float:right; width:34px; height:22px; }
  .course-tile .tile-sub{ min-height:calc(var(--em) + 20px); font-size:12px; }
  .course-tile .tile-emblem{ width:var(--em); height:var(--em); right:6px; bottom:4px; }
  .course-tile.new-tile{ min-height:132px; }
  .course-tile :is(.tile-reports, .tile-share, .tile-download){ width:28px; height:28px; bottom:12px; right:auto !important; }
  .course-tile .tile-share{ left:12px; } .course-tile .tile-reports{ left:46px; }
  .course-tile:has(.tile-download) .tile-download{ left:12px; }
  .course-tile:has(.tile-download) .tile-share{ left:46px; } .course-tile:has(.tile-download) .tile-reports{ left:80px; }
  .course-tile:not(:has(.tile-share)) .tile-reports{ left:12px; }
  .course-tile .tile-more{ top:10px; right:8px; }
  /* 28px chips with a 44px hit area (the padding is the pseudo-element) */
  .course-tile :is(.tile-reports, .tile-share, .tile-download)::after{ content:''; position:absolute; inset:-8px -3px; }
  .course-tile .tile-more::after{ content:''; position:absolute; inset:-11px -8px; }
}
@media (max-width:600px){
  .course-tile{ --em:72px; }
  .course-grid{ grid-template-columns:repeat(2, minmax(0, 1fr)); }
  .project-slab{ padding:26px 12px 28px; }
}
"""


# ── Recently deleted as a corner bin icon (Q6A, Luke 2026-10-28: "(a) Corner icon"): the same size as the other corner controls,
#    opens the list in a panel above it (no jump to the bottom of the page) ──
BIN_START = "function drawBin(pages){"
BIN_END = "  binSlab = g;\n}\n"
BIN_JS = r"""function drawBin(pages){
  if(binSlab){ binSlab.remove(); binSlab = null; }
  const c = window.AltoCloud;
  const items = (pages || []).filter(p => p.binned).sort((a, b) => b.binned - a.binned);
  if(!items.length || !c || !c.user) return;
  const days = c.binDays || 30;
  const g = document.createElement('div'); g.id = 'bin-corner';
  const btn = document.createElement('button'); btn.type = 'button'; btn.id = 'bin-btn';
  const nm = 'Recently deleted (' + items.length + ')';
  btn.title = nm; btn.setAttribute('aria-label', nm); btn.setAttribute('aria-expanded', binOpen ? 'true' : 'false');
  btn.innerHTML = '<svg viewBox="0 0 20 20" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3.5 6h13M8 6V4.2h4V6M5.2 6l.7 9.6a1.3 1.3 0 0 0 1.3 1.2h5.6a1.3 1.3 0 0 0 1.3-1.2L14.8 6M8.4 9v5M11.6 9v5"/></svg>';
  btn.classList.toggle('open', !!binOpen);
  btn.addEventListener('click', e => { e.stopPropagation(); binOpen = !binOpen; drawBin(lastPrivatePages); });
  const panel = document.createElement('div'); panel.id = 'bin-panel'; panel.hidden = !binOpen;
  const hd = document.createElement('div'); hd.className = 'bin-head'; hd.textContent = nm;
  panel.appendChild(hd);
  const list = document.createElement('div'); list.className = 'bin-list';
  items.forEach(pg => {
    const r = document.createElement('div'); r.className = 'bin-row';
    const tx = document.createElement('div'); tx.className = 'br-t';
    const b = document.createElement('b'); b.textContent = pg.heading || pg.title || 'Untitled timeline';
    b.insertAdjacentHTML('afterbegin', fmtBadge(pg.fmt));
    const left = Math.max(0, Math.ceil(days - (Date.now() / 1000 - pg.binned) / 86400));
    const sm = document.createElement('small');
    sm.textContent = (pg.project ? pg.project + ' · ' : '') + (left <= 1 ? 'removed for good within a day' : 'removed for good in ' + left + ' days');
    tx.appendChild(b); tx.appendChild(sm); r.appendChild(tx);
    const rb = document.createElement('button'); rb.type = 'button'; rb.textContent = 'Restore';
    rb.addEventListener('click', () => {
      rb.disabled = true;
      c.restoreTimeline(pg.key).then(() => { pg.binned = 0; showToast('Restored'); renderPrivate(); })
        .catch(() => { rb.disabled = false; showToast('Could not restore'); });
    });
    r.appendChild(rb); list.appendChild(r);
  });
  panel.appendChild(list);
  g.appendChild(btn); g.appendChild(panel);
  document.body.appendChild(g);
  binSlab = g;
}
if(!window._altoBinClose){
  window._altoBinClose = 1;
  const shut = () => { if(binOpen){ binOpen = false; drawBin(lastPrivatePages); } };
  document.addEventListener('click', e => { if(binOpen && binSlab && !binSlab.contains(e.target)) shut(); });
  document.addEventListener('keydown', e => { if(e.key === 'Escape') shut(); });
}
"""


def swap_bin(template: str) -> str:
    """The template's drawBin (a folded 'Recently deleted' group under the projects) becomes the corner bin's."""
    a = template.index(BIN_START)
    z = template.index(BIN_END, a) + len(BIN_END)
    return template[:a] + BIN_JS + template[z:]


BIN_CSS = """
/* Q6A: the bin: a corner control like the others (35px, bottom-left beside the account on a computer; in the top row, left of the
   background button, on a phone); the list opens in a panel above it, in place */
#bin-btn{ position:fixed; bottom:24px; left:71.5px; z-index:200; width:35px; height:35px; border-radius:50%; padding:0;
  display:flex; align-items:center; justify-content:center; color:var(--muted); cursor:pointer;
  background:var(--card-glass-bg); border:1px solid var(--card-glass-border);
  -webkit-backdrop-filter:blur(18px) brightness(var(--card-glass-bright)); backdrop-filter:blur(18px) brightness(var(--card-glass-bright));
  box-shadow:0 10px 26px var(--node-rest-shadow), inset 0 0 0 0.5px var(--card-glass-rim); }
#bin-btn:hover, #bin-btn.open{ border-color:var(--muted); color:var(--text); }
#bin-btn svg{ display:block; }
@media (min-width:641px){ #bin-btn{ zoom:var(--alto-zoom, 0.8); } #bin-panel{ zoom:var(--alto-zoom, 0.8); } }
#bin-panel{ position:fixed; left:24px; bottom:calc(24px + 35px + 12px); z-index:320; width:360px; max-width:calc(100vw - 32px); max-height:min(520px, 62vh);
  overflow-y:auto; padding:14px 14px 10px; border-radius:12px; color:var(--text);
  background:rgba(252,252,255,.95); border:1px solid var(--glass-slab-border);
  -webkit-backdrop-filter:blur(30px) saturate(185%); backdrop-filter:blur(30px) saturate(185%);
  box-shadow:0 18px 48px var(--node-hover-shadow), inset 0 1px 0 var(--card-glass-hi); }
html.dark #bin-panel{ background:rgba(18,20,30,.95); }
#bin-panel[hidden]{ display:none; }
#bin-panel .bin-head{ font-size:10.5px; letter-spacing:.14em; text-transform:uppercase; color:var(--muted); margin:0 2px 2px; }
#bin-panel .bin-list{ margin-top:8px; }
@media (max-width:640px){
  #bin-btn::after{ content:''; position:absolute; inset:-5px; }
  #bin-btn{ position:fixed !important; top:calc(63px + env(safe-area-inset-top,0px)); bottom:auto; left:auto; right:140px; width:34px; height:34px; border-radius:10px; }
  #bin-panel{ left:14px; right:14px; width:auto; max-width:none; top:calc(106px + env(safe-area-inset-top,0px)); bottom:auto; }
}
@media print{ #bin-corner{ display:none !important; } }
"""

CSS = '<style id="alto-home-look">' + _CLASSIC + BIN_CSS + "</style>"
