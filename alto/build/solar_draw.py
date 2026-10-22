"""What the browser draws and does for a solar outline (brief.layout "solar").

solar.py plans the systems (window._ALTO_SOLAR: every circle's t = 0 centre,
its role, diameter and orbit period); the page puts the centres where the plan
says through the tree's own plan runner. This module is the rest, on desktop
only (a phone keeps the engine's column of cards):

* Circles. A resting .node-card is a disc of the plan's diameter showing the
  path number and the title, clamped (.sol-face). Enlarged (the engine's own
  focus fly and zoom ramp) it is the ordinary card again, description and
  chips and all: while the card grows it is clipped from its disc out to the
  card (a real disc whose diameter, --scd, follows the card's own zoom on
  every frame; never a clip-path: Safari resolved one in the wrong box under
  page zoom), and back down to the disc as it shrinks, so neither end of
  the ramp jumps. The engine's .alto-fshadow is a
  card's, which is right: the enlarged thing is a card.
* #solar-svg, under the cards: faint orbit rings (one per body round what it
  orbits: no two bodies share one), a short spoke from each body to what it
  orbits, a faint dashed link between suns, a soft glow behind each sun —
  the same in both looks (the Star chart adds its skin over them). The
  engine's unit bands, labels and bars go (as on a horizontal timeline); a
  chip names each system.
* Motion ("orbit", both looks). One rAF loop turns every body round what it orbits by
  2π·t/period from its plan centre (solar.py periods and spin) and, with
  several systems, each system slowly as a whole about its own sun (inside its
  R, never toward a neighbour). Bodies move by their own left/top — the D-GRID
  margin centring keeps them centred; never a transform (engine_patches,
  1.8.28) — rounded to device px so text stays crisp. It stops at once on
  hover (a card or a line), focus, a search ring, dimmed cards, the detail
  page, edit mode (where it also turns back to t = 0, the plan's layout),
  print, a hidden tab and prefers-reduced-motion, and eases back in. The
  connections are drawn as straight Alto tubes edge to edge between circles
  and kept on them every frame, with their data-edge-hit paths and the Blink
  card mask's holes.
* Arrow keys pick the nearest body that way from where the bodies are now
  (focusing freezes the orbit, so the fly lands where the card is).

* Edit mode: window._altoSolarSync(tables) plans the systems again from the
  live outline (SOLAR_PLAN_JS, solar_plan in JS) before the page lays out.

The engine hooks (engine_patches.py): solar-layout-hook (end of initLayout),
solar-lines-hook (the base redraw), solar-card-mask-round/-follows, and lines added to the
D-GRID script (a circle grows from its centre; content moving under a still
pointer is not a hover) and to focusNeighbor (window._altoSolarNav).
"""
from __future__ import annotations

import json

from .solar import GOLDEN, LOOK_FLAGS, SOLAR, SPIN

SOLAR_CSS = r"""
  html.alto-solar:not(.mobile) #world .phase-band,html.alto-solar:not(.mobile) #world .phase-label-float,html.alto-solar:not(.mobile) #world .unit-bar{display:none !important;}
  #solar-svg{position:absolute;left:0;top:0;z-index:5;pointer-events:none;overflow:visible;}
  html.mobile #solar-svg,html.mobile .sol-unit,html.mobile .sol-face{display:none !important;}
  #solar-svg .sol-hit{fill:none;stroke:transparent;stroke-width:13px;pointer-events:stroke;cursor:pointer;}
  #solar-svg .sol-hit.sol-oband{display:none;}
  #solar-svg .sol-rider{opacity:0;transition:opacity .35s cubic-bezier(.25,.2,.4,1);pointer-events:none;}
  #solar-svg .sol-rider.on{opacity:1;}
  #solar-svg .sol-rider .sol-rh{fill:var(--accent,#6d5bd0);fill-opacity:.22;}
  #solar-svg .sol-rider .sol-rc{fill:#fff;stroke:var(--accent,#6d5bd0);stroke-width:2.2;}
  html.dark #solar-svg .sol-rider .sol-rh{fill:#cfc6ff;} html.dark #solar-svg .sol-rider .sol-rc{stroke:#cfc6ff;}
  #solar-svg .sol-rider .sol-ship{display:none;}
  html.alto-stars #solar-svg .sol-rider .sol-ship{display:inline;} html.alto-stars #solar-svg .sol-rider :is(.sol-rh,.sol-rc){display:none;}   /* (the chosen craft: solar_craft.py) */
  .sol-ship .sh-hull,.fly-ship .sh-hull{fill:#14161c;stroke:#d9ae55;stroke-width:.9;stroke-linejoin:round;}
  .sol-ship .sh-deck,.fly-ship .sh-deck{fill:#262a33;}
  .sol-ship .sh-fin,.fly-ship .sh-fin{fill:#0c0e12;stroke:#d9ae55;stroke-width:.8;stroke-linejoin:round;}
  .sol-ship .sh-gold,.fly-ship .sh-gold{fill:none;stroke:#d9ae55;stroke-width:.7;}
  .sol-ship .sh-eng,.fly-ship .sh-eng{fill:#ffe6a8;}
  .sol-ship .sh-glow,.fly-ship .sh-glow{fill:#ffd27a;fill-opacity:.3;}
  .sol-ship .sh-ring,.fly-ship .sh-ring{fill:none;stroke:#d9ae55;stroke-width:1.1;stroke-opacity:.55;} .sol-ship .sh-near,.fly-ship .sh-near{stroke-opacity:1;stroke-width:1.3;}
  #solar-svg :is(.sol-spoke,.sol-link).sol-ride{stroke-opacity:.95 !important;stroke-width:3px !important;}
  html.sk-retro.alto-stars #solar-svg :is(.sol-spoke,.sol-link).sol-ride{stroke:#ffd27a !important;}
  #canvas.sol-nudge #world .node.sol-hint:not(.focused) .node-card{animation:sol-nudge .7s cubic-bezier(.25,.2,.4,1) 2;}
  @keyframes sol-nudge{50%{filter:brightness(1.45);}}
  html.alto-editing #solar-svg .sol-hit,html.mobile #solar-svg .sol-hit,#canvas.sol-ov #solar-svg .sol-hit{pointer-events:none;}
  html:not(.mobile) #canvas.sol-lhov #world .node[data-solar]:not(.edge-end):not(.focused) .node-card{opacity:.35 !important;}
  html:not(.mobile) #canvas.sol-lhov #solar-svg :is(.sol-ring,.sol-spoke):not(.sol-hot){stroke-opacity:.07 !important;}
  html:not(.mobile) #canvas.sol-lhov #river-svg{opacity:.15;}
  #solar-svg .sol-spoke.sol-hot.sol-hot{stroke-opacity:.8 !important;stroke-width:2.6px !important;}
  #solar-svg .sol-ring.sol-hot.sol-hot{stroke-opacity:.75 !important;stroke-width:2.2px !important;}
  #solar-svg .sol-ring{fill:none;stroke:color-mix(in srgb,var(--u,var(--text)) 45%,var(--text));stroke-opacity:calc(.3 * var(--lk,1));stroke-width:calc(1.5px * var(--lw,1));}
  #solar-svg .sol-ubd{fill:none;stroke:var(--u,var(--text));stroke-opacity:.32;stroke-width:1.4;pointer-events:none;}
  #solar-svg .sol-ubd.w{stroke-opacity:.09;stroke-width:16;}
  #solar-svg .sol-oort{display:none;fill:none;stroke:rgb(205,218,255);stroke-opacity:.42;stroke-linecap:round;pointer-events:none;}
  #solar-svg .sol-oort.h{stroke:color-mix(in srgb,var(--u,#9fb4ff) 40%,rgb(190,205,255));stroke-opacity:.05;stroke-width:38;}
  html.alto-stars #solar-svg .sol-ubd{display:none;}
  html.alto-stars #solar-svg .sol-oort{display:inline;}
  #solar-svg .sol-ring.sol-m{stroke-opacity:calc(.24 * var(--lk,1));stroke-width:calc(1.2px * var(--lw,1));}
  #solar-svg .sol-spoke{stroke:color-mix(in srgb,var(--u,var(--text)) 40%,var(--text));stroke-opacity:calc(.44 * var(--lk,1));stroke-width:calc(1.9px * var(--lw,1));stroke-linecap:round;}
  #solar-svg .sol-link{fill:none;stroke:var(--text);stroke-opacity:.2;stroke-width:1.6;stroke-dasharray:1.5 7;stroke-linecap:round;}
  html:not(.mobile) #canvas #solar-svg{transition:opacity var(--alto-fly,.25s) var(--alto-ease,ease);}
  html:not(.mobile) #canvas.focus-mode #solar-svg{opacity:.1;}
  html:not(.mobile) #canvas.edge-hover #solar-svg{opacity:.35;}
  .sol-unit{position:absolute;z-index:6;white-space:nowrap;pointer-events:none;font-size:12.5px;font-weight:800;letter-spacing:.12em;
    text-transform:uppercase;color:var(--u);padding:6.25px 12.5px;border-radius:10px;background:color-mix(in srgb,var(--surface) 80%,transparent);
    border:1.5px solid color-mix(in srgb,var(--u) 45%,transparent);}
  .sol-unit b{font-weight:800;opacity:.6;margin-right:7.5px;}
  html.dark .sol-unit{color:color-mix(in srgb,var(--u) 55%,#fff);}
  /* the whole chart (zoomed out to fit): its toggle is the key toggle's round glass, under the bars */
  /* the look switch (System | Star chart) and the orbit switch: glass, under the bars at the top left */
  #sol-ctl{position:fixed;z-index:310;left:71.5px;bottom:24px;height:35px;display:flex;gap:12.5px;align-items:center;font-family:inherit;}   /* in the bottom row beside the account toggle, as palace.py #pal-ctl (round 10) */
  #sol-ctl>*{height:35px;box-sizing:border-box;border-radius:17.5px !important;}
  #sol-ctl .sol-sw{position:relative;display:inline-block;width:26px;height:15px;border-radius:8px;background:color-mix(in srgb,var(--text) 22%,transparent);transition:background .15s;flex:none;}
  #sol-ctl .sol-sw::after{content:'';position:absolute;left:2px;top:2px;width:11px;height:11px;border-radius:50%;background:var(--surface,#fff);transition:transform .15s;}
  #sol-ctl .on .sol-sw{background:var(--accent,#6d5bd0);} #sol-ctl .on .sol-sw::after{transform:translateX(11px);}
  #sol-ctl .sol-st{font-size:10.5px;letter-spacing:.08em;opacity:.75;min-width:22px;text-align:left;}
  #sol-ctl button{font:inherit;font-size:12.5px;font-weight:600;letter-spacing:.02em;display:inline-flex;align-items:center;gap:6px;cursor:pointer;
    color:var(--muted);background:transparent;border:0;padding:6.25px 11.25px;border-radius:999px;line-height:1;}
  #sol-ctl .sol-seg,#sol-ctl #sol-motion,#sol-ctl .sol-opt{background:var(--card-glass-bg, var(--surface));-webkit-backdrop-filter:blur(18px) saturate(190%);backdrop-filter:blur(18px) saturate(190%);
    border:1px solid var(--card-glass-border, var(--border));box-shadow:0 10px 26px var(--node-rest-shadow), inset 0 0 0 0.5px var(--card-glass-rim);border-radius:999px;}
  #sol-ctl .sol-seg{display:inline-flex;padding:2.5px;}
  #sol-ctl button:hover:not(:disabled){color:var(--text);}
  #sol-ctl .sol-seg button.on{color:var(--text);background:color-mix(in srgb,var(--accent,#6d5bd0) 16%,transparent);}
  #sol-ctl #sol-motion,#sol-ctl .sol-opt{padding:8.75px 12.5px;}
  #sol-ctl .sol-opt.on{color:var(--accent,#6d5bd0);}
  #sol-ctl .sol-opt[hidden],#sol-ctl .sol-seg[hidden]{display:none;}
  #sol-ctl #sol-sty button{padding:6.25px 10px;}
  #canvas.sol-lock{overflow:hidden !important;}
  #sol-ctl #sol-motion.on{color:var(--accent,#6d5bd0);}
  #sol-ctl #sol-motion:disabled{opacity:.42;cursor:default;}
  #sol-ctl #sol-motion .sol-ic-play,#sol-ctl #sol-motion.on .sol-ic-pause{display:block;}
  #sol-ctl #sol-motion .sol-ic-pause,#sol-ctl #sol-motion.on .sol-ic-play{display:none;}
  #sol-ctl button:focus-visible{outline:2px solid var(--accent,#6d5bd0);outline-offset:2px;}
  html.mobile #sol-ctl{display:none !important;}
  @media print{ #sol-ctl{display:none !important;} }
  /* no rectangle at any zoom (Luke): the board's own glass is not drawn on a solar page; the page's
     background (System) or the star chart's sky (a fixed, window-filling layer) shows everywhere */
  html.alto-solar:not(.mobile) #world #glass-slab{visibility:hidden !important;}
  #canvas.sol-ov{cursor:zoom-in;}
  #canvas.sol-ov #world,#canvas.sol-ovanim #world{pointer-events:none;transform-origin:0 0;will-change:transform;}
  .sol-face{display:none;}
  /* enlarged: on top at once (the engine holds a node's z-index change back .34s,
     for a card shrinking home; a moon beside its planet would cover the card) */
  html.alto-solar:not(.mobile) #world .node[data-solar].focused{transition:z-index 0s !important;}
  /* a body is a disc at rest (--sd) and a bigger disc enlarged (--sD): never a rectangle. Inside its
     .node-card, bottom to top: a skin (VIS, solar_stars.py: z-index <= 1), .sol-scrim (z 2, enlarged
     only), then .sol-face / .sol-body / the chips (z 3). The round clip is the card's own. */
  html.alto-solar:not(.mobile) #world .node[data-solar] .node-card{min-height:0 !important;padding:0 !important;border-radius:50% !important;
    overflow:hidden;box-sizing:border-box;}
  html.alto-solar:not(.mobile) #world .node[data-solar]:not(.focused):not(.sol-closing) .node-card{width:var(--sd) !important;height:var(--sd) !important;border-top-width:1.5px;}
  html.alto-solar:not(.mobile) #world .node[data-solar].focused .node-card,html.alto-solar:not(.mobile) #world .node[data-solar].sol-closing .node-card{
    width:var(--scd,var(--sD)) !important;height:var(--scd,var(--sD)) !important;}
  html.alto-solar:not(.mobile) #world .node[data-solar] .node-card::before{left:0;right:0;top:0;height:100%;border-radius:50%;
    background:radial-gradient(ellipse 72% 52% at 50% 14%,var(--card-glass-sheen) 0%,rgba(255,255,255,.08) 58%,rgba(255,255,255,0) 100%);}
  html.alto-solar #world .alto-fshadow{border-radius:50% !important;}
  html.alto-solar:not(.mobile) #world .node[data-solar] .sol-face{display:flex;position:absolute;z-index:3;left:50%;top:50%;width:var(--sd);height:var(--sd);
    margin:calc(var(--sd) / -2) 0 0 calc(var(--sd) / -2);flex-direction:column;align-items:center;justify-content:center;gap:2.5px;
    text-align:center;box-sizing:border-box;padding:0 calc(var(--sd) * .15);pointer-events:none;color:var(--text);}
  html.alto-solar:not(.mobile) #world .node[data-solar].focused:not(.sol-clip) .sol-face{display:none;}
  .sol-face b{font-weight:600;font-variant-numeric:tabular-nums;opacity:.72;font-size:10px;line-height:12.5px;letter-spacing:.02em;}
  .sol-face span{display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:3;line-clamp:3;overflow:hidden;
    overflow-wrap:break-word;hyphens:auto;-webkit-hyphens:auto;font-size:12.5px;line-height:15px;max-width:100%;}
  .node[data-solar=sun] .sol-face b{font-size:12.5px;line-height:15px;}
  .node[data-solar=sun] .sol-face span{font-size:16.25px;line-height:20px;-webkit-line-clamp:4;line-clamp:4;}
  /* moons and satellites are small (real-ratio sizes, round 7): a moon shows its own number only, a
     satellite nothing; their number and title are the card's tooltip and accessible name, and the
     enlarged disc's */
  .node[data-solar=moon] .sol-face{padding:0;}
  .node[data-solar=moon] .sol-face b{font-size:10px;line-height:12.5px;opacity:.9;}
  .node[data-solar=moon] .sol-face span,.node[data-solar=sat] .sol-face span,.node[data-solar=sat] .sol-face b{display:none;}
  /* enlarged: the content, in a square inscribed in the disc (corners inside the circle), scrolling
     inside it when long, faded at its top and bottom edges; the chips pool beneath it */
  .sol-body,.sol-scrim{display:none;}
  html.alto-solar:not(.mobile) #world .node[data-solar].focused .sol-body,html.alto-solar:not(.mobile) #world .node[data-solar].sol-closing .sol-body{
    display:flex;flex-direction:column;justify-content:center;position:absolute;z-index:3;left:calc(50% - var(--sD) * .33);width:calc(var(--sD) * .66);top:calc(50% - var(--sD) * .36);height:calc(var(--sD) * .5);overflow:hidden;
    text-align:center;box-sizing:border-box;padding:4px 4px 6px;opacity:var(--sbo,1);}
  html.alto-solar:not(.mobile) #world .node[data-solar].focused .sol-scrim,html.alto-solar:not(.mobile) #world .node[data-solar].sol-closing .sol-scrim{
    display:block;position:absolute;z-index:2;inset:0;border-radius:50%;pointer-events:none;opacity:var(--sbo,1);
    background:radial-gradient(circle,color-mix(in srgb,var(--surface) 84%,transparent) 0 64%,color-mix(in srgb,var(--surface) 52%,transparent) 100%);}
  .sol-body .node-order{position:static !important;float:none !important;display:block;margin:0 0 4px !important;text-align:center;}
  .sol-body .node-tag,.sol-body .node-title,.sol-body .node-desc{text-align:center;}
  .sol-body .node-title{display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:3;overflow:hidden;flex:none;}
  html.alto-solar:not(.mobile) #world .node[data-solar] .sol-body .node-tag{padding-left:0 !important;padding-right:0 !important;}   /* (a card's tag leaves room for its number; the disc's is above it) */
  .sol-body .node-desc{-webkit-line-clamp:4 !important;line-clamp:4;display:-webkit-box !important;-webkit-box-orient:vertical;overflow:hidden !important;text-overflow:ellipsis;flex:none;}
  /* the chips lie in arcs along the disc's bottom edge, side by side, each turned to the arc's tangent (pool()) */
  html.alto-solar:not(.mobile) #world .node[data-solar]:not(.focused):not(.sol-closing) .node-card>.node-footer{display:none !important;}
  html.alto-solar:not(.mobile) #world .node[data-solar]:is(.focused,.sol-closing) .node-card>.node-footer{display:block;position:absolute;z-index:3;margin:0;
    inset:0;pointer-events:none;opacity:var(--sbo,1);}
  .node-card>.node-footer .footer-sep{display:none;}
  /* each chip is placed by pool() (in px from the disc's centre) */
  .node-card>.node-footer>button,.node-card>.node-footer>.sol-more{border-radius:999px !important;display:inline-flex;align-items:center;justify-content:center;text-align:center;
    position:absolute;left:50%;top:50%;height:24px !important;min-width:24px;box-sizing:border-box;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
    max-width:min(130px,calc(var(--sD) * .4));pointer-events:auto;font-size:11px;line-height:14px;transform-origin:50% 50%;}
  .node-card>.node-footer>.esym-btn,.node-card>.node-footer>.tsym-btn,.node-card>.node-footer>.sol-more{padding:0 10px !important;}
  /* a named chip is one line; past its width the text ends in an ellipsis (a flex box cannot take one) */
  .node-card>.node-footer>button.sol-txt{display:block;line-height:22px;text-align:center;}
  /* the engine's chip label inside a disc: wraps (it may be a long name) and is kept inside the circle (sol-tip) */
  html.alto-solar:not(.mobile) #world .node[data-solar] .node-footer .chip-tip{white-space:normal;width:max-content;max-width:calc(var(--sD) * .62);text-align:center;}
  .node-card>.node-footer>.sol-more{font-weight:600;color:var(--text);cursor:default;border:1px dashed var(--border);background:var(--chip-plate,var(--surface));}
  /* growing / shrinking (--scd): no frost on the moving disc (a zoomed element can lose it anyway), never a clip-path */
  html.alto-solar:not(.mobile) #world .node.sol-clip .node-card{-webkit-backdrop-filter:none !important;backdrop-filter:none !important;background:var(--node-glass-bg,var(--panel-glass-bg)) !important;}
  html.alto-solar:not(.mobile) #world .node.sol-clip .sol-face{opacity:var(--sfo,0);}
  /* a detail page shows no chart chrome (Luke, round 8) */
  body:has(#detail-page.visible) #sol-ctl{display:none !important;}
  /* every body's name (round 8): a label under it (or above / beside it, wherever it is clear), upright, the
     same size on screen at any zoom (--ils counter-scales the whole chart's --ovs); the planet's own
     disc then shows its number only. Hidden where it would cover a bigger body or a label of one (.sol-lx),
     shown on hover. .sol-dot: a body never smaller than a few px on screen (zoomed out). */
  .sol-lbl,.sol-dot{display:none;}
  html.alto-solar:not(.mobile) #world .node[data-solar]>.sol-lbl{display:block;position:absolute;left:50%;top:50%;z-index:4;pointer-events:none;white-space:nowrap;
    --lr:calc(max(var(--dn,20) * var(--ovs,1) / 2, 2.5) * 1px);transform-origin:0 0;transform:scale(var(--ils,1)) translate(-50%,calc(var(--lr) + 3px));
    max-width:170px;overflow:hidden;text-overflow:ellipsis;font-style:normal;font-size:12px;line-height:15px;font-weight:600;letter-spacing:.01em;color:var(--text);
    text-shadow:0 0 3px var(--bg,#fff),0 0 2px var(--bg,#fff);transition:opacity .2s;}
  html.alto-solar.dark:not(.mobile) #world .node[data-solar]>.sol-lbl{text-shadow:0 0 3px #000,0 0 2px #000;}
  html.alto-stars:not(.mobile) #world .node[data-solar]>.sol-lbl{color:#eef2ff;text-shadow:0 0 3px #000,0 0 2px #000;}
  .sol-lbl::after{content:attr(data-l);}
  html.alto-solar:not(.mobile) #world .node[data-solar]>.sol-lbl.sol-l1{transform:scale(var(--ils,1)) translate(-50%,calc(-100% - var(--lr) - 3px));}
  html.alto-solar:not(.mobile) #world .node[data-solar]>.sol-lbl.sol-l2{transform:scale(var(--ils,1)) translate(calc(var(--lr) + 4px),-50%);}
  html.alto-solar:not(.mobile) #world .node[data-solar]>.sol-lbl.sol-l3{transform:scale(var(--ils,1)) translate(calc(-100% - var(--lr) - 4px),-50%);}
  html.alto-solar:not(.mobile) #world .node[data-solar=moon]>.sol-lbl,html.alto-solar:not(.mobile) #world .node[data-solar=sat]>.sol-lbl{font-size:11px;line-height:13.75px;font-weight:500;}
  html.alto-solar:not(.mobile) #world .node[data-solar=sun]>.sol-lbl{font-size:16px;line-height:20px;font-weight:700;}
  #canvas.sol-ov #world .node[data-solar=planet]>.sol-lbl{font-size:14px;line-height:17.5px;}
  html.alto-solar:not(.mobile) #world .node[data-solar]>.sol-lbl.sol-lx{opacity:0;}
  html.alto-solar:not(.mobile) #canvas:not(.sol-lo) #world .node[data-solar=sun]>.sol-lbl,
  html.alto-solar:not(.mobile) #canvas.sol-lo #world .node[data-solar=sat]>.sol-lbl,
  html.alto-solar:not(.mobile) #canvas.sol-lm #world .node[data-solar=moon]>.sol-lbl{display:none;}
  #canvas.sol-lo #world .node[data-solar] .sol-face{visibility:hidden;}
  html.alto-solar:not(.mobile) #world .node[data-solar]:not(.focused):hover>.sol-lbl{opacity:1;z-index:9;max-width:none;}
  html.alto-solar:not(.mobile) #world .node[data-solar]:is(.focused,.sol-closing)>.sol-lbl,
  html.alto-solar:not(.mobile) #canvas.focus-mode #world .node[data-solar]:not(.sol-flank)>.sol-lbl{opacity:0 !important;}
  html.alto-solar:not(.mobile) #world .node-card:is(.dimmed,.rel-dimmed,.ent-dimmed)~.sol-lbl{opacity:.14;}
  .node[data-solar=planet] .sol-face span{display:none;}
  .node[data-solar=planet] .sol-face b{font-size:12.5px;line-height:15px;}
  html.alto-solar:not(.mobile) #world .node[data-solar]>.sol-dot{display:block;position:absolute;left:50%;top:50%;pointer-events:none;border-radius:50%;opacity:0;
    width:calc(max(4, var(--dn,20) * var(--ovs,1)) * 1px);height:calc(max(4, var(--dn,20) * var(--ovs,1)) * 1px);transform-origin:0 0;
    transform:scale(var(--ils,1)) translate(-50%,-50%);background:color-mix(in srgb,var(--u,var(--text)) 55%,var(--text));}
  #canvas.sol-ov #world .node[data-solar]>.sol-dot{opacity:clamp(0, calc((7 - var(--dn,20) * var(--ovs,1)) / 3), 1);}
  html.alto-stars #canvas.sol-ov #world .node[data-solar]>.sol-dot{background:var(--sk-c,#cfd8ff);}
  html.alto-stars #world .node[data-solar=sun]>.sol-dot{background:#ffcf4a !important;}
  #canvas.sol-ov #solar-svg :is(.sol-ring,.sol-spoke,.sol-link){vector-effect:non-scaling-stroke;}
  /* a speck of a chart (.sol-tiny): each body a flat dot of its colour, its picture / glass not drawn at all */
  #canvas.sol-tiny #world .node[data-solar]:not(.focused)>.sol-dot{opacity:1;}
  #canvas.sol-tiny #world .node[data-solar]:not(.focused) .node-card{visibility:hidden;}   /* a hairline at least, at any zoom */
  #canvas.sol-ov .sol-unit{transform-origin:50% 100%;transform:scale(var(--cls,1));transition:opacity .2s;}
  #sol-ulay{position:absolute;left:0;top:0;width:0;height:0;z-index:7;pointer-events:none;}
  #sol-ulay .sol-unit{left:0 !important;top:0 !important;transform-origin:50% 100%;}
  #canvas:not(.sol-ov) #sol-ulay{display:none;}
  .sol-unit.sol-lx{opacity:0;}
  /* an enlarged body's own (its children: moons of a planet, satellites of a moon) come up beside it */
  html:not(.mobile) #canvas.focus-mode #world .node.sol-flank .node-card{opacity:1 !important;}
  html.alto-solar:not(.mobile) #world .node.sol-flank{z-index:200 !important;}
  html.alto-solar:not(.mobile) #world .node.sol-flank>.sol-lbl{max-width:150px;}
  #sol-flank-svg{position:absolute;left:0;top:0;z-index:6;pointer-events:none;overflow:visible;}
  #sol-flank-svg line{stroke:color-mix(in srgb,var(--accent,#6d5bd0) 55%,var(--text));stroke-opacity:.55;stroke-width:1.6;stroke-linecap:round;}
  html.alto-stars #sol-flank-svg line{stroke:rgb(190,210,255);}
  html.mobile #sol-flank-svg{display:none;}
  /* navigation hints (round 11): a pill on each place an arrow goes (key, move, name), its way drawn under the
     bodies, and the same pill at the window's edge for a place off it. Up: a filled key; down: a ringed key;
     the same level: a plain key and a dotted way. No filter or blur (WebKit), opacity only in motion. */
  @keyframes solnh{from{opacity:0}}
  #sol-way{position:absolute;left:0;top:0;z-index:5;pointer-events:none;overflow:visible;}
  #sol-way path{fill:none;stroke:color-mix(in srgb,var(--accent,#6d5bd0) 75%,var(--text));stroke-opacity:.75;stroke-width:2.6px;stroke-linecap:round;animation:solnh .4s ease-out .1s both;}
  #sol-way path:is([data-k=e],[data-k=w]){stroke-dasharray:.1 8;stroke-width:3.4px;stroke-opacity:.7;}
  #sol-nav{position:absolute;left:0;top:0;width:0;height:0;z-index:400;}
  html.mobile :is(#sol-way,#sol-nav),.sol-nhx,#sol-nav [hidden]{display:none !important;}
  html.sol-flying :is(#sol-way,#sol-nav,#world .sol-nh){opacity:0 !important;transition:opacity .15s;}   /* a flight (solar_fly.py): gone at once, back faded in on landing */
  html.alto-solar:not(.mobile) #world .node.sol-hint>.sol-lbl{opacity:0 !important;}
  html:not(.mobile) #canvas.focus-mode #world .node.sol-hint .node-card{opacity:1 !important;}
  #world .sol-nh{position:absolute;left:50%;top:50%;z-index:8;display:flex;align-items:center;gap:6px;white-space:nowrap;pointer-events:none;
    --lr:calc(max(var(--dn,20) * var(--ovs,1) / 2, 2.5) * 1px);transform-origin:0 0;transform:scale(var(--ils,1)) translate(-50%,calc(var(--lr) + 6px));
    padding:3px 11px 3px 3px;border-radius:14px;font-size:12px;line-height:18px;font-weight:600;font-style:normal;color:var(--text);
    --nc:var(--u,var(--accent,#6d5bd0));background:color-mix(in srgb,var(--bg,#fff) 93%,transparent);box-shadow:0 0 0 1px color-mix(in srgb,var(--nc) 35%,transparent),0 4px 14px rgba(20,24,60,.16);animation:solnh .35s ease-out .12s both;}
  #world .sol-nh[data-p=a]{transform:scale(var(--ils,1)) translate(-50%,calc(-100% - var(--lr) - 6px));}
  #world .sol-nh[data-p=r]{transform:scale(var(--ils,1)) translate(calc(var(--lr) + 8px),-50%);}
  #world .sol-nh[data-p=l]{transform:scale(var(--ils,1)) translate(calc(-100% - var(--lr) - 8px),-50%);}
  #sol-nav .sol-nh{left:0;top:0;transform:translate(var(--o,-50%,-50%));pointer-events:auto;cursor:pointer;}
  .sol-nh>kbd{display:grid;place-items:center;min-width:22px;height:18px;border-radius:9px;font:800 12px/1 system-ui,sans-serif;box-shadow:inset 0 0 0 1.3px color-mix(in srgb,var(--text) 38%,transparent);}
  .sol-nh[data-k=n]>kbd{background:var(--nc);color:#fff;box-shadow:none;}
  .sol-nh[data-k=s]>kbd{background:color-mix(in srgb,var(--nc) 22%,transparent);box-shadow:inset 0 0 0 1.8px var(--nc);}
  .sol-nh>i{font-style:normal;font-size:9.5px;font-weight:700;letter-spacing:.09em;text-transform:uppercase;opacity:.6;}
  .sol-nh>i::after{content:attr(data-a);} #canvas.sol-lock .sol-nh>i::after{content:attr(data-b);}
  .sol-nh>b{max-width:170px;overflow:hidden;text-overflow:ellipsis;font-weight:650;}
  .sol-nh>em{display:none;font-style:normal;font-size:12px;width:12px;text-align:center;opacity:.75;transform:rotate(var(--a,0deg));}
  #sol-nav .sol-nh>em{display:block;margin-left:5px;}
  html.alto-stars #world .sol-nh{color:#eef2ff;background:rgba(5,10,28,.9);box-shadow:0 0 0 1px rgba(170,198,255,.42),0 4px 16px rgba(0,0,0,.55);}
  html.alto-stars .sol-nh>kbd{box-shadow:inset 0 0 0 1.3px rgba(220,230,255,.5);}
  html.alto-stars .sol-nh[data-k=n]>kbd{background:#d6e4ff;color:#06102a;}
  html.alto-stars .sol-nh[data-k=s]>kbd{color:#cfe0ff;box-shadow:inset 0 0 0 1.8px #a9c6ff;}
  html.alto-stars #sol-way path{stroke:#bcd3ff;}
"""

