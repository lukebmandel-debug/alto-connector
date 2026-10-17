"""The toy fleet's rules (1.9.99): the grey moulded plastic of the toy warships and bases, the old art of the other boats (tall ships, small craft), the
armed-weapon bar and the glow of the armed toy. They travel with the hosted script (palace_fleet_asset.py), not in the page."""
from __future__ import annotations

_B = ".pal-svg .pl-boat"

FLEET_CSS = (r"""
  @B{pointer-events:none;}
  @B.wp{pointer-events:all;cursor:pointer;}
  @B .bb-tur{fill:#69748c;stroke:#232c44;stroke-width:1.6;vector-effect:non-scaling-stroke;}
  @B .bb-wall{stroke:#8a919d;stroke-width:.8;vector-effect:non-scaling-stroke;}
  @B .bb-plastic{fill:#d2d6dc;stroke:#8f96a2;stroke-width:1.4;vector-effect:non-scaling-stroke;}
  @B .bb-pdeck{fill:#cbd0d7;stroke:#aab0ba;stroke-width:1;vector-effect:non-scaling-stroke;}
  @B .bb-gloss{fill:rgba(255,255,255,.4);stroke:none;}
  @B .bb-eng{stroke:#a3a9b4;stroke-width:1;stroke-linecap:round;vector-effect:non-scaling-stroke;}
  @B .bb-m{fill:#dde1e6;stroke:#a0a7b2;stroke-width:1;vector-effect:non-scaling-stroke;} @B .bb-ms{fill:rgba(60,68,86,.3);stroke:none;}
  @B .bb-hole{fill:#a7adb8;stroke:#868d99;stroke-width:1;vector-effect:non-scaling-stroke;} @B .bb-hole2{fill:#c4c9d1;} @B .bb-hl{fill:none;stroke:#f1f3f6;stroke-width:1.6;stroke-linecap:round;}
  @B .bb-barrel-o{stroke:#8d94a0;stroke-width:5.2;stroke-linecap:round;} @B .bb-barrel{stroke:#d7dbe1;stroke-width:3.4;stroke-linecap:round;}
  html.dark @B .bb-plastic{fill:#9aa1ad;} html.dark @B .bb-pdeck{fill:#949ba7;} html.dark @B .bb-m{fill:#a8afbb;} html.dark @B .bb-hole{fill:#7c8390;} html.dark @B .bb-hole2{fill:#8f96a2;}
  @B .bb-barrel{stroke:#4a5160;stroke-width:3.4;stroke-linecap:round;} @B .bb-bore{fill:#05070d;}
  @B .bb-pad{fill:none;stroke:rgba(255,255,255,.65);stroke-width:1.6;stroke-dasharray:5 4;vector-effect:non-scaling-stroke;}
  @B .fl-run{fill:#7a8190;stroke:#59606e;stroke-width:1;vector-effect:non-scaling-stroke;} @B .fl-dash{stroke:rgba(255,255,255,.85);stroke-width:1.3;stroke-dasharray:7 6;vector-effect:non-scaling-stroke;}
  @B .fl-el{fill:#c0c5cd;stroke:#9097a4;stroke-width:1;vector-effect:non-scaling-stroke;} @B .fl-sh{fill:rgba(24,30,46,.22);stroke:none;}
  @B .fl-gr{fill:#aeb8a6;stroke:#8d977f;stroke-width:1.4;vector-effect:non-scaling-stroke;} @B .fl-gr2{fill:#a3ad9a;stroke:#8d977f;stroke-width:1;vector-effect:non-scaling-stroke;}
  html.dark @B .fl-gr{fill:#7f8a76;} html.dark @B .fl-gr2{fill:#78836f;} html.dark @B .fl-run{fill:#565d6b;}
  @B .fl-tk{fill:#c2c8b6;stroke:#8d977f;stroke-width:1;vector-effect:non-scaling-stroke;}
  @B.armed .bt-foam{fill:rgba(255,120,80,.5);}
  @B.armed .bb-plastic,@B.armed .fl-gr{stroke:#ff5a3c;stroke-width:3;}
  @B.armed{filter:drop-shadow(0 0 7px rgba(255,70,40,.75));}
  @B .bt-foam{fill:rgba(255,255,255,.62);stroke:none;}
  @B .bt-bowwave{fill:none;stroke:rgba(255,255,255,.7);stroke-width:1.6;stroke-linecap:round;vector-effect:non-scaling-stroke;}
  @B .bt-hull{fill:#4c5b78;stroke:#2b3652;stroke-width:1.3;vector-effect:non-scaling-stroke;}
  @B.tall .bt-hull{fill:#3f3a38;}
  @B .bt-boot{fill:none;stroke:#9c3f3a;stroke-width:1.6;stroke-opacity:.85;vector-effect:non-scaling-stroke;}
  @B .bt-deck{fill:#a9b4c8;stroke:#74829f;stroke-width:1;vector-effect:non-scaling-stroke;}
  @B .bt-deck.wood{fill:#cdb88f;stroke:#8d7852;}
  @B .bt-cl{stroke:rgba(40,52,80,.35);stroke-width:1;vector-effect:non-scaling-stroke;}
  @B .bt-plank{stroke:rgba(110,86,50,.45);stroke-width:1;vector-effect:non-scaling-stroke;}
  @B .bt-mast{stroke:#4a3f36;stroke-width:2;stroke-linecap:round;vector-effect:non-scaling-stroke;}
  @B .bt-yard{stroke:#4a3f36;stroke-width:1.6;stroke-linecap:round;vector-effect:non-scaling-stroke;}
  @B .bt-sail{fill:rgba(250,247,238,.8);stroke:rgba(120,108,88,.55);stroke-width:1;vector-effect:non-scaling-stroke;}
  @B .bt-fb{fill:#8e9bb3;stroke:#52607e;stroke-width:1;vector-effect:non-scaling-stroke;} @B .bt-ft{fill:#c5cddb;stroke:#52607e;stroke-width:1;vector-effect:non-scaling-stroke;} @B .bt-fh{fill:#2f3850;}
  html.dark @B .bt-foam{fill:rgba(255,255,255,.2);} html.dark @B .bt-deck{fill:#6f7b96;} html.dark @B .bt-deck.wood{fill:#8b7a58;} html.dark @B .bt-sail{fill:rgba(230,226,214,.7);}
  .pal-svg .pl-boat-l text{font-size:11px;font-weight:800;fill:var(--text,#222);stroke:var(--pal-halo,#fff);stroke-width:3.2px;paint-order:stroke;stroke-linejoin:round;}
  .pal-svg.far .pl-boat-l{display:none;}
  html.fx-armed .pal-svg .pl-lmb .lm-art{pointer-events:all;}                                       /* a tower's body, not only its card, can be hit */
  html.fx-armed #world .node,html.fx-armed .pal-svg .pl-lmb,html.fx-armed #world .node .nb3d *{cursor:crosshair !important;}
  #pal-fxbar{position:fixed;left:50%;top:112px;transform:translateX(-50%);z-index:312;display:none;padding:7px 15px;border-radius:999px;font-size:12px;font-weight:650;color:var(--text);
    background:var(--panel-glass-bg,var(--surface));-webkit-backdrop-filter:blur(24px) saturate(185%);backdrop-filter:blur(24px) saturate(185%);border:1px solid #ff7a3c;box-shadow:0 12px 32px var(--node-hover-shadow);}
  #pal-fxbar .fx-x{margin:-3px -9px -3px 10px;width:24px;height:24px;border-radius:50%;border:1px solid color-mix(in srgb,var(--text) 22%,transparent);background:transparent;color:var(--text);font:inherit;font-size:16px;line-height:1;cursor:pointer;padding:0;vertical-align:middle;}
  #pal-fxbar .fx-x:hover{background:#ff7a3c;border-color:#ff7a3c;color:#fff;}
  html.fx-armed #pal-fxbar{display:block;} html.mobile #pal-fxbar{display:none !important;}
  .node.nb-ruin .node-card{opacity:0 !important;pointer-events:none;}
  .pal-svg .pl-fx{pointer-events:none;}
""").replace("@B", _B)
