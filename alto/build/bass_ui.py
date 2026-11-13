"""Bass: the wizard UI (Upload, Review, Build, Edit), the edit panel and the credits meter: Alto's built-in path for people without a Claude plan.

GATED OFF. Everything here does nothing unless the build is made with ALTO_BASS_UI=1 (`enabled()`): a normal build is byte-for-byte what it was.
When on, a page carries only what must be inline: on the homepage, the first tile ("New with Bass", dashed, the balance as a small line of text), and on
a timeline, a Bass button (the bass-clef glyph) in the Edit pill. Both call `window._altoBassOpen(mode)`, a ~700 byte loader that fetches the hosted
bundle /bass/alto-bass-<hash>.js (palace_assets.ASSETS, like /retro/, /phone/ and /alto-bglib.js) on the FIRST click, so the ~976 KB private page
does not grow by the UI. The bundle (bass_ui_js.py, bass_ui_css.py) holds the whole UI and, until `window._ALTO_BASS_BASE` names a URL, an in-page
SIMULATOR of the backend contract (docs/bass-api.md on branch alto-bass): no network, no key, no Anthropic call. The real backend swaps in by
setting that one base. `#bass=<state>` in the page's address opens the UI in any state (upload, review, estimate, build, built, edit, nocredits, busy,
paused, offtopic, refused, capped, error, stopped) for screenshots and tests.

The glyph is Luke's pick A (ORG/bass-glyph/assets/bass-a-*): the small currentColor cut for buttons, the gradient mark for Classic headers and the tile,
flat gold for Retro. Its viewBox is centred on its bounding box including the dots (a test measures it)."""
from __future__ import annotations

import hashlib as _hashlib
import json as _json
import os
import re as _re

ENV = "ALTO_BASS_UI"
FOLDER = "bass"

# ── the glyph (bass-a-*.svg, ORG/bass-glyph/assets), viewBox "26 15 78 98" ──
_CLEF = ('<path d="M58 104.5 H68 Q84 104.5 84 88.5 V39 Q84 23.5 68.5 23.5 H56 Q41.0 23.5 41.0 37 V43.1"/>'
         '<path transform="rotate(-90 41.0 43.1)" d="M41.0 43.1 A3.6 3.6 0 1 0 44.2 46.9 A1.5 1.5 0 0 0 42.2 46.6"/>')
GLYPH_SMALL = ('<svg viewBox="26 15 78 98" aria-hidden="true" focusable="false"><g transform="translate(-6 0)"><g fill="none" stroke="currentColor" stroke-linecap="round" '
               'stroke-linejoin="round"><g stroke-width="10.2">' + _CLEF + '</g></g><circle cx="100.4" cy="33.25" r="5.6" fill="currentColor"/>'
               '<circle cx="100.4" cy="53.75" r="5.6" fill="currentColor"/></g></svg>')
GLYPH_MARK = ('<svg viewBox="26 15 78 98" aria-hidden="true" focusable="false"><defs><linearGradient id="bsera" gradientUnits="userSpaceOnUse" x1="36" y1="22" x2="100" y2="106">'
              '<stop offset="0%" stop-color="#ff6f91"/><stop offset="30%" stop-color="#b06ef0"/><stop offset="56%" stop-color="#5b8cff"/><stop offset="80%" stop-color="#28b9c4"/>'
              '<stop offset="100%" stop-color="#39dc84"/></linearGradient></defs><g transform="translate(-6 0)"><g fill="none" stroke="url(#bsera)" stroke-linecap="round" '
              'stroke-linejoin="round"><g stroke-width="7.2">' + _CLEF + '</g></g><circle cx="96.5" cy="33.25" r="4.7" fill="url(#bsera)"/><circle cx="96.5" cy="53.75" r="4.7" fill="url(#bsera)"/></g></svg>')
GLYPH_RETRO = ('<svg viewBox="26 15 78 98" aria-hidden="true" focusable="false"><g transform="translate(-6 0)"><g fill="none" stroke="#d9ae55" stroke-linecap="round" '
               'stroke-linejoin="round"><g stroke-width="7.2">' + _CLEF + '</g></g><circle cx="96.5" cy="33.25" r="4.7" fill="#d9ae55"/>'
               '<circle cx="96.5" cy="53.75" r="4.7" fill="#d9ae55"/></g></svg>')


def enabled() -> bool:
    """True only for a build made with ALTO_BASS_UI=1."""
    return os.environ.get(ENV) == "1"


