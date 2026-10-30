"""The Memory Atlas's hosted renderer (brief.palace_view "world"): /world/palace-world-<hash>.js, loaded by the page (palace_assets.py).

The page holds a ~350 byte loader and the page data (`window._ALTO_WORLD`, world_data below: each card's number, title, unit and — for the cards that
stand on the map — where, in world units, plus the clusters round them); the map itself is the hosted geodata (world_geo.py: base tier at 1:110m, a
continent's 1:50m detail and a country's state lines fetched when zoomed in). A page whose script or map is missing (an exported single file, no
network) keeps its cards.

Luke's design (2026-10-22, the spec in the CEO notes world-palace/): a smoothed real world (Equal Earth, coastlines curved), flat Alto glass land,
only the countries in use tinted (the unit's colour) and labelled; numbered pins; the route as curved flight arcs in the unit's colour with
direction chevrons, a dotted arc handing one unit to the next; a place opens into its cluster of cards; free zoom / pan, a click flies there, and a
Tour steps the route (◀ ▶, the arrow keys). Classic and Retro (retro.FORMAT_CSS styles #wpal-root); no first-person view. Text is only ever
written with textContent.

SEAMS: window.AltoWorld — data, mount(data), show(), hide(), select(nodeId) (enlarges it), hop(±1), tour(i), tourMode(on?) (the Tour switch; no argument reads it), unit(a), world(), view() -> {cx, cy, k}, on(event, fn)
('ready' when the map is drawn, 'select', 'land' when a flight ends).
"""
from __future__ import annotations

import hashlib as _hashlib
import json as _json

from .palace_assets import loader as _loader

