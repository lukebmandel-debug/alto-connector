"""The hosted Bass bundle for ONE allowlisted account on luke-alto: served only by the server gate (alto/bass/hosted.py), never published.

It is the same Bass UI bundle the gated build uses (bass_ui.ASSET), pointed at the function the generic hook asked (window.__altoExtUrl,
set by alto/cloud/ext_hook.py), plus two entry points in the page's own places (no always-visible button): a "Build it with Bass" choice in the NEW dialog (the wizard) and "+ Make a study plan" on a card (window._altoStudyPlanMake, the panel in plan mode). The hook runs it on the homepage only. It registers NO "Make it with Bass" route in the homepage's
"Turn into another format..." sheet (STAMP-hosted FAIL-HIDE: convert is untested on the live path from that sheet). The hook runs this as an inline script and runs it again
if the page rewrites its document, so every part here is idempotent per document."""
from __future__ import annotations

import base64
import hashlib
import json

from . import bass_ui

BUTTON_ID = "nt-bass"          # the Bass choice in the NEW dialog (no always-visible button)
LABEL = "Bass"

_WIRE = r"""(function(){var d=document;if(d.__altoBassWired)return;d.__altoBassWired=1;
var P='.nt-kinds:not(.nt-sck) .nt-kind[data-kind="palace"][aria-pressed="true"]';
var st=d.createElement('style');st.id='alto-bass-css';st.textContent='#nt-bass{margin-bottom:8px}#nt-modal:has('+P+') #nt-bass{display:none}@media print{#nt-bass{display:none}}';d.head.appendChild(st);
var c=d.getElementById('nt-claude');
if(c&&!d.getElementById('nt-bass')){var b=d.createElement('button');b.type='button';b.id='nt-bass';b.className=c.className;
b.appendChild(d.createTextNode('Build it with Bass from my notes'));var sm=d.createElement('small');sm.textContent='Bass builds the cards, then you adjust by hand.';b.appendChild(sm);
b.addEventListener('click',function(){var x=d.getElementById('nt-cancel');if(x)x.click();if(window._altoBass)window._altoBass.open('wizard');});
c.parentNode.insertBefore(b,c);}
window._altoStudyPlanMake=function(rec){if(!rec||typeof rec.tid!=='string'||!rec.tid||!window._altoBass)return false;window._altoBass.open('panel',{tid:rec.tid,plan:true});return true;};
})();
"""


def bundle() -> str:
    head = "(function(){var u=window.__altoExtUrl;if(typeof u==='string'&&u)window._ALTO_BASS_BASE=u;})();\n"
    return head + bass_ui.ASSET + "\n" + _WIRE


def pin(js: str | None = None) -> str:
    """"sha384-<base64> <utf-8 bytes>": the integrity of the bundle the gate serves (the same form a CSP or SRI hash takes) and its exact size.
    The committed copy is alto/cloud/ext_pin.txt; tests, build_bundle.py --firebase and the function's cold start all refuse a drift."""
    b = (bundle() if js is None else js).encode("utf-8")
    return "sha384-" + base64.b64encode(hashlib.sha384(b).digest()).decode("ascii") + " " + str(len(b))