# The beta (Luke, 2026-10-30): testers are unpaid and allowlisted, so credits are a FREE allowance from Luke's pool. Nothing is sold: no
# "Add credits", no purchase toast, no price in dollars; the meter reads "Beta credits remaining: N"; a used-up share or pool shows the
# friendly "Beta credits used up" message and nothing more is sent. Turning this off is a deliberate change (a paid launch), not a flag.
BETA = True
# The proxy's URL (deploy/bass-proxy). Empty (the default, and every test) = the in-page simulator. IT sets it for a build at deploy
# time (ALTO_BASS_BASE); with it set, the Bass buttons stay hidden until the proxy says this signed-in account is on the allowlist.
BASE_ENV = "ALTO_BASS_BASE"


def base_url() -> str:
    return os.environ.get(BASE_ENV, "").strip()


NOTICE_VERSION = "1"                                                  # bump when the first-use notice's text changes: it shows again
PRIVACY_URL = "/privacy"                                              # placeholder: the Privacy Policy page (bench-mobile-1); one place to change


def _slim(src: str) -> str:
    src = _re.sub(r"/\*.*?\*/", "", src, flags=_re.S)
    return "\n".join(t for t in (ln.strip() for ln in src.split("\n")) if t)


def _bundle() -> str:
    from .bass_ui_css import CSS
    from .bass_ui_docs import DOCS_CSS, DOCS_JS
    from .bass_ui_js import JS
    CSS = CSS + DOCS_CSS
    js = (JS.replace("__DOCS__", DOCS_JS).replace("__BETA__", "true" if BETA else "false").replace("__NOTICE_V__", NOTICE_VERSION).replace("__PRIVACY_URL__", PRIVACY_URL).replace("__GL_MARK__", GLYPH_MARK).replace("__GL_RETRO__", GLYPH_RETRO).replace("__GL_SMALL__", GLYPH_SMALL))
    return ("(function(){var s=document.createElement('style');s.id='alto-bass-css';s.textContent=" + _json.dumps(_slim(CSS)) + ";document.head.appendChild(s);})();\n" + _slim(js))


ASSET = _bundle()
V = _hashlib.sha256(ASSET.encode("utf-8")).hexdigest()[:10]
PATH = f"/{FOLDER}/alto-bass-{V}.js"
LABEL = "Bass"                                                         # the one name: tooltips, aria-labels, Info


def bass_asset() -> tuple[str, str]:
    """(file name under /bass/, the script) for the site (palace_assets.ASSETS)."""
    return PATH.rsplit("/", 1)[1], ASSET


# ── what a page carries (all of it only when enabled()) ──
# The loader: fetch the bundle on first use. `#bass=<state>` in the address opens the UI at once (for screenshots and tests).
_LOADER = r"""window._altoBassOpen=function(m){var b=window._altoBass;if(b)return b.open(m);var s=document.createElement('script');s.src=__PATH__;
s.onload=function(){if(window._altoBass)window._altoBass.open(m)};
s.onerror=function(){var t=document.createElement('div');t.setAttribute('style','position:fixed;left:50%;bottom:90px;transform:translateX(-50%);z-index:8800;padding:9px 14px;border-radius:10px;background:var(--surface,#fff);color:var(--text,#111);border:1px solid var(--border,#ccc);font-size:13px');t.textContent='Bass is not available here.';document.body.appendChild(t);setTimeout(function(){t.remove()},3000)};
document.head.appendChild(s)};
__AUTO__"""
# The allowlist gate for the inline buttons (only with a proxy URL): hidden until the proxy's free `balance` says this signed-in account may
# use Bass (anything but bass_off), remembered per account for 6 hours. UI only: the proxy refuses a non-allowlisted account on every call.
_GATE = r"""(function(){var B=window._ALTO_BASS_BASE,R=document.documentElement;if(!B||window._altoBassGate)return;window._altoBassGate=1;R.classList.add('alto-bass-off');
function k(u){return 'alto-bass-ok-'+u.uid}
function chk(){var c=window.AltoCloud,u=c&&c.user,v=null;if(!u||!u.getIdToken){R.classList.add('alto-bass-off');return}try{v=JSON.parse(localStorage.getItem(k(u)))}catch(e){}
if(v&&Date.now()-v.t<216e5){R.classList.toggle('alto-bass-off',!v.ok);return}
u.getIdToken().then(function(t){return fetch(B,{method:'POST',headers:{'content-type':'application/json','authorization':'Bearer '+t},body:'{"action":"balance","args":{}}'})}).then(function(r){return r.ok?r.json():null}).then(function(j){if(!j)return;var ok=j.code!=='bass_off';R.classList.toggle('alto-bass-off',!ok);try{localStorage.setItem(k(u),JSON.stringify({ok:ok,t:Date.now()}))}catch(e){}}).catch(function(){})}
addEventListener('alto-auth',chk);chk()})();
"""
_AUTO = "if(/[#&]bass=/.test(location.hash))addEventListener('load',function(){window._altoBassOpen('__MODE__')});"


