"""Bass UI: the bundle's stylesheet (see bass_ui.py). Written against the engine's own tokens (--surface, --text, --muted, --border, --accent), so
Classic, the dark theme and Retro (whose dark tokens retro.CHROME_CSS puts in force) all work; `html.alto-retro` adds Retro's square, gold, spaced-capitals
look (black, a 1px gold rim, #d9ae55 accents, as retro.CHROME_CSS draws the other controls). Option sheet RmyVRRyAEzgyPfJskoJ1vW is the spec."""

CSS = r"""
.bs-root{--bs-dis:#5b3fc4;--bs-bg:var(--surface,#fff);--bs-ink:var(--text,#1a1a2e);--bs-mut:var(--muted,#5a5a80);--bs-bd:var(--border,#c8c8d8);--bs-acc:var(--accent,#3b4a9e);--bs-on:#fff;
  --bs-glass:var(--card-glass-bg,var(--surface,#fff));--bs-rad:12px;--bs-r:14px;--bs-ls:.01em;--bs-up:none;--bs-font:inherit;--bs-shadow:0 14px 40px rgba(20,22,40,.28);
  position:fixed;inset:0;z-index:8700;pointer-events:none;font-family:var(--bs-font);color:var(--bs-ink);font-size:13px;line-height:1.4;-webkit-text-size-adjust:100%}
.bs-root *{box-sizing:border-box}
html.alto-retro .bs-root{--bs-dis:#d9ae55;--bs-bg:#05070b;--bs-glass:#000;--bs-ink:#efe6cf;--bs-mut:#b9b2a0;--bs-bd:rgba(217,174,85,.55);--bs-acc:#d9ae55;--bs-on:#000;--bs-rad:0;--bs-r:0;--bs-ls:.12em;--bs-up:uppercase;
  --bs-font:"Avenir Next",Futura,"Century Gothic","Helvetica Neue",system-ui,sans-serif;--bs-shadow:0 0 0 4px #000}
.bs-root svg{display:block;flex:none}
.bs-g{height:var(--s,18px);width:calc(var(--s,18px) * .796)}
.bs-root .bs-gc{display:block}.bs-root .bs-gr{display:none}
html.alto-retro .bs-root .bs-gc{display:none}html.alto-retro .bs-root .bs-gr{display:block}
.bs-i{width:1em;height:1em}
.bs-scrim{position:fixed;inset:0;background:rgba(8,9,16,.42);pointer-events:auto;display:flex;align-items:center;justify-content:center;padding:20px}
html.alto-retro .bs-scrim{background:rgba(0,0,0,.62)}
.bs-win,.bs-panel{pointer-events:auto;background:var(--bs-bg);border:1px solid var(--bs-bd);border-radius:calc(var(--bs-rad) + 2px);box-shadow:var(--bs-shadow);display:flex;flex-direction:column;overflow:hidden;min-height:0}
.bs-win{width:580px;max-width:100%;height:min(520px,100%)}
.bs-panel{position:fixed;right:64px;top:112px;bottom:84px;width:330px;border-radius:var(--bs-rad)}
.bs-h{display:flex;align-items:center;gap:9px;padding:10px 12px;border-bottom:1px solid var(--bs-bd);font-size:13px;letter-spacing:var(--bs-ls);text-transform:var(--bs-up)}
.bs-h .bs-name{font-weight:600}.bs-h .bs-sp{flex:1}
.bs-h .bs-g{color:var(--bs-acc)}
.bs-b{flex:1;min-height:0;padding:14px 16px;display:flex;flex-direction:column;gap:11px;overflow:auto;-webkit-overflow-scrolling:touch}
.bs-f{padding:7px 14px;border-top:1px solid var(--bs-bd);font-size:10.5px;color:var(--bs-mut)}
.bs-act{display:flex;gap:8px;align-items:center;justify-content:flex-end;padding:0 16px 10px;flex-wrap:wrap}
.bs-act .bs-sp{flex:1}
.bs-ib{width:30px;height:30px;display:inline-grid;place-items:center;border-radius:var(--bs-r);border:1px solid transparent;background:none;color:var(--bs-mut);cursor:pointer;font-size:16px;padding:0}
.bs-ib:hover,.bs-ib:focus-visible{color:var(--bs-ink);border-color:var(--bs-bd);outline:none}
.bs-chip{display:inline-flex;align-items:center;gap:5px;height:26px;padding:0 10px;border-radius:14px;border:1px solid var(--bs-bd);background:var(--bs-glass);font-size:12px;letter-spacing:var(--bs-ls);white-space:nowrap;color:var(--bs-ink)}
html.alto-retro .bs-chip{border-radius:0}
.bs-chip .bs-coin{color:var(--bs-acc);font-size:14px}
.bs-btn{display:inline-flex;align-items:center;justify-content:center;gap:6px;min-height:34px;padding:0 15px;border-radius:var(--bs-rad);border:1px solid var(--bs-bd);background:var(--bs-glass);color:var(--bs-ink);
  font:inherit;font-size:12.5px;letter-spacing:var(--bs-ls);text-transform:var(--bs-up);cursor:pointer;-webkit-tap-highlight-color:transparent}
.bs-btn:hover{border-color:var(--bs-acc)}
.bs-btn.pri{background:var(--bs-dis);border-color:var(--bs-dis);color:var(--bs-on);font-weight:600}
.bs-btn[disabled]{opacity:.45;cursor:default}
.bs-btn.pri[disabled]{background:transparent;color:var(--bs-dis);border:1px dashed var(--bs-dis);opacity:1}   /* disabled primary: outlined, not a dim fill: text stays readable */
.bs-btn:focus-visible,.bs-inp:focus-visible,.bs-ck:focus-visible{outline:2px solid var(--bs-acc);outline-offset:2px}
.bs-dots{display:flex;align-items:center;gap:6px;font-size:10.5px;color:var(--bs-mut);letter-spacing:var(--bs-ls);text-transform:var(--bs-up)}
.bs-dots i{width:10px;height:10px;border-radius:50%;border:1.5px solid var(--bs-acc);display:block;flex:none}
html.alto-retro .bs-dots i{border-radius:0}
.bs-dots i.on{background:var(--bs-acc)}
.bs-dots u{flex:1;height:1px;background:var(--bs-bd);display:block;text-decoration:none;max-width:60px}
.bs-dots span{margin-left:6px;white-space:nowrap}
.bs-t{font-size:15px;letter-spacing:var(--bs-ls);text-transform:var(--bs-up);margin:0;font-weight:600}
.bs-lbl{font-size:10.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--bs-mut);margin:0}
.bs-inp{display:flex;align-items:center;gap:6px;border:1px solid var(--bs-bd);border-radius:var(--bs-rad);padding:0 10px;min-height:36px;background:var(--bs-glass);color:var(--bs-ink);font:inherit;font-size:13px;width:100%}
.bs-inp input{flex:1;min-width:0;border:0;background:none;color:inherit;font:inherit;outline:none;padding:7px 0}
.bs-inp input::placeholder{color:var(--bs-mut)}
.bs-inp .bs-ib{width:26px;height:26px;color:var(--bs-acc)}
.bs-grp{display:flex;flex-direction:column;gap:6px}
.bs-wrap{display:flex;flex-wrap:wrap;gap:6px}
.bs-pill{display:inline-flex;align-items:center;gap:6px;min-height:28px;padding:0 6px 0 10px;border-radius:15px;border:1px solid var(--bs-bd);background:var(--bs-glass);font-size:12px}
html.alto-retro .bs-pill{border-radius:0}
.bs-pill .bs-dot{width:7px;height:7px;border-radius:50%;background:var(--bs-acc);flex:none}
.bs-pill .bs-dot.b{background:#4f8fd6}.bs-pill .bs-dot.g{background:#58a56b}
html.alto-retro .bs-pill .bs-dot{border-radius:0;background:var(--bs-acc)}
.bs-pill button{width:20px;height:20px;border:0;background:none;color:var(--bs-mut);padding:0;cursor:pointer;display:grid;place-items:center;font-size:11px;border-radius:50%}
.bs-pill button:hover{color:var(--bs-ink)}
.bs-pill.add{padding:0 10px;color:var(--bs-mut);cursor:pointer;border-style:dashed;background:none;font:inherit;font-size:12px}
.bs-pill.add:hover{color:var(--bs-ink);border-color:var(--bs-acc)}
.bs-pill input{border:0;background:none;color:inherit;font:inherit;width:110px;outline:none}
.bs-drop{border:1.5px dashed var(--bs-acc);border-radius:var(--bs-rad);padding:22px 14px;display:flex;flex-direction:column;align-items:center;gap:5px;color:var(--bs-mut);text-align:center;cursor:pointer;font-size:12.5px}
.bs-ddrive{margin-top:8px}.bs-ddrive svg{margin-right:6px}.bs-ddh{display:block;margin:4px 0 0}
html.mobile .bs-ddrive,html.mobile .bs-ddh{display:none !important}
.bs-drop.over{background:color-mix(in srgb,var(--bs-acc) 10%,transparent)}
.bs-drop svg{font-size:26px;color:var(--bs-acc)}
.bs-drop b{color:var(--bs-ink);font-weight:600;font-size:13.5px}
.bs-paste{display:block;box-sizing:border-box;width:100%;height:72px;min-height:72px;resize:vertical;border:1px solid var(--bs-bd);border-radius:var(--bs-rad);padding:9px 10px;background:var(--bs-glass);color:var(--bs-ink);font:inherit;font-size:16px;line-height:1.4;outline:none}   /* (16px: iOS does not zoom the page on focus) */
.bs-pg{flex:none;padding-bottom:8px}   /* (the step body scrolls; the field is never squeezed or cut flat) */
.bs-paste::placeholder{color:var(--bs-mut)}
.bs-paste:focus-visible{outline:2px solid var(--bs-acc);outline-offset:2px}
.bs-row{display:flex;align-items:center;gap:8px;min-height:34px;border:1px solid var(--bs-bd);border-radius:calc(var(--bs-rad) - 3px);padding:0 6px 0 10px;font-size:12.5px;background:var(--bs-glass)}
.bs-row svg{color:var(--bs-mut);font-size:14px}
.bs-row .bs-sp{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.bs-row small{color:var(--bs-mut)}
.bs-ckr{display:flex;gap:9px;align-items:flex-start;font-size:12px;color:var(--bs-mut);cursor:pointer}
.bs-ck{appearance:none;-webkit-appearance:none;width:18px;height:18px;border:1.5px solid var(--bs-acc);border-radius:4px;flex:none;margin:1px 0 0;display:grid;place-items:center;cursor:pointer;background:none}
html.alto-retro .bs-ck{border-radius:0}
.bs-ck:checked{background:var(--bs-acc)}
.bs-ck:checked::after{content:'';width:9px;height:5px;border-left:2px solid var(--bs-on);border-bottom:2px solid var(--bs-on);transform:rotate(-45deg) translate(1px,-1px)}
.bs-step{display:flex;align-items:center;gap:9px;font-size:12.5px;color:var(--bs-mut)}
.bs-step i{width:20px;height:20px;border-radius:50%;border:1px solid var(--bs-bd);display:grid;place-items:center;font-style:normal;font-size:10px;flex:none}
html.alto-retro .bs-step i{border-radius:0}
.bs-step.done i{background:var(--bs-acc);color:var(--bs-on);border-color:var(--bs-acc)}
.bs-step.cur{color:var(--bs-ink);font-weight:600}.bs-step.cur i{border-color:var(--bs-acc);color:var(--bs-acc)}
.bs-step svg{font-size:12px}
.bs-bar{height:6px;background:var(--bs-bd);border-radius:3px;overflow:hidden}
html.alto-retro .bs-bar{border-radius:0}
.bs-bar b{display:block;height:100%;background:var(--bs-acc);transition:width .3s}
.bs-alert{display:flex;gap:11px;align-items:flex-start}
.bs-alert>svg{font-size:22px;color:var(--bs-acc);margin-top:1px}
.bs-alert b{display:block;font-weight:600;font-size:13.5px}
.bs-alert p{margin:3px 0 0;color:var(--bs-mut);font-size:12px}
.bs-log{flex:1;min-height:0;display:flex;flex-direction:column;gap:8px;overflow:auto;padding:2px 0}
.bs-msg{max-width:88%;padding:7px 10px;border-radius:calc(var(--bs-rad) - 2px);font-size:12.5px;border:1px solid var(--bs-bd);overflow-wrap:anywhere}
.bs-msg.u{align-self:flex-end;background:var(--bs-dis);color:var(--bs-on);border-color:var(--bs-dis)}
.bs-msg.a{align-self:flex-start;background:var(--bs-glass)}
.bs-msg.a small{display:block;color:var(--bs-mut);font-size:11px;margin-top:2px}
.bs-typing{align-self:flex-start;display:flex;gap:4px;padding:8px 10px}
.bs-typing i{width:6px;height:6px;border-radius:50%;background:var(--bs-mut);animation:bs-b 1s infinite ease-in-out}
.bs-typing i:nth-child(2){animation-delay:.15s}.bs-typing i:nth-child(3){animation-delay:.3s}
@keyframes bs-b{0%,80%,100%{opacity:.25}40%{opacity:1}}
.bs-toast{position:fixed;left:50%;bottom:90px;transform:translateX(-50%);z-index:8800;max-width:min(420px,90vw);padding:9px 14px;border-radius:var(--bs-rad);background:var(--bs-bg);color:var(--bs-ink);border:1px solid var(--bs-bd);box-shadow:var(--bs-shadow);pointer-events:none;font-size:12.5px}
.bs-note{font-size:11px;color:var(--bs-mut);margin:0}
.bs-dev{position:fixed;left:8px;top:8px;z-index:8800;pointer-events:auto;background:var(--bs-bg);border:1px solid var(--bs-bd);padding:4px 6px;font-size:11px;color:var(--bs-mut);display:none}
@media (max-width:640px){
  .bs-scrim{padding:0;align-items:stretch}
  .bs-win{width:100%;height:100%;border-radius:0;border:0}
  .bs-panel{left:0;right:0;top:auto;bottom:0;width:auto;height:min(52vh,460px);border-radius:var(--bs-rad) var(--bs-rad) 0 0;padding-bottom:env(safe-area-inset-bottom,0px)}
  .bs-win{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}
  .bs-toast{bottom:calc(30px + env(safe-area-inset-bottom,0px))}
  .bs-paste{height:120px;min-height:96px}   /* (a phone's step is the whole screen; the desktop window is 520px tall, so there the whole field has to fit above Next) */
  .bs-btn,.bs-ib,.bs-pill button{min-height:40px}.bs-ib{width:40px;height:40px}.bs-pill button{width:32px;height:32px}
  .bs-act{flex-wrap:nowrap}
}
html.mobile .bs-panel{left:0;right:0;top:auto;bottom:0;width:auto;height:min(52vh,460px);border-radius:var(--bs-rad) var(--bs-rad) 0 0}
/* embedded in the New window (alto/engine/home_template.html #nt-modal): no scrim, window or panel of its own */
.bs-emb{position:static;display:block;pointer-events:auto;--bs-acc:var(--bs-dis)}
.bs-ew{display:flex;flex-direction:column;min-height:0}
.bs-emb .bs-b{padding:2px 0 8px;overflow:visible}
.bs-emb .bs-act{padding:0 0 4px}
.bs-emb .bs-f{padding:7px 0 0;border-top:1px solid var(--bs-bd);margin-top:8px}
.bs-eh{display:flex;justify-content:flex-end;margin:-2px 0 6px}
.bs-bal{font-size:11px;letter-spacing:.04em;color:var(--bs-mut)}
.bs-hint{font-size:11.5px;color:var(--bs-mut);margin:0;line-height:1.45}
.bs-pill.pl{padding:0 8px 0 10px;cursor:pointer;font:inherit;font-size:12px;color:var(--bs-ink)}
.bs-pill.pl-off{color:var(--bs-mut)}
.bs-pill.pl-on{border:1.5px solid var(--bs-dis)}
.bs-pill .bs-dot.p{background:#a86bd1}
.bs-pill.pl svg{width:11px;height:11px}
html.alto-retro .bs-pill.pl-on{border-color:var(--bs-dis)}
/* the window styles its own inputs and labels (#nt-modal input / label): the Bass steps put theirs back */
#nt-modal .bs-emb input{width:auto;height:auto;margin:0;padding:0;border-radius:0;font-size:inherit;border:0;background:none;outline:none}
#nt-modal .bs-emb .bs-inp input{flex:1;min-width:0;width:auto;padding:7px 0}
#nt-modal .bs-emb .bs-pill input{width:110px}
#nt-modal .bs-emb input[type=checkbox]{-webkit-appearance:checkbox;appearance:auto;width:16px;height:16px;flex:none;margin:1px 0 0;accent-color:var(--bs-dis)}
#nt-modal .bs-emb label{margin:0;letter-spacing:normal;text-transform:none;font-size:12px;color:var(--bs-mut)}
#nt-modal .bs-emb .bs-drop{display:flex;font-size:12.5px}
#nt-modal .bs-emb .bs-ckr{display:flex}
/* the first-use notice: a sheet inside the Bass window or panel, not a window of its own */
.bs-win,.bs-ew{position:relative}
.bs-nw{min-height:300px}
.bs-sheet{position:absolute;inset:0;z-index:5;background:var(--bs-bg);display:flex;align-items:flex-start;justify-content:center;padding:18px;border-radius:inherit;overflow:auto;pointer-events:auto}
.bs-sheet-in{width:100%;max-width:440px;display:flex;flex-direction:column;gap:12px}
.bs-np{margin:0;font-size:13.5px;line-height:1.5;color:var(--bs-ink)}
.bs-link{color:var(--bs-dis);text-decoration:underline;text-underline-offset:2px}
html.dark:not(.alto-retro) .bs-link{color:#b9a9ff}   /* Classic dark: the indigo is too dim on the dark sheet; this lavender is AA (about 8:1) */
.bs-nact{display:flex;gap:8px;align-items:center;justify-content:flex-end;flex-wrap:wrap;padding-top:4px}
.bs-sheet .bs-btn{min-height:44px;padding:0 18px}
.bs-win>.bs-sheet,.bs-panel>.bs-sheet{top:46px}
/* Conversation sharing sheet (Art SPEC-optin-step.md): equal buttons, No thanks first; desktop max 480; phone a bottom sheet; Retro = black, cream, gold. The promise line and the two buttons are pinned at the bottom while the text scrolls above them. */
.bs-share .bs-sheet-in{max-width:480px;position:relative}
.bs-share .bs-sht{font-size:20px;font-weight:600;margin:0;padding-right:48px;outline:none}
.bs-shx{position:absolute;top:-4px;right:-6px;width:44px;height:44px}
.bs-sharing .bs-h [data-a="close"]{visibility:hidden}
.bs-share .bs-np{font-size:15px;line-height:1.5}
.bs-share .bs-link{font-size:14px}
html.dark:not(.alto-retro) .bs-share .bs-link{color:#b9a9ff}
.bs-sact{display:flex;flex-direction:column;align-items:stretch;gap:8px;position:sticky;bottom:-18px;margin-bottom:-18px;padding:10px 0 18px;background:var(--bs-bg)}
.bs-sact::before{content:"";position:absolute;left:0;right:0;top:-26px;height:26px;background:linear-gradient(transparent,var(--bs-bg));pointer-events:none}   /* scroll cue: the text fades under the pinned choice */
.bs-promise{margin:0;font-weight:600}
.bs-sbtns{display:flex;gap:8px}
.bs-sbtn{flex:1 1 0;min-width:0;min-height:44px;box-sizing:border-box;border-width:2px;font-size:15px;font-weight:600;line-height:1.15;padding:6px 10px}
.bs-sbtn:not(.bs-syes){border:2px solid var(--bs-ink);background:var(--bs-glass);color:var(--bs-ink)}
.bs-syes{background:#5b3fc4;border-color:#5b3fc4;color:#fff}
.bs-sbtn:focus-visible{outline:3px solid #5b3fc4;outline-offset:3px}
html.dark:not(.alto-retro) .bs-sbtn:focus-visible{outline-color:#b9a9ff}
html.alto-retro .bs-sbtn{border-radius:0;border:1.5px solid #d9ae55;background:#000;color:#d9ae55;letter-spacing:.04em;padding:6px 6px}
html.alto-retro .bs-syes{background:#d9ae55;color:#000}
html.alto-retro .bs-sbtn:focus-visible{outline-color:#fff}
.bs-shr{display:flex;flex-wrap:wrap;gap:8px 12px;align-items:center;padding:8px 14px 0;font-size:13.5px;color:var(--bs-ink)}
.bs-shr .bs-sbtn{flex:0 0 auto;min-width:112px}
.bs-shn{flex:1 0 100%;font-size:12.5px;color:var(--bs-mut)}
@media (max-width:640px){
  .bs-share{flex-direction:column;align-items:stretch;justify-content:flex-start;padding:16px max(16px,env(safe-area-inset-right,0px)) max(16px,env(safe-area-inset-bottom,0px)) max(16px,env(safe-area-inset-left,0px))}
  .bs-share .bs-sheet-in{max-width:none;margin-top:auto}      /* bottom sheet that still scrolls from its top when the text is long */
  .bs-sact{bottom:calc(-1 * max(16px,env(safe-area-inset-bottom,0px)));margin-bottom:calc(-1 * max(16px,env(safe-area-inset-bottom,0px)));padding:10px 0 max(16px,env(safe-area-inset-bottom,0px))}
  .bs-sbtns{flex-direction:column;gap:10px}.bs-sbtns .bs-sbtn{flex:0 0 auto;width:100%}
}
@media print{.bs-root,.bs-toast{display:none !important}}
"""