WORLD_CSS = r"""
#wpal-root{--w-sea1:#eef2fb;--w-sea2:#dde6f6;--w-land:rgba(255,255,255,.93);--w-edge:rgba(110,125,165,.30);--w-grat:rgba(110,130,180,.11);
  --w-text:var(--text,#1d2433);--w-sub:var(--text-dim,#5b6478);--w-panel:rgba(255,255,255,.78);--w-panel-b:rgba(255,255,255,.95);
  --w-card:rgba(255,255,255,.9);--w-shadow:0 10px 30px rgba(40,55,95,.16);--w-font:inherit;--w-mix:#fff;--w-used:30%;--w-pin:#fff;
  position:fixed;left:0;right:0;bottom:0;top:var(--w-top,0px);z-index:30;overflow:hidden;touch-action:none;user-select:none;-webkit-user-select:none;
  background:radial-gradient(120% 90% at 50% 42%,var(--w-sea1),var(--w-sea2));color:var(--w-text);font-family:var(--w-font);}
html.dark #wpal-root{--w-sea1:#16203a;--w-sea2:#0b1122;--w-land:rgba(36,44,66,.95);--w-edge:rgba(170,185,225,.22);--w-grat:rgba(170,190,240,.07);
  --w-panel:rgba(20,26,42,.86);--w-panel-b:rgba(255,255,255,.12);--w-card:rgba(22,28,46,.94);--w-shadow:0 12px 32px rgba(0,0,0,.45);--w-mix:#1a2238;--w-used:42%;--w-pin:#121a2e;}
#wpal-root[hidden]{display:none;}
html.wpal-open #world{visibility:hidden !important;}
#wpal-root svg.wp-svg{position:absolute;inset:0;width:100%;height:100%;display:block;cursor:grab;}
#wpal-root.wp-drag svg.wp-svg{cursor:grabbing;}
#wpal-root .wp-grat{fill:none;stroke:var(--w-grat);stroke-width:1px;vector-effect:non-scaling-stroke;}
#wpal-root .wp-sphere{fill:none;stroke:var(--w-edge);stroke-width:1.2px;vector-effect:non-scaling-stroke;}
#wpal-root .wp-c{fill:var(--w-land);stroke:var(--w-edge);stroke-width:.8px;vector-effect:non-scaling-stroke;stroke-linejoin:round;fill-rule:evenodd;}
#wpal-root .wp-land{filter:drop-shadow(0 3px 5px rgba(40,55,95,.13));}
html.dark #wpal-root .wp-land{filter:none;}
#wpal-root .wp-c.wp-u{fill:color-mix(in srgb,var(--u) var(--w-used),var(--w-mix));stroke:color-mix(in srgb,var(--u) 80%,transparent);stroke-width:1.2px;cursor:pointer;}
#wpal-root .wp-c.wp-on{fill:color-mix(in srgb,var(--u) 52%,var(--w-mix));stroke-width:2.2px;}
#wpal-root.wp-focus .wp-c.wp-u:not(.wp-on){opacity:.55;}
#wpal-root .wp-a1{fill:none;stroke:var(--w-edge);stroke-width:.8px;stroke-dasharray:3 3;vector-effect:non-scaling-stroke;}
#wpal-root .wp-arc{fill:none;stroke-linecap:round;vector-effect:non-scaling-stroke;}
#wpal-root .wp-arc.h{stroke:color-mix(in srgb,var(--u) 35%,transparent);stroke-width:6px;}
#wpal-root .wp-arc.m{stroke:var(--u);stroke-width:3px;}
#wpal-root .wp-arc.s{stroke:rgba(255,255,255,.6);stroke-width:1px;}
#wpal-root .wp-arc.k{stroke:var(--u);stroke-width:1.6px;stroke-opacity:.85;}
#wpal-root .wp-arc.hand{stroke:var(--w-sub);stroke-width:1.6px;stroke-dasharray:2 7;stroke-opacity:.7;}
#wpal-root.wp-focus .wp-arcs g:not(.wp-on){opacity:.22;}
#wpal-root svg.wp-ov{position:absolute;inset:0;width:100%;height:100%;pointer-events:none;overflow:visible;}
#wpal-root .wp-chev{fill:none;stroke:#fff;stroke-width:1.8px;stroke-linecap:round;stroke-linejoin:round;}
#wpal-root .wp-link{fill:none;stroke:var(--u);stroke-width:2.2px;stroke-linecap:round;opacity:.9;}
#wpal-root .wp-dot{fill:var(--u);}
#wpal-root .wp-layer{position:absolute;inset:0;pointer-events:none;}
#wpal-root .wp-pin{position:absolute;left:0;top:0;width:12px;height:12px;translate:-50% -50%;border-radius:999px;box-sizing:border-box;pointer-events:auto;cursor:pointer;
  background:var(--w-pin);border:2px solid var(--u);box-shadow:0 0 0 3px color-mix(in srgb,var(--u) 25%,transparent);white-space:nowrap;
  display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:700;line-height:1;color:color-mix(in srgb,var(--u) 75%,#000);}
html.dark #wpal-root .wp-pin{color:color-mix(in srgb,var(--u) 70%,#fff);}
/* a numbered pin is a pill as wide as its number ("2.1-11" stays inside it), centred on its place */
#wpal-root .wp-pin.n{width:auto;min-width:24px;height:24px;padding:0 5px;}
#wpal-root .wp-pin.wp-on{min-width:34px;height:34px;font-size:11px;border-width:2.5px;}
#wpal-root .wp-pin.wp-on:not(.n){width:34px;}
#wpal-root .wp-pin.wp-dim{opacity:.16;}
#wpal-root .wp-c.wp-u.wp-dim{opacity:.4;}
#wpal-root .wp-card.wp-dim{opacity:.35;}
/* an enlarged card is the timeline's own card, borrowed from the hidden board while it shows (its chips, highlights, filters and edits
   come with it; a click on it opens its page, as everywhere in Alto) */
#wpal-root .wp-enl{position:absolute;left:0;top:0;pointer-events:auto;z-index:4;transform-origin:50% 100%;}
/* a Tour stop (Art's option B "Hand-off", 2026-10-29): the card a stop leaves folds into its own pin (220 ms) and the next grows out of its
   marker, starting just before the map stops; the origin of both is their pin, set every frame, so they ride it */
#wpal-root :is(.wp-enl,.wp-card){transition:opacity .3s cubic-bezier(.25,.2,.4,1),scale .78s cubic-bezier(.2,.75,.25,1);}
#wpal-root :is(.wp-enl,.wp-card).wp-grow{opacity:0;scale:.12;transition:none;}
#wpal-root .wp-ghost{position:absolute;left:0;top:0;pointer-events:none;z-index:3;transition:opacity .22s ease-in,scale .22s cubic-bezier(.5,0,.75,0);}
#wpal-root .wp-ghost.wp-fold{opacity:0;scale:.06;}
#wpal-root .wp-enl.kid{transform-origin:50% 50%;z-index:5;}
#wpal-root .wp-enl.s-down{transform-origin:50% 0;}#wpal-root .wp-enl.s-left{transform-origin:100% 50%;}#wpal-root .wp-enl.s-right{transform-origin:0 50%;}
#wpal-root .wp-enl > .node{position:relative !important;left:auto !important;top:auto !important;right:auto !important;bottom:auto !important;
  transform:none !important;translate:none !important;scale:none !important;rotate:none !important;margin:0 !important;opacity:1 !important;visibility:visible !important;
  display:block !important;animation:none !important;zoom:1.18;}
#wpal-root .wp-enl > .node > .node-card{position:relative !important;left:auto !important;top:auto !important;transform:none !important;scale:none !important;margin:0 !important;
  animation:none !important;opacity:1 !important;}
@media (prefers-reduced-motion: reduce){#wpal-root :is(.wp-enl,.wp-card){transition:opacity .15s linear;}#wpal-root :is(.wp-enl,.wp-card).wp-grow{scale:1;transition:none;}
  #wpal-root .wp-ghost{transition:opacity .15s linear;}#wpal-root .wp-ghost.wp-fold{scale:1;}}
#wpal-root .wp-rel{fill:none;stroke:var(--u);stroke-width:1.8px;stroke-dasharray:5 5;stroke-linecap:round;opacity:.85;}
#wpal-root .wp-reld{fill:var(--u);stroke:var(--w-pin);stroke-width:1.5px;}
#wpal-root .wp-relh{fill:none;stroke:transparent;stroke-width:16px;pointer-events:stroke;cursor:pointer;}
#wpal-root .wp-relh:hover ~ .wp-reld,#wpal-root g:hover > .wp-rel{stroke-width:3px;opacity:1;}
/* a background the reader picked (a photo, a colour, a pattern) is the sea: the land lies on it */
html.alto-bg:not(.alto-bg-map) #wpal-root{background:none;}
/* the map is not drawn over a card's page, nor while the cards are edited by hand */
html.detail-open #wpal-root{visibility:hidden !important;}
#wpal-root .wp-pin:focus-visible{outline:2px solid var(--u);outline-offset:3px;}
#wpal-root .wp-pin .wp-nm{position:absolute;right:-9px;top:-11px;width:11px;height:14px;pointer-events:none;}
#wpal-root .wp-pin .wp-nm path{fill:var(--u);stroke:var(--w-pin);stroke-width:1.5px;}
#wpal-root.wp-focus .wp-pin:not(.wp-in){opacity:.35;}
#wpal-root .wp-lbl{position:absolute;left:0;top:0;transform:translate(-50%,0);white-space:nowrap;text-align:center;font-size:11.5px;font-weight:650;line-height:1.25;
  text-shadow:0 0 3px var(--w-sea1),0 0 3px var(--w-sea1),0 0 6px var(--w-sea1);pointer-events:none;}
#wpal-root .wp-lbl i{display:block;font-style:normal;font-weight:500;font-size:11px;color:var(--w-sub);}
#wpal-root :is(.wp-lbl,.wp-tag,.wp-pin){transition:opacity .22s,visibility 0s linear 0s,width .22s,height .22s,margin .22s,font-size .22s;}
#wpal-root :is(.wp-lbl,.wp-tag).wp-off{opacity:0;visibility:hidden;pointer-events:none;transition:opacity .22s,visibility 0s linear .22s;}
#wpal-root .wp-tag{position:absolute;left:0;top:0;transform:translate(-50%,-50%);padding:3px 9px;border-radius:999px;border:1.5px solid var(--u);background:var(--w-card);
  font:inherit;font-size:11.5px;color:var(--w-text);white-space:nowrap;box-shadow:var(--w-shadow);pointer-events:auto;cursor:pointer;}
#wpal-root .wp-tag b{color:color-mix(in srgb,var(--u) 75%,var(--w-text));margin-right:4px;}
#wpal-root .wp-tag span{color:var(--w-sub);}
#wpal-root .wp-card{position:absolute;left:0;top:0;width:220px;box-sizing:border-box;padding:10px 13px 11px;border-radius:14px;background:var(--w-card);border:1px solid var(--w-panel-b);
  box-shadow:var(--w-shadow);-webkit-backdrop-filter:blur(14px);backdrop-filter:blur(14px);font-size:12px;line-height:1.35;pointer-events:auto;cursor:pointer;text-align:left;color:var(--w-text);font-family:var(--w-font);}
#wpal-root .wp-card:hover{border-color:var(--u);}
#wpal-root .wp-card .n{font-size:10.5px;font-weight:700;letter-spacing:.04em;color:color-mix(in srgb,var(--u) 80%,var(--w-text));text-transform:uppercase;}
#wpal-root .wp-card h4{margin:2px 0 0;font-size:14px;line-height:1.22;font-weight:650;}
#wpal-root .wp-card.main{width:290px;padding:13px 16px 14px;}
#wpal-root .wp-card.main h4{font-size:17px;}
#wpal-root .wp-card .pl{margin-top:5px;color:var(--w-sub);font-size:11.5px;}
#wpal-root .wp-list{position:absolute;right:20px;top:64px;bottom:96px;width:300px;overflow:auto;padding:10px;border-radius:14px;background:var(--w-panel);border:1px solid var(--w-panel-b);
  box-shadow:var(--w-shadow);pointer-events:auto;-webkit-backdrop-filter:blur(16px);backdrop-filter:blur(16px);touch-action:pan-y;}
#wpal-root .wp-list[hidden]{display:none;}
#wpal-root .wp-list button{display:block;width:100%;text-align:left;border:0;background:none;color:var(--w-text);font:inherit;font-size:13px;padding:7px 8px;border-radius:9px;cursor:pointer;}
#wpal-root .wp-list button:hover{background:color-mix(in srgb,var(--u) 14%,transparent);}
#wpal-root .wp-list button b{color:color-mix(in srgb,var(--u) 80%,var(--w-text));margin-right:6px;font-size:11px;}
#wpal-root .wp-bar{position:absolute;display:flex;align-items:center;gap:8px;padding:7px 9px;border-radius:14px;background:var(--w-panel);border:1px solid var(--w-panel-b);
  box-shadow:var(--w-shadow);-webkit-backdrop-filter:blur(16px);backdrop-filter:blur(16px);font-size:13px;white-space:nowrap;}
#wpal-root .wp-bar[hidden]{display:none;}
#wpal-root .wp-btn{border:1px solid var(--w-edge);background:none;color:var(--w-text);font:inherit;font-size:12.5px;padding:5px 11px;border-radius:9px;cursor:pointer;}
#wpal-root .wp-btn:hover{background:color-mix(in srgb,var(--w-text) 7%,transparent);}
#wpal-root .wp-btn.r{width:30px;height:30px;padding:0;border-radius:50%;display:flex;align-items:center;justify-content:center;}
#wpal-root .wp-ctl{right:16px;top:12px;}html.mobile #wpal-root .wp-ctl{top:112px !important;}
#wpal-root .wp-tour{left:50%;bottom:18px;transform:translateX(-50%);max-width:calc(100% - 32px);}
#wpal-root .wp-tour .d{color:var(--w-sub);overflow:hidden;text-overflow:ellipsis;max-width:180px;}
#wpal-root .wp-tour .c{font-weight:650;overflow:hidden;text-overflow:ellipsis;}
#wpal-root .wp-key{left:16px;bottom:66px;display:block;font-size:12px;line-height:20px;max-width:340px;white-space:normal;}
#wpal-root .wp-key button.u{display:flex;align-items:center;gap:7px;border:0;background:none;color:var(--w-text);font:inherit;padding:0 4px;border-radius:6px;cursor:pointer;width:100%;text-align:left;}
#wpal-root .wp-key button.u:hover{background:color-mix(in srgb,var(--u) 14%,transparent);}
#wpal-root .wp-key i{display:inline-block;width:10px;height:10px;border-radius:5px;background:var(--u);flex:none;}
#wpal-root .wp-key span{color:var(--w-sub);}
#wpal-root .wp-key .wp-kt{display:flex;align-items:center;gap:6px;border:0;background:none;color:var(--w-text);font:inherit;padding:0;cursor:pointer;}
#wpal-root .wp-key.shut .u,#wpal-root .wp-key.shut .wp-kn{display:none;}
#wpal-root .wp-key:not(.shut) .wp-kt{margin-bottom:4px;color:var(--w-sub);}
#wpal-root .wp-kn{color:var(--w-sub);margin-top:4px;display:flex;align-items:center;gap:6px;}
/* the Tour switch (Luke, 2026-10-26: "i can't turn tour mode off and freely go around the world"): on, the route as before; off, the map is free */
#wpal-root .wp-tt{display:flex;align-items:center;gap:7px;}
#wpal-root .wp-sw{position:relative;width:24px;height:14px;border-radius:7px;background:color-mix(in srgb,var(--w-text) 22%,transparent);transition:background .2s;flex:none;}
#wpal-root .wp-sw::after{content:'';position:absolute;left:2px;top:2px;width:10px;height:10px;border-radius:5px;background:var(--w-pin);box-shadow:0 1px 2px rgba(0,0,0,.25);transition:translate .2s;}
#wpal-root .wp-tt[aria-pressed="true"] .wp-sw{background:var(--accent,#5b6cff);}
#wpal-root .wp-tt[aria-pressed="true"] .wp-sw::after{translate:10px 0;}
#wpal-root .wp-tour .x{margin-left:2px;}
/* where a card stands ("Lima, Peru"; "Peru" for a country's own card): under the enlarged card, and on its page under its kind */
#wpal-root .wp-where{display:flex;align-items:center;gap:5px;margin:7px auto 0;width:max-content;max-width:100%;box-sizing:border-box;padding:3px 10px 3px 8px;border-radius:999px;
  background:var(--w-card);border:1px solid var(--w-panel-b);box-shadow:var(--w-shadow);font-size:10.5px;font-weight:600;line-height:1.3;letter-spacing:.12em;text-transform:uppercase;
  color:var(--w-sub);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;-webkit-backdrop-filter:blur(14px);backdrop-filter:blur(14px);}
#wpal-root .wp-where svg,#detail-page .wp-where-d svg{width:9px;height:11px;flex:none;}
#wpal-root .wp-where path,#detail-page .wp-where-d path{fill:var(--u,currentColor);}
#detail-page .wp-where-d{display:flex;align-items:center;gap:6px;margin-top:7px;font-size:12px;letter-spacing:.16em;text-transform:uppercase;color:var(--muted,#5b6478);}
html.alto-retro #wpal-root .wp-where:not(#_){border-radius:0;box-shadow:none;-webkit-backdrop-filter:none;backdrop-filter:none;font-family:var(--rt-f);font-weight:400;letter-spacing:.2em;color:#d9ae55;border-color:rgba(217,174,85,.55);background:#0b0d12;}
html.alto-retro #detail-page .wp-where-d:not(#_){color:#d9ae55;font-family:var(--rt-f);letter-spacing:.3em;}
html.alto-retro #wpal-root .wp-sw,html.alto-retro #wpal-root .wp-sw::after{border-radius:0;}
html.alto-retro #wpal-root .wp-tt[aria-pressed="true"] .wp-sw{background:#d9ae55;}
#wpal-root .wp-msg{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);color:var(--w-sub);font-size:13px;}
/* the key in Alto's floating key toggle (outside the map's root): the same rows */
.key-pop.wk button.u{display:flex;align-items:center;gap:7px;border:0;background:none;color:var(--text);font:inherit;padding:2px 4px;border-radius:6px;cursor:pointer;width:100%;text-align:left;line-height:20px;}
.key-pop.wk button.u:hover{background:color-mix(in srgb,var(--u) 14%,transparent);}
.key-pop.wk i{display:inline-block;width:10px;height:10px;border-radius:5px;background:var(--u);flex:none;}
.key-pop.wk span{color:var(--muted);}.key-pop.wk h5 span{color:inherit;}
.key-pop.wk .wp-kn{color:var(--muted);margin-top:4px;display:flex;align-items:center;gap:6px;}
html:not(.wpal-open) #key-toggle,html:not(.wpal-open) .key-pop.wk{display:none !important;}
html.alto-retro .key-pop.wk i{border-radius:0;}
/* moving round the map the System's way (solar_navopt.py, adapted): Back up a level, where you are, Next along the level, the minimap; the
   places beside the one you are on are lit and numbered (1-9); ? lists the keys. Desktop only: a phone keeps its map as it is (suggest-first). */
#wpal-root .wp-nav{left:16px;bottom:66px;gap:2px;padding:3px 5px;}
#wpal-root .wp-nav .wp-btn.r{border:0;width:28px;height:28px;color:var(--w-sub);}
#wpal-root .wp-nav .wp-btn.r:hover:not(:disabled){color:var(--w-text);}
#wpal-root .wp-nav .wp-btn.r:disabled{opacity:.35;cursor:default;}
#wpal-root .wp-nav .wp-btn.r.on{color:var(--accent,#5b6cff);}
#wpal-root .wp-nav svg{width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:1.6px;stroke-linecap:round;stroke-linejoin:round;}
#wpal-root .wp-at{border:0;background:none;font:inherit;font-size:12.5px;color:var(--w-sub);padding:0 6px;max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;cursor:pointer;line-height:28px;}
#wpal-root .wp-at b{color:var(--w-text);font-weight:650;}#wpal-root .wp-at:hover b{text-decoration:underline;text-underline-offset:3px;}
#wpal-root .wp-hk{position:absolute;right:-8px;top:-8px;min-width:15px;height:15px;padding:0 3px;box-sizing:border-box;border-radius:8px;background:var(--u);color:var(--w-pin);
  font-size:10px;font-weight:700;line-height:15px;text-align:center;pointer-events:none;font-family:var(--w-font);}
#wpal-root .wp-pin.wp-hint{box-shadow:0 0 0 5px color-mix(in srgb,var(--u) 38%,transparent);opacity:1 !important;}
#wpal-root .wp-pin.wp-hint:not(.n):not(.wp-on){width:16px;height:16px;}
#wpal-root .wp-lbl.wp-hint{font-size:12.5px;}#wpal-root .wp-lbl.wp-hint b{text-decoration:underline;text-decoration-color:color-mix(in srgb,var(--u) 60%,transparent);text-underline-offset:3px;}
#wpal-root .wp-card.wp-hint,#wpal-root .wp-enl.wp-hint{outline:0;}
#wpal-root .wp-mm{position:absolute;right:16px;bottom:66px;padding:5px;opacity:0;visibility:hidden;transition:opacity .28s ease,visibility 0s .28s;cursor:pointer;touch-action:none;}
#wpal-root .wp-mm.on{opacity:1;visibility:visible;transition:opacity .28s ease;}
#wpal-root .wp-mm svg{display:block;width:176px;height:86px;}
#wpal-root .wp-mm .c{fill:color-mix(in srgb,var(--w-text) 16%,transparent);stroke:none;}
#wpal-root .wp-mm .c.u{fill:color-mix(in srgb,var(--u) 55%,transparent);}
#wpal-root .wp-mm circle{fill:var(--u);stroke:none;}
#wpal-root .wp-mm circle.h{fill:none;stroke:var(--w-text);stroke-width:1.6px;vector-effect:non-scaling-stroke;}
#wpal-root .wp-mm rect{fill:var(--accent,#5b6cff);fill-opacity:.1;stroke:var(--accent,#5b6cff);stroke-width:1.4px;vector-effect:non-scaling-stroke;cursor:move;}
#wpal-root .wp-mmtip{position:absolute;right:16px;bottom:168px;padding:3px 9px;font-size:11.5px;border-radius:8px;pointer-events:none;}
#wpal-root .wp-help{right:16px;top:64px;width:min(330px,calc(100% - 32px));display:block;white-space:normal;line-height:1.5;font-size:12.5px;padding:12px 14px;}
#wpal-root .wp-help kbd{font:inherit;font-weight:700;border:1px solid var(--w-edge);border-radius:5px;padding:0 5px;}
#wpal-root.wp-mmon .wp-list{bottom:178px;}
html:is(.mobile,.alto-editing) #wpal-root :is(.wp-nav,.wp-mm,.wp-mmtip,.wp-help){display:none !important;}
html.alto-retro #wpal-root :is(.wp-hk,.wp-help kbd,.wp-mm):not(#_){border-radius:0;}
html.alto-retro #wpal-root .wp-nav .wp-btn.r:not(#_){border:0;}html.alto-retro #wpal-root .wp-nav .wp-btn.r.on:not(#_){background:#d9ae55;color:#000;}
html.alto-retro #wpal-root .wp-at{font-family:var(--rt-f,inherit);}html.alto-retro #wpal-root .wp-at b{color:#efe6cf;font-weight:400;}
html.alto-retro #wpal-root .wp-mm rect{fill:#d9ae55;stroke:#d9ae55;}
@media (max-width:700px){#wpal-root :is(.wp-nav,.wp-mm,.wp-mmtip){display:none !important;}}
@media print{#wpal-root{display:none !important;}html.wpal-open #world{visibility:visible !important;}}
@media (max-width:700px){#wpal-root .wp-card{width:180px;padding:8px 10px 9px;}#wpal-root .wp-card.main{width:220px;}#wpal-root .wp-card h4{font-size:13px;}
  #wpal-root .wp-card.main h4{font-size:15px;}#wpal-root .wp-tour .d{display:none;}#wpal-root .wp-tour{bottom:68px;}
  #wpal-root .wp-key{bottom:120px;left:12px;max-width:calc(100% - 24px);}#wpal-root .wp-ctl{right:10px;top:8px;}
  #wpal-root .wp-list{left:12px;right:12px;width:auto;top:auto;bottom:120px;max-height:40%;}
  #wpal-root .wp-enl > .node{zoom:1;max-width:calc(100vw - 28px);}}
"""