def hash_reads() -> int:
    """How many `location.hash` reads the Bass loader adds to a timeline page (0 when the UI is not built in). single_file counts every
    `location.hash` in a page to swap it for `__altoHash()` (a srcdoc page has no real hash), so it must know about these too."""
    return pill_script().count("location.hash") if enabled() else 0


def loader_js(mode: str, auto: bool = True) -> str:
    base = base_url()
    head = ("window._ALTO_BASS_BASE=window._ALTO_BASS_BASE||" + _json.dumps(base) + ";\n" + _GATE) if base else ""
    return head + (_LOADER.replace("__AUTO__", _AUTO if auto else "")).replace("__PATH__", _json.dumps(PATH)).replace("__MODE__", mode)


# the Edit pill's Bass half (alto/build/manual_edit.py): a button, then its divider; the glyph's small cut, 20px high
PILL_FN = ("var BASS_SVG = " + _json.dumps(GLYPH_SMALL.replace("<svg ", '<svg width="16" height="20" ')) + ";\n"
           "  function bassHalf(phone){ return '<button type=\"button\" class=\"aep-half aep-bass\" data-tip=\"Bass\" aria-label=\"Bass\">' + BASS_SVG + '</button><span class=\"aep-div\" aria-hidden=\"true\"></span>'; }\n  ")
PILL_USE = "bassHalf(phone) + "
PILL_WIRE = " else if(t.classList.contains('aep-bass')){ if(window._altoBassOpen) window._altoBassOpen('panel'); }"
PILL_CSS = """  html.alto-bass-off .aep-bass, html.alto-bass-off .aep-bass + .aep-div{display:none !important;}
  #alto-edit-pill .aep-bass{padding:0 12px;}
  .alto-edit-pill .aep-bass svg{width:16px;height:20px;}
"""


def pill_script() -> str:
    return '<script id="alto-bass-loader">' + loader_js("panel") + "</script>\n"


# ── the homepage: a Bass | Claude switch at the top of the New / New project window (alto/engine/home_template.html #nt-modal) ──
# Claude = the window as it is. Bass = the same window with its body swapped for the hosted bundle's steps (format tiles cloned from the window's own).
HOME_SWITCH_ANCHOR = '<div class="acct-title" id="nt-head">New</div>'
HOME_SWITCH = ('<div class="nt-sw" id="nt-sw" role="group" aria-label="Build with">'
               '<button type="button" class="nt-sw-b" data-sw="bass" aria-pressed="false" aria-label="Bass" title="Bass: no Claude plan needed, uses credits">' + GLYPH_SMALL.replace("<svg ", '<svg width="16" height="20" ') + '<span>Bass</span></button>'
               '<button type="button" class="nt-sw-b on" data-sw="claude" aria-pressed="true" aria-label="Claude" title="Claude: your own plan or connector"><span>Claude</span></button></div>'
               '\n    ')