SOLAR_JS = r"""
/* The renderer: a function of the plan (window._ALTO_SOLAR, solar.page_plans: the plan and
   look:'stars'|'hub', the look a viewer sees first) mounted on the engine's #world. One System
   page, ONE plan, two looks (Luke, round 7): System (rings, spokes, glass circles)
   and the Star chart (the same, plus the skin, solar_stars.py, and flights, solar_fly.py); both
   orbit. One mount per page (its engine hooks are page globals). */
window._altoSolarMount=function(R, opt){
opt=opt||{}; if(!R || window._altoSolarMounted) return false;
var de=document.documentElement, NS='http://www.w3.org/2000/svg', TAU=Math.PI*2, K=1.7;
/* the viewer's choices, per timeline (look, motion) */
var KEY=(typeof COURSE_ID!=='undefined' && COURSE_ID) || 'page';
function pref(k){ try{ return localStorage.getItem('alto-solar-'+k+':'+KEY); }catch(e){ return null; } }
function keep(k, v){ try{ localStorage.setItem('alto-solar-'+k+':'+KEY, String(v)); }catch(e){} }
function lk(v){ return v==='hub' || v==='plain' ? 'hub' : v==='stars' ? 'stars' : null; }   /* ('plain': 1.9.108's still look, now System) */
var LOOK=lk(pref('look')) || lk(R.look) || 'stars';
var S=R;
if(!S || !S.nodes) return false; window._altoSolarMounted=true;
window._altoSolarView=1;          /* the opening view is this script's (openView), not the engine's centreWorld */
var ORBIT, SPIN, DEF=S.sizes||{sun:184, planet:96, moon:50, sat:20}, NUM=null;
function desk(){ return !de.classList.contains('mobile'); }
if(desk()) de.classList.add('alto-solar');

/* the bodies, each after what it orbits */
var B={}, ORD=[], SY=[], MOVES=false, GAL=null;
function q(v){ return Math.round(v/2.5)*2.5; }      /* D-GRID: half a diameter on the 1.25px grid */
function body(id, role, p, per, si, o){
  var n=S.nodes[id]||{}; B[id]={id:id, role:role, p:p, per:ORBIT ? (+per||0) : 0, si:si, d:q(n.d||DEF[role]),
    orb:(ORBIT && n.orbit && n.orbit.e>0 && o) ? n.orbit : null, r:o ? +o.r : 0, a0:o ? +o.a0 : 0,
    look:n.look||'', tumble:ORBIT ? (+n.tumble||0) : 0}; ORD.push(id); }
function bodies(){
  ORBIT=S.style!=='spoke'; SPIN=S.spin||-1; B={}; ORD=[]; SY=S.systems||[]; GAL=(S.core && SY.length>1 && S.core.p>0) ? S.core : null;
  SY.forEach(function(s, si){ body(s.sun, 'sun', null, 0, si);
    (s.planets||[]).forEach(function(pl){ body(pl.id, 'planet', s.sun, pl.period, si, pl);
      (pl.moons||[]).forEach(function(m){ body(m.id, 'moon', pl.id, m.period, si, m);
        (m.sats||[]).forEach(function(t){ body(t.id, 'sat', m.id, t.period, si, t); }); }); }); });
  MOVES=ORBIT && ORD.some(function(i){ return B[i].per>0; });
}
bodies();
looks();
var world=null, svg=null, PAD=0, zq=1, links=[], spokes=[], rings=[], sunl=[], chips=[], ready=false;
function el(t, a, p){ var e=document.createElementNS(NS, t); for(var k in a) e.setAttribute(k, a[k]); if(p) p.appendChild(e); return e; }
function f2(v){ return Math.round(v*100)/100; }
function rd(v){ return Math.round(v*zq)/zq; }
function unitColor(si){ var pm=(typeof PHASE_META!=='undefined') ? PHASE_META[(SY[si]||{}).unit] : null; return pm ? pm.colorRaw : ''; }
/* the face a resting circle shows: its path number and title */
function face(n, id){
  var c=n.querySelector('.node-card'); if(!c) return;
  var f=c.querySelector('.sol-face'); if(!f){ f=document.createElement('div'); f.className='sol-face'; f.innerHTML='<b></b><span></span>'; c.appendChild(f); }
  var num=(NUM && NUM[id]) || (typeof NODE_ORDER_MAP!=='undefined' && NODE_ORDER_MAP[id]) || '', t=c.querySelector('.node-title'), tt=t ? t.textContent : '';
  var b=B[id];
  var small=b.role==='moon' || b.role==='sat';
  f.querySelector('b').textContent=small ? (num.split(/[.\-]/).pop()||num) : num;
  var sp=f.querySelector('span'), base={sun:16.25, planet:12.5, moon:8.75}[b.role], L=Math.max.apply(null, tt.split(/\s+/).map(function(w){ return w.length; }).concat([1]));
  sp.textContent=tt; sp.style.fontSize=sp.style.lineHeight='';
  /* a word too long for the disc: the type steps down (to 72%) before a word is broken */
  var fs=base ? Math.max(base*.72, Math.min(base, b.d*.68/(L*.55))) : 0;
  if(fs && fs<base){ fs=Math.round(fs*4)/4; sp.style.fontSize=fs+'px'; sp.style.lineHeight=Math.round(fs*1.2*4)/4+'px'; }
  f.setAttribute('aria-hidden', 'true');
  if(small){ c.setAttribute('title', (num ? num+'  ' : '')+tt); c.setAttribute('aria-label', (num ? num+' ' : '')+tt); }
  /* its name beside it (the text an attribute: never markup) and its dot for the zoomed-out chart */
  var lb=n.querySelector(':scope > .sol-lbl');
  if(!lb){ lb=document.createElement('i'); lb.className='sol-lbl'; lb.setAttribute('aria-hidden', 'true'); n.appendChild(lb);
    var dt=document.createElement('i'); dt.className='sol-dot'; dt.setAttribute('aria-hidden', 'true'); n.appendChild(dt); }
  lb.setAttribute('data-l', tt.replace(/\s+/g, ' ').trim()); n.style.setProperty('--dn', b.d); b.lb=lb; b.w0=b.w1=null;
  if(unitColor(b.si)) n.style.setProperty('--u', unitColor(b.si));
  disc(n, c, id, b);
}
/* markup as the plain text it reads as (a tooltip, a label, an attribute) */
function plain(h){ var t=document.createElement('template'); t.innerHTML=String(h==null ? '' : h); return (t.content.textContent||'').replace(/\s+/g, ' ').trim(); }
/* the enlarged disc's layers: the card's own number / tag / title / description / chips go into
   .sol-body (the same elements, so edit mode edits them in place), a .sol-scrim under it, the
   chips pooled at the bottom (pool()); and --sD, the enlarged diameter, by how much there is to read.
   A click on the disc (or Enter) opens its full page: the engine's own card click, left alone. */
function disc(n, c, id, b){
  var body=c.querySelector(':scope > .sol-body');
  if(!body){ body=document.createElement('div'); body.className='sol-body';
    [].slice.call(c.children).forEach(function(k){ if(/(^| )(node-order|node-tag|node-title|node-desc)( |$)/.test(k.className)) body.appendChild(k); });
    var sc=document.createElement('div'); sc.className='sol-scrim'; sc.setAttribute('aria-hidden', 'true');
    c.insertBefore(sc, c.firstChild); c.appendChild(body);
    var ft=c.querySelector('.node-footer'); if(ft) c.appendChild(ft);   /* the chips: pooled along the disc's bottom */
  }
  var L=(body.textContent||'').length;
  var D=L<200 ? 300 : L<400 ? 340 : 380;
  n.style.setProperty('--sD', Math.max(D, q(b.d+40))+'px');
  if(n.classList.contains('focused')) pool(n);
}
/* ── the chips of an enlarged disc (Luke, 1.9.117): side by side in arcs along its bottom edge, each turned to the
   arc's tangent; a full arc (~75 degrees either way, or the text above) is followed by one just inside it; >= 12px
   inside the border; the rest fold into "+N"; one line each, <= .4 D wide, an ellipsis past that (the engine's chip
   label shows the name whole). Computed once, as the disc opens (and a frame later); px from the disc's centre. */
function pool(n){
  var c=n.querySelector('.node-card'), ft=c && c.querySelector(':scope > .node-footer'), body=c && c.querySelector(':scope > .sol-body');
  if(!ft || !body) return;
  var D=parseFloat(n.style.getPropertyValue('--sD'))||300, R=D/2, M=12, G=6, H=24, CAPW=Math.min(130, D*.4), top0=-D*.36, cap=D*.04, LIM=75*Math.PI/180, bx=D*.33+4;
  var btns=[].slice.call(ft.querySelectorAll(':scope > button')), more=ft.querySelector(':scope > .sol-more:not(.sol-tm)'), tm=ft.querySelector(':scope > .sol-tm');
  if(!more){ more=document.createElement('span'); more.className='sol-more'; more.setAttribute('role', 'note'); ft.appendChild(more); }
  if(!tm){ tm=document.createElement('span'); tm.className='sol-more sol-tm'; tm.setAttribute('role', 'note'); ft.appendChild(tm); }
  btns.forEach(function(k){ k.style.display=''; k.style.transform=''; k.style.maxWidth=CAPW+'px';
    k.classList.toggle('sol-txt', !k.children.length && (k.textContent||'').trim().length>2); });     /* a named chip: block, so its text can take an ellipsis */
  [more, tm].forEach(function(el){ el.style.display='none'; el.style.transform=''; el.style.maxWidth=CAPW+'px'; });
  /* (Luke, round 10) glyph chips keep the bottom arcs, upright; named chips sit level in centred rows under the text */
  var all=btns.filter(function(k){ return !k.classList.contains('sol-txt'); }), txt=btns.filter(function(k){ return k.classList.contains('sol-txt'); });
  var N=all.length, W=all.map(function(k){ return k.offsetWidth; });
  /* where a chip of width w at angle th (from straight down, + to the right) on an arc of radius r reaches */
  function box(r, th, w){ var x=r*Math.sin(th), y=r*Math.cos(th); return {x:x, y:y, l:x-w/2, r:x+w/2, t:y-H/2, o:Math.sqrt(Math.pow(Math.abs(x)+w/2, 2)+Math.pow(Math.abs(y)+H/2, 2))}; }   /* upright */
  function lay(ws){
    var out=[], i=0, k=0;
    while(i<ws.length){
      var wm=0, j, r, ri;
      for(j=i; j<ws.length; j++) wm=Math.max(wm, ws[j]);
      r=Math.sqrt(Math.pow(R-M, 2)-wm*wm/4)-H/2;                                  /* the widest chip's corners stay M inside the border */
      if(k){ var rp=out[k-1].r, rr=rp-H-G;
        for(var t=0; t<4; t++){ var q=rr+H/2; rr=rp-H-G-(Math.sqrt(q*q+wm*wm/4)-q); }     /* the ends of a chip bulge outward: leave room for them */
        r=Math.min(r, rr); }
      if(r<H) return null;
      ri=r-H/2;
      var items=[], ok;
      /* upright chips side by side: centres spaced along a level line (widths + G), each lifted onto the arc */
      function place(tr, r){ var tot=-G; tr.forEach(function(it){ tot+=ws[it.j]+G; }); var x=-tot/2;
        for(var u=0; u<tr.length; u++){ var cx=x+ws[tr[u].j]/2; if(Math.abs(cx)>=r) return false; tr[u].th=Math.asin(cx/r); if(Math.abs(tr[u].th)>LIM) return false; x+=ws[tr[u].j]+G; }
        return true; }
      /* the arc's radius: the outermost (in steps of 3px, <= 36px in) that holds the most of the chips left */
      function fill(r){ var its=[], ok;
        for(var j5=i; j5<ws.length; j5++){
          var trial=its.map(function(it){ return {j:it.j}; }).concat([{j:j5}]);
          ok=place(trial, r);
          for(var u2=0; ok && u2<trial.length; u2++){
            var bb=box(r, trial[u2].th, ws[trial[u2].j]); if((bb.r>-bx && bb.l<bx && bb.t<cap) || bb.o>R-M) ok=false;      /* clear of the text above, inside the rim */
            for(var a3=0; ok && a3<out.length; a3++) out[a3].items.forEach(function(it){ var b2=box(out[a3].r, it.th, ws[it.j]);
              if(bb.l<b2.r+G && b2.l<bb.r+G && bb.t<b2.t+H+G && b2.t<bb.t+H+G) ok=false; }); }      /* and of the arcs outside it */
          if(!ok) break;
          its=trial; }
        return its; }
      var r0=r;
      for(var st=0; st<=12; st++){ var rr2=r0-3*st; if(rr2<H) break; var f5=fill(rr2); if(f5.length>items.length){ items=f5; r=rr2; } if(i+items.length>=ws.length) break; }
      j=i+items.length;
      if(!items.length) return null;
      out.push({r:r, items:items}); i=j; k++;
    }
    return out;
  }
  var arcs=null, k=N;
  for(; k>=0; k--){
    var ws=W.slice(0, k);
    if(k<N){ more.textContent='+'+(N-k); more.style.display=''; ws.push(more.offsetWidth); }
    arcs=lay(ws); if(arcs) break;
  }
  if(!arcs){ more.style.display='none'; arcs=[]; k=0; }
  var hidden=N-k, hi=null;
  arcs.forEach(function(ar){ ar.items.forEach(function(it){
    var el=it.j<k ? all[it.j] : more, w=it.j<k ? W[it.j] : el.offsetWidth, bb=box(ar.r, it.th, w);
    el.style.left='calc(50% + '+(bb.x-w/2).toFixed(1)+'px)'; el.style.top='calc(50% + '+(bb.y-H/2).toFixed(1)+'px)';
    el.style.transform='';                                             /* upright: the glyph faces north */
    el.setAttribute('data-arc', String(arcs.indexOf(ar)));
    if(bb.r>-bx && bb.l<bx) hi=hi==null ? bb.t : Math.min(hi, bb.t); }); });
  all.forEach(function(el, j){ if(j>=k) el.style.display='none'; });
  if(hidden) more.title=all.slice(k).map(function(e){ return e.title; }).filter(Boolean).join(', ');
  /* the named chips: level rows (<= 3), centred, filled top-down in order, each no wider than the disc's chord
     there less M; the block sits as low as it can (just above the arcs, or the rim) and climbs until all fit,
     never into the text's least height; the rest fold into the last row's "+N" */
  if(txt.length){
    var TW=txt.map(function(e){ return e.offsetWidth; }), y0=(hi!=null ? hi-G : R-M), RM=R-M, floor=top0+D*.3+6, rows=[], i0=0;
    function chord(y){ var a=Math.max(Math.abs(y), Math.abs(y+H)); return a>=RM ? 0 : 2*Math.sqrt(RM*RM-a*a); }
    function fit(yb, nr){ var rs=[], i=0, y=yb-nr*H-(nr-1)*G;
      for(var q2=0; q2<nr && i<txt.length; q2++, y+=H+G){ var lim=chord(y), row=[], w=0;
        for(; i<txt.length; i++){ var w2=w+(row.length ? G : 0)+TW[i]; if(w2>lim) break; row.push(i); w=w2; }
        if(!row.length && TW[i]>lim) break; rs.push({y:y, j:row, w:w}); }
      return {rows:rs, i:i}; }
    var best=null;
    for(var nr=1; nr<=3 && !(best && best.i===txt.length); nr++)
      for(var yb=y0; yb-nr*H-(nr-1)*G>=floor-.5; yb-=6){ var f=fit(yb, nr); if(!best || f.i>best.i) best=f; if(f.i===txt.length) break; }
    if(best){ rows=best.rows.filter(function(rw){ return rw.j.length; }); i0=best.i; }
    var left=txt.length-i0;
    if(left && rows.length){ var lr=rows[rows.length-1]; tm.textContent='+'+left; tm.style.display=''; var mw=tm.offsetWidth;
      while(lr.j.length && lr.w+G+mw>chord(lr.y)){ var dj=lr.j.pop(); lr.w-=TW[dj]+(lr.j.length ? G : 0); left++; tm.textContent='+'+left; mw=tm.offsetWidth; }
      tm.title=txt.slice(txt.length-left).map(function(e){ return e.title||e.textContent; }).filter(Boolean).join(', '); }
    else if(left){ tm.textContent='+'+left; tm.style.display=''; }
    var shown={};
    rows.forEach(function(rw, ri){ var last=ri===rows.length-1 && tm.style.display!=='none', tw=rw.w+(last ? G+tm.offsetWidth : 0), x=-tw/2;
      rw.j.forEach(function(j3){ var el=txt[j3]; shown[j3]=1; el.style.left='calc(50% + '+x.toFixed(1)+'px)'; el.style.top='calc(50% + '+rw.y.toFixed(1)+'px)'; el.setAttribute('data-arc', 'row'+ri); x+=TW[j3]+G; });
      if(last){ tm.style.left='calc(50% + '+x.toFixed(1)+'px)'; tm.style.top='calc(50% + '+rw.y.toFixed(1)+'px)'; }
      hi=hi==null ? rw.y : Math.min(hi, rw.y); });
    if(!rows.length && left){ tm.style.left='calc(50% - '+(tm.offsetWidth/2)+'px)'; tm.style.top='calc(50% + '+(R-M-H)+'px)'; }
    txt.forEach(function(el, j4){ if(!shown[j4]) el.style.display='none'; });
  }
  /* the text gives way to the chips: the body ends just above the highest one under it */
  body.style.height=hi==null ? '' : Math.max(D*.3, hi-6-top0).toFixed(1)+'px';
  var ds=body.querySelector('.node-desc'), kk=4;
  function over(){ var s=0; [].forEach.call(body.children, function(e){ s+=e.offsetHeight+8; }); return s>body.clientHeight; }
  if(ds){ ds.style.removeProperty('-webkit-line-clamp'); ds.style.removeProperty('line-clamp');
    if(hi!=null) while(kk>1 && over()){ kk--; ds.style.setProperty('-webkit-line-clamp', String(kk), 'important'); ds.style.setProperty('line-clamp', String(kk), 'important'); } }
}
/* ── the layout: at the end of initLayout (engine patch solar-layout-hook),
   before the lines are drawn. Every body's home is its plan centre. */
window._altoSolarLayout=function(pos){
  if(!desk()) return;
  world=document.getElementById('world'); if(!world) return;
  de.classList.add('alto-solar');
  PAD=(typeof WORLD_PAD_TOP!=='undefined') ? WORLD_PAD_TOP : 0;
  zq=(parseFloat(getComputedStyle(de).zoom)||1)*(window.devicePixelRatio||1);
  var NM={};
  if(typeof NODES!=='undefined') NODES.forEach(function(n){ NM[n.id]=n; });
  ORD.forEach(function(id){
    var b=B[id], n=document.getElementById('node-'+id), P=S.nodes[id]||{};
    b.n=n; b.c=n ? n.querySelector('.node-card') : null; if(!n) return;
    /* the plan's centre: circles are never dragged, and whatever the page's
       plan runner did (edit mode lays a tree out with its own; initLayout's
       numeral check nudges cards at the right edge) the orbit is the plan's */
    b.hx=P.x; b.hy=P.y+PAD;
    if(pos) pos[id]=P.y;
    n.setAttribute('data-solar', b.role); n.style.setProperty('--sd', b.d+'px');
    if(!n.classList.contains('focused')){ n.style.setProperty('--mx', (-b.d/2)+'px'); n.style.setProperty('--my', (-b.d/2)+'px'); }   /* centred at once (D-GRID's ResizeObserver would only catch up at the next frame) */
    b.rx=b.ry=null; b.x=b.hx; b.y=b.hy;
    if(NM[id]){ NM[id].displayX=b.hx; NM[id].y=b.hy-PAD; }
    face(n, id);
  });
  var W=Math.max(1700, (S.world||{}).w||0), H=((S.world||{}).h||0)+PAD;
  ORD.forEach(function(id){ var b=B[id]; if(b.n) H=Math.max(H, b.hy+b.d/2+115); });
  slab(W, H);
  var rv=document.getElementById('river-svg'); if(rv){ rv.setAttribute('height', H); if(W>1700) rv.setAttribute('width', W); }
  draw(W, H);
  ready=true; hov=0;
  apply(true); skin();
  if(MOVES) go();
  ctl(); lockSync();
  if(OV){ ovHold(true); clampO(OV); ovSet(OV); }
  fitBtn();
  if(!opened) setTimeout(openView, 0);
};
/* ── where the page opens (once, on the first layout) ──────────────────────
   A chart bigger than the window opened on the top of the board — a district
   chip over empty space, the first sun below the fold (Luke, Torts, 1.9.105).
   It opens on the first sun (the plan's first system) at full size, in the
   middle of the window; a chart small enough to read whole (the whole-chart
   fit at 0.6 or more) opens zoomed out to all of it. System keeps the
   engine's opening (centred across, at the top) while its first sun is in
   view there. A view something else asked for wins: a #find= link, an
   enlarged card, the detail page, a canvas already scrolled down. */
var opened=false;
function openView(){
  var c=cvs(); if(opened || !c || !c.clientWidth || !ready || !desk()) return;
  opened=true;
  var over=c.scrollWidth-c.clientWidth, dl=over>1 ? Math.round(over/2) : 0;   /* the engine's centreWorld */
  if(/[#&]find=/.test(String(document.URL).split('#')[1]||'') || window._focusedNodeId || c.scrollTop>1 || document.querySelector('#detail-page.visible')) return;
  var b=SY[0] && B[SY[0].sun];
  if(!b || !b.n){ c.scrollLeft=dl; return; }
  var off=woff(c), cw=c.clientWidth, ch=c.clientHeight, x=b.hx+off.x, y=b.hy+off.y, r=b.d/2;
  var f=fitS();
  if(f>=1){ c.scrollLeft=dl; return; }                                        /* all of it in view as it is */
  if(f>=.6){ ovZoom(f, null, null, false); return; }
  var sl=Math.max(0, Math.min(c.scrollWidth-cw, x-cw/2)), st=Math.max(0, Math.min(c.scrollHeight-ch, y-ch/2)), ax=window._altoScrollAxis;
  if(ax){ ax('scrollLeft').go(sl); ax('scrollTop').go(st); } else { c.scrollLeft=sl; c.scrollTop=st; }
}
/* the board is the plan's size: the glass behind it (whose end the page's
   height follows), tinted down the page by the systems' unit colours */
function slab(W, H){
  var sl=document.getElementById('glass-slab');
  if(W>1700){ world.style.setProperty('width', W+'px', 'important'); if(sl) sl.style.setProperty('width', W+'px', 'important'); }
  world.style.minHeight=H+'px';
  if(!sl) return;
  var cs=getComputedStyle(world), pads=(parseFloat(cs.paddingTop)||0)+(parseFloat(cs.paddingBottom)||0);
  var t0=parseFloat(sl.style.top)||0, sh=Math.max(1, H+pads-t0), st=[], seen={};   /* the page fits #world's min-height to the glass's end, less its padding */
  sl.style.height=sh+'px';
  SY.forEach(function(s, si){ var b=B[s.sun], c=unitColor(si); if(!b || !c || seen[Math.round(b.hy)]) return; seen[Math.round(b.hy)]=1;
    st.push({p:Math.max(0, Math.min(100, (b.hy-t0)/sh*100)), c:c}); });
  st.sort(function(a, b){ return a.p-b.p; });
  if(!st.length) return;
  sl.style.backgroundImage='linear-gradient(180deg, '+st[0].c+'b3 0%, '+st.map(function(q){ return q.c+'b3 '+q.p.toFixed(1)+'%'; }).join(', ')+', '+st[st.length-1].c+'b3 100%)';
  window._headerTint={slabTop:t0, slabH:sh, stops:[{p:0, c:st[0].c}].concat(st, [{p:100, c:st[st.length-1].c}])};
  if(window.updateHeaderTint) try{ window.updateHeaderTint(); }catch(e){}
}
/* rings, spokes, sun links, glows, the systems' chips */
/* a ring's click target (Luke, round 9: a click on an orbit enlarges its body): a wide transparent
   stroke under the bodies; on a shared ring, the body on it nearest the click */
function hitR(r, tag, a, g){ var h=el(tag, Object.assign({'class':'sol-hit sol-rgh'}, a)); g.insertBefore(h, r.e); h._r=r; r.h=h; return r; }
function ringAt(e){ var h=e.target, r=h && h._r; if(!r || !h.classList || !h.classList.contains('sol-hit')) return null;
  if(r.sp) return window._focusedNodeId===r.sp.b ? r.sp.a : r.sp.b;     /* a spoke (round 10): to its far end — outward, or back in from the body it leads to */
  if(r.ids.length<2) return r.ids[0];
  var m=svg && svg.getScreenCTM(), p=m ? new DOMPoint(e.clientX, e.clientY).matrixTransform(m.inverse()) : {x:0, y:0}, x=p.x, y=p.y, best=null, bd=Infinity;
  r.ids.forEach(function(i){ var b=B[i], d=Math.hypot(b.rx-x, b.ry-y); if(d<bd){ bd=d; best=i; } }); return best; }
['pointerover', 'pointerout'].forEach(function(t){ document.addEventListener(t, function(e){ var h=e.target; if(h && h._r && h._r.e){ h._r.e.classList.toggle('sol-hot', t==='pointerover'); if(h._r.b) h._r.b.classList.toggle('sol-hot', t==='pointerover'); } }); });
/* ── a resting pointer on an orbit or a spoke (round 10, outline mode's rules: blocks.py LINE_NAV_GLUE — a
   300ms dwell, 6px slop, never a line slid under a still pointer; its ends stay, the rest fades; the same
   .line-tip label at the pointer, following it, gone on leaving) names it: a spoke its two ends, an orbit
   what it goes round (and what is on it) ── */
var LH={t:0, r:null, x:0, y:0, on:null, tip:null};
function lname(id){ var n=(typeof NODES_SRC!=='undefined') ? NODES_SRC.filter(function(q){ return q.id===id; })[0] : null; return plain((n && n.title) || id); }
function ltext(r){ if(r.sp) return lname(r.sp.a)+' \u2014 '+lname(r.sp.b);
  var on=(r.ids||[]).map(lname); return 'Orbit of '+lname(r.c)+(on.length && on.length<=3 ? ': '+on.join(', ') : on.length ? ': '+on.length+' bodies' : ''); }
function lclear(){ clearTimeout(LH.t); LH.t=0; LH.r=null; if(!LH.on) return; LH.on=null;
  var c=cvs(); if(c) c.classList.remove('sol-lhov'); [].forEach.call(document.querySelectorAll('#world .node.edge-end'), function(n){ n.classList.remove('edge-end'); });
  if(LH.tip) LH.tip.style.display='none'; }
function lshow(r){ var c=cvs(); if(!c || c.classList.contains('focus-mode') || c.classList.contains('sol-ov')) return;
  LH.on=r; var ends=r.sp ? [r.sp.a, r.sp.b] : [r.c].concat(r.ids||[]);
  ends.forEach(function(id){ var n=B[id] && B[id].n; if(n) n.classList.add('edge-end'); }); c.classList.add('sol-lhov');
  if(!LH.tip){ LH.tip=document.createElement('div'); LH.tip.className='line-tip'; document.body.appendChild(LH.tip); }
  LH.tip.textContent=ltext(r); LH.tip.style.display='block'; LH.tip.style.left=(LH.x+12)+'px'; LH.tip.style.top=(LH.y+14)+'px'; }
document.addEventListener('pointerover', function(e){ var h=e.target, r=h && h._r;
  if(!r || !h.classList || !h.classList.contains('sol-hit') || !desk() || de.classList.contains('alto-editing')) return;
  if(window._altoPointerStill && window._altoPointerStill(e)) return;
  if(LH.on && LH.on!==r) lclear(); if(LH.on===r) return;
  clearTimeout(LH.t); LH.r=r; LH.x=e.clientX; LH.y=e.clientY; LH.t=setTimeout(function(){ LH.t=0; if(LH.r===r) lshow(r); }, 300); });
document.addEventListener('pointermove', function(e){
  if(LH.on){ if(LH.tip){ LH.tip.style.left=(e.clientX+12)+'px'; LH.tip.style.top=(e.clientY+14)+'px'; } return; }
  if(LH.r && LH.t && Math.hypot(e.clientX-LH.x, e.clientY-LH.y)>6){ var r=LH.r; clearTimeout(LH.t); LH.x=e.clientX; LH.y=e.clientY;
    LH.t=setTimeout(function(){ LH.t=0; if(LH.r===r) lshow(r); }, 300); } });
document.addEventListener('pointerout', function(e){ var h=e.target; if(h && h._r && h.classList && h.classList.contains('sol-hit')){ var to=e.relatedTarget; if(!(to && to._r===h._r)) lclear(); } });
['wheel', 'pointerdown', 'keydown'].forEach(function(t){ window.addEventListener(t, function(){ if(LH.on || LH.t) lclear(); }, true); });
document.addEventListener('click', function(e){ if(!e.target || !e.target._r || de.classList.contains('alto-editing') || !desk()) return;
  var id=ringAt(e); if(!id) return; e.stopPropagation(); e.preventDefault(); if(window.enterFocus) window.enterFocus(id); }, true);
/* Retro (Luke, 2026-10-21): the coloured bands ARE the orbits. Each orbit is a band — a wide ring, edge to edge
   with its neighbours (its edges halfway to the orbits either side), so a system is still the poster's stepped
   discs, light near the sun, dark at its reach — and the bodies sit on and travel along their bands. A band is
   its orbit's click and hover target (the same travel, label and highlight as a ring); the thin rings are not
   drawn in Retro. A comet's band is its ellipse, widened. Under every line (and every spoke's own target). */
function hexMix(a, b, t){ var A=parseInt(a.slice(1), 16), Z=parseInt(b.slice(1), 16), o='#';
  [16, 8, 0].forEach(function(sh){ var x=(A>>sh)&255, y=(Z>>sh)&255; o+=('0'+Math.round(x+(y-x)*t).toString(16)).slice(-2); }); return o; }
function oBands(g, si){
  var by={}, mine=rings.filter(function(r){ var b=B[r.c]; return b && b.si===si && !r.b; });
  mine.forEach(function(r){ (by[r.c]=by[r.c]||[]).push(r); });
  var gb=el('g', {'class':'sol-obands'}), dep=function(id){ var k=0; while(B[id] && B[id].p){ id=B[id].p; k++; } return k; };
  Object.keys(by).sort(function(a, b){ return dep(a)-dep(b); }).forEach(function(c){
    var C=B[c], L=by[c].filter(function(r){ return r.r!=null; }).sort(function(a, b){ return a.r-b.r; }), n=L.length, sun=!C.p,
      c0=sun ? '#2b64a6' : '#4a86c6', c1=sun ? '#061224' : '#1a3e70';
    L.forEach(function(r, j){ var gi=j ? r.r-L[j-1].r : (n>1 ? L[1].r-r.r : 48), go=j<n-1 ? L[j+1].r-r.r : gi;
      var lo=j ? (L[j-1].r+r.r)/2 : Math.max(C.d/2+8, r.r-gi/2), hi=j<n-1 ? (r.r+L[j+1].r)/2 : r.r+Math.max(18, go/2), w=Math.max(12, hi-lo);
      r.b=el('circle', {'class':'sol-hit sol-oband'+(sun ? '' : ' sol-m'), r:f2((lo+hi)/2), style:'--bw:'+f2(w)+'px;--bc:'+hexMix(c0, c1, n>1 ? j/(n-1) : .4)}, gb); r.b._r=r; });
    by[c].filter(function(r){ return r.r==null && r.e; }).forEach(function(r){   /* a comet's */
      r.b=el('ellipse', {'class':'sol-hit sol-oband sol-ocomet', rx:r.e.getAttribute('rx'), ry:r.e.getAttribute('ry'), style:'--bw:16px;--bc:#173a66'}, gb); r.b._r=r; });
  });
  g.insertBefore(gb, g.firstChild);
}
function draw(W, H){
  var old=document.getElementById('solar-svg'); if(old) old.remove();
  document.querySelectorAll('#world .sol-unit,#sol-ulay .sol-unit').forEach(function(e){ e.remove(); });
  svg=el('svg', {id:'solar-svg', width:W, height:H, 'aria-hidden':'true'});
  var rv=document.getElementById('river-svg');
  world.insertBefore(svg, rv && rv.parentNode===world ? rv : world.firstChild);
  var defs=el('defs', {}, svg); spokes=[]; rings=[]; sunl=[]; chips=[];
  SY.forEach(function(s, si){
    var sun=B[s.sun]; if(!sun || !sun.n) return;
    var u=unitColor(si), g=el('g', {'data-sys':si}, svg);
    if(u) g.style.setProperty('--u', u);
    if(u){ var gr=el('radialGradient', {id:'sol-glow-'+si}, defs);
      el('stop', {offset:'0', 'stop-color':u, 'stop-opacity':'.42'}, gr); el('stop', {offset:'1', 'stop-color':u, 'stop-opacity':'0'}, gr);
      sun.glow=el('circle', {r:f2(sun.d*1.15), fill:'url(#sol-glow-'+si+')'}, g); }
    /* the unit's border (round 10): a soft hue ring in the unit's colour (System look); an Oort cloud, a faint
       shell of specks, in the Star chart look (CSS picks one). It goes round the system, with its sun. */
    if(s.R){ var BR=s.R+28, bg=el('g', {'class':'sol-bd'}, g), OB=BR*1.5;
      /* Retro's imperial sigil round the sun (Luke: Foundation's Empire): a ring of rays, long and short, between two hairlines */
      var sr=sun.d/2, sg=el('g', {'class':'sol-sig'}, bg), r1=sr+22, r2=sr+46;
      el('circle', {r:f2(r1-6)}, sg); el('circle', {r:f2(r2+8)}, sg); el('circle', {'class':'w', r:f2(r2+20)}, sg);
      for(var q=0; q<48; q++){ var an=q*Math.PI/24, lo=q%4===0 ? r2+14 : q%2===0 ? r2 : r1+12, cs=Math.cos(an), sn=Math.sin(an);
        el('line', {x1:f2(cs*r1), y1:f2(sn*r1), x2:f2(cs*lo), y2:f2(sn*lo), 'class':q%4===0 ? 'k' : ''}, sg); }
      el('circle', {'class':'sol-ubd w', r:f2(BR)}, bg); el('circle', {'class':'sol-ubd', r:f2(BR)}, bg);
      [[-10, 1.7, '0.1 9', 0], [-3, 1.3, '0.1 13', 5], [5, 1.9, '0.1 11', 2], [13, 1.2, '0.1 17', 8], [21, 1, '0.1 23', 3]].forEach(function(o){
        el('circle', {'class':'sol-oort', r:f2(BR+o[0]), 'stroke-width':o[1], 'stroke-dasharray':o[2], 'stroke-dashoffset':o[3]}, bg); });
      el('circle', {'class':'sol-oort h', r:f2(BR+4)}, bg);
      sun.bd=bg; }
    /* rings: each planet's round the sun, each moon's round its planet, each satellite's round its moon */
    var seen={};
    ORD.forEach(function(id){
      var b=B[id]; if(b.si!==si || !b.p || !b.n) return;
      var p=B[b.p]; if(!p.n) return;
      if(b.orb && window._altoSolarAt){                 /* a comet's path: its ellipse about what it orbits */
        var c0=window._altoSolarAt(b.r, b.a0, b.orb), qq=(function(e){ var q=Math.sqrt(Math.max(0, 1-e*e)); return (1-q)/(1+q); })(b.orb.e), ea={rx:f2(b.r*(1+qq)), ry:f2(b.r*(1-qq))};
        rings.push(hitR({c:b.p, ids:[id], ox:b.hx-p.hx-c0[0], oy:b.hy-p.hy-c0[1], rot:b.orb.rot*180/Math.PI,
          e:el('ellipse', Object.assign({'class':'sol-ring sol-comet'+(b.role==='planet' ? '' : ' sol-m')}, ea), g)}, 'ellipse', ea, g));
      } else { var r=Math.hypot(b.hx-p.hx, b.hy-p.hy), k=b.p+'|'+Math.round(r/2);
        if(!seen[k]){ seen[k]=rings.length; rings.push(hitR({c:b.p, r:r, ids:[id], e:el('circle', {'class':'sol-ring'+(b.role==='planet' ? '' : ' sol-m'), r:f2(r)}, g)}, 'circle', {r:f2(r)}, g)); }
        else rings[seen[k]].ids.push(id); }
      var sp={a:b.p, b:id, e:[el('line', {'class':'sol-spoke'}, g)]}; sp.spoke=1;
      sp.bn=[-2, -1, 1, 2].map(function(k){ var l=el('line', {'class':'sol-bun'}, g); l._k=k; return l; });   /* Retro: the spoke as a beam of parallel lines */ sp.h=el('line', {'class':'sol-hit'}); g.insertBefore(sp.h, g.firstChild);   /* under every ring's: where they cross, the ring wins */ sp.h._r={sp:sp, e:sp.e[0]};
      spokes.push(sp);
    });
    oBands(g, si);
    /* one chip per unit (a district of several systems: over all of them) */
    var U=null; (S.units||[]).forEach(function(q){ if(q.suns && q.suns[0]===s.sun) U=q; });
    var pm=(typeof PHASE_META!=='undefined') ? PHASE_META[s.unit] : null, lbl=(U && U.label) || s.label || (pm ? pm.label : ''), bb=(U && U.bbox) || s.bbox;
    lbl=plain(lbl).split(' — ').pop();
    if(lbl && (U || !S.units)){ var ch=document.createElement('div'); ch.className='sol-unit'; if(u) ch.style.setProperty('--u', u);
      ch.setAttribute('data-unit', s.unit); ch.innerHTML='<b></b><span></span>'; ch.querySelector('b').textContent=pm ? pm.numeral : ''; ch.querySelector('span').textContent=lbl;
      world.appendChild(ch);
      var top=Math.max(PAD+24, (bb ? bb[1]+PAD : sun.hy-(s.R||sun.d))-44);
      ch.style.left=Math.round((U ? (bb[0]+bb[2])/2 : sun.hx)-ch.offsetWidth/2)+'px'; ch.style.top=Math.round(top)+'px'; chips.push(ch);
      if(!U){ sun.ch=ch; ch._ox=parseFloat(ch.style.left)-sun.hx; ch._oy=parseFloat(ch.style.top)-sun.hy; } }   /* (round 10) the name rides with its sun as the galaxy turns */
  });
  var lg=el('g', {'class':'sol-links'}, svg);
  (S.sun_links||[]).forEach(function(l){ if(!B[l[0]] || !B[l[1]] || !B[l[0]].n || !B[l[1]].n) return;
    sunl.push({a:l[0], b:l[1], e:[el('path', {'class':'sol-link'}, lg)]}); });
}
/* the connections, edge to edge between circles: drawn in place of the router
   (engine patch solar-lines-hook); a parent's line to its child is the spoke */
window._altoSolarLines=function(){
  if(!ready || !desk()) return false;
  var rv=document.getElementById('river-svg'); if(!rv) return false;
  rv.innerHTML=''; links=[];
  var dark=de.classList.contains('dark'), sheen=dark ? 'rgba(255,255,255,0.50)' : 'rgba(255,255,255,0.72)', pairs={};
  (typeof CONNECTIONS!=='undefined' ? CONNECTIONS : []).forEach(function(c){
    var a=B[c[0]], b=B[c[1]]; if(!a || !b || !a.n || !b.n || a.p===b.id || b.p===a.id) return;
    var k=c[0]<c[1] ? c[0]+'|'+c[1] : c[1]+'|'+c[0]; if(pairs[k]) return; pairs[k]=1;
    var spine=c[2]==='spine', col=COLOR_MAP[c[2]] || 'var(--line-flow)';
    if(spine) col=dark ? 'rgb(208,212,226)' : 'rgb(60,64,84)';
    else try{ var pm=PHASE_META[NODE_ACT[c[0]]||0], era=pm ? _lineToRgb(pm.colorRaw) : null, base=dark ? [12,13,20] : [240,239,234];
      var bg=era ? [0,1,2].map(function(i){ return Math.round(era[i]*.7+base[i]*.3); }) : base;
      var ad=_lineAdapt(_lineToRgb(_lineResolveVar(col)), bg); if(ad) col='rgb('+ad.join(',')+')'; }catch(e){}
    var w=spine ? 4.2 : 5, t=el('path', {fill:'none', stroke:col, 'stroke-width':w, 'stroke-linecap':'round', 'stroke-linejoin':'round',
      'data-edge':c[0]+'|'+c[1], 'stroke-opacity':spine ? .92 : .96}, rv);
    var s=el('path', {fill:'none', stroke:sheen, 'stroke-width':Math.max(1.3, w*.34), 'stroke-linecap':'round'}, rv);
    links.push({a:c[0], b:c[1], k:c[0]+'|'+c[1], e:[t, s]});
  });
  apply(true);
  return true;
};

/* ── motion ──────────────────────────────────────────────────────────────── */
var T=0, rk=1, back=1, sp=0, last=null, raf=0, slT=0, hov=0, hovT=0, printing=0, mq=null, reduced=false;
try{ mq=matchMedia('(prefers-reduced-motion: reduce)'); reduced=mq.matches;
  var mqf=function(){ reduced=mq.matches; if(pref('motion')==null){ MOTION=!reduced; ctl(); } go(); }; if(mq.addEventListener) mq.addEventListener('change', mqf); else mq.addListener(mqf); }catch(e){}
/* the orbit switch (both looks): on by default, off by default for reduced motion, the viewer's choice kept */
var MOTION=pref('motion')==null ? !reduced : pref('motion')==='1', RAMP=1.2;
function wrap(a){ a%=TAU; if(a>Math.PI) a-=TAU; if(a<-Math.PI) a+=TAU; return a; }
/* where every body is at time T (rk < 1: on the way back to T = 0) */
function place(){
  var g=(GAL && ORBIT) ? GAL : null;   /* (both looks: a look switch moves nothing) */
  ORD.forEach(function(id){
    var b=B[id]; if(!b.n) return;
    orbitAt(b, g); if(b.fs) fpos(b);
  });
}
function orbitAt(b, g){
    /* the galaxy (plan.core, 2+ systems) turns rigidly about the core (period g.p):
       every sun round it, every body's angle with it — rigid, so no two systems ever meet */
    var ga=g ? SPIN*TAU*T/g.p : 0;
    if(!b.p){ if(!g){ b.x=b.hx; b.y=b.hy; return; }
      var w=wrap(ga)*rk, cx=g.x, cy=g.y+PAD, ex=b.hx-cx, ey=b.hy-cy, c0=Math.cos(w), s0=Math.sin(w);
      b.x=cx+ex*c0-ey*s0; b.y=cy+ex*s0+ey*c0; return; }
    var p=B[b.p], dx=b.hx-p.hx, dy=b.hy-p.hy, a=b.per>0 ? wrap(SPIN*TAU*T/b.per+ga)*rk : wrap(ga)*rk, cs=Math.cos(a), sn=Math.sin(a);
    if(b.orb && window._altoSolarAt){ var o=window._altoSolarAt(b.r, b.a0+a, b.orb), o0=window._altoSolarAt(b.r, b.a0, b.orb);   /* a comet: its ellipse (solar.orbit_offset), anchored at its plan home */
      b.x=p.x+dx+(o[0]-o0[0]); b.y=p.y+dy+(o[1]-o0[1]); return; }
    b.x=p.x+dx*cs-dy*sn; b.y=p.y+dx*sn+dy*cs;
}
function seg(a, b, ga, gb){
  var dx=b.rx-a.rx, dy=b.ry-a.ry, L=Math.hypot(dx, dy)||1, ux=dx/L, uy=dy/L, ra=a.d/2+ga, rb=b.d/2+gb;
  if(L<=ra+rb) return null;
  return [f2(a.rx+ux*ra), f2(a.ry+uy*ra), f2(b.rx-ux*rb), f2(b.ry-uy*rb)];
}
/* ── seams for the star chart's skin (solar_stars.py) and its travel (solar_fly.py) ──
   window._altoSolarT: the orbit clock in seconds — a body's angle is a0 + spin*2*pi*T/period
     about what it orbits (plus, with 2+ systems, spin*2*pi*T/core.p: the whole
     galaxy turned rigidly about plan.core, suns included): solar.py's formula, as place() runs it.
   window._altoSkinTick(plan, bodies, T), if defined, is called after every frame that moved the
     bodies, and once after each layout. bodies: {id: {id, role, p (what it orbits), per, si
     (system index), d (diameter), n (.node), c (.node-card), hx, hy (home), x, y (now, float),
     rx, ry (now, as written to left/top), r, a0 (its orbit's radius and t = 0 angle), orb (a comet's
     ellipse {e, rot, k}, else null), look ('blackhole' | 'comet' | 'asteroid' | ''), tumble (an
     asteroid's spin, rad/s: its angle is tumble * T)}} — world px (WORLD_PAD_TOP included). Read-only.
     A comet's place: the plan's formula (solar.orbit_offset, window._altoSolarAt(r, angle, orb)) at
     angle a0 + spin*2*pi*T/period (+ the galaxy's turn), about what it orbits.
     Not called while the orbit is held (hover, focus, edit mode...): a skin that animates on its
     own runs its own frames. A skin's layers go inside .node-card under .sol-scrim (z-index <= 1). */
function skin(){ window._altoSolarT=T; if(window._altoSkinTick) try{ window._altoSkinTick(S, B, T); }catch(e){} }
function setD(p, d){ if(p.hasAttribute('data-d0')) p.setAttribute('data-d0', d); else p.setAttribute('d', d); }
/* write the bodies and everything drawn with them; all = also what did not move */
function apply(all){
  if(!ready) return;
  place();
  var moved={}, any=false;
  ORD.forEach(function(id){
    var b=B[id]; if(!b.n) return;
    var x=rd(b.x), y=rd(b.y);
    if(x!==b.rx || y!==b.ry || all){
      if(x!==b.rx) b.n.style.left=x+'px'; if(y!==b.ry) b.n.style.top=y+'px';
      if(b.rx!=null && (x!==b.rx || y!==b.ry)) any=true;
      b.rx=x; b.ry=y; moved[id]=1;
      if(b.glow){ b.glow.setAttribute('cx', x); b.glow.setAttribute('cy', y); }
      if(b.bd) b.bd.setAttribute('transform', 'translate('+x+' '+y+')');
      if(b.ch && b.ch.isConnected){ b.ch.style.left=Math.round(x+b.ch._ox)+'px'; b.ch.style.top=Math.round(y+b.ch._oy)+'px'; if(OV) ulq=1; }
      if(b.mk && b.mk.isConnected){ var w=b.mk._w; b.mk.setAttribute('x', f2(x-w/2+1)); b.mk.setAttribute('y', f2(y-w/2+1)); }
    }
  });
  if(ulq){ ulq=0; ulay(); }
  if(!all && !any) return;
  rings.forEach(function(r){ if(!moved[r.c]) return; var cx=f2(B[r.c].rx+(r.ox||0)), cy=f2(B[r.c].ry+(r.oy||0));
    [r.e, r.h, r.b].forEach(function(e){ if(!e) return; e.setAttribute('cx', cx); e.setAttribute('cy', cy); if(r.rot!=null) e.setAttribute('transform', 'rotate('+f2(r.rot)+' '+cx+' '+cy+')'); }); });
  spokes.concat(sunl).forEach(function(s){
    if(!moved[s.a] && !moved[s.b]) return;
    var g=seg(B[s.a], B[s.b], 3, 3);
    if(s.e[0].tagName==='line'){ var e=s.e[0]; if(!g){ e.setAttribute('x2', e.getAttribute('x1')||0); return; }
      [e, s.h].forEach(function(l){ if(!l) return; l.setAttribute('x1', g[0]); l.setAttribute('y1', g[1]); l.setAttribute('x2', g[2]); l.setAttribute('y2', g[3]); });
      if(s.bn && RETRO){ var L=Math.hypot(g[2]-g[0], g[3]-g[1])||1, nx=-(g[3]-g[1])/L*3.4, ny=(g[2]-g[0])/L*3.4;
        s.bn.forEach(function(l){ var k=l._k; l.setAttribute('x1', f2(g[0]+nx*k)); l.setAttribute('y1', f2(g[1]+ny*k)); l.setAttribute('x2', f2(g[2]+nx*k)); l.setAttribute('y2', f2(g[3]+ny*k)); }); } }
    else { var d=g ? 'M'+g[0]+' '+g[1]+' L'+g[2]+' '+g[3] : 'M0 0'; s.e.forEach(function(p){ p.setAttribute('d', d); }); }
  });
  links.forEach(function(l){
    if(!moved[l.a] && !moved[l.b]) return;
    var g=seg(B[l.a], B[l.b], 1, 1), d=g ? 'M '+g[0]+' '+g[1]+' L '+g[2]+' '+g[3] : 'M0 0';
    if(!l.h || !l.h.isConnected) l.h=svgHit(l.k);
    l.e.forEach(function(p){ setD(p, d); }); if(l.h) l.h.setAttribute('d', d);
  });
  if(any && window._altoContentMoved) window._altoContentMoved();
  declutter(all);
}
function svgHit(k){ var rv=document.getElementById('river-svg'), r=null;
  if(rv) [].some.call(rv.querySelectorAll('[data-edge-hit]'), function(h){ if(h.getAttribute('data-edge-hit')===k){ r=h; return true; } });
  return r; }
/* the Blink mask's holes follow their circles (engine patch solar-card-mask-round) */
window._altoSolarMask=function(){ ORD.forEach(function(id){ var b=B[id]; b.mk=null; });
  [].forEach.call(document.querySelectorAll('#alto-card-mask [data-mk]'), function(r){
    var b=B[r.getAttribute('data-mk').slice(5)]; if(b){ b.mk=r; r._w=parseFloat(r.getAttribute('width'))+2; } }); };
/* scrolling or zooming (round 10, "slow to move"): the orbits ease to a rest while it lasts, so a frame is the
   scroll alone, not the whole galaxy turning under it as well; they run on 400ms after it stops */
var SCR=0, scrT=0;
function scrolling(){ SCR=1; clearTimeout(scrT); scrT=setTimeout(function(){ SCR=0; go(); }, 400); }
window.addEventListener('wheel', scrolling, {capture:true, passive:true});
document.addEventListener('scroll', function(e){ if(e.target && e.target.id==='canvas') scrolling(); }, {capture:true, passive:true});
function hold(){
  if(!MOVES || !MOTION || !desk() || document.hidden || hov || FLN || SCR || RD) return true;
  if(window._focusedNodeId || document.querySelector('#canvas.focus-mode,#canvas.edge-hover,#detail-page.visible')) return true;
  return !!document.querySelector('#world .node.alto-found,#world .node.sol-closing,#world .node-card.dimmed,#world .node-card.rel-dimmed,#world .node-card.ent-dimmed');
}
function tick(ts){
  raf=0; if(!ready || DRV) return;
  var dt=last==null ? 0 : Math.min(.1, (ts-last)/1000); last=ts;
  if(OV && (de.classList.contains('alto-editing') || window._focusedNodeId)) ovLeave(null, true);
  if(de.classList.contains('alto-editing') || printing){          /* the plan's own layout, turned back to */
    sp=0; if(T){ back=printing ? 0 : Math.max(0, back-dt/.45); rk=back*back*(3-2*back); apply(); skin(); if(back) return go(); T=0; back=rk=1; }
    return sleep(); }
  if(back<1){ T=0; back=rk=1; apply(); }
  if(hold()){ sp=0; return sleep(); }
  sp=Math.min(1, sp+dt/RAMP); if(sp>=1) RAMP=1.2; T+=dt*sp*sp*(3-2*sp); apply(); skin(); go();
}
function go(){ clearTimeout(slT); if(!raf && MOVES && (MOTION || (T && (printing || de.classList.contains('alto-editing'))))) raf=requestAnimationFrame(tick); }   /* Orbit off: no frames at all (but edit mode / print still turn it home) */
function sleep(){ last=null; clearTimeout(slT); slT=setTimeout(go, 180); }
/* a flight (solar_fly.py) drives the clock: while it flies T is its own, set every
   frame, and the loop here waits; let go, the orbits run on from the rate it hands
   back (0: still, 1: full speed), easing as ever. _altoSolarRate: the rate now. */
var DRV=0;
window._altoSolarDrive=function(t, r){
  if(t==null){ if(DRV){ DRV=0; r=Math.max(0, Math.min(1, +r||0)); sp=r>0 ? .5-Math.sin(Math.asin(1-2*r)/3) : 0; last=null; go(); } return T; }
  if(!DRV){ DRV=1; cancelAnimationFrame(raf); raf=0; clearTimeout(slT); }
  T=t; back=rk=1; apply(); skin(); return T;
};
window._altoSolarRate=function(){ return {T:T, r:(DRV || !MOVES || hold() || de.classList.contains('alto-editing') || printing) ? 0 : sp*sp*(3-2*sp)}; };
window.addEventListener('beforeprint', function(){ printing=1; ovLeave(null, true); if(T){ T=0; rk=1; apply(); } });
window.addEventListener('afterprint', function(){ printing=0; go(); });
document.addEventListener('visibilitychange', function(){ last=null; go(); });
/* a hover is the pointer moving onto a circle or a line, not one sliding under a still pointer */
function hot(t){ return t && t.closest && t.closest('#world .node[data-solar],#river-svg [data-edge-hit]'); }
function over(e){ if(!hot(e.target) || (window._altoPointerStill && window._altoPointerStill(e))) return; clearTimeout(hovT); hov=1; }
document.addEventListener('mouseover', over); document.addEventListener('mousemove', over, {passive:true});
document.addEventListener('mouseout', function(e){ if(hot(e.relatedTarget)) return; clearTimeout(hovT); hovT=setTimeout(function(){ hov=0; }, 320); });

/* ── an enlarged body's own, beside it (Luke, round 8: "the direct children of that should come up as
   side things on either side of it") ─────────────────────────────────────────
   The bodies orbiting the enlarged one (a sun's planets, a planet's moons, a moon's satellites) leave
   their orbits for slots left and right of the disc — alternately, in columns from the disc outward,
   clear of the disc, of the window's edges (EDGE) and of the bars — each with its label and a short
   spoke to the disc, as they look at rest. They glide there on the focus's own clock and curve (the
   engine's --alto-fly and _altoEase), and home again when the disc lets go; the orbits wait for them.
   A click or an arrow to one of them enlarges it where it is (its own come up round it, the others go
   home); a flight (solar_fly.py) starts with the disc let go, so they go home and it flies as ever.
   b.fs: {m:'to', ox, oy (from), sx, sy (the slot)} or {m:'home', ox, oy (from), hx, hy (the orbit
   point it left)}, t0, dur — placed by fpos() after the orbit (place()). */
var FLN=0, FLR=0, FLID=null, fsvg=null, EDGE=115;
function fe(fs){ var p=fs.dur>0 ? Math.min(1, (performance.now()-fs.t0)/fs.dur) : 1; return {p:p, e:ease(p)}; }
function fpos(b){
  var fs=b.fs, k=fe(fs);
  if(fs.m==='to'){ b.x=fs.ox+(fs.sx-fs.ox)*k.e; b.y=fs.oy+(fs.sy-fs.oy)*k.e; return; }
  if(fs.hx==null){ fs.hx=b.x; fs.hy=b.y; }
  b.x+=(fs.ox-fs.hx)*(1-k.e); b.y+=(fs.oy-fs.hy)*(1-k.e);
  if(k.p>=1) b.fs=null;
}
/* the slots round the enlarged body fid, world px (its disc is in the middle of the canvas once the
   focus fly lands): {id: [x, y]} */
function slots(fid){
  var F=B[fid], kids=ORD.filter(function(i){ return B[i].p===fid && B[i].n; }), out={}, c=cvs(); if(!kids.length || !c) return out;
  var R=sDof(F.n, F)*K/2, G=34, cw=c.clientWidth, ch=c.clientHeight, TOP=72, BOT=72, GAP=14, LH=18, LW=150, E=EDGE;
  var dm=Math.max.apply(null, kids.map(function(i){ return B[i].d; })), side=[[], []];
  kids.forEach(function(id, k){ side[k%2].push(id); });
  var n=side[0].length, cellH=dm+LH+GAP, rows, cols, cellW, avW;
  for(var t=0;t<4;t++){                                     /* roomier labels, then a narrower edge, before running off the window */
    cellW=Math.max(dm, LW)+GAP; avW=cw/2-R-G-E;
    rows=Math.max(1, Math.floor((ch-TOP-BOT+GAP)/cellH)); cols=Math.ceil(n/rows);
    if(cols*cellW-GAP<=avW) break;
    if(t===0) LW=110; else if(t===1) E=60; else { cols=Math.max(1, Math.floor((avW+GAP)/cellW)); rows=Math.ceil(n/cols); }
  }
  rows=Math.ceil(n/Math.max(1, Math.ceil(n/rows)));
  side.forEach(function(ids, sd){ var sg=sd ? 1 : -1;
    ids.forEach(function(id, i){ var j=Math.floor(i/rows), r=i%rows, m=Math.min(rows, ids.length-j*rows);
      out[id]=[F.x+sg*(R+G+Math.max(dm, LW)/2+j*cellW), F.y+(r-(m-1)/2)*cellH-LH/2]; }); });
  return out;
}
/* the focus changed (or edit mode / the whole chart came): who stands beside the disc now */
function flankSync(){
  if(!ready || !world) return;
  var fid=window._focusedNodeId, F=fid && B[fid], now=performance.now(), cv=cvs();
  var ms=reduced ? 0 : (parseFloat(cv && cv.style.getPropertyValue('--alto-fly'))||420);
  if(!(F && F.n && F.n.classList.contains('focused') && desk() && !de.classList.contains('alto-editing') && !OV)) fid=F=null;
  if(F && F.fs) F.fs={m:'to', ox:F.x, oy:F.y, sx:F.x, sy:F.y, t0:now, dur:0};   /* one that stood beside the last disc is enlarged where it stands */
  var want=fid ? slots(fid) : {};
  ORD.forEach(function(id){ var b=B[id]; if(!b.n) return;
    var w=id!==fid && want[id];
    if(w){ if(!b.fs || b.fs.m!=='to' || b.fs.sx!==w[0] || b.fs.sy!==w[1]) b.fs={m:'to', ox:b.x, oy:b.y, sx:w[0], sy:w[1], t0:now, dur:ms}; }
    else if(b.fs && b.fs.m==='to' && id!==fid) b.fs={m:'home', ox:b.x, oy:b.y, t0:now, dur:ms};
    b.n.classList.toggle('sol-flank', !!w);
  });
  FLID=fid; flTick.t0=now; flRun(); if(NH) hints();
}
function flRun(){ if(!FLR) FLR=requestAnimationFrame(flTick); }
function flTick(){
  FLR=0; if(!ready) return;
  var live=0;
  ORD.forEach(function(id){ var b=B[id]; if(b.fs && fe(b.fs).p<1) live++; });
  if(!DRV){ apply(); skin(); }                              /* (a flight's frames place everything themselves) */
  FLN=0; ORD.forEach(function(id){ if(B[id].fs) FLN++; });
  fspokes(); declutter(true); nhQ();
  var F=FLID && B[FLID], z=F && F.c ? parseFloat(F.c.style.zoom)||1 : K;
  if(live || (F && Math.abs(z-K)>1e-3 && performance.now()-flTick.t0<1500) || document.querySelector('#world .node.sol-closing')) flRun();
  else if(!FLN) go();
}
/* a short spoke from the disc's edge (its size now) to each body beside it */
function fspokes(){
  if(!fsvg || !fsvg.isConnected){ fsvg=el('svg', {id:'sol-flank-svg', width:1, height:1, 'aria-hidden':'true'}); world.appendChild(fsvg); fsvg._l={}; }
  var keep={};
  ORD.forEach(function(id){
    var b=B[id], P=b.fs && B[b.p]; if(!P || !P.n || !(P.n.classList.contains('focused') || P.n.classList.contains('sol-closing'))) return;
    var k=fe(b.fs), o=b.fs.m==='to' ? k.e : 1-k.e, cz=P.c ? parseFloat(P.c.style.zoom)||1 : 1;
    var r=(parseFloat(P.n.style.getPropertyValue('--scd'))||(P.n.classList.contains('focused') ? sDof(P.n, P) : P.d))*cz/2+5;
    var cx=P.rx+(P.n._fx||0), cy=P.ry+(P.n._fy||0), dx=b.rx-cx, dy=b.ry-cy, L=Math.hypot(dx, dy), rb=b.d/2+4;
    var e=fsvg._l[id]; if(!e){ e=fsvg._l[id]=el('line', {}, fsvg); }
    keep[id]=1;
    if(L<=r+rb+2 || o<=.01){ e.setAttribute('opacity', 0); return; }
    e.setAttribute('x1', f2(cx+dx/L*r)); e.setAttribute('y1', f2(cy+dy/L*r)); e.setAttribute('x2', f2(b.rx-dx/L*rb)); e.setAttribute('y2', f2(b.ry-dy/L*rb));
    e.setAttribute('opacity', f2(o));
  });
  for(var id in fsvg._l) if(!keep[id]){ fsvg._l[id].remove(); delete fsvg._l[id]; }
}
/* ── who shows a label (round 8): suns over planets over moons over satellites; a label that would
   cover a label shown already, or a body as big as its own or bigger, tries above, right, left, else
   waits (hover shows it). Sizes are measured once per mode (natural size, zoomed out); the rest is
   arithmetic in world px, at most ~14 times a second while things move. ── */
var DCT=0, RK={sun:0, planet:1, moon:2, sat:3};
function ov2(a, b){ return a[0]<b[2] && b[0]<a[2] && a[1]<b[3] && b[1]<a[3]; }
function setP(lb, p, hide){ if(lb._p!==p){ lb.classList.remove('sol-l1', 'sol-l2', 'sol-l3'); if(p) lb.classList.add('sol-l'+p); lb._p=p; }
  if(lb._x!==hide){ lb.classList.toggle('sol-lx', hide); lb._x=hide; } }
function declutter(force){
  if(!ready || !world || !desk()) return;
  var now=performance.now(); if(!force && now-DCT<70) return; DCT=now;
  var cv=cvs(), ov=!!OV, s=ov ? OV.s : 1, k=1/s, cl=function(c){ return !!cv && cv.classList.contains(c); }, lo=cl('sol-lo'), lm=cl('sol-lm'), fm=cl('focus-mode'), mk=cl('sol-ov') ? 'w1' : 'w0';
  var todo=ORD.filter(function(id){ var b=B[id]; return b.n && b.lb && b.lb.isConnected; });
  function shown(b){ return !((b.role==='sun' && !lo) || (b.role==='sat' && lo) || (b.role==='moon' && lm)); }
  todo.forEach(function(id){ var b=B[id]; if((!b[mk] || !b[mk][0]) && shown(b)) b[mk]=[b.lb.offsetWidth, b.lb.offsetHeight]; });
  var placed=[], discs=[], cls=ov ? (1+.15*(1-s))/s : 1;
  todo.forEach(function(id){ var b=B[id], r=Math.max(b.d/2, 2.5*k); discs.push([b.rx-r, b.ry-r, b.rx+r, b.ry+r, RK[b.role], id]); });
  function chipsGo(){ chips.forEach(function(ch){ if(!ov){ if(ch._x) setP(ch, 0, false); return; }
    if(!ch._wh) ch._wh=[ch.offsetWidth, ch.offsetHeight];
    var w=ch._wh[0]*cls, h=ch._wh[1]*cls, x=parseFloat(ch.style.left)+ch._wh[0]/2, y=parseFloat(ch.style.top)+ch._wh[1], q=[x-w/2, y-h, x+w/2, y];
    setP(ch, 0, false); placed.push(q); }); }       /* a unit's name always shows, first: the bodies' labels give way to it (round 10: it flickered as labels turned under it) */
  function clash(q, b){ var i, rk=RK[b.role]; for(i=0;i<placed.length;i++) if(ov2(q, placed[i])) return true;
    for(i=0;i<discs.length;i++){ var d=discs[i]; if(d[5]!==b.id && d[4]<=rk && ov2(q, d)) return true; } return false; }
  var cg=1; chipsGo();
  todo.sort(function(a, b){ return RK[B[a].role]-RK[B[b].role]; }).forEach(function(id){
    var b=B[id], wh=b[mk];
    if(!cg && b.role!=='sun'){ cg=1; chipsGo(); }          /* the systems' names after the suns', before the rest */
    if(fm){ if(b.n.classList.contains('sol-flank')) setP(b.lb, 0, false); return; }
    if(!shown(b) || !wh || !wh[0]) return;      /* (not shown at this zoom) */
    var w=wh[0]*k, h=wh[1]*k, rr=Math.max(b.d*s/2, 2.5)*k, g=3*k, gx=4*k, x=b.rx, y=b.ry, pick=-1;
    var C=[[x-w/2, y+rr+g], [x-w/2, y-rr-g-h], [x+rr+gx, y-h/2], [x-rr-gx-w, y-h/2]];
    for(var i=0;i<4 && pick<0;i++) if(!clash([C[i][0], C[i][1], C[i][0]+w, C[i][1]+h], b)) pick=i;
    if(pick>=0) placed.push([C[pick][0], C[pick][1], C[pick][0]+w, C[pick][1]+h]);
    setP(b.lb, pick<0 ? (b.lb._p||0) : pick, pick<0);
  });
  if(!cg) chipsGo();
}
/* the whole chart's scale, for what keeps its size on screen (labels, dots, the systems' chips) and
   what it shows at that size (level of detail: .sol-lo faces and satellites' labels go, the suns' labels
   come; .sol-lm moons' labels go; .sol-tiny (< .12) flat dots in place of the bodies' pictures) */
function ovVars(sc){
  var c=cvs(); if(!world || !c) return;
  if(sc==null || sc>=.9999){ ['--ovs', '--ils', '--cls', '--lk', '--lw'].forEach(function(v){ world.style.removeProperty(v); }); c.classList.remove('sol-lo', 'sol-lm', 'sol-tiny'); }
  else { world.style.setProperty('--ovs', f2(sc*1e4)/1e4); world.style.setProperty('--ils', f2(1e4/sc)/1e4); world.style.setProperty('--cls', f2((1+.15*(1-sc))/sc*1e4)/1e4);
    world.style.setProperty('--lk', f2(Math.min(1.7, 1+.9*(1-sc))*100)/100); world.style.setProperty('--lw', f2(Math.min(1.4, 1+.5*(1-sc))*100)/100);   /* lines: a little stronger the further out (round 10) */
    c.classList.toggle('sol-lo', sc<.5); c.classList.toggle('sol-lm', sc<.3); c.classList.toggle('sol-tiny', sc<.12); }
  declutter(true);
}

/* ── an enlarged circle stays a circle (Luke, rounds 4 and 7): no clip-path. Under Safari's page zoom a
   clip-path circle() on a zoomed card was resolved in another box than the one painted (Luke's Torts
   copy, Safari 27, html zoom 0.86: a smaller circle up-left of the card, the text running out of its
   bottom, the card's own edge showing as an arc and its shadow a bigger circle down-right). So the
   card is a REAL disc at every frame: border-radius 50% and overflow hidden on a box whose diameter
   (--scd) goes from the resting disc's to the enlarged one's (--sD) with the engine's zoom ramp, read
   off the card's own zoom on every frame. The content sits at fixed px about the centre (sized by
   --sD), so it never re-wraps and the growing disc reveals it; the engine's .alto-fshadow is kept the
   same circle (its scale set from the card's real diameter). The face fades out, the content
   (.sol-body, .sol-scrim, the chips) fades in. ───── */
var zmo=(typeof MutationObserver==='function') ? new MutationObserver(function(ms){ ms.forEach(function(m){ var n=m.target.closest && m.target.closest('.node'); if(n) clip(n); }); }) : null, morphing=[], mraf=0;
function sDof(n, b){ return parseFloat(n.style.getPropertyValue('--sD'))||b.d; }
/* the focus shadow: the card's circle, whatever size the engine measured it at */
function shade(n, w, z){
  var sh=n._fsh, g=sh && sh._g, W=sh ? parseFloat(sh.style.width)||0 : 0; if(!W || !g) return;
  var want=w*z;                                                 /* the disc's diameter in the board's px */
  if(Math.abs(z-K)<1e-4 && Math.abs(want-W)<0.5) return;        /* full size: the engine's own placement is this circle */
  sh.style.left=g[0]+'px'; sh.style.top=g[1]+'px';
  sh.style.transform='translate('+(n._fx||0)+'px,'+(n._fy||0)+'px) scale('+f2(want/W*1e4)/1e4+')';
}
function clip(n){
  var c=n.querySelector('.node-card'), b=B[(n.id||'').slice(5)]; if(!c || !b) return;
  var z=parseFloat(c.style.zoom)||1, f=n.classList.contains('focused'), i=morphing.indexOf(c);
  if(i<0 && !f) return;
  if(!f && z<=1.0005){                                         /* home: a circle again */
    n.classList.remove('sol-closing'); n.classList.remove('sol-clip');
    ['--scd','--sfo','--sbo'].forEach(function(v){ n.style.removeProperty(v); });
    if(i>=0) morphing.splice(i, 1);
    if(!morphing.length) go();
    return; }
  var p=Math.max(0, Math.min(1, (z-1)/(K-1)*1.5)), s=p*p*(3-2*p), d=b.d, D=sDof(n, b);
  if(f && s>=1){ n.classList.remove('sol-clip'); ['--scd','--sfo','--sbo'].forEach(function(v){ n.style.removeProperty(v); });
    if(i>=0) morphing.splice(i, 1); shade(n, D, z); return; }
  n.classList.add('sol-clip');
  var w=f2(d+(D-d)*s);                                          /* the disc's own diameter, from the resting one to the enlarged one */
  n.style.setProperty('--scd', w+'px');
  n.style.setProperty('--sfo', String(Math.max(0, 1-s*2.2))); n.style.setProperty('--sbo', String(Math.min(1, s*1.6)));
  shade(n, w, z);
}
/* a backstop to the observer: every morphing disc is looked at once a frame until it has settled */
function msweep(){ mraf=0; morphing.slice().forEach(function(c){ var n=c.closest && c.closest('.node'); if(n) clip(n); }); if(morphing.length) mraf=requestAnimationFrame(msweep); }
function morph(n, open){
  var c=n.querySelector('.node-card'); if(!c) return;
  if(!open) n.classList.add('sol-closing');
  if(morphing.indexOf(c)<0) morphing.push(c);
  if(zmo && !c._zmo){ c._zmo=1; zmo.observe(c, {attributes:true, attributeFilter:['style']}); }
  clip(n);
  if(!mraf && morphing.length) mraf=requestAnimationFrame(msweep);
}
function watch(){
  var w=document.getElementById('world'); if(!w || typeof MutationObserver!=='function') return;
  var cv=document.getElementById('canvas'); if(cv) cv.addEventListener('scroll', camTell, {passive:true});
  new MutationObserver(camTell).observe(w, {attributes:true, attributeFilter:['style']});   /* the board's pan (focus fly) and transform */
  new MutationObserver(function(ms){ var fl=0; ms.forEach(function(m){
    var n=m.target; if(!n.classList || !n.classList.contains('node') || !n.hasAttribute('data-solar') || !desk()) return;
    var f=n.classList.contains('focused'); if(f===!!n._solF) return; n._solF=f; if(f && OV) ovLeave(null, true); morph(n, f); fl=1;
    if(f){ pool(n); requestAnimationFrame(function(){ if(n.classList.contains('focused')) pool(n); }); }
    var cd=n.querySelector('.node-card');
    if(cd){ if(f){ cd._t0=cd.getAttribute('title'); cd._a0=cd.getAttribute('aria-label'); cd.setAttribute('title', 'Open the full page'); cd.setAttribute('aria-label', 'Open the full page'); }
      else if('_t0' in cd){ [['title', cd._t0], ['aria-label', cd._a0]].forEach(function(p){ if(p[1]==null) cd.removeAttribute(p[0]); else cd.setAttribute(p[0], p[1]); }); delete cd._t0; } }
  }); if(fl) flankSync(); }).observe(w, {attributes:true, subtree:true, attributeFilter:['class']});
  /* edit mode wants the board at full size and still */
  new MutationObserver(function(){ if(de.classList.contains('alto-editing')){ if(OV) ovLeave(null, true); if(FLID) flankSync(); go(); } }).observe(de, {attributes:true, attributeFilter:['class']});
}
/* a click on a body beside the disc enlarges it (the engine would read it as a click away from the disc) */
document.addEventListener('click', function(e){
  var n=e.target && e.target.closest && e.target.closest('#world .node.sol-flank'); if(!n || de.classList.contains('alto-editing') || !desk()) return;
  e.stopPropagation(); e.preventDefault(); if(window.enterFocus) window.enterFocus(n.id.slice(5));
}, true);
if(document.readyState!=='loading') watch(); else document.addEventListener('DOMContentLoaded', watch);

/* ── the detail page and back (Luke, round 9): the same enlarged body (or none) and the same
   camera, no flight. The engine keeps the focus while a solar page's detail page shows (engine
   patch solar-detail-keeps-focus); the view is noted as the page opens and put back as it closes ── */
var DV=null;
window._altoKeepFocusOnDetail=function(){ return ready && desk(); };
function dvSnap(){ var c=cvs(); if(!ready || !desk() || !c || DV || c.style.display==='none') return;
  DV={f:window._focusedNodeId||null, ov:OV ? {s:OV.s, tx:OV.tx, ty:OV.ty} : null, l:c.scrollLeft, t:c.scrollTop}; }
function dvBack(){ var v=DV, c=cvs(); DV=null; if(!v || !c || !ready) return;
  if(v.ov){ OV={s:v.ov.s, tx:v.ov.tx, ty:v.ov.ty}; ovHold(true); c.classList.add('sol-ov'); ovSet(OV); c.scrollLeft=0; c.scrollTop=0; }
  else { if(OV) ovLeave(null, true); c.scrollLeft=v.l; c.scrollTop=v.t; }
  var f=window._focusedNodeId||null;
  if(f!==v.f){ if(f && window.exitFocus) window.exitFocus(); if(v.f && window.enterFocus) window.enterFocus(v.f); } }
(function(){ var sd=window.showDetail; if(typeof sd==='function' && !sd._sol){ var w=function(){ dvSnap(); return sd.apply(this, arguments); }; w._sol=1; window.showDetail=w; }
  var dp=document.getElementById('detail-page'), was=false;
  if(dp && typeof MutationObserver==='function') new MutationObserver(function(){ var v=dp.classList.contains('visible'); if(v===was) return; was=v;
    if(!v) requestAnimationFrame(dvBack); }).observe(dp, {attributes:true, attributeFilter:['class']}); })();
/* ── a settle watchdog (Luke, round 9: a board left dimmed with nothing enlarged, the look's skin
   showing in the other look): with no flight, no detail page and no glide running, a focus the
   board has lost is let go, a stray .focused / flank cleared, and html.alto-stars matches the look ── */
function heal(){
  if(!ready || !desk() || DV) return;
  var c=cvs(), dp=document.getElementById('detail-page'); if(!c || (dp && dp.classList.contains('visible'))) return;
  if(LOOK!=='stars' && de.classList.contains('alto-stars')){ de.classList.remove('alto-stars'); tell(lookFns, LOOK); }
  if(window._altoSolarFlight && window._altoSolarFlight()) return;
  var f=window._focusedNodeId, n=f && document.getElementById('node-'+f);
  if(f && (!n || !n.classList.contains('focused'))){ window._focusedNodeId=null; f=null; }
  if(!f){ if(c.classList.contains('focus-mode')) c.classList.remove('focus-mode');
    [].forEach.call(document.querySelectorAll('#world .node.focused,#world .node.sol-flank'), function(x){ x.classList.remove('focused'); if(x.classList.contains('sol-flank')) flankSync(); }); }
}
setInterval(heal, 700);
/* ── arrows and the enlarged disc's wheel: strictly by outline level (Luke, round 9). Up: what it
   orbits (a sun: stays). Down: the child it was come up from, else its first (none: stays).
   Left / right: the previous / next body of the same level in outline order (ORD: system by
   system, depth first), on into the next system's at the ends. A diagonal is its up / down.
   Returns id itself to stay (the engine then does nothing), null off the chart (a phone). ──── */
var UPFROM={};
function navTo(id, dir){
  var a=B[id]; if(!a || !a.n || !desk()) return null;
  var d=String(dir||'').charAt(0), j, nx=null;
  if(LOCK) return ways(id).k[d] || id;            /* Spokes only: the spoke that way (the Spokes only block below) */
  if(d==='n'){ if(a.p && B[a.p]){ UPFROM[a.p]=id; nx=a.p; } }
  else if(d==='s'){ var u=UPFROM[id]; if(u && B[u] && B[u].p===id && B[u].n) nx=u;
    else for(j=0;j<ORD.length;j++){ if(B[ORD[j]].p===id && B[ORD[j]].n){ nx=ORD[j]; break; } } }
  else if(d==='e' || d==='w'){ var i=ORD.indexOf(id), st=d==='e' ? 1 : -1;
    for(j=i+st;j>=0 && j<ORD.length;j+=st){ var b=B[ORD[j]]; if(b.role===a.role && b.n){ nx=ORD[j]; break; } } }
  return nx || id;
}
/* Spokes only: never a jump — a ride along the spoke that way (none that way: a gentle word); the engine stays put */
window._altoSolarNav=function(id, dir){
  if(LOCK && ready && desk() && B[id]){ var to=navTo(id, dir); if(to && to!==id) ride(id, to); else nope(); return id; }
  return navTo(id, dir); };
var levelNav=navTo;     /* (unwrapped: solar_fly.py wraps the global to fly the hop) */
window._altoSolarLevelNav=levelNav;   /* (solar_3d.py's hints, without a flight) */
/* ── navigation hints (round 11; Luke on round 10's glow and badges: "just not adequate"). With a body
   enlarged, each place an arrow key goes (with Spokes only: a scroll that way) says so where it is: a pill
   beside that body — the key, the move, the body's name (its own label steps aside). The way there is
   drawn under the bodies: up / down along their spoke, solid; the same level, a dotted arc bowed out
   along the orbits. A place off the window gets the same pill at the window's edge, on the line towards
   it, with a pointer (a click goes there). Up a level: a filled key; down: a ringed key; same level: a
   plain key. Built once per focus (none in a flight: back on landing, faded in); after that only the
   arcs and edge pills move — on the canvas's scroll and the flank's glide, a frame at most — all in
   world px. Spokes only: a pill on every body one spoke away and on nothing else — the way (arrow, or a scroll
   that way) that rides there, else a click — each way drawn straight along its spoke; with nothing enlarged,
   one pill where you are. ── */
var NH={k:undefined, t:[], L:null, g:null, f:null, q:0}, NHD={n:['↑', 'Up a level', 'Ride'], s:['↓', 'Down a level', 'Ride'],
  w:['←', 'Previous', 'Ride'], e:['→', 'Next', 'Ride'], c:['•', 'Click to ride', 'Click to ride'], o:['⇕', 'Scroll to enlarge', 'Scroll to enlarge']};
function nhPill(id, d, wd){ var p=document.createElement('span'), D=NHD[d], b=B[id]; p.className='sol-nh'; p.setAttribute('data-k', d); p.setAttribute('aria-hidden', 'true');
  p.innerHTML='<em>➜</em><kbd></kbd><i></i><b></b>'; p.children[1].textContent=D[0]; p.children[2].setAttribute('data-a', wd||D[1]); p.children[2].setAttribute('data-b', D[2]);
  p.children[3].textContent=(b.lb && b.lb.getAttribute('data-l'))||''; return p; }
function nhOn(id, d, side, wd){ var n=B[id].n, p=nhPill(id, d, wd);
  p.setAttribute('data-p', side); n.classList.add('sol-hint'); n.appendChild(p); return p; }
function hints(){
  var dp=document.getElementById('detail-page'), ok=ready && desk() && world && !RD && !(window._altoSolarFlight && window._altoSolarFlight()) && !(dp && dp.classList.contains('visible')) && !de.classList.contains('alto-editing');
  var f=ok && window._focusedNodeId, o=null; if(f && !(B[f] && B[f].n && B[f].n.classList.contains('focused'))) f=null;
  if(f) LASTF=f; else if(ok && LOCK) o=home();
  var k=(LOCK ? 'L' : '')+(f ? 'f'+f : o ? 'o'+o : ''); if(k===NH.k) return; NH.k=k;
  NH.t.forEach(function(t){ t.n.classList.remove('sol-hint'); t.p.remove(); if(t.q) t.q.remove(); if(t.w) t.w.remove(); }); NH.t=[]; NH.f=f || null;
  if(o){ NH.t.push({id:o, n:B[o].n, p:nhOn(o, 'o', 'b')}); return; }
  if(!f) return;
  if(!NH.L || !NH.L.isConnected){ NH.L=document.createElement('div'); NH.L.id='sol-nav'; world.appendChild(NH.L); }
  if(!NH.g || !NH.g.isConnected){ NH.g=el('svg', {id:'sol-way', width:1, height:1, 'aria-hidden':'true'}); world.insertBefore(NH.g, svg && svg.parentNode===world ? svg.nextSibling : world.firstChild); }
  var F=B[f], Wy=LOCK ? ways(f) : null;
  (Wy ? Wy.nb.map(function(to){ return [Wy.d[to]||'c', to]; }) : ['n', 's', 'w', 'e'].map(function(d){ return [d, levelNav(f, d)]; })).forEach(function(dt){ var d=dt[0], to=dt[1], b=B[to]; if(!to || to===f || !b || !b.n || NH.t.some(function(t){ return t.id===to; })) return;
    var wd=!Wy && (d==='e' || d==='w') && b.si!==F.si && (d==='e' ? 'Next system' : 'Previous system'), q=nhPill(to, d, wd); q.setAttribute('data-id', to); q.style.cssText=(b.n.style.cssText.match(/--u:[^;]*/)||[''])[0]; NH.L.appendChild(q);
    NH.t.push({id:to, d:d, n:b.n, p:nhOn(to, d, 'b', wd), q:q, w:el('path', {'data-k':d}, NH.g)}); });
  nhPlace();
}
function nhQ(){ if(NH && NH.f && !NH.q) NH.q=requestAnimationFrame(nhPlace); }
function nhPlace(){
  NH.q=0; var F=NH.f && B[NH.f], c=cvs(); if(!F || !F.n || !c || !world) return;
  var tr=String(getComputedStyle(world).translate||'').split(' ').map(parseFloat), wo=woff(c), sx=c.scrollLeft-wo.x-(tr[0]||0), sy=c.scrollTop-wo.y-(tr[1]||0), cw=c.clientWidth, ch=c.clientHeight;
  var x0=sx+44, x1=sx+cw-44, y0=sy+120, y1=sy+ch-96;            /* the window in world px, inside its bars: a place here shows its own pill */
  var cz=F.c ? parseFloat(F.c.style.zoom)||1 : 1, rf=(parseFloat(F.n.style.getPropertyValue('--scd'))||sDof(F.n, F))*cz/2+6, cx=F.rx+(F.n._fx||0), cy=F.ry+(F.n._fy||0), done=[];
  function clear(q){ var X=Math.max(q[0], Math.min(q[2], cx)), Y=Math.max(q[1], Math.min(q[3], cy));   /* a box inside the window, off the disc and off the pills placed */
    return q[0]>=x0-30 && q[2]<=x1+30 && q[1]>=y0-24 && q[3]<=y1+30 && Math.hypot(X-cx, Y-cy)>rf && !done.some(function(o){ return ov2(o, q); }); }
  NH.t.forEach(function(t){ var b=B[t.id], dx=b.rx-cx, dy=b.ry-cy, L=Math.hypot(dx, dy)||1, ux=dx/L, uy=dy/L, rb=b.d/2+6, mx=(cx+b.rx)/2, my=(cy+b.ry)/2, qx=mx, qy=my;
    if(!LOCK && (t.d==='e' || t.d==='w')){ var P=b.p===F.p && B[F.p], ax=P ? mx-P.rx : dy, ay=P ? my-P.ry : -dx, al=Math.hypot(ax, ay)||1; qx+=ax/al*L*.2; qy+=ay/al*L*.2; }   /* bowed away from what both orbit */
    var u=function(x, y, X, Y, r){ var l=Math.hypot(X-x, Y-y)||1; return [f2(x+(X-x)/l*r), f2(y+(Y-y)/l*r)]; }, s=u(cx, cy, qx, qy, rf), e=u(b.rx, b.ry, qx, qy, rb);
    t.w.setAttribute('d', L>rf+rb+4 ? 'M'+s+'Q'+f2(qx)+' '+f2(qy)+' '+e : 'M0 0');
    var w=t.pw||(t.pw=t.p.offsetWidth||180), h=24, r=b.d/2, bx={b:[b.rx-w/2, b.ry+r+6, b.rx+w/2, b.ry+r+6+h], a:[b.rx-w/2, b.ry-r-6-h, b.rx+w/2, b.ry-r-6],
      r:[b.rx+r+8, b.ry-h/2, b.rx+r+8+w, b.ry+h/2], l:[b.rx-r-8-w, b.ry-h/2, b.rx-r-8, b.ry+h/2]};
    var sd=(b.fs && b.fs.m==='to') ? ['b'] : (Math.abs(dx)>Math.abs(dy) ? [dx>0 ? 'r' : 'l'] : [dy>0 ? 'b' : 'a']).concat(['b', 'a', 'r', 'l']), k=sd.filter(function(x){ return clear(bx[x]); })[0];
    var on=!!k && b.rx>=x0 && b.rx<=x1 && b.ry>=y0 && b.ry<=y1 && L>rf;
    t.p.classList.toggle('sol-nhx', !on); t.q.hidden=on;
    if(on){ t.p.setAttribute('data-p', k); done.push(bx[k]); return; }   /* its pill on the side away from the disc, else the first side clear (beside the disc: under it, where its label was) */
    /* else (off the window, or under the disc): the pill on the line from the disc to it — at the window's edge, or at the disc's rim */
    var X, Y;
    if(L>rf){ var ex0=sx+14, ex1=sx+cw-14, ey0=sy+100, ey1=sy+ch-72, px=Math.max(ex0, Math.min(ex1, cx)), py=Math.max(ey0, Math.min(ey1, cy)),
      kx=dx ? ((dx>0 ? ex1 : ex0)-px)/dx : 1e9, ky=dy ? ((dy>0 ? ey1 : ey0)-py)/dy : 1e9, kk=Math.max(0, Math.min(kx, ky, 1)); X=px+dx*kk; Y=py+dy*kk; ux=-ux; uy=-uy; }
    else { X=cx+ux*rf; Y=cy+uy*rf; }
    var cl=function(v){ return Math.max(-1, Math.min(1, v*2)); }, ox=50*cl(ux)-50, oy=50*cl(uy)-50, q=[X+ox/100*w, Y+oy/100*h, X+(ox/100+1)*w, Y+(oy/100+1)*h];
    for(var j=0; j<4 && done.some(function(o){ return ov2(o, q); }); j++){ var dv=(uy<0 ? -1 : 1)*(h+6); Y+=dv; q[1]+=dv; q[3]+=dv; }   /* (two on one edge: stacked) */
    done.push(q);
    t.q.style.left=f2(X)+'px'; t.q.style.top=f2(Y)+'px'; t.q.style.setProperty('--o', f2(ox)+'%,'+f2(oy)+'%');   /* (its anchor: a custom property, no transform written) */
    t.q.style.setProperty('--a', Math.round(Math.atan2(dy, dx)*180/Math.PI)+'deg'); });
}
setInterval(hints, 250);
document.addEventListener('scroll', function(e){ if(e.target && e.target.id==='canvas') nhQ(); }, {capture:true, passive:true});
window.addEventListener('resize', nhQ);
['pointerdown', 'mousedown', 'click'].forEach(function(t){ document.addEventListener(t, function(e){   /* an edge pill: a click hops there (before the board takes it for a click on empty space) */
  var p=e.target && e.target.closest && e.target.closest('#sol-nav .sol-nh'); if(!p) return; e.stopPropagation(); e.preventDefault(); if(t==='click'){ if(LOCK) rideTo(p.getAttribute('data-id')); else lockStep(p.getAttribute('data-k')); } }, true); });
/* ── edit mode changed the outline (manual_edit.py calls this before it lays
   the page out again with the live tables {kids, parent, num, seqs, act}): the
   systems are planned again here — SOLAR_PLAN_JS, solar.py's solar_plan in
   JS — and the circles go where the tree's plan runner puts them ──────── */
window._altoSolarSync=function(t){
  t=t||{};
  var P=window._altoSolarPlan(t, S); if(!P) return false;
  usePlan(P);
  NUM=t.num||NUM; bodies(); T=0; back=rk=1;
  treePlan(P, t.seqs||[]);
  return true;
};
/* the page's tree plan (layout float ops) follows the plan, so initLayout puts every circle there */
function treePlan(P, seqs){
  var TP=window._ALTO_TREE_PLAN;
  if(TP){ TP.x={}; TP.w={}; TP.acts=[]; TP.cx=P.world.w/2; TP.shift=null; TP.slide=null;
    seqs.forEach(function(ids, a){ TP.acts[a]=[];
      ids.forEach(function(id){ var n=P.nodes[id]; if(!n) return; TP.x[id]=n.x; TP.w[id]=n.d; TP.acts[a].push(['float', ['card', id, 0], n.y, 'mid']); }); }); }
}
/* the plan now drawn: S, mirrored on window._ALTO_SOLAR (what FLY / VIS read) */
function usePlan(P){
  S=P;
  for(var k0 in R) if(k0!=='look' && !(k0 in P)) delete R[k0];
  for(var k in P) if(k!=='look') R[k]=P[k];
}
/* ── the whole chart: the board zoomed out to fit the window ─────────────────
   Pinch out (ctrl+wheel; Safari's gesture), ⌘− / ctrl+−, or the toggle under the
   bars. As on a horizontal timeline's whole view (lanes_nav.py) the board is
   scaled by a transform about its corner, the canvas held at 0,0 (a spacer
   keeps its scroll extent, so scrollbars never come and go) and moved by its
   own translate: wheel or drag pans, pinch zooms about the pointer, the orbits
   go on. A click (or ⌘+ / ⌘0 / Esc / an arrow) comes back down to full size —
   on the body clicked, which is then enlarged. Only layout px are used: where
   a body is comes from its own left/top, the pointer from the canvas's rect. */
var OV=null, ovA=0, OVMIN=.03;
function cvs(){ return document.getElementById('canvas'); }
function zk(c){ var r=c.getBoundingClientRect(); return (r.width && c.offsetWidth) ? r.width/c.offsetWidth : 1; }
function woff(c){ var ox=0, oy=0, q=world; while(q && q!==c){ ox+=q.offsetLeft; oy+=q.offsetTop; q=q.offsetParent; } return {x:ox, y:oy}; }
/* the board's height: the world, or the glass under it where that runs on (its padding) */
function wh(){ var sl=document.getElementById('glass-slab'); return Math.max(world.offsetHeight, sl ? sl.offsetTop+sl.offsetHeight : 0); }
function fitS(){ var c=cvs(); return Math.max(OVMIN, Math.min(1, (c.clientWidth-60)/world.offsetWidth, (c.clientHeight-60)/wh())); }
/* the zoomed-out board: any scale from OVMIN to natural size; moved freely, only held so that at
   least KEEP px of the chart stay in the window (it can be pushed aside, never lost) */
var KEEP=160;
/* the floor of a gesture's zoom (round 8: "fully zoomed out, it's impossible to see anything"): the whole
   chart filling 85% of the window — all of it in view, never a speck (the camera's own floor, for flights, stays OVMIN) */
function omin(){ var c=cvs(); if(!c || !world) return OVMIN; return Math.max(.005, Math.min(.5, .85*Math.min((c.clientWidth-60)/world.offsetWidth, (c.clientHeight-60)/wh()))); }
function clampO(o){ var c=cvs(), cw=c.clientWidth, ch=c.clientHeight, w, h;
  var lo=Math.min(omin(), OV ? OV.s : 1);         /* (below it already, by a flight's camera: no jump) */
  o.s=Math.max(lo, Math.min(1, o.s));
  w=world.offsetWidth*o.s; h=wh()*o.s;
  o.tx=Math.max(Math.min(KEEP, w)-w, Math.min(cw-Math.min(KEEP, w), o.tx)); o.ty=Math.max(Math.min(KEEP, h)-h, Math.min(ch-Math.min(KEEP, h), o.ty));
  /* nearing the floor, the chart is drawn into the window (all of it, at the floor), continuously */
  var g=Math.max(0, Math.min(1, (1.6*lo-o.s)/(.6*lo)));
  if(g>0){ var ix=w<=cw ? Math.max(0, Math.min(cw-w, o.tx)) : Math.max(cw-w, Math.min(0, o.tx)), iy=h<=ch ? Math.max(0, Math.min(ch-h, o.ty)) : Math.max(ch-h, Math.min(0, o.ty));
    o.tx+=(ix-o.tx)*g; o.ty+=(iy-o.ty)*g; }
  return o; }
function ovSet(o){ var off=woff(cvs()); world.style.transform='translate('+rd(o.tx-off.x)+'px,'+rd(o.ty-off.y)+'px) scale('+o.s+')'; ovVars(o.s); ulay(); camTell(); reRaster(o.s); }
/* ── the systems' names, zoomed out (Luke, 2026-10-21: the units' labels "look glitchy" in Safari). On the scaled
   board they were text inside a layer drawn at one scale and shown at another (and moved by fractions of a pixel as
   their suns turned), so thin lettering lost strokes. Zoomed out they leave the board for a layer of their own over
   it (#sol-ulay, unscaled), each placed on whole device pixels at its point of the board, at the size on screen it
   had (the board's scale times --cls); back on the board at full size. Their left / top stay the board's. ── */
var UL=null, ulq=0;
function ulay(){
  var c=cvs(); if(!c || !world) return;
  if(!OV){ if(UL) chips.forEach(function(ch){ if(ch.parentNode===UL){ ch.style.transform=''; world.appendChild(ch); } }); return; }
  if(!UL || !UL.isConnected){ UL=document.createElement('div'); UL.id='sol-ulay'; UL.setAttribute('aria-hidden', 'true'); c.appendChild(UL); }
  var z=(parseFloat(getComputedStyle(de).zoom)||1)*(window.devicePixelRatio||1), k=Math.round((1+.15*(1-OV.s))*1e4)/1e4, q=function(v){ return Math.round(v*z)/z; };
  chips.forEach(function(ch){ if(!ch.isConnected) return; if(!ch._wh) ch._wh=[ch.offsetWidth, ch.offsetHeight];
    if(ch.parentNode!==UL) UL.appendChild(ch);
    var x=OV.tx+(parseFloat(ch.style.left)+ch._wh[0]/2)*OV.s, y=OV.ty+(parseFloat(ch.style.top)+ch._wh[1])*OV.s;
    ch.style.transform='translate('+q(x)+'px,'+q(y)+'px) translate(-50%,-100%) scale('+k+')'; });
}
/* (round 10, the Chrome flash) a will-change layer is never re-rastered as its scale changes: zoomed out from fit,
   Chrome kept the whole world (since round 9's galaxy ~20,000 px square) at full scale, ran out of tiles and showed
   frames with bodies, sky and bars missing. Once a zoom settles at a scale far from the last raster's, the layer is
   let go for two frames and taken again, so it is drawn afresh at the scale on screen. Any settled change of scale,
   not only a far one (Luke, 2026-10-21: the units' names "look glitchy" in Safari): a layer drawn at one scale and
   shown at another resamples its text, and Retro's thin, widely spaced capitals lost strokes to it. */
var RS={t:0, s:1};
function reRaster(s){ clearTimeout(RS.t); if(!world) return;
  RS.t=setTimeout(function(){ RS.t=0; var w=world; if(!w || !OV || Math.abs(Math.log(OV.s/RS.s))<.01) return;
    var s2=OV.s; w.style.willChange='auto';
    requestAnimationFrame(function(){ requestAnimationFrame(function(){ w.style.willChange=''; RS.s=s2; }); }); }, 140); }
function ovHold(on){
  var c=cvs(), sp=document.getElementById('sol-ov-hold');
  if(!on){ if(sp) sp.remove(); return; }
  if(!sp){ sp=document.createElement('div'); sp.id='sol-ov-hold'; sp.setAttribute('aria-hidden', 'true');
    sp.style.cssText='position:absolute;left:0;top:0;width:1px;height:1px;visibility:hidden;pointer-events:none;'; c.appendChild(sp); }
  sp.style.width=c.scrollWidth+'px'; sp.style.height=c.scrollHeight+'px';
}
function ease(p){ return window._altoEase ? window._altoEase(p) : p*p*(3-2*p); }
function ovAnim(from, to, done){
  cancelAnimationFrame(ovA); var c=cvs(); c.classList.add('sol-ovanim');
  if(reduced){ ovSet(to); c.classList.remove('sol-ovanim'); return done(); }
  var t0=performance.now();
  (function fr(now){ var p=Math.min(1, (now-t0)/560), k=ease(p), sc=Math.exp(Math.log(from.s)+(Math.log(to.s)-Math.log(from.s))*k),
      u=Math.abs(to.s-from.s)>1e-6 ? (sc-from.s)/(to.s-from.s) : k;
    ovSet({s:sc, tx:from.tx+(to.tx-from.tx)*u, ty:from.ty+(to.ty-from.ty)*u});
    if(p<1) ovA=requestAnimationFrame(fr); else { ovA=0; c.classList.remove('sol-ovanim'); done(); } })(t0);
}
/* to scale s about (fx, fy) in the canvas's px (default: its middle) */
function ovZoom(s, fx, fy, anim){
  var c=cvs(); if(!c || !ready || !desk()) return;
  if(fx==null){ fx=c.clientWidth/2; fy=c.clientHeight/2; }
  if(!OV){
    if(window._focusedNodeId && window.exitFocus){ window.exitFocus(); setTimeout(function(){ ovZoom(s, null, null, anim); }, UNF); return; }
    var off=woff(c); OV={s:1, tx:off.x-c.scrollLeft, ty:off.y-c.scrollTop};
    ovHold(true); ovSet(OV); c.scrollLeft=0; c.scrollTop=0; c.classList.add('sol-ov'); fitBtn();
  }
  var from={s:OV.s, tx:OV.tx, ty:OV.ty}, to=clampO({s:s, tx:fx-(fx-OV.tx)*s/OV.s, ty:fy-(fy-OV.ty)*s/OV.s});
  if(to.s>=.999 && from.s>=.999) return ovLeave(null, true);
  OV=to;
  if(anim) ovAnim(from, to, function(){}); else ovSet(to);
}
/* back to full size, the world point p (default: what is in the middle) in the middle */
function ovLeave(p, instant, then){
  if(!OV) return; var c=cvs(), o=OV, off=woff(c), cw=c.clientWidth, ch=c.clientHeight;
  if(!p) p={x:(cw/2-o.tx)/o.s, y:(ch/2-o.ty)/o.s};
  OV=null; cancelAnimationFrame(ovA); c.classList.remove('sol-ov'); fitBtn(); clearTimeout(RS.t); RS.s=1; world.style.willChange=''; ulay();
  var sl=Math.max(0, Math.min(c.scrollWidth-cw, p.x+off.x-cw/2)), st=Math.max(0, Math.min(c.scrollHeight-ch, p.y+off.y-ch/2));
  var fin=function(){ world.style.transform=''; ovVars(null); ovHold(false);
    var ax=window._altoScrollAxis; if(ax){ ax('scrollLeft').go(sl); ax('scrollTop').go(st); } else { c.scrollLeft=sl; c.scrollTop=st; }
    if(then) then(); };
  if(instant) return fin();
  ovAnim(o, {s:1, tx:off.x-sl, ty:off.y-st}, fin);
}
function local(e){ var c=cvs(), r=c.getBoundingClientRect(), k=zk(c); return {x:(e.clientX-r.left)/k, y:(e.clientY-r.top)/k}; }
function nearest(wx, wy){ var best=null, bd=Infinity;
  ORD.forEach(function(id){ var b=B[id]; if(!b.n) return; var d=Math.hypot(b.rx-wx, b.ry-wy)-b.d/2; if(d<bd){ bd=d; best=id; } });
  return best; }
function fitBtn(){ var t=document.getElementById('sol-fit'); if(t) t.remove(); }   /* (the whole-chart button is gone: zoom is continuous) */
function mine(e){ var c=cvs(); return c && e.target && c.contains(e.target); }
/* ── pinch / ctrl+wheel: one gesture, one owner ──────────────────────────────
   Luke, 1.9.105: "If I zoom in and try to zoom back out, it basically doesn't
   work." Three faults, all here: (1) a pinch at rest let Safari's own page zoom
   start — gesturestart was stopped before the engine's preventDefault and never
   prevented here; (2) gestureend was swallowed even when this script had done
   nothing, so a pinch IN at rest never enlarged a card in Safari, and from the
   whole chart a pinch in stalled short of full size; (3) one ctrl+wheel stream
   did two things — left the whole chart and then enlarged whatever was under
   the pointer, or (from a card) let it go and dropped straight on.
   Now every gesture event is prevented (no native zoom, ever), and each gesture
   (a pinch, or a ctrl+wheel stream: events < 220 ms apart) has ONE owner,
   decided at its start: zooming out at rest or anything on the whole chart is
   this script's (the board's scale); zooming in at rest, or anything while a
   card is enlarged, is the engine's (enlarge / let go). A gesture stops at full
   size (a new one enlarges a card). Zooming out of an enlarged card lets it go
   at once and, once the engine's glide home is over (UNF ms), carries on into
   the whole chart in the same movement. */
var ZS=null, UNF=380;
function gpt(e){ var c=cvs(); return (e.clientX!=null && mine(e)) ? local(e) : {x:c.clientWidth/2, y:c.clientHeight/2}; }
/* enlarge (the engine's focus) the body under the event's point, else the nearest to it */
function enlargeAt(e){
  var el=document.elementFromPoint(e.clientX||0, e.clientY||0), n=el && el.closest && el.closest('#world .node[data-solar]'), id=n ? n.id.slice(5) : null;
  if(!id){ var c=cvs(), q=local(e), off=woff(c); id=nearest(c.scrollLeft+q.x-off.x, c.scrollTop+q.y-off.y); }
  if(id && window.enterFocus) window.enterFocus(id);
}
function ovStep(s2, q){                                   /* this gesture's scale; false once it has come back to full size */
  if(s2>=.999){ if(!OV) return true; ovLeave({x:(q.x-OV.tx)/OV.s, y:(q.y-OV.ty)/OV.s}, true); return false; }
  ovZoom(s2, q.x, q.y, false); return true;
}
window.addEventListener('wheel', function(e){
  if(!ready || !desk()) return;
  if(e.ctrlKey) e.preventDefault();                        /* never the browser's own zoom, wherever the pointer is (the engine's own
                                                              wheel listener is passive at rest in Safari, so its preventDefault is not heard) */
  if(!mine(e)) return;
  if(!e.ctrlKey){
    if(!OV) return;
    e.preventDefault(); e.stopImmediatePropagation();
    var mm=e.deltaMode===1 ? 40 : e.deltaMode===2 ? 800 : 1;
    OV.tx-=e.deltaX*mm; OV.ty-=e.deltaY*mm; if(e.shiftKey && !e.deltaX){ OV.ty+=e.deltaY*mm; OV.tx-=e.deltaY*mm; }
    clampO(OV); ovSet(OV); return;
  }
  var now=performance.now(), f=!!window._focusedNodeId;
  if(!ZS || ZS.k!=='w' || now-ZS.t>220) ZS={k:'w', own:(f || (!OV && e.deltaY<0)) ? 'engine' : 'me', f0:f, ex:0, done:false};
  ZS.t=now;
  if(ZS.own==='engine'){
    if(f===ZS.f0) return;                                  /* the engine's, until it has acted */
    e.stopImmediatePropagation();
    if(!(ZS.f0 && e.deltaY>0)) return;                     /* it enlarged a card: the rest of this gesture is spent */
    if(!ZS.ex) ZS.ex=now; if(now-ZS.ex<UNF) return;        /* let go: on into the whole chart once it is home */
    ZS.own='me';
  }
  e.stopImmediatePropagation();
  if(ZS.done) return;
  var m=e.deltaMode===1 ? 40 : e.deltaMode===2 ? 800 : 1;
  if(!OV){                                                 /* at natural size: zooming on in enlarges the body under the pointer */
    if(e.deltaY<0){ ZS.acc=(ZS.acc||0)-e.deltaY*m; if(ZS.acc>48){ ZS.done=true; enlargeAt(e); } }
    else ZS.acc=0;
    if(e.deltaY<=0) return;
  }
  ovStep((OV ? OV.s : 1)*Math.max(.5, Math.min(2, Math.exp(-e.deltaY*m*.012))), local(e));
}, {passive:false, capture:true});
/* Safari: a trackpad pinch is gesturestart / gesturechange / gestureend */
document.addEventListener('gesturestart', function(e){
  e.preventDefault();
  if(!ready || !desk()){ ZS=null; return; }
  var f=!!window._focusedNodeId;
  ZS={k:'g', own:f ? 'engine' : (OV ? 'me' : '?'), f0:f, base:OV ? OV.s : 1, sx:1, ex:0, done:false};
  if(ZS.own==='me') e.stopImmediatePropagation();
}, {passive:false});
document.addEventListener('gesturechange', function(e){
  e.preventDefault();
  if(!ZS || ZS.k!=='g') return;
  if(ZS.own==='?'){ if(e.scale<.97) ZS.own='me'; else if(e.scale>1.03){ ZS.own='engine'; return; } else return; }
  if(ZS.own==='engine'){
    if(!ZS.f0 || e.scale>=.88) return;                     /* the engine's: pinch in at rest, or a card held */
    e.stopImmediatePropagation();
    if(!ZS.ex){ ZS.ex=performance.now(); if(window.exitFocus) window.exitFocus(); return; }
    if(performance.now()-ZS.ex<UNF || window._focusedNodeId) return;
    ZS.own='me'; ZS.base=1; ZS.sx=e.scale; return;          /* from here the pinch is the board's */
  }
  e.stopImmediatePropagation();
  if(ZS.done) return;
  var s2=ZS.base*e.scale/ZS.sx;
  if(!OV && s2>=1){ if(s2>1.1){ ZS.done=true; enlargeAt(e); } return; }   /* past natural size: enlarge the body under the pinch */
  if(!ovStep(Math.min(1, s2), gpt(e))){ ZS.base=1; ZS.sx=e.scale; }       /* came back to natural size: carry on from here */
}, {passive:false});
document.addEventListener('gestureend', function(e){
  e.preventDefault();
  var z=ZS; ZS=null; if(!z || z.k!=='g') return;
  if(z.own==='me' || z.ex){ e.stopImmediatePropagation(); if(OV && OV.s>=.97) ovLeave(null, true); }
}, {passive:false});
/* Enter on an enlarged disc opens its full page, as a click on it does */
window.addEventListener('keydown', function(e){
  var id=window._focusedNodeId, ae=document.activeElement, tg=ae && ae.tagName;
  if(e.key!=='Enter' || !ready || !desk() || !id || e.metaKey || e.ctrlKey || e.altKey || de.classList.contains('alto-editing') || !B[id]) return;
  if(ae && (ae.isContentEditable || /^(INPUT|TEXTAREA|BUTTON|A|SELECT)$/.test(tg))) return;
  if(document.querySelector('#detail-page.visible,#summary-wrap.open') || typeof showDetail!=='function') return;
  e.preventDefault(); showDetail('node', id);
});
window.addEventListener('keydown', function(e){
  if(!ready || !desk() || locked() || (document.activeElement && (document.activeElement.isContentEditable || /^(INPUT|TEXTAREA)$/.test(document.activeElement.tagName)))) return;   /* (Spokes only: no zoom) */
  var k=e.key, mod=e.metaKey || e.ctrlKey, hit=false;
  if(mod && k==='-' && !window._focusedNodeId && !document.querySelector('#summary-wrap.open,#detail-page.visible')){ ovZoom((OV ? OV.s : 1)/1.6, null, null, true); hit=true; }
  else if(OV && mod && (k==='=' || k==='+')){ if(OV.s*1.6>=.97) ovLeave(); else ovZoom(OV.s*1.6, null, null, true); hit=true; }
  else if(OV && mod && k==='0'){ ovLeave(); hit=true; }
  if(hit){ e.preventDefault(); e.stopImmediatePropagation(); }
}, true);
(function(){
  var dn=null;
  document.addEventListener('pointerdown', function(e){ if(!OV || !mine(e)) return; e.preventDefault(); e.stopPropagation();
    dn={x:e.clientX, y:e.clientY, tx:OV.tx, ty:OV.ty, moved:false, id:e.pointerId}; }, true);
  document.addEventListener('pointermove', function(e){ if(!dn || !OV || e.pointerId!==dn.id) return; var k=zk(cvs());
    if(!dn.moved && Math.abs(e.clientX-dn.x)+Math.abs(e.clientY-dn.y)<5) return;
    dn.moved=true; OV.tx=dn.tx+(e.clientX-dn.x)/k; OV.ty=dn.ty+(e.clientY-dn.y)/k; clampO(OV); ovSet(OV); }, true);
  document.addEventListener('pointerup', function(e){ if(!dn || e.pointerId!==dn.id) return; var d=dn; dn=null;
    if(!OV || d.moved) return;
    var q=local(e), wx=(q.x-OV.tx)/OV.s, wy=(q.y-OV.ty)/OV.s, id=nearest(wx, wy), b=id && B[id];
    if(!b || Math.hypot(b.rx-wx, b.ry-wy)>b.d/2+10/OV.s) return;
    ovLeave({x:b.rx, y:b.ry}, false, function(){ if(window.enterFocus) window.enterFocus(id); }); }, true);
  /* nothing under the whole chart is clicked through to */
  ['mousedown', 'click', 'dblclick'].forEach(function(t){ document.addEventListener(t, function(e){ if(OV && mine(e)){ e.preventDefault(); e.stopPropagation(); } }, true); });
  document.addEventListener('scroll', function(e){ var c=cvs(); if(OV && e.target===c && (c.scrollLeft || c.scrollTop)){ c.scrollLeft=0; c.scrollTop=0; } }, true);
  window.addEventListener('resize', function(){ if(OV){ ovHold(true); clampO(OV); ovSet(OV); } });
})();
/* ── the camera: window._altoSolarCam (solar_fly.py and anything else that moves the view) ──
     get()   -> {cx, cy, scale}: the PLAN point (plan.nodes coordinates: x, y without
                WORLD_PAD_TOP) at the middle of the canvas, and the board's scale
                (1 = natural size, < 1 = the whole-chart view). Includes the board pan of
                an enlarged card's fly (window._altoPan).
     set(cx, cy, scale) -> puts that plan point in the middle at that scale, at once, and
                returns get(): scale >= 1 through the canvas's own scroll (the engine's
                whole-px axis, _altoScrollAxis), < 1 through the whole-chart transform
                (translate rounded to device px). scale is kept within [the floor .03, 1];
                the translation is not clamped, so set(get()) changes nothing. An enlarged
                card is let go first (exitFocus; its glide home then runs — let go and wait
                UNF ms yourself before a set() that must be exact).
     onChange(fn) -> fn(get()) after the view moves (scroll, board pan, zoom), at most once
                a frame; returns a function that unsubscribes.
   The whole-chart toggle, pinch and cmd-minus move the same OV state, so get() reads them. */
var camFns=[], camRaf=0;
function camGet(){
  var c=cvs(); if(!c || !world) return null; var cw=c.clientWidth, ch=c.clientHeight;
  if(OV) return {cx:(cw/2-OV.tx)/OV.s, cy:(ch/2-OV.ty)/OV.s-PAD, scale:OV.s};
  var off=woff(c), pn=window._altoPan ? window._altoPan() : {x:0, y:0};
  return {cx:c.scrollLeft+cw/2-off.x-pn.x, cy:c.scrollTop+ch/2-off.y-pn.y-PAD, scale:1};
}
function camTell(){ if(!camFns.length || camRaf) return;
  camRaf=requestAnimationFrame(function(){ camRaf=0; var g=camGet(); camFns.slice().forEach(function(f){ try{ f(g); }catch(e){} }); }); }
window._altoSolarCam={
  get:camGet,
  set:function(cx, cy, scale){
    var c=cvs(); if(!c || !ready || !desk()) return null;
    scale=Math.min(1, Math.max(OVMIN, scale==null ? 1 : +scale));
    if(window._focusedNodeId && window.exitFocus) window.exitFocus();
    var cw=c.clientWidth, ch=c.clientHeight, wx=+cx, wy=+cy+PAD;
    if(scale<.999){
      if(!OV){ var o0=woff(c); OV={s:1, tx:o0.x-c.scrollLeft, ty:o0.y-c.scrollTop}; ovHold(true); c.scrollLeft=0; c.scrollTop=0; c.classList.add('sol-ov'); fitBtn(); }
      cancelAnimationFrame(ovA); OV.s=scale; OV.tx=cw/2-wx*scale; OV.ty=ch/2-wy*scale; ovSet(OV);
    } else {
      if(OV) ovLeave(null, true);
      var off=woff(c), ax=window._altoScrollAxis, sl=wx+off.x-cw/2, st=wy+off.y-ch/2;
      if(ax){ ax('scrollLeft').go(sl); ax('scrollTop').go(st); } else { c.scrollLeft=Math.round(sl); c.scrollTop=Math.round(st); }
      camTell();
    }
    return camGet();
  },
  onChange:function(fn){ camFns.push(fn); return function(){ var i=camFns.indexOf(fn); if(i>=0) camFns.splice(i, 1); }; }
};
window._altoSolarZoom=function(s){ if(s==null) return OV ? OV.s : 1; if(s>=1) ovLeave(null, true); else ovZoom(s, null, null, false); return OV ? OV.s : 1; };
/* ── the two looks and the orbit switch ──────────────────────────────────────
   window._altoSolarLook   = {get() -> 'stars'|'hub', set(look), onChange(fn), plan() -> the plan drawn}
   window._altoSolarMotion = {get() -> the orbit clock runs (switched on, in either look), set(on), onChange(fn)}
   <html> carries .alto-solar-stars or .alto-solar-hub. Both looks draw the SAME plan, so a change
   of look moves nothing: the Star chart's skin and flights come or go (solar_stars.py,
   solar_fly.py, through onChange); an enlarged body, the zoom, the orbit clock, edit mode and
   the viewer's choices carry over. Orbit off: the bodies stop where they are, _altoSolarT
   stops; on again: the clock eases back in over ~400 ms from where it stopped. Both choices are
   kept per timeline per viewer (localStorage alto-solar-look:<id>, alto-solar-motion:<id>; an
   old 'plain' reads as 'hub'). */
var lookFns=[], motFns=[];
function tell(fns, v){ fns.slice().forEach(function(f){ try{ f(v); }catch(e){} }); }
function looks(){ var d=desk(); de.classList.toggle('alto-solar-stars', d && LOOK==='stars'); de.classList.toggle('alto-solar-hub', d && LOOK==='hub'); }   /* desktop only: a phone shows the engine's cards */
function setLook(look){
  look=lk(look); if(!look || look===LOOK) return LOOK;
  LOOK=look; keep('look', look); looks(); if(typeof stySync==='function') stySync();
  if(ready){ ctl(); apply(true); skin(); }
  tell(lookFns, look); tell(motFns, MOTION && MOVES);
  return LOOK;
}
window._altoSolarLook={get:function(){ return LOOK; }, set:setLook, plan:function(){ return S; },
  onChange:function(fn){ lookFns.push(fn); return function(){ var i=lookFns.indexOf(fn); if(i>=0) lookFns.splice(i, 1); }; }};
window._altoSolarMotion={get:function(){ return !!MOTION && MOVES; },
  set:function(on){ on=!!on; if(on===!!MOTION) return MOTION; MOTION=on; keep('motion', on ? 1 : 0); if(on){ sp=0; RAMP=.4; last=null; } ctl(); tell(motFns, MOTION && MOVES); go(); return MOTION; },
  onChange:function(fn){ motFns.push(fn); return function(){ var i=motFns.indexOf(fn); if(i>=0) motFns.splice(i, 1); }; }};
/* the controls, under the bars at the top left: System | Star chart, and Orbit */
var IC_EXTRA={fly:'<svg viewBox="0 0 20 20" width="16" height="16" aria-hidden="true"><path d="M3 13.5 16.5 4.5 12 16l-2.6-4.2L3 13.5z" fill="currentColor"/></svg>',
  lock:'<svg viewBox="0 0 20 20" width="16" height="16" aria-hidden="true"><circle cx="4" cy="10" r="2.4" fill="currentColor"/><circle cx="16" cy="5" r="2.4" fill="currentColor"/><circle cx="16" cy="15" r="2.4" fill="currentColor"/><path d="M4 10 16 5M4 10l12 5" stroke="currentColor" stroke-width="1.5"/></svg>'};
var IC={stars:'<svg viewBox="0 0 20 20" width="16" height="16" aria-hidden="true"><circle cx="10" cy="10" r="4.4" fill="currentColor"/><ellipse cx="10" cy="10" rx="8.6" ry="3" fill="none" stroke="currentColor" stroke-width="1.4" transform="rotate(-22 10 10)"/></svg>',
  hub:'<svg viewBox="0 0 20 20" width="16" height="16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.4"><circle cx="10" cy="10" r="2.6"/><circle cx="10" cy="10" r="5.6" stroke-opacity=".55"/><circle cx="10" cy="10" r="8.4" stroke-opacity=".55"/><circle cx="15.6" cy="10" r="1.6" fill="currentColor"/><circle cx="5" cy="3.6" r="1.4" fill="currentColor"/></svg>',
  pause:'<svg class="sol-ic-pause" viewBox="0 0 20 20" width="14" height="14" aria-hidden="true" fill="currentColor"><rect x="5" y="4" width="3.4" height="12" rx="1"/><rect x="11.6" y="4" width="3.4" height="12" rx="1"/></svg>',
  play:'<svg class="sol-ic-play" viewBox="0 0 20 20" width="14" height="14" aria-hidden="true" fill="currentColor"><path d="M6 4.2v11.6c0 .6.7 1 1.2.6l8.6-5.8c.4-.3.4-1 0-1.2L7.2 3.6C6.7 3.3 6 3.6 6 4.2z"/></svg>'};
IC.fly=IC_EXTRA.fly; IC.lock=IC_EXTRA.lock;
/* ── round 10: Flights on/off (#6: off = straight there, as in the System look; solar_fly.py honours
   window._altoFlyOff), kept per timeline per viewer, like the look and the motion. ── */
window._altoFlyOff=pref('fly')==='0';
/* ── Spokes only (Luke, 2026-10-21: "travelling only by spokes"). On, there is no free camera at all: no
   panning, no zoom, no dragging the view, no click away. You are always at a body. An arrow, a scroll that
   way, or a click on a body one spoke away (or on that spoke) RIDES the spoke there: the enlarged card goes
   home, a rider runs along the spoke (Retro: the ship), the view following it like a train on its track and
   the orbits holding still, and the body is enlarged on arrival. One ride reaches only what the body is
   joined to: what it orbits, what orbits it, and (a sun) the suns its system is linked to. The four ways go
   to the joined bodies lying most that way on the screen, one body each; the rest by a click. Anything else
   does nothing but say so. Kept per timeline per viewer. ── */
var LOCK=pref('lock')==='1', LW={t:0, x:0, y:0, done:false}, RD=null, RQ=[], LASTF=null;
function lockSync(){ var c=cvs(); if(c) c.classList.toggle('sol-lock', !!(LOCK && ready && desk())); }
function setLock(on){ LOCK=!!on; keep('lock', LOCK ? 1 : 0); if(LOCK && OV) ovLeave(null, true); if(!LOCK){ RQ=[]; if(RD) rideEnd(true); } lockSync(); ctl(); if(LOCK && !window._focusedNodeId) lockStep(null); return LOCK; }
function locked(){ return LOCK && ready && desk() && !de.classList.contains('alto-editing') && !printing; }
/* the body nearest the middle of the window: where Spokes only boards when there is no body yet */
function nearestMid(){ var c=cvs(); if(!c) return null; var r=c.getBoundingClientRect(), cx=r.left+r.width/2, cy=r.top+r.height/2, best=null, bd=Infinity;
  ORD.forEach(function(id){ var n=B[id].n; if(!n) return; var q=n.getBoundingClientRect(); if(!q.width) return; var d=Math.hypot(q.left+q.width/2-cx, q.top+q.height/2-cy); if(d<bd){ bd=d; best=id; } });
  return best; }
/* where you are: the enlarged body, else the last one (Esc only lets the card go home), else the one in the middle */
function home(){ var f=window._focusedNodeId; if(f && B[f] && B[f].n) return f; return (LASTF && B[LASTF] && B[LASTF].n) ? LASTF : nearestMid(); }
/* what a body is joined to by a drawn spoke: what it orbits, what orbits it, the suns its sun is linked to */
function joined(id){ var a=B[id], o=[]; if(!a) return o;
  function add(j){ if(j && j!==id && B[j] && B[j].n && o.indexOf(j)<0) o.push(j); }
  add(a.p); spokes.forEach(function(s){ if(s.a===id) add(s.b); });
  sunl.forEach(function(s){ if(s.a===id) add(s.b); else if(s.b===id) add(s.a); });
  return o; }
/* a body's place on the screen's axes (world px; the 3D scene: its projection) */
function spot(id){ if(de.classList.contains('sk-3d') && window._altoSolar3D && window._altoSolar3D.project){ var q=window._altoSolar3D.project(id); if(q) return [q.x, q.y]; }
  var b=B[id], n=b.n; return [b.rx+((n && n._fx)||0), b.ry+((n && n._fy)||0)]; }
/* the four ways from a body: each to the joined body lying most that way (within 80°), one body each, nearest
   angle first. {nb: joined, k: way -> id, d: id -> way} */
var WAYS={e:0, s:90, w:180, n:-90};
function ways(id){ var nb=joined(id), c=[], k={}, d={}; if(!B[id]) return {nb:nb, k:k, d:d}; var p=spot(id);
  nb.forEach(function(j){ var q=spot(j), an=Math.atan2(q[1]-p[1], q[0]-p[0])*180/Math.PI;
    for(var w in WAYS){ var df=Math.abs(((an-WAYS[w])%360+540)%360-180); if(df<=80) c.push([df, w, j]); } });
  c.sort(function(x, y){ return x[0]-y[0]; });
  c.forEach(function(x){ if(k[x[1]] || d[x[2]]) return; k[x[1]]=x[2]; d[x[2]]=x[1]; });
  return {nb:nb, k:k, d:d}; }
/* the drawn line between two joined bodies (a spoke or a sun link) */
function rideLine(a, b){ var r=null; spokes.concat(sunl).some(function(s){ if((s.a===a && s.b===b) || (s.a===b && s.b===a)){ r=s.e[0]; return true; } }); return r; }
/* the rider: a bright bead (Retro: the ship, solar_fly.py's art), on the spoke, over the lines, under the bodies */
/* the rider is the chosen craft (solar_craft.py: window._altoCraft), drawn in this style's look */
var RDg=null;
function rider(){ if(RDg && RDg.isConnected && RDg.parentNode===svg) return RDg; if(!svg) return null;
  RDg=el('g', {'class':'sol-rider', 'aria-hidden':'true'}, svg);
  el('circle', {r:15, 'class':'sol-rh'}, RDg); el('circle', {r:5.5, 'class':'sol-rc'}, RDg);
  el('g', {'class':'sol-ship', transform:'scale(1.5)'}, RDg); return RDg; }
function craft(){ return window._altoCraft ? window._altoCraft.get() : {k:1, svg:''}; }
function enter(id){ LASTF=id; if(window.enterFocus) window.enterFocus(id); }
function ride(from, to){
  if(!locked() || !B[from] || !B[to] || !B[to].n) return false;
  if(RD){ return false; }
  if(OV) ovLeave(null, true);
  lclear(); LASTF=to;
  var g=camGet();
  if((de.classList.contains('sk-3d') && window._altoFlyOff) || reduced || !g || !svg){ enter(to); return true; }   /* the 3D scene with Flights off: its camera glides there; reduced motion: straight there */
  var A=B[from], Z=B[to], L=Math.hypot(Z.rx-A.rx, Z.ry-A.ry), cr=craft(), ms=Math.round(Math.min(2600, Math.max(900, 650+L*.55))*(RETRO ? 1.25 : 1)*(cr.k||1));
  if(window._focusedNodeId && window.exitFocus) window.exitFocus();
  var ln=rideLine(from, to); if(ln) ln.classList.add('sol-ride');
  RD={from:from, to:to, t0:performance.now(), ms:ms, x0:g.cx, y0:g.cy, ln:ln};
  window._altoFlyMs=ms+480;                              /* (the engine's hop queue waits for the arrival) */
  var r=rider(); if(r){ r.setAttribute('transform', 'translate('+f2(A.rx)+' '+f2(A.ry)+')'); r.classList.add('on'); r.querySelector('.sol-ship').innerHTML=cr.svg||''; }
  de.classList.add('sol-riding');
  requestAnimationFrame(rideF); return true;
}
function rideF(now){
  var R=RD; if(!R) return;
  if(!locked() || window._focusedNodeId || document.querySelector('#detail-page.visible')) return rideEnd(!window._focusedNodeId);   /* someone else took the focus or the switch: theirs */
  var k=Math.min(1, Math.max(0, (now-R.t0)/R.ms)), ez=window._altoEase || function(x){ return x*x*(3-2*x); }, e=ez(k);
  var A=B[R.from], Z=B[R.to], dx=Z.rx-A.rx, dy=Z.ry-A.ry, px=A.rx+dx*e, py=A.ry+dy*e;
  if(window._altoSolarCam) window._altoSolarCam.set(R.x0+(Z.rx-R.x0)*e, R.y0+(Z.ry-PAD-R.y0)*e, 1);   /* the view behind the rider, from where it was to the body */
  R.p=[px, py]; R.h=Math.atan2(dy, dx);                                              /* (the 3D scene flies its model here: window._altoSolarRide) */
  var r=rider(); if(r) r.setAttribute('transform', 'translate('+f2(px)+' '+f2(py)+') rotate('+f2(R.h*180/Math.PI)+')');
  if(k>=1) return rideEnd(true);
  requestAnimationFrame(rideF);
}
function rideEnd(arrive){
  var R=RD; RD=null; if(!R) return;
  if(R.ln) R.ln.classList.remove('sol-ride'); if(RDg) RDg.classList.remove('on'); de.classList.remove('sol-riding');
  if(arrive) enter(R.to);
  setTimeout(rideNext, (window._altoFlyMs=520));
}
window._altoSolarRide=function(){ return RD && RD.p ? {p:RD.p, h:RD.h, from:RD.from, to:RD.to} : null; };
function rideNext(){ if(RD || !RQ.length) return; var d=RQ.shift(), f=window._focusedNodeId; if(!f || !LOCK){ RQ=[]; return; } window._altoSolarNav(f, d); }
/* anything not one spoke away: nothing happens, and it says so (the joined bodies' pills nudge) */
var NOPE=null, nopeT=0;
function nope(e){
  if(!NOPE){ NOPE=document.createElement('div'); NOPE.className='line-tip sol-nope'; document.body.appendChild(NOPE); }
  var c=cvs(), r=c ? c.getBoundingClientRect() : {left:0, width:0, bottom:0}, x=e ? e.clientX+12 : r.left+r.width/2-110, y=e ? e.clientY+14 : r.bottom-130;
  NOPE.textContent='Spokes only: ride a lit spoke from here'; NOPE.style.left=x+'px'; NOPE.style.top=y+'px'; NOPE.style.display='block';
  if(c){ c.classList.remove('sol-nudge'); void c.offsetWidth; c.classList.add('sol-nudge'); }
  clearTimeout(nopeT); nopeT=setTimeout(function(){ NOPE.style.display='none'; if(c) c.classList.remove('sol-nudge'); }, 1500);
}
/* a body or a line asked for (a click; the 3D scene's pick): ridden to if it is one spoke away */
function rideTo(id, e){
  if(!locked() || RD) return false;
  var h=home(); if(!id || !h) return nope(e), false;
  if(id===h){ if(!window._focusedNodeId) enter(id); return true; }
  if(joined(h).indexOf(id)<0) return nope(e), false;
  return ride(h, id);
}
window._altoSolarGo=rideTo;
/* the clicks: on the enlarged disc its own (its full page); a body or a line one spoke away rides there; the rest nothing */
window.addEventListener('click', function(e){
  if(!locked() || e.button) return;
  var c=cvs(), t=e.target; if(!c || !t || t.nodeType!==1 || !c.contains(t) || t.id==='sk3d' || document.querySelector('#detail-page.visible')) return;
  if(t.closest('button,a,input,select,textarea,[contenteditable],#sol-ctl,#sol-nav')) return;
  var n=t.closest('#world .node[data-solar]'), id=n ? n.id.slice(5) : (t._r && t.classList.contains('sol-hit')) ? ringAt(e) : null;
  if(id && id===window._focusedNodeId) return;
  e.preventDefault(); e.stopImmediatePropagation(); rideTo(id, e);
}, true);
/* no dragging the view: a press on empty space does nothing (bodies, lines, buttons still take their clicks) */
['pointerdown', 'mousedown'].forEach(function(ty){ document.addEventListener(ty, function(e){ if(!locked()) return; var c=cvs(), t=e.target;
  if(!c || !c.contains(t) || t.id==='sk3d' || (t.closest && t.closest('.node,button,a,input,#sol-ctl')) || (t._r)) return;   /* (the 3D scene: solar_3d.py turns nothing while it is on) */
  e.preventDefault(); e.stopImmediatePropagation(); }, true); });
/* no pinch zoom (Safari's gesture events; the others' are a ctrl wheel, below) */
['gesturestart', 'gesturechange', 'gestureend'].forEach(function(ty){ window.addEventListener(ty, function(e){ if(!locked()) return; e.preventDefault(); e.stopImmediatePropagation(); }, {capture:true, passive:false}); });
/* the arrows with no body enlarged (or on a ride): board at home, or queue the next ride */
window.addEventListener('keydown', function(e){
  var d={ArrowUp:'n', ArrowDown:'s', ArrowLeft:'w', ArrowRight:'e'}[e.key]; if(!d || !locked() || e.metaKey || e.ctrlKey || e.altKey) return;
  var ae=document.activeElement; if(ae && (ae.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(ae.tagName))) return;
  if(document.querySelector('#detail-page.visible,#summary-wrap.open')) return;
  if(!RD && window._focusedNodeId) return;               /* (the engine's arrows: focusNeighbor -> window._altoSolarNav -> a ride) */
  e.preventDefault(); e.stopImmediatePropagation(); if(!e.repeat || !RQ.length) lockStep(d);
}, true);
window._altoSolarLock={get:function(){ return LOCK; }, set:setLock, ways:function(id){ return ways(id || home()); }, riding:function(){ return RD ? {from:RD.from, to:RD.to, ms:RD.ms} : null; }};
/* the Star chart's style (round 10): Classic (the painted scene) or Retro (solar_stars.py RETRO_CSS), per timeline */
function styOf(v){ return v==='retro' || v==='real' ? v : 'classic'; }
var STY=styOf(pref('style')), RETRO=false;
function stySync(){ RETRO=STY==='retro' && LOOK==='stars'; de.classList.toggle('sk-retro', STY==='retro'); de.classList.toggle('sk-real', STY==='real');
  var m=document.getElementById('sk-mark');      /* the poster's wordmark: the timeline's name, lower left */
  var fr=document.getElementById('sk-frame');
  if(RETRO && desk()){ if(!fr){ fr=document.createElement('div'); fr.id='sk-frame'; fr.setAttribute('aria-hidden', 'true'); fr.innerHTML='<i></i><i></i><i></i><i></i><b></b>'; document.body.appendChild(fr); } }
  else if(fr) fr.remove();
  if(RETRO && desk()){ if(!m){ m=document.createElement('div'); m.id='sk-mark'; m.setAttribute('aria-hidden', 'true'); document.body.appendChild(m); }
    var tt=document.getElementById('title-text'); m.textContent=plain(tt ? tt.textContent : document.title).split(/\s+[\u2014\u2013-]\s+/)[0]; }
  else if(m) m.remove(); }
function setSty(v){ STY=styOf(v); keep('style', STY); stySync(); chips.forEach(function(c){ c._wh=null; }); if(ready) apply(true); ctl(); return STY; }
window._altoSolarStyle={get:function(){ return STY; }, set:setSty};
stySync();
function lockStep(d){
  if(LOCK){
    if(RD){ if(d && RQ.length<2) RQ.push(d); return; }
    var f=window._focusedNodeId;
    if(!f || !B[f]){ var h=home(); if(h) enter(h); return; }   /* no body enlarged: board where you are */
    if(d) window._altoSolarNav(f, d); return; }
  var k={n:'ArrowUp', s:'ArrowDown', e:'ArrowRight', w:'ArrowLeft'}[d]; if(!k) return;
  document.dispatchEvent(new KeyboardEvent('keydown', {key:k, code:k, bubbles:true, cancelable:true}));
  setTimeout(function(){ document.dispatchEvent(new KeyboardEvent('keyup', {key:k, code:k, bubbles:true})); }, 30);
}
/* Spokes only: a wheel or a trackpad never moves or zooms the view; one gesture rides one spoke, the way it goes */
window.addEventListener('wheel', function(e){
  if(!locked()) return;
  var dp=document.getElementById('detail-page'); if(dp && dp.classList.contains('visible')) return;
  var c=cvs(); if(!c || !c.contains(e.target)) return;
  e.preventDefault(); e.stopImmediatePropagation();
  if(e.ctrlKey) return;                                          /* a pinch: no zoom */
  var m=e.deltaMode===1 ? 16 : e.deltaMode===2 ? 400 : 1;
  if(e.timeStamp-LW.t>260) LW={t:0, x:0, y:0, done:false};        /* a new gesture: one step each */
  LW.t=e.timeStamp; if(LW.done) return;
  LW.x+=e.deltaX*m; LW.y+=e.deltaY*m;
  if(Math.max(Math.abs(LW.x), Math.abs(LW.y))<40) return;
  LW.done=true; lockStep(Math.abs(LW.y)>=Math.abs(LW.x) ? (LW.y>0 ? 's' : 'n') : (LW.x>0 ? 'e' : 'w'));
}, {capture:true, passive:false});
function ctl(){
  var w=document.getElementById('sol-ctl');
  if(!desk() || !ready){ if(w) w.remove(); return; }
  if(!w){ w=document.createElement('div'); w.id='sol-ctl'; w.setAttribute('role', 'group'); w.setAttribute('aria-label', 'How the chart looks');
    w.innerHTML='<div class="sol-seg" role="radiogroup" aria-label="Look">'+
      '<button type="button" data-look="hub" role="radio" title="System: the orbits in Alto\'s own look">'+IC.hub+'<span>System</span></button>'+
      '<button type="button" data-look="stars" role="radio" title="Star chart: the same orbits as a space scene, with flights between bodies">'+IC.stars+'<span>Star chart</span></button></div>'+
      '<button type="button" id="sol-motion">'+IC.pause+IC.play+'<span>Orbit</span></button>'+
      '<div class="sol-seg" id="sol-sty" role="radiogroup" aria-label="Star chart style"><button type="button" data-sty="retro" role="radio" title="Retro: flat poster colours, gold spokes">Retro</button>'+
      '<button type="button" data-sty="classic" role="radio" title="Classic: the painted space scene">Classic</button>'+
      '<button type="button" data-sty="real" role="radio" title="Realistic 3D: turning globes lit by their suns, clouds, depth">Realistic 3D</button></div>'+
      '<button type="button" id="sol-fly" class="sol-opt">'+IC.fly+'<span>Flights</span><i class="sol-sw"></i><b class="sol-st"></b></button>'+
      '<button type="button" id="sol-craft" class="sol-opt" aria-haspopup="dialog" aria-expanded="false"><i class="cr-i"></i><span>Ship</span></button>'+
      '<button type="button" id="sol-lock" class="sol-opt">'+IC.lock+'<span>Spokes only</span><i class="sol-sw"></i><b class="sol-st"></b></button>';
    w.addEventListener('click', function(e){ var b=e.target.closest && e.target.closest('button'); if(!b) return; e.stopPropagation();
      if(b.getAttribute('data-look')) setLook(b.getAttribute('data-look'));
      else if(b.getAttribute('data-sty')) setSty(b.getAttribute('data-sty'));
      else if(b.id==='sol-motion' && !b.disabled) window._altoSolarMotion.set(!MOTION);
      else if(b.id==='sol-fly'){ window._altoFlyOff=!window._altoFlyOff; keep('fly', window._altoFlyOff ? 0 : 1); ctl(); }
      else if(b.id==='sol-lock') setLock(!LOCK);
      else if(b.id==='sol-craft' && window._altoCraft) window._altoCraft.open(b); });
    if(window._altoCraft) window._altoCraft.onChange(function(){ ctl(); });
    document.body.appendChild(w); }
  [].forEach.call(w.querySelectorAll('[data-look]'), function(b){ var on=b.getAttribute('data-look')===LOOK; b.classList.toggle('on', on); b.setAttribute('aria-checked', on ? 'true' : 'false'); });
  var m=w.querySelector('#sol-motion'), run=!!MOTION && MOVES;
  m.disabled=!MOVES; m.classList.toggle('on', run); m.setAttribute('aria-pressed', run ? 'true' : 'false');
  m.title=!MOVES ? 'Orbit: nothing here orbits' : run ? 'Orbit on/off (Space): on, click to stop the planets where they are' : 'Orbit on/off (Space): off, click to set the planets moving again';
  m.setAttribute('aria-label', m.title);
  var sy=w.querySelector('#sol-sty'); sy.hidden=LOOK!=='stars';
  [].forEach.call(sy.querySelectorAll('[data-sty]'), function(b){ var on=b.getAttribute('data-sty')===STY; b.classList.toggle('on', on); b.setAttribute('aria-checked', on ? 'true' : 'false'); });
  var fb=w.querySelector('#sol-fly'), fo=!window._altoFlyOff; fb.hidden=LOOK!=='stars'; fb.classList.toggle('on', fo); fb.setAttribute('aria-pressed', fo ? 'true' : 'false');
  fb.title=fo ? 'Flights on: a spaceship flies you between bodies (click to go straight there instead)' : 'Flights off: you go straight to each body (click to fly again)';
  fb.querySelector('.sol-st').textContent=fo ? 'ON' : 'OFF';
  var cb=w.querySelector('#sol-craft'), CR=window._altoCraft; cb.hidden=LOOK!=='stars' || !CR;
  if(CR){ var cc=CR.get(); if(cb._c!==cc.id+STY){ cb._c=cc.id+STY; cb.querySelector('.cr-i').innerHTML=CR.art(cc.id); }
    cb.title='Your ship: '+cc.name+' (click to choose another)'; cb.setAttribute('aria-label', cb.title); }
  var lb=w.querySelector('#sol-lock'); lb.classList.toggle('on', LOCK); lb.querySelector('.sol-st').textContent=LOCK ? 'ON' : 'OFF'; lb.setAttribute('aria-pressed', LOCK ? 'true' : 'false');
  lb.title=LOCK ? 'Spokes only: on. Arrows, scrolling and clicks ride the spokes from body to body; no free panning or zooming (click to move freely)' : 'Spokes only: off. Click to travel only by riding the spokes';
}
/* the space bar starts / stops the orbit like the Orbit button: only while the system is showing (the button is there
   and enabled: not a phone, not the detail page, not edit mode, not print), no modifier, not held down, not in a field or on
   a button / link / chip (space does its own thing there) */
if(!window._altoSolarSpace){ window._altoSolarSpace=1;
  document.addEventListener('keydown', function(e){
    if((e.key!==' ' && e.code!=='Space') || e.repeat || e.ctrlKey || e.metaKey || e.altKey || e.shiftKey || e.defaultPrevented) return;
    var m=document.getElementById('sol-motion'); if(!m || m.disabled || !ready || !desk() || printing) return;
    if(de.classList.contains('alto-editing') || document.querySelector('#detail-page.visible')) return;
    var bad=function(t){ return !!(t && t.nodeType===1 && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT|BUTTON|A|SUMMARY)$/.test(t.tagName) || t.closest('[contenteditable=""],[contenteditable="true"],[role=button],[role=radio],[role=textbox],[role=searchbox],[role=combobox]'))); };
    if(bad(e.target) || bad(document.activeElement)) return;
    e.preventDefault(); window._altoSolarMotion.set(!MOTION); });
}
/* the engine's chip label also comes up on keyboard focus */
document.addEventListener('focusin', function(e){ var t=e.target; if(t && t.closest && t.closest('.node[data-solar] .node-footer') && t.matches('button'))
  t.dispatchEvent(new MouseEvent('mouseover', {bubbles:true})); });
document.addEventListener('focusout', function(e){ var t=e.target; if(t && t.closest && t.closest('.node[data-solar] .node-footer') && t.matches('button'))
  t.dispatchEvent(new MouseEvent('mouseout', {bubbles:true})); });
/* the label of a chip in a disc is slid sideways to stay inside the circle (the card clips to it) */
if(!window._altoSolarTip){ var _ts=window._altoTipShow;
  if(_ts) window._altoTipShow=window._altoSolarTip=function(chip, tip){
    _ts(chip, tip);
    var c=chip.closest('.node[data-solar] .node-card'); if(!c) return;
    var t0=performance.now();
    (function fr(){ if(tip._chip!==chip) return;
      var cr=c.getBoundingClientRect(), k=cr.width/(c.offsetWidth||1), R=cr.width/2, cx=cr.left+R, cy=cr.top+R, tr=tip.getBoundingClientRect();
      var yy=Math.min(Math.abs(tr.top-cy), Math.abs(tr.bottom-cy)), half=Math.sqrt(Math.max(0, Math.pow(R-10*k, 2)-yy*yy)), l=tr.left-cx, r=tr.right-cx, sh=0;
      if(r>half) sh=half-r; if(l+sh<-half) sh=-half-l;
      if(Math.abs(sh)>.5){ tip.style.left=(parseFloat(tip.style.left)+sh/(k*(parseFloat(getComputedStyle(document.documentElement).zoom)||1)))+'px'; }
      if(performance.now()-t0<760) requestAnimationFrame(fr); })(); }; }
window._altoSolarGeo=function(){ var o={}; ORD.forEach(function(id){ var b=B[id]; if(b.n) o[id]={x:b.rx, y:b.ry, hx:b.hx, hy:b.hy, d:b.d, role:b.role, p:b.p, si:b.si}; });
  return {T:T, moving:!!raf, bodies:o, units:SY.map(function(s, si){ return {sun:s.sun, si:si, unit:s.unit, R:s.R||0, c:unitColor(si)||''}; })}; };
return true;
};
if(window._ALTO_SOLAR) window._altoSolarMount(window._ALTO_SOLAR);
else document.addEventListener('DOMContentLoaded', function(){ if(window._ALTO_SOLAR) window._altoSolarMount(window._ALTO_SOLAR); });
"""