WORLD_JS = r"""
var NS='http://www.w3.org/2000/svg', A=window.AltoWorld={}, ev={};
var S={k:1,cx:0,cy:0,vw:1,vh:1,kW:1,paths:{},bb:{},base:{},det:{},detOn:{},cont:{},a1:{},pins:{},lbls:{},tags:[],chev:[],sel:null,ti:-1,ptr:{},anim:null,cl:null,
  out:{},dimSig:null,bor:null,cur:null,rel:[],tour:true};
try{ S.tour=localStorage.getItem('alto-world-tour')!=='off'; }catch(x){}      // the Tour switch, remembered on this device
function on(e,f){ (ev[e]=ev[e]||[]).push(f); }
function emit(e,d){ (ev[e]||[]).slice().forEach(function(f){ try{ f(d); }catch(x){} }); }
function el(t,a,p){ var n=document.createElementNS(NS,t); if(a) for(var k in a) n.setAttribute(k,a[k]); if(p) p.appendChild(n); return n; }
function h(t,a,p,txt){ var n=document.createElement(t); if(a) for(var k in a) n.setAttribute(k,a[k]); if(txt!=null) n.textContent=txt; if(p) p.appendChild(n); return n; }
function dec(s){ var t=document.createElement('textarea'); t.innerHTML=s==null?'':String(s); return t.value; }
function clamp(v,a,b){ return Math.max(a,Math.min(b,v)); }
function mj(t){ return t*t*t*(10-15*t+6*t*t); }            // minimum jerk: Alto's one motion curve
function reduced(){ try{ return window.matchMedia('(prefers-reduced-motion: reduce)').matches; }catch(x){ return false; } }
function phone(){ return S.vw<700; }

// ── geometry: integer delta rings → smooth closed curves (centripetal Catmull-Rom) ──
function decode(flat,q){ var x=flat[0],y=flat[1],o=[[x/q,y/q]]; for(var i=2;i<flat.length;i+=2){ x+=flat[i]; y+=flat[i+1]; o.push([x/q,y/q]); } return o; }
function curve(P,dp){
  var n=P.length, f=function(v){ return v.toFixed(dp); };
  if(n<4){ var s='M'+f(P[0][0])+' '+f(P[0][1]); for(var j=1;j<n;j++) s+='L'+f(P[j][0])+' '+f(P[j][1]); return s+'Z'; }
  var d='M'+f(P[0][0])+' '+f(P[0][1]);
  for(var i=0;i<n;i++){
    var p0=P[(i-1+n)%n],p1=P[i],p2=P[(i+1)%n],p3=P[(i+2)%n];
    var l01=Math.sqrt(Math.hypot(p1[0]-p0[0],p1[1]-p0[1])),l12=Math.sqrt(Math.hypot(p2[0]-p1[0],p2[1]-p1[1])),l23=Math.sqrt(Math.hypot(p3[0]-p2[0],p3[1]-p2[1]));
    var a1=p1,a2=p2,e=1e-9;
    if(l01>e){ var a=2*l01*l01+3*l01*l12+l12*l12, nn=3*l01*(l01+l12); a1=[(p1[0]*a-p0[0]*l12*l12+p2[0]*l01*l01)/nn,(p1[1]*a-p0[1]*l12*l12+p2[1]*l01*l01)/nn]; }
    if(l23>e){ var b=2*l23*l23+3*l23*l12+l12*l12, m=3*l23*(l23+l12); a2=[(p2[0]*b+p1[0]*l23*l23-p3[0]*l12*l12)/m,(p2[1]*b+p1[1]*l23*l23-p3[1]*l12*l12)/m]; }
    d+='C'+f(a1[0])+' '+f(a1[1])+' '+f(a2[0])+' '+f(a2[1])+' '+f(p2[0])+' '+f(p2[1]);
  }
  return d+'Z';
}
// bb gets the box of the country's main landmass (its largest ring): France is zoomed to France, not to French Guiana as well
function rings2d(list,q,dp,bb){ var d='', best=-1; list.forEach(function(fl){ var P=decode(fl,q), b=[1e9,1e9,-1e9,-1e9];
  P.forEach(function(p){ if(p[0]<b[0])b[0]=p[0]; if(p[1]<b[1])b[1]=p[1]; if(p[0]>b[2])b[2]=p[0]; if(p[1]>b[3])b[3]=p[1]; });
  var a=(b[2]-b[0])*(b[3]-b[1]); if(a>best){ best=a; bb[0]=b[0]; bb[1]=b[1]; bb[2]=b[2]; bb[3]=b[3]; } d+=curve(P,dp); }); return d; }
function line2d(flat,q){ var P=decode(flat,q), d='M'+P[0][0].toFixed(2)+' '+P[0][1].toFixed(2); for(var i=1;i<P.length;i++) d+='L'+P[i][0].toFixed(2)+' '+P[i][1].toFixed(2); return d; }
function quad(a,b,bend){ var mx=(a[0]+b[0])/2,my=(a[1]+b[1])/2,dx=b[0]-a[0],dy=b[1]-a[1],L=Math.hypot(dx,dy)||1,k=bend*Math.min(L,520);
  return {c:[mx-dy/L*k,my+dx/L*k],L:L}; }

// ── view ──
// The engine may scale the whole page (CSS zoom on <html>, e.g. ×0.85 on a 1440 px window): the map is laid out in CSS px, while
// events and getBoundingClientRect come in the window's px. cp() turns a window point into the map's own (S.z, S.rl, S.rt from resize).
function cp(x,y){ return [(x-(S.rl||0))/(S.z||1),(y-(S.rt||0))/(S.z||1)]; }
function scr(x,y){ return [(x-S.cx)*S.k+S.vw/2,(y-S.cy)*S.k+S.vh/2]; }
function wld(sx,sy){ return [(sx-S.vw/2)/S.k+S.cx,(sy-S.vh/2)/S.k+S.cy]; }
function inset(){ return phone()?{t:56,b:124,l:14,r:14}:{t:60,b:96,l:30,r:70}; }      // (clear of the page's own corner buttons and side rail)
function fitBox(bb,pad){ var I=inset(), w=S.vw-I.l-I.r-2*pad, hh=S.vh-I.t-I.b-2*pad, bw=Math.max(bb[2]-bb[0],1e-3), bh=Math.max(bb[3]-bb[1],1e-3);
  var k=Math.min(w/bw,hh/bh); return {k:k,cx:(bb[0]+bb[2])/2-((I.l-I.r)/2)/k,cy:(bb[1]+bb[3])/2-((I.t-I.b)/2)/k}; }
// The whole world, centred in the map (Luke, 2026-10-26: "have the map centered when opening from homepage"): the same margin on either
// side (the map's bars float over the sea), less on a short landscape phone; a phone held upright shows the world taller (60% of its
// height) and the reader pans sideways from its middle.
function worldView(){ var short=S.vh<500, px=phone()?10:short?16:40, py=short?18:62, bw=2000, bh=974;
  var k=Math.min((S.vw-2*px)/bw,(S.vh-2*py)/bh); if(phone()&&!short) k=Math.max(k,(S.vh-2*py)*.6/bh);
  return {k:k,cx:0,cy:0}; }
function apply(){ if(S.mmBox) mmBox();
  S.g.setAttribute('transform','translate('+(S.vw/2-S.cx*S.k).toFixed(2)+' '+(S.vh/2-S.cy*S.k).toFixed(2)+') scale('+S.k.toFixed(5)+')');
  place();
}
function setView(cx,cy,k){ var kmin=S.kW*(phone()?.35:.6), kmax=S.kW*60; S.k=clamp(k,kmin,kmax); S.cx=clamp(cx,-1100,1100); S.cy=clamp(cy,-560,560); apply(); settleSoon(); }
function zoomAt(f,sx,sy){ S.zt=performance.now(); var p=wld(sx,sy), k=clamp(S.k*f,S.kW*(phone()?.35:.6),S.kW*60); S.cx=p[0]-(sx-S.vw/2)/k; S.cy=p[1]-(sy-S.vh/2)/k; S.k=k; stop(); apply(); settleSoon(); }
function stop(){ if(S.anim){ cancelAnimationFrame(S.anim.raf); S.anim=null; } }
function fly(cx,cy,k,done,early){
  stop(); var c0=[S.cx,S.cy,S.k], d=Math.hypot(cx-c0[0],cy-c0[1]), kmin=Math.min(c0[2],k), l0=Math.log(c0[2]), l1=Math.log(k);
  var far=d*kmin/Math.max(S.vw,1), dip=far>1.1&&!phone()?Math.log(Math.max((S.vw*.85)/(d*kmin),.08)):0;       // a long flight rises first (not on a phone)
  var cap=1875*d*Math.exp((l0+l1)/2+dip)/(1.4*Math.max(S.vw,1));            // min-jerk's peak speed is 1.875 d/T: kept under 1.4 widths a second
  var ms=reduced()?0:clamp(Math.max(480+260*Math.log2(1+far)+90*Math.abs(l1-l0)/Math.LN2,cap),480,phone()?1500:1100);
  if(!ms){ S.cx=cx; S.cy=cy; S.k=k; apply(); settleSoon(); if(early) early(); if(done) done(); return; }
  var t0=performance.now(), pre=early?Math.max(0,ms-200):-1;
  var A0={raf:0}; S.anim=A0;
  (function step(now){
    var t=clamp((now-t0)/ms,0,1), e=mj(t);
    S.cx=c0[0]+(cx-c0[0])*e; S.cy=c0[1]+(cy-c0[1])*e; S.k=Math.exp(l0+(l1-l0)*e+dip*4*e*(1-e)); apply();
    if(pre>=0&&now-t0>=pre&&S.anim===A0){ pre=-1; early(); }
    if(t<1&&S.anim===A0) A0.raf=requestAnimationFrame(step); else if(S.anim===A0){ S.anim=null; settleSoon(); if(done) done(); emit('land',S.sel); }
  })(t0);
}
var settleT=0; function settleSoon(){ clearTimeout(settleT); settleT=setTimeout(settle,140); }
function settle(){ detail(); labels(); }

// ── page data ──
function D(){ return A.data||{}; }
function N(id){ return (D().nodes||{})[id]; }
function placed(id){ var n=N(id); return n&&n.x!=null; }
function unitOf(id){ var n=N(id); return n?n.a:0; }
function stops(){ var o=[]; (D().u||[]).forEach(function(u){ if(u.hub) o.push(u.hub); (u.st||[]).forEach(function(id){ if(placed(id)) o.push(id); }); }); return o; }
function hubUnit(id){ var U=D().u||[]; for(var a=0;a<U.length;a++) if(U[a].hub===id) return a; return -1; }
function ucls(a){ return 'wu'+(a%12); }
function placeOf(id){ var n=N(id); while(n&&n.x==null&&n.par){ id=n.par; n=N(id); } return n&&n.x!=null?id:null; }
// every card in the order the Tour and the arrow keys hop through them: each stop, then the cards clustered round it
function seq(){ var o=[]; stops().forEach(function(id){ o.push(id); ((D().cl||{})[id]||[]).forEach(function(c){ o.push(c); }); }); return o; }
// the reader's filters (the engine dims a card it hides): a filtered-out card's pin fades and the hops skip it
function out(id){ var e=document.getElementById('node-'+id), c=e&&e.querySelector('.node-card'); return !!(c&&(c.classList.contains('dimmed')||c.classList.contains('ent-dimmed'))); }
function live(){ return seq().filter(function(id){ return !S.out[id]; }); }

// ── drawing ──
function drawBase(G){
  S.base=G; var q=G.q, used=D().used||{};
  (G.grat||[]).forEach(function(fl){ el('path',{d:line2d(fl,q),'class':'wp-grat'},S.gGrat); });
  if(G.sphere) el('path',{d:curve(decode(G.sphere,q),1),'class':'wp-sphere'},S.gGrat);
  Object.keys(G.c).sort().forEach(function(cid){
    if(cid==='ATA'&&used[cid]==null) return;
    var bb=[1e9,1e9,-1e9,-1e9], d=rings2d(G.c[cid],q,1,bb); S.bb[cid]=bb;
    var p=el('path',{d:d,'class':'wp-c'+(used[cid]!=null?' wp-u '+ucls(used[cid]):'')},S.gLand); p._base=d; p._cid=cid; S.paths[cid]=p;
    if(used[cid]!=null) p.addEventListener('click',function(){ if(S.dragged) return; var f=firstIn(cid); if(f) A.select(f); });
  });
}
function firstIn(cid){ var s=stops(); for(var i=0;i<s.length;i++) if(N(s[i]).c===cid) return s[i]; return null; }
function drawArcs(){
  var g=S.gArcs; while(g.firstChild) g.removeChild(g.firstChild); S.chev=[];
  var U=D().u||[], prev=null;
  U.forEach(function(u,a){
    var gu=el('g',{'class':ucls(a),'data-u':a},g), tops=(u.tops||[]).filter(placed);
    for(var i=0;i+1<tops.length;i++) tube(gu,N(tops[i]),N(tops[i+1]),a,.22,true);
    tops.forEach(function(t){ (D().cl[t]||[]).concat(kidsPlaced(t)).forEach(function(c){ if(placed(c)&&N(c).par===t) tube(gu,N(t),N(c),a,.12,false,'k'); }); });
    if(prev&&tops.length){ var p0=N(prev),p1=N(tops[0]); if(Math.hypot(p1.x-p0.x,p1.y-p0.y)>1){ var Q=quad([p0.x,p0.y],[p1.x,p1.y],.18);
      el('path',{d:'M'+p0.x+' '+p0.y+'Q'+Q.c[0].toFixed(2)+' '+Q.c[1].toFixed(2)+' '+p1.x+' '+p1.y,'class':'wp-arc hand'},gu); } }
    if(tops.length) prev=tops[tops.length-1];
  });
}
function kidsPlaced(t){ var o=[]; var all=D().nodes||{}; for(var id in all) if(all[id].par===t&&all[id].x!=null) o.push(id); return o; }
function tube(g,a,b,u,bend,chev,only){
  if(Math.hypot(b.x-a.x,b.y-a.y)<.5) return;
  var Q=quad([a.x,a.y],[b.x,b.y],bend), d='M'+a.x+' '+a.y+'Q'+Q.c[0].toFixed(2)+' '+Q.c[1].toFixed(2)+' '+b.x+' '+b.y;
  if(only){ el('path',{d:d,'class':'wp-arc '+only},g); return; }
  el('path',{d:d,'class':'wp-arc h'},g); el('path',{d:d,'class':'wp-arc m'},g); el('path',{d:d,'class':'wp-arc s'},g);
  if(chev) S.chev.push({a:[a.x,a.y],c:Q.c,b:[b.x,b.y],u:u});
}
function drawPins(){
  var all=D().nodes||{}, groups={};
  Object.keys(all).forEach(function(id){ var n=all[id]; if(n.x==null) return;
    var key=n.x.toFixed(1)+','+n.y.toFixed(1); (groups[key]=groups[key]||[]).push(id);
    var p=h('button',{type:'button','class':'wp-pin '+ucls(n.a),'aria-label':dec(n.n+' '+n.t+' — '+(n.pl||''))},S.lPins);
    p.addEventListener('click',function(e){ e.stopPropagation(); if(!S.dragged) A.select(id); });
    if(n.r){ var s=el('svg',{'class':'wp-nm',viewBox:'-8 -16 16 17'},p); el('path',{d:'M0,0 c-5,-7 -8,-11 -8,-15 a8,8 0 1 1 16,0 c0,4 -3,8 -8,15z'},s);
      p.title='Place named in your notes'+(n.nm?': '+dec(n.nm):''); }
    var t=h('span',null,p,''); var L=h('div',{'class':'wp-lbl'},S.lLbl); h('b',null,L,dec(n.pl||'')); h('i',null,L,dec(n.t||''));
    S.pins[id]={el:p,num:t,lbl:L,off:[0,0]};
  });
  Object.keys(groups).forEach(function(k){ var g=groups[k]; if(g.length<2) return;            // cards sharing a capital fan round it
    g.forEach(function(id,i){ var a=-Math.PI/2+i*2*Math.PI/g.length, r=12+3*g.length; S.pins[id].off=[r*Math.cos(a),r*Math.sin(a)]; S.pins[id].fan=1; }); });
  (D().u||[]).forEach(function(u,a){
    var tg=h('button',{type:'button','class':'wp-tag '+ucls(a)},S.lTag); h('b',null,tg,String(a+1)); tg.appendChild(document.createTextNode(dec((D().acts[a]||{}).n||''))); h('span',null,tg,' · '+(u.tops||[]).length);
    tg.addEventListener('click',function(e){ e.stopPropagation(); if(S.dragged) return; if(u.hub) A.select(u.hub); else A.unit(a); });
    S.tags.push({el:tg,a:a});
  });
}
// Markers (the shared rules, Luke 2026-10-22: "shifting so much and changing size"): every pin, name and tag keeps one screen size and is
// pinned to its place, so a zoom or a pan changes only its transform; which names show, where the tags sit and whether pins carry their
// numbers is decided once the gesture settles (bands, not thresholds), a marker keeps its place while it is still free, and what goes fades.
function place(){
  var big=S.big;
  for(var id in S.pins){ var P=S.pins[id], n=N(id), s=scr(n.x,n.y), f=big?1.6:1, x=s[0]+P.off[0]*f, y=s[1]+P.off[1]*f;
    P.x=x; P.y=y; P.el.style.transform='translate('+x.toFixed(1)+'px,'+y.toFixed(1)+'px)';
    P.lbl.style.transform='translate(-50%,0) translate('+x.toFixed(1)+'px,'+(y+(big?16:10)).toFixed(1)+'px)'; }
  S.tags.forEach(function(T){ if(T.pos&&T.d){ var s=scr(T.pos[0],T.pos[1]); T.el.style.transform='translate(-50%,-50%) translate('+(s[0]+T.d[0]).toFixed(1)+'px,'+(s[1]+T.d[1]).toFixed(1)+'px)'; } });
  var ov=S.ovChev; while(ov.firstChild) ov.removeChild(ov.firstChild);
  S.chev.forEach(function(C){ var t=.5, x=(1-t)*(1-t)*C.a[0]+2*(1-t)*t*C.c[0]+t*t*C.b[0], y=(1-t)*(1-t)*C.a[1]+2*(1-t)*t*C.c[1]+t*t*C.b[1];
    var tx=2*(1-t)*(C.c[0]-C.a[0])+2*t*(C.b[0]-C.c[0]), ty=2*(1-t)*(C.c[1]-C.a[1])+2*t*(C.b[1]-C.c[1]), s=scr(x,y);
    if(Math.hypot(C.b[0]-C.a[0],C.b[1]-C.a[1])*S.k<46) return;
    el('path',{d:'M-4,-4L3,0L-4,4','class':'wp-chev','transform':'translate('+s[0].toFixed(1)+' '+s[1].toFixed(1)+') rotate('+(Math.atan2(ty,tx)*180/Math.PI).toFixed(1)+')',opacity:S.sel!=null&&unitOf(S.sel)!==C.u?.25:1},ov); });
  // the enlarged card's links to other cards (the hover lines of every other format): dashed arcs from its place to theirs
  var rv=S.ovRel; while(rv.firstChild) rv.removeChild(rv.firstChild);
  var A0=S.cur&&S.pins[placeOf(S.cur)];
  if(A0) S.rel.forEach(function(to){ var P=S.pins[to]; if(!P||P===A0||S.out[to]) return; var Q=quad([A0.x,A0.y],[P.x,P.y],.2), g=el('g',{'class':ucls(N(to).a)},rv);
    var d='M'+A0.x.toFixed(1)+' '+A0.y.toFixed(1)+'Q'+Q.c[0].toFixed(1)+' '+Q.c[1].toFixed(1)+' '+P.x.toFixed(1)+' '+P.y.toFixed(1);
    el('path',{d:d,'class':'wp-rel'},g); el('path',{d:d,'class':'wp-relh','data-to':to},g);
    el('circle',{cx:P.x.toFixed(1),cy:P.y.toFixed(1),r:4.5,'class':'wp-reld'},g); });
  cluster(); (S.ghosts||[]).forEach(gpos);
}
function band(was,v,lo,hi){ return was?v>=lo:v>=hi; }
function off(e,on){ e.classList.toggle('wp-off',!on); }
function labels(){                                  // decided once a gesture settles: names that fit, the ones already showing first
  var lvl=S.k/S.kW, big=S.big=band(S.big,lvl,1.65,1.9), tags=S.tagsOn=!band(!S.tagsOn,lvl,1.3,1.55), tight=!big;
  for(var id0 in S.pins){ var P0=S.pins[id0], n0=N(id0); P0.el.classList.toggle('n',big); P0.num.textContent=big?(n0.n||''):''; }
  place();
  var taken=[];
  for(var id in S.pins){ var P=S.pins[id]; taken.push([P.x-8,P.y-8,P.x+8,P.y+8]); }
  if(S.cl) S.cl.boxes.forEach(function(b){ taken.push(b); });
  [S.ctlEl,S.keyEl,S.tourEl,S.list,S.navEl,S.mmEl].forEach(function(e){ if(!e||e.hidden||(e===S.mmEl&&!e.classList.contains('on'))) return; var r=e.getBoundingClientRect(); if(!r.width) return;      // the map's own panels: no name goes under them
    var a=cp(r.left,r.top), b=cp(r.right,r.bottom); taken.push([a[0]-6,a[1]-6,b[0]+6,b[1]+6]); });
  var hit=function(b,sl){ sl=sl||0; for(var i=0;i<taken.length;i++){ var t=taken[i]; if(b[0]+sl<t[2]&&b[2]-sl>t[0]&&b[1]+sl<t[3]&&b[3]-sl>t[1]) return true; } return false; };
  var seenC={}, order=Object.keys(S.hint||{}).concat(stops(),Object.keys(S.pins)), was=order.filter(function(id){ return S.pins[id]&&S.pins[id].on; });
  was.concat(order).forEach(function(id){ var P=S.pins[id]; if(!P||P._done===S) return; P._done=S; var n=N(id);
    var L=P.lbl, show=!S.out[id]&&!(S.cl&&S.cl.id===id)&&P.x>-50&&P.x<S.vw+50&&P.y>-50&&P.y<S.vh+50;
    if(show&&tight){ if(seenC[n.c]&&n.k==='country') show=false; seenC[n.c]=1; }
    L.querySelector('i').style.display=tight?'none':'';
    if(show){ var w=L.offsetWidth, hh=L.offsetHeight, y=P.y+(tight?10:16), b=[P.x-w/2,y,P.x+w/2,y+hh]; if(hit(b,P.on?3:0)) show=false; else taken.push(b); }
    P.on=show; off(L,show); });
  for(var k in S.pins) delete S.pins[k]._done;
  // the unit tags (world view only): beside their unit's pins where nothing else is; a tag keeps its side while that is free
  S.tags.forEach(function(T){ var u=D().u[T.a], ids=(u.tops||[]).filter(placed); if(!ids.length){ T.pos=null; off(T.el,false); return; }
    var cx=0,cy=0; ids.forEach(function(i){ cx+=N(i).x; cy+=N(i).y; }); cx/=ids.length; cy/=ids.length; T.pos=[cx,cy];
    var w=T.el.offsetWidth||120, hh=T.el.offsetHeight||22, s=scr(cx,cy), best=null, I=inset();
    var fits=function(v,sl){ var dx=v[0]*(w/2+44), dy=v[1]*(hh/2+40), b=[s[0]+dx-w/2,s[1]+dy-hh/2,s[0]+dx+w/2,s[1]+dy+hh/2];
      if(b[0]<10||b[2]>S.vw-10||b[1]<I.t||b[3]>S.vh-I.b||hit(b,sl)) return null; taken.push(b); return [dx,dy]; };
    if(T.v) best=fits(T.v,3);
    if(!best) [[-1,0],[1,0],[0,-1],[0,1],[-1,-1],[1,-1],[-1,1],[1,1],[-1.6,0],[1.6,0],[0,-1.8],[0,1.8]].some(function(v){ best=fits(v,0); if(best) T.v=v; return !!best; });
    if(best) T.d=best; off(T.el,!!best&&tags); });
  place();
}

// ── zoomed-in detail: a continent at 1:50m, a country's state lines ──
function fetchJSON(url){ return fetch(url,{credentials:'same-origin'}).then(function(r){ if(!r.ok) throw new Error('HTTP '+r.status); return r.json(); }); }
function visBox(){ var a=wld(0,0), b=wld(S.vw,S.vh); return [a[0],a[1],b[0],b[1]]; }
function meets(a,b){ return a[0]<b[2]&&a[2]>b[0]&&a[1]<b[3]&&a[3]>b[1]; }
function detail(){
  var want=S.k>=S.kW*2.4, vb=visBox();
  Object.keys(GEO.cont).forEach(function(cs){
    if(want&&meets(CBOX[cs]||[-1e9,-1e9,1e9,1e9],vb)){
      if(!S.cont[cs]){ S.cont[cs]='loading'; fetchJSON(GEO.cont[cs]).then(function(G){ S.cont[cs]=G; if(S.k>=S.kW*2.4) swapIn(cs); }).catch(function(){ S.cont[cs]=null; }); }
      else if(S.cont[cs]!=='loading') swapIn(cs);
    } else if(S.detOn[cs]) swapOut(cs);
  });
  if(want) (D().multi||[]).forEach(function(cid){ if(S.a1[cid]||!GEO.a1[cid]||!S.bb[cid]||!meets(S.bb[cid],vb)) return; S.a1[cid]='loading';
    fetchJSON(GEO.a1[cid]).then(function(G){ S.a1[cid]=G; var g=el('g',{'data-c':cid},S.gA1); G.l.forEach(function(fl){ el('path',{d:line2d(fl,G.q),'class':'wp-a1'},g); }); }).catch(function(){}); });
  S.gA1.style.display=want?'':'none';
}
function swapIn(cs){ if(S.detOn[cs]) return; var G=S.cont[cs]; if(!G||!G.c) return; S.detOn[cs]=1; var used=D().used||{};
  Object.keys(G.c).forEach(function(cid){ var p=S.paths[cid];
    if(cid==='ATA'&&used[cid]==null) return;
    if(!p){ p=el('path',{'class':'wp-c'+(used[cid]!=null?' wp-u '+ucls(used[cid]):'')},S.gLand); p._cid=cid; p._extra=1; S.paths[cid]=p; }
    if(!p._det){ var bb=[1e9,1e9,-1e9,-1e9]; p._det=rings2d(G.c[cid],G.q,2,bb); if(!S.bb[cid]) S.bb[cid]=bb; }
    p.setAttribute('d',p._det); p.style.display=''; }); }
function swapOut(cs){ var G=S.cont[cs]; S.detOn[cs]=0; if(!G||!G.c) return; Object.keys(G.c).forEach(function(cid){ var p=S.paths[cid]; if(!p) return; if(p._extra) p.style.display='none'; else p.setAttribute('d',p._base); }); }

// ── a place and its cluster ──
function placeView(id){
  var n=N(id), bb=S.bb[n.c], I=inset(), room=Math.min(S.vw-I.l-I.r,S.vh-I.t-I.b);
  var span=bb?Math.max(bb[2]-bb[0],bb[3]-bb[1]):8; if(n.k==='sub') span=Math.min(span,110); else if(n.k==='city') span=Math.min(span,60);
  var cities=n.k==='country'&&Object.keys(D().nodes||{}).some(function(c){ var m=N(c); return m.par===id&&m.k==='city'; });
  var k=clamp(room*(phone()?.62:cities?.72:.42)/Math.max(span,4),S.kW*2.2,S.kW*30);          // (a country with cards on its cities: close enough to tell them apart)
  return {cx:n.x,cy:n.y-(phone()?40:30)/k,k:k};
}
// A card is enlarged where it stands (Luke, 2026-10-23: "it should still have the ability to enlarge nodes"): a pin, a cluster card, a
// Tour stop or an arrow key enlarges that card; a click on the enlarged card opens its page, a click away or Esc shrinks it.
A.select=function(id,opts){
  if(hubUnit(id)>=0) return A.unit(hubUnit(id),opts);
  var pl=placed(id)?id:placeOf(id); if(!pl) return; opts=opts||{};
  S.cur=id; S.ua=null; rels(id);
  if(S.cl&&S.cl.id===pl&&!S.anim){ swapEnl(id); tourBar(); place(); emit('select',id); return; }      // a card of the cluster that is open
  S.sel=pl; var n=N(pl); closeCluster(true);
  focus(n.a,n.c,pl); tourBar();
  var v=placeView(pl);
  var land=function(){ if(S.sel===pl&&S.cur===id&&!(S.cl&&S.cl.id===pl)) openCluster(pl,null,id); };
  if(opts.instant){ S.cx=v.cx; S.cy=v.cy; S.k=v.k; apply(); settle(); land(); } else fly(v.cx,v.cy,v.k,land,land);
  emit('select',id);
};
function rels(id){ S.rel=[]; if(typeof CONNECTIONS==='undefined') return; var seen={}, n=N(id);
  try{ CONNECTIONS.forEach(function(c){ var o=c[0]===id?c[1]:c[1]===id?c[0]:null, m=o&&N(o); if(!m||n.par===o||m.par===id) return;
    var p=placeOf(o); if(p&&!seen[p]){ seen[p]=1; S.rel.push(p); } }); }catch(x){} }
function focus(a,cid,id){
  S.root.classList.toggle('wp-focus',a!=null);
  Object.keys(S.paths).forEach(function(c){ S.paths[c].classList.toggle('wp-on',c===cid); });
  [].forEach.call(S.gArcs.children,function(g){ g.classList.toggle('wp-on',+g.getAttribute('data-u')===a); });
  for(var k in S.pins){ S.pins[k].el.classList.toggle('wp-in',N(k).a===a); S.pins[k].el.classList.toggle('wp-on',k===id); }
}
function unfocus(){ closeCluster(true); S.sel=null; S.cur=null; S.ua=null; S.rel=[]; focus(null,null,null); tourBar(); place(); }
// the timeline's own card, borrowed from the board while it is enlarged and given back after (the board keeps its order)
function giveBack(){ var B=S.bor; if(!B) return; S.bor=null; var n=B.el; n.classList.remove('wp-bnode');
  if(B.par&&B.par.isConnected&&document.getElementById(n.id)===n) B.par.insertBefore(n,B.nxt&&B.nxt.parentNode===B.par?B.nxt:null); else n.remove(); }
function enlarge(id,kid){
  var n=N(id), node=document.getElementById('node-'+id); if(!node||node.closest('#wpal-root')) return card(id,!kid);
  giveBack(); var w=h('div',{'class':'wp-enl '+ucls(n.a)+(kid?' kid':'')+' wp-grow','data-id':id},S.lCards);
  S.bor={el:node,par:node.parentNode,nxt:node.nextSibling}; node.classList.add('wp-bnode'); w.appendChild(node); whereLine(id,'wp-where',w);
  return w;
}
// where a card stands: its own place or the place it is clustered round ("Lima, Peru"; "Peru"), a unit's own card its regions
function where(id){ var p=placeOf(id); if(!p){ var a=hubUnit(id); return a>=0?dec((D().u[a].reg||[]).join(', ')):''; }
  var n=N(p), cn=dec((D().names||{})[n.c]||''), pl=dec(n.pl||''); if(n.k==='country'||!pl) return cn||pl; return pl+(cn&&pl!==cn?', '+cn:''); }
function pinIcon(p){ var s=el('svg',{viewBox:'-8 -16 16 17','aria-hidden':'true'},p); el('path',{d:'M0,0 c-5,-7 -8,-11 -8,-15 a8,8 0 1 1 16,0 c0,4 -3,8 -8,15z'},s); return s; }
function whereLine(id,cls,p){ var t=where(id); if(!t) return null; var d=h('div',{'class':cls},p); pinIcon(d); h('span',null,d,t); d.title=t; return d; }
function closeCluster(fold){ if(!S.cl) return; var C=S.cl; if(fold) els(C).forEach(function(e){ ghost(e,C.id,C.at); }); giveBack(); els(C).forEach(function(e){ e.remove(); }); S.list.hidden=true; S.cl=null; S.ovLinks.innerHTML=''; }
// a copy of a card (no ids: the card itself goes back to the board) folding into its pin, riding it while the map moves
function ghost(e,id,at){ if(!e||!e.isConnected||e._x==null) return; var g=e.cloneNode(true); g.removeAttribute('data-id');
  [].forEach.call(g.querySelectorAll('[id]'),function(x){ x.removeAttribute('id'); }); g.removeAttribute('id');
  g.className=e.className.replace(/\bwp-(grow|hint)\b/g,'')+' wp-ghost'; [].forEach.call(g.querySelectorAll('.wp-hk'),function(x){ x.remove(); });
  var P=anchorOf({id:id,at:at}); if(!P) return; var G={el:g,id:id,at:at,dx:e._x-P.x,dy:e._y-P.y}; S.ghosts=(S.ghosts||[]).concat([G]);
  S.lCards.insertBefore(g,S.lCards.firstChild); gpos(G); void g.offsetWidth; g.classList.add('wp-fold');
  setTimeout(function(){ g.remove(); S.ghosts=S.ghosts.filter(function(x){ return x!==G; }); },reduced()?200:280); }
function gpos(G){ var P=anchorOf({id:G.id,at:G.at}); if(!P) return; var x=P.x+G.dx, y=P.y+G.dy;
  G.el.style.transform='translate('+x.toFixed(1)+'px,'+y.toFixed(1)+'px)'; G.el.style.transformOrigin=P.x.toFixed(1)+'px '+P.y.toFixed(1)+'px'; }
// a card that stands by its pin grows out of it (the next frame, once its place and origin are set)
function grow(list){ var g=list.filter(function(e){ return e&&e.classList.contains('wp-grow'); }); if(!g.length) return; void g[0].offsetWidth;
  requestAnimationFrame(function(){ g.forEach(function(e){ e.classList.remove('wp-grow'); }); }); }
function els(C){ return [C.main].concat(C.cards.map(function(K){ return K.el; })); }
function card(id,main){
  var n=N(id), c=h('div',{'class':'wp-card wp-grow '+ucls(n.a)+(main?' main':'')+(S.out[id]?' wp-dim':''),role:'button',tabindex:'0','data-id':id},S.lCards);
  var ha=hubUnit(id);
  h('div',{'class':'n'},c,ha>=0?'Unit '+(ha+1)+' · '+(D().u[ha].reg||[]).join(', '):dec(n.n||'')+(main&&n.pl?' · '+dec(n.pl):''));
  h('h4',null,c,dec(n.t||''));
  if(main&&n.nm) h('div',{'class':'pl'},c,'Named in your notes: '+dec(n.nm));
  var go=function(e){ if(e) e.stopPropagation(); A.select(id); };
  c.addEventListener('click',go); c.addEventListener('keydown',function(e){ if(e.key==='Enter'||e.key===' '){ e.preventDefault(); go(); } });
  return c;
}
function anchorOf(C){ if(C.at){ var s=scr(C.at[0],C.at[1]); return {x:s[0],y:s[1]}; } return S.pins[C.id]; }
function openCluster(id,at,enl){
  closeCluster(); enl=enl||id; var kids=at?[]:((D().cl||{})[id]||[]), cards=[];
  var main=enl===id?enlarge(id,false):card(id,true);
  var many=kids.length>(phone()?4:10);
  if(many){ S.list.hidden=false; S.list.className='wp-list '+ucls(N(id).a); while(S.list.firstChild) S.list.removeChild(S.list.firstChild);
    kids.forEach(function(c){ var b=h('button',{type:'button'},S.list); h('b',null,b,dec(N(c).n||'')); b.appendChild(document.createTextNode(dec(N(c).t||''))); b.addEventListener('click',function(){ A.select(c); }); });
    if(enl!==id) cards.push({id:enl,el:enlarge(enl,true),extra:1}); }
  else kids.forEach(function(c){ cards.push({id:c,el:c===enl?enlarge(c,true):card(c,false)}); });
  S.cl={id:id,main:main,cards:cards,k:S.k,boxes:[],at:at||null,enl:enl};
  layoutCluster(); place(); labels(); navSync(); grow(els(S.cl));
}
function swapEnl(id){
  var C=S.cl; if(!C||C.enl===id) return;
  var rec=function(x){ for(var i=0;i<C.cards.length;i++) if(C.cards[i].id===x) return C.cards[i]; return null; };
  var was=C.enl===C.id?C.main:(rec(C.enl)||{}).el; ghost(was,C.id,C.at); giveBack();         // the card it leaves folds into the pin
  var put=function(K,big){ var nid=K?K.id:C.id, e=big?enlarge(nid,!!K):card(nid,!K), old=K?K.el:C.main; old.replaceWith(e); if(K) K.el=e; else C.main=e; };
  if(C.enl===C.id) put(null,false); else { var K0=rec(C.enl); if(K0&&K0.extra){ K0.el.remove(); C.cards.splice(C.cards.indexOf(K0),1); } else if(K0) put(K0,false); }
  if(id===C.id) put(null,true);
  else { var K=rec(id); if(K) put(K,true); else { K={id:id,el:enlarge(id,true),extra:1,c:[Math.min(S.vw*.28,320),0]}; C.cards.push(K); } }
  C.enl=id; place(); labels(); navSync(); grow(els(C));
}
function layoutCluster(){
  var C=S.cl; if(!C) return; var P=anchorOf(C), I=inset();
  var mw=C.main.offsetWidth, mh=C.main.offsetHeight, gap=phone()?22:30;
  // the place's own card goes on the side of its pin that hides the fewest other pins (above, then beside, then below)
  var cost=function(sd){ var b=mainBox(P,sd,mw,mh), c=b[0]<8||b[2]>S.vw-8||b[1]<8||b[3]>S.vh-I.b+40?1000:0;
    for(var k in S.pins){ var Q=S.pins[k]; if(k!==C.id&&Q.x>b[0]-14&&Q.x<b[2]+14&&Q.y>b[1]-14&&Q.y<b[3]+14) c++; } return c; };
  C.side=['up','right','left','down'].reduce(function(best,sd){ return cost(sd)<cost(best)?sd:best; },'up');
  var mb=mainBox(P,C.side,mw,mh);
  var n=C.cards.length, rx=Math.min(S.vw*(phone()?.3:.36),430), ry=Math.min(S.vh*.3,250), boxes=[mb,[P.x-20,P.y-20,P.x+20,P.y+20]];
  C.cards.forEach(function(K,i){
    var w=K.el.offsetWidth, hh=K.el.offsetHeight, a=(n===1?35:-160+i*(320/(n-1)))*Math.PI/180, r=1, b;
    for(var tries=0;tries<14;tries++){
      var x=P.x+Math.cos(a)*rx*r-w/2, y=P.y+Math.sin(a)*ry*r-hh/2;
      x=clamp(x,I.l,S.vw-I.r-w); y=clamp(y,I.t,S.vh-I.b-hh); b=[x,y,x+w,y+hh];
      if(!boxes.some(function(o){ return b[0]<o[2]+10&&b[2]>o[0]-10&&b[1]<o[3]+8&&b[3]>o[1]-8; })) break;
      r+=.14; a+=(i%2?-1:1)*.09;
    }
    boxes.push(b); K.c=[(b[0]+b[2])/2-P.x,(b[1]+b[3])/2-P.y];                   // (its centre: an enlarged card grows round it)
  });
  C.boxes=boxes; C.main.classList.remove('s-down','s-left','s-right'); if(C.side!=='up') C.main.classList.add('s-'+C.side);
}
function mainBox(P,sd,mw,mh){ var g=phone()?22:30, x=sd==='left'?P.x-g-mw:sd==='right'?P.x+g:P.x-mw/2, y=sd==='up'?P.y-g-mh:sd==='down'?P.y+g:P.y-mh/2;
  return [x,y,x+mw,y+mh]; }
function cluster(){
  var C=S.cl; if(!C) return; var P=anchorOf(C);
  if(!P||S.k<C.k*.55||S.k>C.k*1.9){ if(!S.anim){ closeCluster(); if(!S.tour) setTimeout(function(){ if(!S.cl&&!S.anim) unfocus(); },0); } return; }
  var I=inset(), links=S.ovLinks; while(links.firstChild) links.removeChild(links.firstChild);
  var mw=C.main.offsetWidth, mh=C.main.offsetHeight, mb=mainBox(P,C.side||'up',mw,mh);
  var mx=clamp(mb[0],8,Math.max(8,S.vw-8-mw)), my=clamp(mb[1],8,Math.max(8,S.vh-8-mh));     // the place's own card beside its pin
  C.main.style.transform='translate('+mx.toFixed(1)+'px,'+my.toFixed(1)+'px)'; C.main._x=mx; C.main._y=my; var org=P.x.toFixed(1)+'px '+P.y.toFixed(1)+'px'; C.main.style.transformOrigin=org;
  C.boxes=[[mx,my,mx+mw,my+mh]];
  C.cards.forEach(function(K){ var w=K.el.offsetWidth, hh=K.el.offsetHeight, x=P.x+K.c[0]-w/2, y=P.y+K.c[1]-hh/2;
    if(K.el.classList.contains('wp-enl')){ x=clamp(x,I.l,Math.max(I.l,S.vw-I.r-w)); y=clamp(y,I.t,Math.max(I.t,S.vh-I.b-hh)); }
    K.el.style.transform='translate('+x.toFixed(1)+'px,'+y.toFixed(1)+'px)'; K.el._x=x; K.el._y=y; K.el.style.transformOrigin=org; C.boxes.push([x,y,x+w,y+hh]);
    var q=[clamp(P.x,x,x+w),clamp(P.y,y,y+hh)], Q=quad([P.x,P.y],q,.1), g=el('g',{'class':ucls(N(C.id).a)},links);
    el('path',{d:'M'+P.x.toFixed(1)+' '+P.y.toFixed(1)+'Q'+Q.c[0].toFixed(1)+' '+Q.c[1].toFixed(1)+' '+q[0].toFixed(1)+' '+q[1].toFixed(1),'class':'wp-link'},g);
    el('circle',{cx:q[0].toFixed(1),cy:q[1].toFixed(1),r:3.5,'class':'wp-dot'},g); });
}

// ── tour, hops, units, the whole world ──
A.tour=function(i){ var s=live(); if(!s.length) return; A.select(s[((i%s.length)+s.length)%s.length]); };
// the arrow keys and ◀ ▶: the next card on the route that the reader's filters show
A.hop=function(d){ var all=seq(), n=all.length; if(!n) return; var i=all.indexOf(S.cur); if(i<0) i=d>0?-1:n;
  for(var k=1;k<=n;k++){ var j=((i+d*k)%n+n)%n; if(!S.out[all[j]]) return A.select(all[j]); } };
A.unit=function(a,opts){ var u=(D().u||[])[a]; if(!u) return; var bb=[1e9,1e9,-1e9,-1e9];
  (u.st||[]).filter(placed).forEach(function(id){ var n=N(id), b=S.bb[n.c]||[n.x,n.y,n.x,n.y]; bb=[Math.min(bb[0],n.x,b[0]),Math.min(bb[1],n.y,b[1]),Math.max(bb[2],n.x,b[2]),Math.max(bb[3],n.y,b[3])]; });
  if(bb[0]>bb[2]) return; opts=opts||{}; closeCluster(true); S.ua=a; S.sel=u.hub||null; S.cur=u.hub||null; if(u.hub) rels(u.hub); else S.rel=[]; focus(a,null,null); tourBar();
  var I=inset(), v=fitBox(bb,phone()?20:60), k=Math.min(v.k,S.kW*14), mh=u.hub?(phone()?150:260):0;
  v.cy-=mh/2/k;                                                               // room above the region for its own card
  var land=function(){ if(u.hub&&S.sel===u.hub&&!(S.cl&&S.cl.id===u.hub)) openCluster(u.hub,[(bb[0]+bb[2])/2,bb[1]]); };
  if(opts.instant){ S.cx=v.cx; S.cy=v.cy; S.k=k; apply(); settle(); land(); } else fly(v.cx,v.cy,k,land,land); emit('select',u.hub||null); };
// the Tour switch: off, the bar goes, nothing is dimmed and the map stays where the reader is (free to pan, zoom and fly anywhere; the
// arrow keys pan); on, it starts from the card the reader is on, or the first stop
A.tourMode=function(v){ if(v==null) return S.tour; S.tour=!!v; try{ localStorage.setItem('alto-world-tour',S.tour?'on':'off'); }catch(x){}
  if(S.tourBtn) S.tourBtn.setAttribute('aria-pressed',String(S.tour)); S.root.classList.toggle('wp-free',!S.tour);
  if(S.tour){ if(S.cur) A.select(S.cur); else A.hop(1); } else { stop(); if(S.cl||S.cur) unfocus(); else tourBar(); if(S.ready) labels(); } };
A.world=function(){ unfocus(); var v=worldView(); fly(v.cx,v.cy,v.k); };
A.view=function(){ return {cx:S.cx,cy:S.cy,k:S.k,kW:S.kW}; };
function tourBar(){ navSync();
  var s=live(), B=S.tourEl, i=s.indexOf(S.cur), on=S.tour&&s.length>0; B.hidden=!on; if(!on) return;      // (the Tour on: its bar is there before the first stop)
  var nm=function(id){ var n=N(id), a=hubUnit(id); if(a>=0) return dec((a+1)+' '+((D().acts[a]||{}).n||'')); var q=N(placeOf(id)||id); return dec((n.n||'')+' '+(n.pl||(q&&q.pl)||'')); };
  if(i<0){ S.tPrev.textContent=''; S.tCur.textContent='Tour · '+s.length+' stops'; S.tNext.textContent=nm(s[0]); return; }
  S.tPrev.textContent=nm(s[(i-1+s.length)%s.length]); S.tNext.textContent=nm(s[(i+1)%s.length]);
  S.tCur.textContent='Tour '+(i+1)+' / '+s.length+' · '+nm(S.cur);
}
// the reader's filters: the cards they hide fade on the map, a country all of whose cards are hidden fades, and the map flies to what is left
function dim(){ if(!S.ready) return; var sig='', any=0, byC={};
  for(var id in (D().nodes||{})){ var o=out(id); S.out[id]=o; if(o){ sig+=id+','; any=1; } var p=placeOf(id); if(p){ var c=N(p).c; byC[c]=byC[c]||[0,0]; byC[c][0]++; if(o) byC[c][1]++; } }
  for(var k in S.pins) S.pins[k].el.classList.toggle('wp-dim',!!S.out[k]);
  for(var c in byC){ var pp=S.paths[c]; if(pp) pp.classList.toggle('wp-dim',byC[c][0]===byC[c][1]); }
  [].forEach.call(S.lCards.querySelectorAll('.wp-card[data-id]'),function(e){ e.classList.toggle('wp-dim',!!S.out[e.getAttribute('data-id')]); });
  if(sig!==S.dimSig){ var first=S.dimSig==null; S.dimSig=sig; tourBar(); labels(); if(!first&&any) fitLive(); } }
function fitLive(){ var bb=[1e9,1e9,-1e9,-1e9], k=0;
  live().forEach(function(id){ var p=placeOf(id), n=p&&N(p); if(!n) return; bb=[Math.min(bb[0],n.x),Math.min(bb[1],n.y),Math.max(bb[2],n.x),Math.max(bb[3],n.y)]; k++; });
  if(!k) return; unfocus(); var v=fitBox([bb[0]-6,bb[1]-6,bb[2]+6,bb[3]+6],phone()?30:80); fly(v.cx,v.cy,Math.min(v.k,S.kW*14)); }
// what happens on the hidden board reaches the map: a search hit (the engine flashes it) or a card the engine enlarges is enlarged here
// A card the engine enlarges because of a zoom on the map is not one (Luke, 2026-10-26: "it keeps bouncing back when i try to zoom in"):
// the engine's focus mode hears a pinch first (window capture) and enlarges the card nearest it; the map's own handlers run after, so its
// 'focused' is weighed once the event is done (a map zoom stamps S.zt) — let go of on the board, never flown to.
function watchBoard(){ var t=0, w=document.getElementById('world');
  var exit=function(){ if(window._focusedNodeId&&window.exitFocus){ try{ window.exitFocus(); }catch(x){} } };
  var go=function(hit){ if(N(hit)&&!S.root.hidden&&!document.documentElement.classList.contains('detail-open')){ exit(); A.select(hit); } };
  var mo=new MutationObserver(function(ms){ var hit=null, foc=null;
    ms.forEach(function(m){ var e=m.target, c=e.classList, was=' '+(m.oldValue||'')+' '; if(!c||!e.id||e.id.indexOf('node-')!==0) return;
      if(c.contains('search-flash')&&was.indexOf(' search-flash ')<0) hit=e.id.slice(5);
      else if(c.contains('focused')&&was.indexOf(' focused ')<0) foc=e.id.slice(5); });
    if(hit) go(hit);
    else if(foc) setTimeout(function(){ if(S.root.hidden) return; if(performance.now()-(S.zt||-1e9)<600) exit(); else go(foc); },0);
    clearTimeout(t); t=setTimeout(dim,60); });
  var o={attributes:true,subtree:true,attributeFilter:['class'],attributeOldValue:true};
  if(w) mo.observe(w,o); mo.observe(S.lCards,o); }

// ── moving round the map the System's way (solar_navopt.py, adapted to the map) ──
// The levels: the whole world ('') > a unit (its own card, or '@<a>') > a stop (a card standing on a place) > the cards clustered round it.
// Back goes up a level, Next along it, and with a card enlarged the arrows (the Tour off) and 1-9 go round what is beside it: what is
// under it, else what is beside it on its own level. The Tour keeps its own arrows (its route is the Atlas's way along); O the whole world.
function ukey(a){ var u=(D().u||[])[a]; return u?(u.hub||'@'+a):''; }
function ua(h){ if(h&&h.charAt(0)==='@') return +h.slice(1); var a=hubUnit(h); return a; }
function nkids(h){ var U=D().u||[];
  if(!h) return U.map(function(u,a){ return (u.tops||[]).some(placed)||u.hub?ukey(a):null; }).filter(Boolean);
  var a=ua(h); if(a>=0) return (U[a].tops||[]).filter(function(id){ return placed(id)&&!S.out[id]; });
  var all=D().nodes||{}, o=seq().filter(function(id){ return all[id]&&all[id].par===h; });
  for(var id in all) if(all[id].par===h&&o.indexOf(id)<0) o.push(id);
  return o.filter(function(id){ return !S.out[id]; }); }
function nup(h){ if(!h||ua(h)>=0) return ''; var n=N(h); if(!n) return '';
  if(n.par&&N(n.par)) return n.par;
  var cl=D().cl||{}; for(var s in cl) if(cl[s].indexOf(h)>=0) return s;
  return ukey(n.a); }
function nsibs(h){ return nkids(nup(h)); }
function nscope(h){ var k=nkids(h); return k.length?k:nsibs(h); }
function nnext(h){ if(!h) return null; var s=nsibs(h), i=s.indexOf(h); return i>=0&&s[i+1]?s[i+1]:null; }
function nround(h,d){ var s=nscope(h), i=s.indexOf(h); if(!s.length||(s.length===1&&i===0)) return null; return i<0?s[d>0?0:s.length-1]:s[(i+d+s.length)%s.length]; }
function nname(h){ if(!h) return 'Whole world'; var a=ua(h); if(a>=0) return dec((a+1)+' '+((D().acts[a]||{}).n||'')); var n=N(h); return n?dec(((n.n||'')+' '+(n.t||'')).trim()):''; }
function nhome(){ return S.cur||(S.ua!=null?ukey(S.ua):''); }
function ngo(h){ if(!h){ A.world(); return; } var a=ua(h); if(a>=0){ A.unit(a); return; } A.select(h); }
var NKEYS=[['Back','up to the place or unit it belongs to'],['Next','the next one at the same level'],['Left / Right arrows','round the ones beside the enlarged card (Tour off; on, the arrows step the Tour)'],['1 – 9','that one beside it (lit and numbered on the map)'],['O','the whole world'],['Esc','the card goes, then the whole world'],['T','the Tour on or off'],['+ / −','zoom']];
function svgI(p,d){ var s=el('svg',{viewBox:'0 0 20 20','aria-hidden':'true'},p); d.forEach(function(x){ el('path',{d:x},s); }); return s; }
function navChrome(){
  var b=S.navEl=h('div',{'class':'wp-bar wp-nav',role:'navigation','aria-label':'Where you are'},S.root);
  S.nUp=h('button',{type:'button','class':'wp-btn r'},b); svgI(S.nUp,['M8 4.5 4 8.5l4 4','M4 8.5h7a5 5 0 0 1 5 5v2']);
  S.nAt=h('button',{type:'button','class':'wp-at'},b);
  S.nNx=h('button',{type:'button','class':'wp-btn r'},b); svgI(S.nNx,['M8 4.5 13.5 10 8 15.5']);
  S.nMp=h('button',{type:'button','class':'wp-btn r'},b); svgI(S.nMp,['M5 4.5h10a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2z','M7.5 8.5v.01','M12.5 11.5v.01','M8.5 9.4 11.5 11']);
  [S.nUp,S.nAt,S.nNx].forEach(function(e){ e.addEventListener('click',function(ev){ ev.stopPropagation(); if(e.disabled) return; ngo(e.getAttribute('data-go')||''); }); });
  S.nMp.addEventListener('click',function(ev){ ev.stopPropagation(); S.mmOn=!S.mmOn; try{ localStorage.setItem('alto-world-map',S.mmOn?'1':'0'); }catch(x){} navSync(); });
  try{ S.mmOn=localStorage.getItem('alto-world-map')!=='0'; }catch(x){ S.mmOn=true; }
  var mm=S.mmEl=h('div',{'class':'wp-bar wp-mm',role:'group','aria-label':'Minimap: the whole world, the box is what the map shows'},S.root);
  S.mmSvg=el('svg',{viewBox:'-1010 -497 2020 994'},mm); S.mmLand=el('g',null,S.mmSvg); S.mmPins=el('g',null,S.mmSvg);
  S.mmHere=el('circle',{'class':'h',r:26},S.mmSvg); S.mmBox=el('rect',null,S.mmSvg);
  S.mmTip=h('div',{'class':'wp-bar wp-mmtip',hidden:''},S.root);
  mmInput(); }
function mmDraw(){ var L=S.mmLand, used=D().used||{}; while(L.firstChild) L.removeChild(L.firstChild);
  for(var cid in S.paths){ var p=S.paths[cid]; if(!p._base) continue; el('path',{d:p._base,'class':'c'+(used[cid]!=null?' u '+ucls(used[cid]):'')},L); }
  var P=S.mmPins; while(P.firstChild) P.removeChild(P.firstChild);
  stops().forEach(function(id){ var n=N(id); if(n&&n.x!=null) el('circle',{cx:n.x,cy:n.y,r:12,'class':ucls(n.a),'data-id':id},P); }); }
function mmPt(e){ var M=S.mmSvg.getScreenCTM(); if(!M) return null; var p=S.mmSvg.createSVGPoint(); p.x=e.clientX; p.y=e.clientY; p=p.matrixTransform(M.inverse()); return [p.x,p.y]; }
function mmNear(q){ var best=null, bd=1e9; stops().forEach(function(id){ var n=N(id); if(!n||S.out[id]) return; var d=Math.hypot(n.x-q[0],n.y-q[1]); if(d<bd){ bd=d; best=id; } }); return bd<=70?best:null; }
function mmInput(){ var mm=S.mmEl, dg=null;
  mm.addEventListener('pointerdown',function(e){ if(e.button>0) return; e.stopPropagation(); var q=mmPt(e); if(!q) return; var b=visBox();
    dg={x:e.clientX,y:e.clientY,q:q,in:q[0]>b[0]&&q[0]<b[2]&&q[1]>b[1]&&q[1]<b[3],c:[S.cx,S.cy],on:0}; try{ mm.setPointerCapture(e.pointerId); }catch(x){} });
  mm.addEventListener('pointermove',function(e){ var q=mmPt(e); if(!q) return;
    if(!dg){ var t=mmNear(q); S.mmTip.hidden=!t; if(t) S.mmTip.textContent=nname(t)+(t===placeOf(nhome())?' · you are here':''); return; }
    if(!dg.on&&Math.hypot(e.clientX-dg.x,e.clientY-dg.y)<4) return; dg.on=1; S.mmTip.hidden=true;
    if(dg.in){ stop(); setView(dg.c[0]+q[0]-dg.q[0],dg.c[1]+q[1]-dg.q[1],S.k); mmBox(); } });
  var up=function(e){ if(!dg) return; var d=dg; dg=null; if(d.on) return; var t=mmNear(d.q); if(t) A.select(t); else fly(d.q[0],d.q[1],S.k); };
  mm.addEventListener('pointerup',up); mm.addEventListener('pointercancel',function(){ dg=null; });
  mm.addEventListener('pointerleave',function(){ if(!dg) S.mmTip.hidden=true; });
  mm.addEventListener('click',function(e){ e.stopPropagation(); }); }
function mmBox(){ if(!S.mmBox||!S.mmEl.classList.contains('on')) return; var b=visBox(), r=S.mmBox;
  r.setAttribute('x',Math.max(b[0],-1010).toFixed(0)); r.setAttribute('y',Math.max(b[1],-497).toFixed(0));
  r.setAttribute('width',Math.max(8,Math.min(b[2],1010)-Math.max(b[0],-1010)).toFixed(0)); r.setAttribute('height',Math.max(8,Math.min(b[3],497)-Math.max(b[1],-497)).toFixed(0)); }
// what is drawn follows where you are: the control's labels, the minimap (only while a card or a unit is enlarged), the lit and numbered places
function navSync(){ if(!S.navEl) return; var hm=nhome(), u=nup(hm), nx=nnext(hm), p=hm?nup(hm):null;
  var lab=function(e,t){ e.title=t; e.setAttribute('aria-label',t); };
  S.nUp.disabled=!hm; S.nUp.setAttribute('data-go',u); lab(S.nUp,hm?'Back to '+nname(u):'Back');
  S.nNx.disabled=!nx; S.nNx.setAttribute('data-go',nx||''); lab(S.nNx,nx?'Next: '+nname(nx):'Nothing after this one');
  S.nMp.classList.toggle('on',!!S.mmOn); S.nMp.setAttribute('aria-pressed',String(!!S.mmOn)); lab(S.nMp,S.mmOn?'Hide the minimap':'Show the minimap');
  var at=S.nAt; while(at.firstChild) at.removeChild(at.firstChild); at.setAttribute('data-go',hm);
  if(hm&&p) at.appendChild(document.createTextNode(nname(p)+' › ')); h('b',null,at,nname(hm)); lab(at,hm?'You are at '+nname(hm)+(p?', in '+nname(p):'')+' (? for the keys)':'The whole world (? for the keys)');
  var mmOn=!!(S.mmOn&&hm&&S.ready); S.mmEl.classList.toggle('on',mmOn); S.root.classList.toggle('wp-mmon',mmOn); if(!mmOn) S.mmTip.hidden=true;
  var hp=placeOf(hm)||(ua(hm)>=0?null:null), hn=hp&&N(hp); if(hn){ S.mmHere.setAttribute('cx',hn.x); S.mmHere.setAttribute('cy',hn.y); S.mmHere.style.display=''; } else S.mmHere.style.display='none';
  mmBox(); hints(hm); }
function hints(hm){ var sc=hm?nscope(hm).slice(0,9):[], on={};
  sc.forEach(function(id,i){ if(id!==hm) on[id]=i+1; }); S.hint=on;
  [].forEach.call(S.root.querySelectorAll('.wp-hk'),function(e){ e.remove(); });
  [].forEach.call(S.root.querySelectorAll('.wp-hint'),function(e){ e.classList.remove('wp-hint'); });
  Object.keys(on).forEach(function(id){ var c=cardEl(id), P=S.pins[id], t=c||(P&&P.el); if(!t) return;
    if(P){ P.el.classList.add('wp-hint'); P.lbl.classList.add('wp-hint'); }
    t.classList.add('wp-hint'); h('span',{'class':'wp-hk','aria-hidden':'true'},t,String(on[id])); }); }
function cardEl(id){ var e=S.lCards.querySelector('[data-id="'+(window.CSS&&CSS.escape?CSS.escape(id):id)+'"]'); return e; }
function help(on){ if(S.helpEl){ S.helpEl.remove(); S.helpEl=null; } if(!on) return;
  var p=S.helpEl=h('div',{'class':'wp-bar wp-help',role:'dialog','aria-label':'How to move'},S.root); h('b',null,p,'How to move');
  NKEYS.forEach(function(k){ h('br',null,p); h('kbd',null,p,k[0]); p.appendChild(document.createTextNode(' '+k[1])); }); }
// the keys the System uses, on the map (the Tour's arrows, T, + and − stay as they were)
function navKey(e){ var k=e.key, hm=nhome();
  if(k==='?'){ if(!e.repeat) help(!S.helpEl); return true; }
  if(k==='o'||k==='O'){ if(!e.repeat){ help(false); A.world(); } return true; }
  if(/^[1-9]$/.test(k)){ if(e.repeat) return true; var to=nscope(hm)[+k-1]; if(to&&to!==hm) ngo(to); return true; }
  if(!S.tour&&hm&&(k==='ArrowLeft'||k==='ArrowRight')){ if(e.repeat) return true; var r=nround(hm,k==='ArrowRight'?1:-1); if(r) ngo(r); return true; }
  return false; }

// ── input: drag, pinch, wheel, Safari's trackpad gestures, keys ──
function bindInput(){
  var svg=S.svg, root=S.root;
  root.addEventListener('wheel',function(e){ if(e.target.closest&&e.target.closest('.wp-list,.wp-key')) return; e.preventDefault(); stop();
    var m=e.deltaMode===1?16:e.deltaMode===2?S.vh:1;
    if(e.ctrlKey){ var q=cp(e.clientX,e.clientY); zoomAt(Math.exp(clamp(-e.deltaY*m*.01,-.3,.3)),q[0],q[1]); }       // a pinch's small steps, a mouse notch at most ×1.35
    else { S.cx+=e.deltaX*m/S.k; S.cy+=e.deltaY*m/S.k; setView(S.cx,S.cy,S.k); } },{passive:false});
  var gs=1;
  root.addEventListener('gesturestart',function(e){ e.stopPropagation(); S.zt=performance.now(); if(Object.keys(S.ptr).length) return; e.preventDefault(); gs=1; },{passive:false});
  root.addEventListener('gesturechange',function(e){ e.stopPropagation(); if(Object.keys(S.ptr).length) return; e.preventDefault(); var q=e.clientX?cp(e.clientX,e.clientY):[S.vw/2,S.vh/2]; zoomAt(e.scale/gs,q[0],q[1]); gs=e.scale; },{passive:false});
  root.addEventListener('gestureend',function(e){ e.stopPropagation(); e.preventDefault(); S.zt=performance.now(); },{passive:false});      // (the engine's gestureend would enlarge a card)
  var last=null;
  var mid=function(){ var k=Object.keys(S.ptr), a=S.ptr[k[0]], b=S.ptr[k[1]]||a; return {x:(a.x+b.x)/2,y:(a.y+b.y)/2,d:Math.hypot(a.x-b.x,a.y-b.y)}; };
  // a drag pans from anywhere on the map, a pin or a name too (not from a card or a panel); it takes the pointer once it is a drag, so a
  // tap on a pin is still the pin's
  var mine=function(t){ return t===svg||!(t.closest&&t.closest('.wp-bar,.wp-list,.wp-enl,.wp-card,.wk,.key-pop')); };
  root.addEventListener('pointerdown',function(e){ if(!mine(e.target)||e.button>0) return; stop(); var q=cp(e.clientX,e.clientY); S.ptr[e.pointerId]={x:q[0],y:q[1]};
    if(e.target===svg) try{ svg.setPointerCapture(e.pointerId); }catch(x){}
    S.dragged=false; S.down={x:e.clientX,y:e.clientY}; last=mid(); root.classList.add('wp-drag'); });
  root.addEventListener('pointermove',function(e){ if(!S.ptr[e.pointerId]) return; var q=cp(e.clientX,e.clientY); S.ptr[e.pointerId]={x:q[0],y:q[1]};
    if(!S.dragged&&Math.hypot(e.clientX-S.down.x,e.clientY-S.down.y)>5){ S.dragged=true; try{ root.setPointerCapture(e.pointerId); }catch(x){} }
    var m=mid(); if(last){ if(Object.keys(S.ptr).length>1&&last.d>0) zoomAt(m.d/last.d,m.x,m.y); S.cx-=(m.x-last.x)/S.k; S.cy-=(m.y-last.y)/S.k; setView(S.cx,S.cy,S.k); } last=m; });
  var up=function(e){ if(!S.ptr[e.pointerId]) return; delete S.ptr[e.pointerId]; last=Object.keys(S.ptr).length?mid():null; if(!last){ root.classList.remove('wp-drag'); if(S.dragged) setTimeout(function(){ S.dragged=false; },0); } };
  root.addEventListener('pointerup',up); root.addEventListener('pointercancel',up);
  svg.addEventListener('click',function(e){ if(S.dragged) return; if(e.target===svg||e.target.classList.contains('wp-c')&&!e.target.classList.contains('wp-u')){ if(S.cl||S.cur) unfocus(); } });
  svg.addEventListener('dblclick',function(e){ e.preventDefault(); var q=cp(e.clientX,e.clientY), s=S.k*2, p=wld(q[0],q[1]); fly(p[0],p[1],s); });
  document.addEventListener('keydown',function(e){
    if(S.root.hidden||document.documentElement.classList.contains('detail-open')) return;
    var t=e.target, tag=t&&t.tagName; if(tag==='INPUT'||tag==='TEXTAREA'||(t&&t.isContentEditable)) return;
    if(e.metaKey||e.ctrlKey||e.altKey){ }
    else if(navKey(e)){ e.preventDefault(); }
    else if(e.key==='Escape'&&S.helpEl){ help(false); }
    else if(!S.tour&&/^Arrow/.test(e.key)){ e.preventDefault(); var st=.18*(e.shiftKey?2.5:1), dx=e.key==='ArrowLeft'?-1:e.key==='ArrowRight'?1:0, dy=e.key==='ArrowUp'?-1:e.key==='ArrowDown'?1:0;
      stop(); setView(S.cx+dx*st*S.vw/S.k,S.cy+dy*st*S.vh/S.k,S.k); }               // the Tour off: the arrows pan the map
    else if(e.key==='ArrowRight'){ e.preventDefault(); A.hop(1); }
    else if(e.key==='ArrowLeft'){ e.preventDefault(); A.hop(-1); }
    else if((e.key==='t'||e.key==='T')&&!e.metaKey&&!e.ctrlKey&&!e.altKey){ A.tourMode(!S.tour); }
    else if(e.key==='Escape'){ if(S.cl||S.cur) unfocus(); else if(S.sel!=null) A.world(); }      // Esc shrinks the card; again, the whole world
    else if(e.key==='+'||e.key==='='){ zoomAt(1.5,S.vw/2,S.vh/2); } else if(e.key==='-'){ zoomAt(1/1.5,S.vw/2,S.vh/2); } });
  window.addEventListener('resize',function(){ if(!S.root.hidden) resize(); });
}
function resize(){ setTop(); var r=S.root.getBoundingClientRect(), was=S.kW; S.vw=S.root.clientWidth||r.width||window.innerWidth; S.vh=S.root.clientHeight||r.height||window.innerHeight;
  S.z=r.width&&S.root.clientWidth?r.width/S.root.clientWidth:1; S.rl=r.left; S.rt=r.top; var v=worldView(); S.kW=v.k;
  if(!S.inited){ S.inited=1; S.cx=v.cx; S.cy=v.cy; S.k=v.k; } else S.k*=S.kW/was; apply(); if(S.cl) layoutCluster(); settleSoon(); }
function setTop(){ var top=0; ['title-bar','nav'].forEach(function(id){ var e=document.getElementById(id); if(!e) return; var b=e.getBoundingClientRect(); if(b.height>0&&b.height<200&&b.top<80&&b.bottom>top) top=Math.round(b.bottom); });
  S.top=top; S.root.style.setProperty('--w-top',top+'px'); }

// ── chrome ──
function chrome(){
  var root=S.root;
  var ctl=S.ctlEl=h('div',{'class':'wp-bar wp-ctl'},root);
  var tb=S.tourBtn=h('button',{type:'button','class':'wp-btn wp-tt','aria-pressed':String(S.tour),title:'Tour the route stop by stop, or turn it off to roam the world (T)'},ctl,'Tour');
  h('span',{'class':'wp-sw','aria-hidden':'true'},tb); tb.addEventListener('click',function(){ A.tourMode(!S.tour); }); root.classList.toggle('wp-free',!S.tour);
  var wb=h('button',{type:'button','class':'wp-btn',title:'The whole world'},ctl,'⤢ World'); wb.addEventListener('click',A.world);
  var zi=h('button',{type:'button','class':'wp-btn r','aria-label':'Zoom in'},ctl,'+'); zi.addEventListener('click',function(){ zoomAt(1.6,S.vw/2,S.vh/2); });
  var zo=h('button',{type:'button','class':'wp-btn r','aria-label':'Zoom out'},ctl,'−'); zo.addEventListener('click',function(){ zoomAt(1/1.6,S.vw/2,S.vh/2); });
  var narrow=(window.innerWidth||1000)<700||document.documentElement.classList.contains('mobile');      // (the map is not measured yet; a phone on its side too)
  var key=S.keyEl=h('div',{'class':'wp-bar wp-key'+(narrow?' shut':'')},root);
  var kt=h('button',{type:'button','class':'wp-kt'},key); (D().acts||[]).forEach(function(a,i){ h('i',{'class':ucls(i),style:'width:8px;height:8px'},kt); }); kt.appendChild(document.createTextNode(' Key'));
  kt.addEventListener('click',function(){ key.classList.toggle('shut'); });
  (D().u||[]).forEach(function(u,a){ var b=h('button',{type:'button','class':'u '+ucls(a)},key); h('i',null,b); b.appendChild(document.createTextNode((a+1)+' '+dec((D().acts[a]||{}).n||'')+' ')); h('span',null,b,'· '+(u.reg||[]).join(', '));
    b.addEventListener('click',function(){ A.unit(a); }); });
  if(Object.keys(D().nodes||{}).some(function(id){ return N(id).r; })){ var kn=h('div',{'class':'wp-kn'},key); var s=el('svg',{viewBox:'-8 -16 16 17',width:10,height:12},kn); el('path',{d:'M0,0 c-5,-7 -8,-11 -8,-15 a8,8 0 1 1 16,0 c0,4 -3,8 -8,15z',fill:'currentColor'},s); kn.appendChild(document.createTextNode('place named in your notes')); }
  // the key is Alto's floating key toggle on desktop (key_toggle.py, as the city palace's and the horizontal timeline's): a round glass
  // button top left under the bars, the key opening beside it; a phone keeps the small key at the bottom (no room for a toggle there)
  if(!narrow&&typeof window._altoKeyToggle==='function'){ key.className='wk'; kt.remove(); var hd=document.createElement('h5'); h('span',null,hd,'Key'); h('span',null,hd,'');
    key.insertBefore(hd,key.firstChild); try{ window._altoKeyToggle(key,'alto-world-key','Key to the map'); }catch(x){} }
  var tour=S.tourEl=h('div',{'class':'wp-bar wp-tour',hidden:''},root);
  var pv=h('button',{type:'button','class':'wp-btn r','aria-label':'Previous stop'},tour,'◀'); pv.addEventListener('click',function(){ A.hop(-1); });
  S.tPrev=h('span',{'class':'d'},tour,''); S.tCur=h('span',{'class':'c'},tour,''); S.tNext=h('span',{'class':'d'},tour,'');
  var nx=h('button',{type:'button','class':'wp-btn r','aria-label':'Next stop'},tour,'▶'); nx.addEventListener('click',function(){ A.hop(1); });
  var tx=h('button',{type:'button','class':'wp-btn r x','aria-label':'End the Tour',title:'End the Tour: roam the world freely'},tour,'✕'); tx.addEventListener('click',function(){ A.tourMode(false); });
  S.list=h('div',{'class':'wp-list',hidden:''},root);
  navChrome();
}
function unitStyle(){ var css=''; (D().acts||[]).forEach(function(a,i){ if(a.c) css+='#wpal-root .wu'+(i%12)+',.wk .wu'+(i%12)+',.wp-where-d.wu'+(i%12)+'{--u:'+String(a.c).replace(/[^#0-9a-zA-Z(),.% ]/g,'')+';}'; });
  var s=document.getElementById('wpal-units')||h('style',{id:'wpal-units'},document.head); s.textContent=css; }

A.show=function(){ if(S.root){ S.root.hidden=false; resize(); } document.documentElement.classList.add('wpal-open'); };
A.hide=function(){ giveBack(); if(S.root) S.root.hidden=true; document.documentElement.classList.remove('wpal-open'); };
A.on=on;
// a card's page hides the map (CSS) and takes its card back to the board; closing it brings the map back where the reader is — on the card
// they stepped to through the pages, if they did. Editing by hand stays on the map (Luke, 2026-10-29: "stay in the mode we are in"): the
// edit layer works on the card the map has opened (manual_edit.py reaches #wpal-root), and the map is only ever hidden by a card's page.
function watchDetail(){ var de=document.documentElement, was=de.classList.contains('detail-open');
  new MutationObserver(function(){ var o=de.classList.contains('detail-open');
    if(o&&!was){ S.reopen=S.cl?{id:S.cl.id,at:S.cl.at,enl:S.cl.enl}:null; S.f0=window._featuredNodeId; giveBack(); }
    if(!o&&was&&S.ready) back();
    was=o; }).observe(de,{attributes:true,attributeFilter:['class']}); }
// a card's page says where the card stands, under its kind (the engine writes the page afresh for every card)
function watchPage(){ var dc=document.getElementById('detail-content'); if(!dc) return;
  var put=function(){ if(window._currentDetailType!=='node') return; var id=window._currentDetailId, n=N(id), r=dc.querySelector('.detail-header .detail-role');
    if(!n||!r||dc.querySelector('.wp-where-d')) return; var d=whereLine(id,'wp-where-d '+ucls(n.a),null); if(d) r.parentNode.insertBefore(d,r.nextSibling); };
  new MutationObserver(put).observe(dc,{childList:true}); put(); }
function back(){ var f=window._featuredNodeId, R=S.reopen; S.reopen=null;
  if(f&&f!==S.f0&&N(f)&&placeOf(f)){ A.select(f,{instant:true}); return; }
  if(R) openCluster(R.id,R.at,R.enl); }
A.mount=function(data){
  if(S.root||!data||!window.fetch) return; A.data=data;
  var st=h('style',{id:'wpal-css'},document.head); st.textContent=WORLD_CSS; unitStyle();
  var root=S.root=h('div',{id:'wpal-root','aria-label':'World map'},document.body);
  S.svg=el('svg',{'class':'wp-svg',role:'img','aria-label':'World map with the cards on their places'},root);
  S.g=el('g',null,S.svg); S.gGrat=el('g',null,S.g); S.gLand=el('g',{'class':'wp-land'},S.g); S.gA1=el('g',null,S.g); S.gArcs=el('g',{'class':'wp-arcs'},S.g);
  S.ov=el('svg',{'class':'wp-ov'},root); S.ovRel=el('g',null,S.ov);
  S.ovRel.addEventListener('click',function(e){ var t=e.target.getAttribute&&e.target.getAttribute('data-to'); if(t){ e.stopPropagation(); A.select(t); } }); S.ovLinks=el('g',null,S.ov); S.ovChev=el('g',null,S.ov);
  S.lTag=h('div',{'class':'wp-layer'},root); S.lLbl=h('div',{'class':'wp-layer'},root); S.lPins=h('div',{'class':'wp-layer'},root); S.lCards=h('div',{'class':'wp-layer'},root);
  var msg=h('div',{'class':'wp-msg'},root,'Loading the world…');
  chrome(); A.show(); bindInput(); watchDetail(); watchPage();
  fetchJSON(GEO.base).catch(function(){ return new Promise(function(ok){ setTimeout(ok,1200); }).then(function(){ return fetchJSON(GEO.base); }); }).then(function(G){
    msg.remove(); drawBase(G); drawArcs(); drawPins(); mmDraw(); S.ready=1; resize(); settle(); watchBoard(); dim(); navSync(); emit('ready');
  }).catch(function(){ msg.remove(); A.hide(); S.root.remove(); S.root=null; });      // no map: the page keeps its cards
};
"""