HOME_BOX_ANCHOR = '<div class="acct-sub" id="nt-sub"></div>'
HOME_BOX = '\n    <div id="nt-bass" hidden></div>'
HOME_CSS = """  html.alto-bass-off #nt-sw{display:none !important;}
  .nt-sw{display:flex;margin:0 0 14px;border:1px solid var(--border);border-radius:var(--radius,10px);overflow:hidden;}
  .nt-sw-b{flex:1;display:flex;align-items:center;justify-content:center;gap:8px;min-height:40px;padding:6px 10px;font:inherit;font-size:14px;letter-spacing:.02em;color:var(--muted);background:transparent;border:0;cursor:pointer;-webkit-tap-highlight-color:transparent;}
  .nt-sw-b+.nt-sw-b{border-left:1px solid var(--border);}
  .nt-sw-b svg{display:block;color:currentColor;}
  .nt-sw-b.on{background:#5b3fc4;color:#fff;font-weight:600;}
  html.alto-retro .nt-sw-b.on{background:#d9ae55;color:#000;}
  #nt-scrim #nt-modal{background:color-mix(in srgb,var(--surface,#fff) 92%,transparent);}
  #nt-bass .nt-modes{flex-wrap:wrap;row-gap:6px;margin:-8px 0 20px;}
  #nt-bass .nt-mode{display:inline-flex;align-items:center;white-space:nowrap;height:auto;min-height:30px;padding:4px 12px;}
  #nt-bass .nt-mode svg{margin:0 6px 0 0 !important;vertical-align:0 !important;}
  .nt-sw-b:focus-visible{outline:2px solid var(--accent);outline-offset:-2px;}
  #nt-modal.nt-bass-on > :not(.nt-sw):not(#nt-bass):not(#nt-head){display:none !important;}
  #nt-modal.nt-bass-on > #nt-bass{display:block;}
  #nt-bass[hidden]{display:none;}
  @media print{ #nt-sw, #nt-bass{display:none !important;} }
"""
HOME_ANCHOR_CSS = "  .project-slab.new-project-slab{"
HOME_ANCHOR_JS = "// ── \"Start new project\" panel below all existing projects."
_HOME_JS = r"""// ── Bass | Claude switch in the New timeline window (hosted bundle on first use: bass_ui.py)
(function(){
  __LOADER__
  // Bass's route for the file menu's "Turn into another format..." (the sheet is in home_template.html; the three palaces need map data: Claude makes those)
  (window._altoConvertRoutes = window._altoConvertRoutes || []).push({id: 'bass', label: 'Make it with Bass', formats: ['timeline', 'outline', 'system', 'lanes'],
    when: function(){ return !document.documentElement.classList.contains('alto-bass-off'); },
    run: function(pg, fmt, ui){ return new Promise(function(done){
      var use = function(){ window._altoBass.convert(pg, fmt, ui).then(done, function(e){ ui.status('Did not work: ' + ((e && e.message) || e)); done(); }); };
      if(window._altoBass) return use();
      var s = document.createElement('script'); s.src = __PATH__;
      s.onload = function(){ if(window._altoBass) use(); else { ui.status('Bass could not be loaded.'); done(); } };
      s.onerror = function(){ ui.status('Bass could not be reached. Nothing was charged.'); done(); };
      document.head.appendChild(s); }); }});
  const m = document.getElementById('nt-modal'), sw = document.getElementById('nt-sw'), box = document.getElementById('nt-bass'), sc = document.getElementById('nt-scrim');
  if(!m || !sw || !box) return;
  const set = on => { m.classList.toggle('nt-bass-on', on); box.hidden = !on;
    sw.querySelectorAll('.nt-sw-b').forEach(b => { const x = (b.dataset.sw === 'bass') === on; b.classList.toggle('on', x); b.setAttribute('aria-pressed', x ? 'true' : 'false'); });
    if(on) window._altoBassOpen('embed'); else if(window._altoBass) window._altoBass.leave(); };
  sw.addEventListener('click', e => { const b = e.target.closest('.nt-sw-b'); if(b) set(b.dataset.sw === 'bass'); });
  new MutationObserver(() => { if(sc.classList.contains('open')) set(false); }).observe(sc, {attributes: true, attributeFilter: ['class']});
  window._altoBassSwitch = set;
  if(/[#&]bass=/.test(location.hash)) addEventListener('load', () => { ntOpen(''); set(true); });
})();

"""


def home_js() -> str:
    return _HOME_JS.replace("__LOADER__", loader_js("embed", False)).replace("__PATH__", _json.dumps(PATH))


# ── Info text. Every control an Info paragraph names must exist (tests/test_bass_ui.py reads INFO_CONTROLS) ──
INFO_DESKTOP_OLD = "<em>Edit with Claude</em>: bigger changes. <em>Edit manually</em>: small ones."
INFO_DESKTOP_NEW = ("<em>Edit with Claude</em>: bigger changes. <em>Bass</em>: asks Bass to change this timeline by chat, no Claude plan needed (it uses credits). "
                    "<em>Edit manually</em>: small ones.")
INFO_PHONE_OLD = "changes its words right here.</p>"
INFO_PHONE_NEW = "changes its words right here. The <strong>Bass</strong> symbol beside it asks Bass to change the page for you; it uses credits.</p>"
INFO_HOME_ANCHOR = '    <p style="margin:5px 0"><strong>Search</strong> &#8212; the magnifier searches every project'
INFO_HOME_NEW = ('    <p style="margin:5px 0"><strong>Bass</strong> &#8212; in <em>New</em> or <em>Start new project</em>, the <em>Bass</em> half of the switch builds a timeline from your own notes without a Claude plan. '
                 'It uses credits, shown in its steps.</p>\n')
# the controls the Info text names (<em> / <strong> words) and where they are drawn, for the test that Info never names a control that is gone
INFO_CONTROLS = {"Bass": 'aria-label="Bass"', "Edit with Claude": 'aria-label="Edit with Claude"', "Edit manually": 'aria-label="Edit manually"',
                 "New": 'id="nt-head">New<', "Start new project": "Start new project</span>"}


def info_desktop(s: str) -> str:
    return s.replace(INFO_DESKTOP_OLD, INFO_DESKTOP_NEW) if enabled() else s


def info_phone(s: str) -> str:
    return s.replace(INFO_PHONE_OLD, INFO_PHONE_NEW) if enabled() else s