# ── solar.py's solar_plan, in the page ──────────────────────────────────────
# Edit mode reshapes the outline in the browser (a card added, moved under
# another, removed) and the page lays itself out again at once, so the plan is
# worked out here too, line for line as solar.py does it (same constants,
# emitted from solar.SOLAR; tests/test_solar_draw.py holds the two equal under
# node). Input: the live tables {kids, parent, seqs}; the circles' sizes and the
# units' labels come from the plan the page was built with.
SOLAR_PLAN_JS = r"""
window._altoSolarPlan=(function(){
var C=__SOLAR__, GOLD=__GOLDEN__, LOOKS=__LOOKS__, D=C.D, PI=Math.PI;
function r2(v){ return Math.round(v*100)/100; }
function r4(v){ return Math.round(v*1e4)/1e4; }
function mx(a){ return a.length ? Math.max.apply(null, a) : 0; }
function even(n, out){ var off=n%2===0 ? PI/n : 0, o=[]; for(var j=0;j<n;j++) o.push(out+off+2*PI*j/n); return o; }
/* a body's diameter: the sun's fixed, a planet / moon a tier up per two children, a bump one more (solar.body_d) */
function bodyD(role, n, bump, pd, st){ if(role==='sun') return D.sun; if(role==='sat' && st) return C.STATION;
  var L=C.TIERS[role], t=role!=='sat' ? Math.min(Math.ceil(n/2), L.length-2) : 0, d=L[Math.min(t+(bump ? 1 : 0), L.length-1)];
  return role==='moon' && pd ? Math.min(d, Math.floor(C.MOON_MAX*pd)) : d; }
/* the looks' arithmetic (solar.hash01 … orbit_offset): FNV-1a, a comet's ellipse, an asteroid's tumble */
function h01(s){ var h=2166136261; for(var i=0;i<s.length;i++){ h^=s.charCodeAt(i); h=Math.imul(h, 16777619)>>>0; } return h/4294967296; }
function cshape(id){ return [r4(C.ECC[0]+(C.ECC[1]-C.ECC[0])*h01('ecc:'+id)), r4(2*PI*h01('rot:'+id))]; }
function eslack(e){ var q=Math.sqrt(Math.max(0, 1-e*e)); return (1-q)/(1+q); }
function tumble(id){ var v=C.TUMBLE[0]+(C.TUMBLE[1]-C.TUMBLE[0])*h01('tumble:'+id); return r4(h01('spin:'+id)<.5 ? v : -v); }
function kepler(m, e){ var p=m; for(var i=0;i<12;i++) p-=(p-e*Math.sin(p)-m)/(1-e*Math.cos(p)); return p; }
function at(r, a, o){ if(!o) return [r*Math.cos(a), r*Math.sin(a)];
  var c=eslack(o.e), A=r*(1+c), B=r*(1-c), m=a-o.rot, p=o.k ? kepler(m, o.e) : m, x=A*Math.cos(p), y=B*Math.sin(p);
  return [x*Math.cos(o.rot)-y*Math.sin(o.rot), x*Math.sin(o.rot)+y*Math.cos(o.rot)]; }
/* concentric rings, one per body, the first innermost (solar._rings): items [id, reach] round a
   centre of radius inner, each annulus gap past the one inside it; a comet's (slack c) pushed out
   to (edge+gap+reach)/(1-c); its orbit into orb. -> [[ring per item], outer edge] */
function secc(c){ var q=(1-c)/(1+c); return Math.sqrt(Math.max(0, 1-q*q)); }
function rings(items, gap, inner, slack, orb){
  var edge=inner, out=[];
  items.forEach(function(it){ var c=slack[it[0]]||0, r=edge+gap+it[1];
    if(c){ var a=Math.min(c*r/(1-c), C.COMET_PX), e; r+=a; e=r4(secc(a/r)); c=eslack(e); r=(edge+gap+it[1])/(1-c)+.05;
      orb[it[0]]={e:e, rot:cshape(it[0])[1], k:0}; }
    out.push(r); edge=r+c*r+it[1]; });
  return [out, edge];
}
function pbody(pid, moons, size, slack){
  var dp=size(pid, 'planet', moons.length, 0), Rp=dp/2, orb={};
  var ms=moons.map(function(m){ var dm=size(m[0], 'moon', m[1].length, dp), Rm=dm/2, sd={}, srs={};
    m[1].forEach(function(q){ sd[q]=size(q, 'sat', 0, dm); });
    var F=rings(m[1].map(function(q){ return [q, sd[q]/2]; }), C.SAT_GAP, Rm, slack, orb);
    m[1].forEach(function(q, j){ srs[q]=F[0][j]; });
    return {id:m[0], d:dm, sats:m[1], sd:sd, srs:srs, sat_r:F[0].length ? F[0][0] : 0, ext:m[1].length ? F[1] : Rm}; });
  var F=rings(ms.map(function(m){ return [m.id, m.ext]; }), C.MOON_GAP, Rp, slack, orb);
  ms.forEach(function(m, j){ m.r=F[0][j]; });
  return {id:pid, d:dp, moons:ms, moon_r:F[0].length ? F[0][0] : 0, e:Math.max(ms.length ? F[1] : Rp, Rp), orb:orb};
}
function local(b, th, r, orbs){
  orbs=orbs||{};
  var P=at(r, th, orbs[b.id]), px=P[0], py=P[1], cs=[[b.id, px, py, b.d/2, null]], ma=even(b.moons.length, th);
  b.moons.forEach(function(m, k){ var o=at(m.r, ma[k], orbs[m.id]), x=px+o[0], y=py+o[1], sa=even(m.sats.length, ma[k]);
    cs.push([m.id, x, y, m.d/2, b.id]);
    m.sats.forEach(function(si, j){ var o2=at(m.srs[si], sa[j], orbs[si]); cs.push([si, x+o2[0], y+o2[1], m.sd[si]/2, m.id]); }); });
  return cs;
}
function period(lh, k, n){ return r2(lh[0]+(lh[1]-lh[0])*(n>1 ? k/(n-1) : .5)); }
function system(unit, sun, planets, size, looks){
  var slack={};
  Object.keys(looks).forEach(function(i){ if(looks[i]==='comet') slack[i]=eslack(cshape(i)[0]); });
  var Rs=D.sun/2, bs=planets.map(function(p){ return pbody(p[0], p[1], size, slack); }), P=bs.length, rg=[], ang=[], orbs={}, belt=null;
  bs.forEach(function(b){ Object.keys(b.orb).forEach(function(i){ orbs[i]=b.orb[i]; }); });
  var edge=Rs, split=P>=C.BELT_MIN ? Math.floor(P/2) : -1;
  bs.forEach(function(b, k){
    if(k===split){ belt={r:edge+C.RING_GAP+C.BELT_W/2, w:C.BELT_W}; edge+=C.RING_GAP+C.BELT_W; }
    var c=slack[b.id]||0, r=edge+C.RING_GAP+b.e;
    if(c){ var a=Math.min(c*r/(1-c), C.COMET_PX_PLANET), e=r4(secc(a/(r+a))); c=eslack(e); r=r/(1-c)+.05;
      orbs[b.id]={e:e, rot:cshape(b.id)[1], k:1}; }
    rg.push(r); ang.push(-PI/2+k*GOLD); b.band=[r-c*r-b.e, r+c*r+b.e]; edge=b.band[1]; });
  var outP=[], loc={}; loc[sun]=[0, 0, D.sun, 'sun', ''];
  var md=function(a){ a%=2*PI; if(a<0) a+=2*PI; return Math.round(a*1e7)/1e7; };
  bs.forEach(function(b, k){
    var r=rg[k], th=ang[k], ma=even(b.moons.length, th), nm=b.moons.length;
    local(b, th, r, orbs).forEach(function(c){ loc[c[0]]=[c[1], c[2], Math.round(c[3]*2), c[4]===null ? 'planet' : (c[4]===b.id ? 'moon' : 'sat'), c[4]||sun]; });
    outP.push({id:b.id, ring:k+1, r:r2(r), a0:md(th), d:b.d, period:period(C.P_PLANET, k, P), e:r2(b.e), moon_r:r2(b.moon_r),
      moons:b.moons.map(function(m, i){ var sa=even(m.sats.length, ma[i]), ns=m.sats.length;
        return {id:m.id, r:r2(m.r), a0:md(ma[i]), d:m.d, period:period(C.P_MOON, i, nm), ext:r2(m.ext), sat_r:r2(m.sat_r),
          sats:m.sats.map(function(si, j){ return {id:si, r:r2(m.srs[si]), a0:md(sa[j]), d:m.sd[si], period:period(C.P_SAT, j, ns)}; })}; })});
  });
  var R=bs.length ? bs[bs.length-1].band[1] : Rs;
  return {unit:unit, sun:sun, r_sun:Rs, R:R, box:[-R, -R, R, R], planets:outP, local:loc, orbs:orbs, belt:belt};
}
/* the systems' places (solar._galaxy): one centred; 2+ a spiral galaxy round the core */
function galaxy(Rs){
  if(!Rs.length) return [[], C.WORLD_W, C.TOP+C.BOTTOM, null];
  if(Rs.length===1){ var W1=Math.ceil(Math.max(C.WORLD_W, 2*Rs[0]+2*C.MARGIN)); return [[[W1/2, C.TOP+Rs[0]]], W1, Math.ceil(C.TOP+2*Rs[0]+C.BOTTOM), null]; }
  var A=C.ARMS, gap=C.SYS_GAP, cg=C.CORE_R+C.CORE_GAP, b=(Rs.reduce(function(s, r){ return s+2*r; }, 0)/Rs.length+gap)*A/(2*PI), a=cg+Rs[0], cur=[], out=[];
  for(var j=0;j<A;j++) cur.push(0);
  Rs.forEach(function(R, k){ var arm=k%A, th=cur[arm], x=0, y=0;
    for(var it=0;it<200000;it++){ var rho=a+b*th, ang=__SPIN__*(th+arm*2*PI/A); x=rho*Math.cos(ang); y=rho*Math.sin(ang);
      if(rho>=R+cg-1e-6 && out.every(function(q){ return Math.hypot(x-q[0], y-q[1])>=R+q[2]+gap-1e-6; })) break;
      th+=Math.min(.05, C.GAL_STEP/rho); }
    cur[arm]=th; out.push([x, y, R]); });
  var G=Math.max.apply(null, out.map(function(q){ return Math.hypot(q[0], q[1])+q[2]; })), W=Math.ceil(Math.max(C.WORLD_W, 2*G+2*C.MARGIN)), ox=W/2, oy=C.TOP+G;
  return [out.map(function(q){ return [ox+q[0], oy+q[1]]; }), W, Math.ceil(C.TOP+2*G+C.BOTTOM), {x:r2(ox), y:r2(oy), r:C.CORE_R, p:C.P_GALAXY}];
}
/* t: {kids, parent, seqs, flags?}; old: the plan the page has (sizes, labels, look flags) */
function plan(t, old){
  var K=t.kids||{}, Par=t.parent||{}, seqs=t.seqs||[], ids={};
  seqs.forEach(function(q){ q.forEach(function(i){ ids[i]=1; }); });
  function kids(i){ return (K[i]||[]).filter(function(k){ return ids[k] && Par[k]===i; }); }
  var labels={}; ((old && old.systems)||[]).forEach(function(s){ labels[s.unit]=s.label; });
  var units=[];
  /* every root a sun (a unit may hold several); loose cards orbit the unit's first */
  seqs.forEach(function(mine, a){
    if(!mine.length) return;
    var tops=mine.filter(function(i){ return !Par[i]; }); if(!tops.length) tops=[mine[0]];
    var loose=mine.filter(function(i){ return tops.indexOf(i)<0 && (!Par[i] || !ids[Par[i]]); });
    tops.forEach(function(sun, k){
      units.push([a, sun, kids(sun).concat(k ? [] : loose).map(function(p){ return [p, kids(p).map(function(m){ return [m, kids(m)]; })]; })]); });
  });
  /* the flags on each node: t.flags {id: [flag ids]}, else the page's NODES_SRC; which bump (plan.sizes.bump), which make a look (plan.look_flags) */
  var bump=((old && old.sizes && old.sizes.bump)||[]), LF=(old && old.look_flags)||{}, FL=t.flags||{};
  if(!t.flags && typeof NODES_SRC!=='undefined') NODES_SRC.forEach(function(n){ if(n.flags) FL[n.id]=n.flags; });
  /* the space stations: the page's own plan's (solar.stations reads the content, which the live tables do not carry) */
  var ST={}; Object.keys((old && old.nodes)||{}).forEach(function(i){ if(old.nodes[i].station && ids[i]) ST[i]=1; });
  var size=function(i, role, n, pd){ return bodyD(role, n, (FL[i]||[]).some(function(f){ return bump.indexOf(f)>=0; }), pd, ST[i]); };
  var looks={};
  Object.keys(ids).forEach(function(i){ var got=(FL[i]||[]).map(function(f){ return LF[f]; }).filter(function(x){ return x; });
    if(got.length) looks[i]=got.sort(function(a, b){ return LOOKS.indexOf(a)-LOOKS.indexOf(b); })[0]; });
  var sy=units.map(function(u){ return system(u[0], u[1], u[2], size, looks); });
  var GX=galaxy(sy.map(function(s){ return s.R; })), W=GX[1], H=GX[2], nodes={}, systems=[], belts=[];
  sy.forEach(function(s, k){
      var cx=GX[0][k][0], cy=GX[0][k][1];
      var pm=(typeof PHASE_META!=='undefined') ? PHASE_META[s.unit] : null;
      systems.push({unit:s.unit, label:labels[s.unit]!=null ? labels[s.unit] : (pm ? pm.label : ''), sun:s.sun, cx:r2(cx), cy:r2(cy), r_sun:s.r_sun, R:r2(s.R),
        bbox:[r2(cx+s.box[0]), r2(cy+s.box[1]), r2(cx+s.box[2]), r2(cy+s.box[3])], planets:s.planets});
      Object.keys(s.local).forEach(function(i){ var c=s.local[i], n={x:r2(cx+c[0]), y:r2(cy+c[1]), d:c[2], role:c[3], unit:s.unit, parent:c[4]};
        if(looks[i]) n.look=looks[i];
        if(s.orbs[i]) n.orbit={e:s.orbs[i].e, rot:s.orbs[i].rot, k:s.orbs[i].k};
        if(looks[i]==='asteroid') n.tumble=tumble(i);
        if(ST[i]) n.station=1;
        nodes[i]=n; });
      if(s.belt) belts.push({sun:s.sun, cx:r2(cx), cy:r2(cy), r:r2(s.belt.r), w:s.belt.w,
        n:Math.floor(Math.min(400, Math.max(40, 2*PI*s.belt.r/18))), seed:Math.floor(h01('belt:'+s.sun)*1e9)});
  });
  var order=systems.map(function(s){ return s.sun; }), uo=[], lk={};
  systems.forEach(function(s){ var u=uo[uo.length-1];
    if(!u || u.unit!==s.unit){ u={unit:s.unit, label:s.label, suns:[], bbox:s.bbox.slice()}; uo.push(u); }
    u.suns.push(s.sun); u.bbox=[Math.min(u.bbox[0], s.bbox[0]), Math.min(u.bbox[1], s.bbox[1]), Math.max(u.bbox[2], s.bbox[2]), Math.max(u.bbox[3], s.bbox[3])]; });
  LOOKS.forEach(function(l){ var a=Object.keys(looks).filter(function(i){ return looks[i]===l; }).sort(); if(a.length) lk[l]=a; });
  var out={style:'orbit', spin:__SPIN__, world:{w:W, h:H}, sizes:(function(){ var z=JSON.parse(JSON.stringify(D)); z.planet_big=C.TIERS.planet[C.TIERS.planet.length-1]; z.station=C.STATION; z.tiers=JSON.parse(JSON.stringify(C.TIERS)); z.bump=bump.slice().sort(); return z; })(),
    systems:systems, units:uo, nodes:nodes, sun_links:order.slice(1).map(function(b, i){ return [order[i], b]; }), warnings:[],
    looks:lk, look_flags:JSON.parse(JSON.stringify(LF)), belts:belts, drifters:[]};
  if(GX[3]) out.core=GX[3];
  return out;
}
window._altoSolarAt=at;          /* where a body is on its orbit (r, angle, orbit {e, rot, k}) — solar_draw places comets with it */
return plan;
})();
""".replace("__SOLAR__", json.dumps(SOLAR, separators=(",", ":"))).replace("__GOLDEN__", repr(GOLDEN)).replace("__SPIN__", str(SPIN)).replace(
    "__LOOKS__", json.dumps([lk for lk, _ in LOOK_FLAGS]))



def _slim(src: str) -> str:
    """The page copy without its comments and indentation (the source keeps
    them): no string or regex in these scripts holds a slash-star."""
    import re
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return "\n".join(l.strip() for l in src.splitlines() if l.strip()) + "\n"


SOLAR_JS = _slim(SOLAR_PLAN_JS + SOLAR_JS)
SOLAR_CSS = _slim(SOLAR_CSS)