def _retro_cards() -> str:
    """Retro's look for the timeline's cards (retro.COMMON_CSS, written for the board #world) on the card the map enlarges."""
    from . import retro
    import re
    body = re.sub(r"/\*.*?\*/", "", retro.COMMON_CSS, flags=re.S)
    rows = [r.strip() for r in re.findall(r"[^{}]+\{[^{}]*\}", body) if "#world .node" in r.split("{")[0] and "phase" not in r.split("{")[0]]
    return retro._slim(retro.scoped("\n".join(rows).replace("#world .node", "#wpal-root .wp-enl .node"), "html.alto-retro"))


def _asset() -> str:
    from .world_geo import manifest, continent_boxes
    from .key_toggle import KEY_CSS, KEY_JS
    return (KEY_JS + "\n(function(){\nvar WORLD_CSS=" + _json.dumps(KEY_CSS + WORLD_CSS + _retro_cards()) + ";\nvar GEO=" + _json.dumps(manifest(), sort_keys=True)
            + ";\nvar CBOX=" + _json.dumps(continent_boxes(), sort_keys=True) + ";\n" + WORLD_JS + "\n})();\n")


WORLD_ASSET = _asset()
WORLD_V = _hashlib.sha256(WORLD_ASSET.encode("utf-8")).hexdigest()[:10]
WORLD_PATH = f"/world/palace-world-{WORLD_V}.js"
# the page's loader: a synchronous request answered from the browser's cache after the first visit, run as an inline script (as the building's)
WORLD_LOADER = "\nfunction altoLoadWorld(){ " + _loader(WORLD_PATH, "AltoWorld") + " }\n"
WORLD_START = ("\n(function(){ function go(){ try{ altoLoadWorld(); if(window.AltoWorld) window.AltoWorld.mount(window._ALTO_WORLD); }catch(e){} }"
               " if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',go); else go(); })();\n")


