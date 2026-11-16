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
var st=d.createElement('style');st.id='alto-bass-css';st.textContent='.nt-tab[data-tab="bass"].on{border-color:#8b6cf0;box-shadow:inset 0 0 0 1px #8b6cf0;background:linear-gradient(color-mix(in srgb,#8b6cf0 14%,transparent),color-mix(in srgb,#8b6cf0 14%,transparent)),var(--surface,var(--bg))}.nt-pane[data-p="bass"]{border-color:color-mix(in srgb,#8b6cf0 60%,transparent)}#nt-bass{background:#5b3fc4}@media print{.nt-tab[data-tab="bass"]{display:none}}';d.head.appendChild(st);
var tabs=d.getElementById('nt-tabs'),c=d.getElementById('nt-claude');
if(tabs&&c&&!d.getElementById('nt-bass')){
var t=d.createElement('button');t.type='button';t.className='nt-tab';t.setAttribute('role','tab');t.setAttribute('aria-selected','false');t.dataset.tab='bass';
t.innerHTML=TABHTML;tabs.insertBefore(t,tabs.firstChild);
var p=d.createElement('div');p.className='nt-pane nt-keep';p.dataset.p='bass';p.hidden=true;
p.innerHTML='<p><b>Build it here with Bass</b></p><p class="nt-pn">You upload your notes or readings. Bass builds the project here in Alto. No Claude plan needed; uses credits.</p>';
var b=d.createElement('button');b.type='button';b.id='nt-bass';b.className='nt-claude';b.textContent='Upload notes';
b.addEventListener('click',function(){var x=d.getElementById('nt-cancel');if(x)x.click();if(window._altoBass)window._altoBass.open('wizard');});
p.appendChild(b);c.parentNode.parentNode.insertBefore(p,c.parentNode);
window._altoNtFirst='bass';}
window._altoStudyPlanMake=function(rec){if(!rec||typeof rec.tid!=='string'||!rec.tid||!window._altoBass)return false;window._altoBass.open('panel',{tid:rec.tid,plan:true});return true;};
})();
"""


def _wire() -> str:
    tab = bass_ui.GLYPH_SMALL.replace("<svg ", '<svg width="20" height="25" ') + "<span>Bass</span>"
    assert "'" not in tab and "\\" not in tab
    return _WIRE.replace("TABHTML", "'" + tab + "'")                         # one literal, like every other markup the bundle sets


def bundle() -> str:
    head = "(function(){var u=window.__altoExtUrl;if(typeof u==='string'&&u)window._ALTO_BASS_BASE=u;})();\n"
    return head + bass_ui.ASSET + "\n" + _wire()


def pin(js: str | None = None) -> str:
    """"sha384-<base64> <utf-8 bytes>": the integrity of the bundle the gate serves (the same form a CSP or SRI hash takes) and its exact size.
    The committed copy is alto/cloud/ext_pin.txt; tests, build_bundle.py --firebase and the function's cold start all refuse a drift."""
    b = (bundle() if js is None else js).encode("utf-8")
    return "sha384-" + base64.b64encode(hashlib.sha384(b).digest()).decode("ascii") + " " + str(len(b))
