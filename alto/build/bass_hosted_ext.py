"""The hosted Bass bundle for ONE allowlisted account on luke-alto: served only by the server gate (alto/bass/hosted.py), never published.

It is the same Bass UI bundle the gated build uses (bass_ui.ASSET), pointed at the function the generic hook asked (window.__altoExtUrl,
set by alto/cloud/ext_hook.py), plus one "Bass (beta)" button, because the page itself carries no Bass entry point. The hook runs it on the homepage only: the button
opens the Bass wizard (a new timeline from notes; its Documents library). It registers NO "Make it with Bass" route in the homepage's
"Turn into another format..." sheet (STAMP-hosted FAIL-HIDE: convert is untested on the live path from that sheet). The hook runs this as an inline script and runs it again
if the page rewrites its document, so every part here is idempotent per document."""
from __future__ import annotations

import base64
import hashlib
import json

from . import bass_ui

BUTTON_ID = "alto-bass-beta"
LABEL = "Bass (beta)"

_BUTTON = r"""(function(){var d=document;if(!d.body||d.getElementById(__ID__))return;
var st=d.createElement('style');st.id=__ID__+'-css';st.textContent='#'+__ID__+'{position:fixed;left:max(16px,env(safe-area-inset-left));bottom:calc(16px + env(safe-area-inset-bottom));z-index:8700;display:flex;align-items:center;gap:8px;height:40px;padding:0 14px 0 10px;border-radius:20px;border:1px solid var(--border,#ccc);background:var(--surface,#fff);color:var(--text,#111);font:600 14px/1 -apple-system,system-ui,sans-serif;box-shadow:0 4px 14px rgba(0,0,0,.18);cursor:pointer;-webkit-tap-highlight-color:transparent}html.rw #'+__ID__+'{position:absolute}#'+__ID__+' svg{width:16px;height:20px;color:#5b3fc4}html.alto-retro #'+__ID__+' svg{color:#d9ae55}@media print{#'+__ID__+'{display:none}}';
d.head.appendChild(st);var b=d.createElement('button');b.type='button';b.id=__ID__;b.setAttribute('aria-label',__LABEL__);b.innerHTML=__BTN_HTML__;
b.addEventListener('click',function(){if(window._altoBass)window._altoBass.open(/^\/pv\//.test(location.pathname)?'panel':'wizard')});d.body.appendChild(b);})();
"""


def bundle() -> str:
    head = "(function(){var u=window.__altoExtUrl;if(typeof u==='string'&&u)window._ALTO_BASS_BASE=u;})();\n"
    btn = (_BUTTON.replace("__ID__", json.dumps(BUTTON_ID)).replace("__LABEL__", json.dumps(LABEL))
           .replace("__BTN_HTML__", json.dumps(bass_ui.GLYPH_SMALL + "<span>" + LABEL + "</span>")))      # ONE literal: no server value
    return head + bass_ui.ASSET + "\n" + btn


def pin(js: str | None = None) -> str:
    """"sha384-<base64> <utf-8 bytes>": the integrity of the bundle the gate serves (the same form a CSP or SRI hash takes) and its exact size.
    The committed copy is alto/cloud/ext_pin.txt; tests, build_bundle.py --firebase and the function's cold start all refuse a drift."""
    b = (bundle() if js is None else js).encode("utf-8")
    return "sha384-" + base64.b64encode(hashlib.sha384(b).digest()).decode("ascii") + " " + str(len(b))