def world_asset() -> tuple[str, str]:
    """(file name under /world/, the script) for the site."""
    return WORLD_PATH.rsplit("/", 1)[1], WORLD_ASSET


def _unit_name(s: str) -> str:
    """A unit's name without its own number ("Unit 1 — Formation" → "Formation"): the map numbers its units itself."""
    import re
    t = re.sub(r"^\s*(unit|part|section|chapter|module|week|topic)\s+[\w.]+\s*[—–:\-]\s*", "", s or "", flags=re.I)
    return t or s


def world_data(b, nodes) -> str:
    """window._ALTO_WORLD: what the hosted renderer needs from the page (the map itself is hosted, world_geo.py)."""
    from .palace import numbers, structure
    from .sanitize import js_json
    from .world_geo import gazetteer
    from .world_plan import plan
    units, floors, _of = structure(b, nodes)
    num = numbers(units, floors)
    p = plan(b, nodes)
    C = gazetteer()["countries"]
    out = {}
    for n in nodes:
        rec = {"n": num.get(n.id, ""), "t": n.title, "a": n.act}
        if n.parent:
            rec["par"] = n.parent
        q = p["places"].get(n.id)
        if q:
            rec.update({"x": q["x"], "y": q["y"], "c": q["c"], "pl": q["label"], "k": q["k"]})
            if q.get("r"):
                rec["r"] = 1
            if q.get("named"):
                rec["nm"] = q["named"]
        out[n.id] = rec
    data = {"v": 1, "lv": p["level"],
            "acts": [{"n": _unit_name(a.short or a.label), "c": a.color or ""} for a in b.acts],
            "u": [{"reg": u["reg"], "tops": u["tops"], "st": u["stops"], **({"hub": u["hub"]} if u.get("hub") else {})} for u in p["units"]],
            "nodes": out, "cl": p["cl"], "used": p["used"], "multi": p["multi"],
            "names": {c: C[c]["n"] for c in p["used"] if c in C}}
    return "\nwindow._ALTO_WORLD=" + js_json(data, separators=(",", ":")) + ";" + WORLD_LOADER + WORLD_START
