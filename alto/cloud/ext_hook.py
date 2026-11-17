"""An optional, generic extension hook for the hosted sync script (alto-cloud.js). OFF unless ALTO_EXT_URL is set for the publish.

With it off (the default and every normal build) alto-cloud.js is emitted exactly as before: nothing is appended, the CSP is unchanged.
With it on, a few lines are appended to the emitted script. After a sign-in, on the homepage ONLY, they ask the URL once (POST, the Firebase
ID token as a bearer) whether this account has an extension. The server answers `{}` to everyone it does not serve, and then nothing more
happens; a served account gets `{"x": "<script>"}`, which runs ONLY if it is byte for byte the one script pinned in ext_pin.txt (size and
SHA-384, checked with WebCrypto): a compromised or misrouted server can never run new code here. Signed out, a share link (/s/), a private
timeline (/pv/) and /connect/ never ask (Board B-1114-001500). The script-src of the CSP is not changed at all.

The hook knows nothing about what an extension is: its text names no product, and a URL that does is refused (no hook at all), so the
script every visitor downloads carries no extension's name. The URL must be a Cloud Functions or Cloud Run https address."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

ENV = "ALTO_EXT_URL"
_URL_RE = re.compile(r"https://(?:[a-z0-9][a-z0-9-]{0,62}\.cloudfunctions\.net/[a-z][a-z0-9-]{0,62}|[a-z0-9][a-z0-9-]{0,62}\.a\.run\.app/?)")
# a URL (and so the script every visitor gets) must not name what it serves
_NAMED = re.compile(r"bass|anthropic|claude|studio", re.I)


def url() -> str:
    """The extension URL, or "" when unset or not of the accepted shape (fail closed: no hook, no CSP addition)."""
    u = os.environ.get(ENV, "").strip()
    return u if _URL_RE.fullmatch(u) and not _NAMED.search(u) else ""


KEEP_ENV = "ALTO_KEEP_HOOK"
DEPLOYED_PIN_FILE_ENV = "ALTO_EXT_DEPLOYED_PIN_FILE"
DEFAULT_DEPLOYED_PIN_FILE = "~/.alto-work/altoext-deployed-pin.txt"
_REPO = Path(__file__).resolve().parents[2]


def deployed_pins(environ=None) -> list:
    """The pins the deployed function is known to serve: the lines of the record file OUTSIDE this repo (default ~/.alto-work/altoext-deployed-pin.txt, or
    ALTO_EXT_DEPLOYED_PIN_FILE), written by the altoext redeploy seat after a verified deploy. [] when the file is missing or unreadable, or when its path
    resolves inside the repo (a record the tree itself could re-pin proves nothing)."""
    env = os.environ if environ is None else environ
    try:
        path = Path(env.get(DEPLOYED_PIN_FILE_ENV) or DEFAULT_DEPLOYED_PIN_FILE).expanduser().resolve()
        if path == _REPO or _REPO in path.parents:
            return []
        return [ln.strip() for ln in path.read_text("utf-8").splitlines() if ln.strip()]
    except (OSError, ValueError):
        return []


def keep_url(environ=None) -> str:
    """What the luke-alto publish step may set as ALTO_EXT_URL so a release that does not touch the extension does not take it away.
    "" unless ALL of: the release seat set ALTO_KEEP_HOOK=1; ALTO_EXT_URL is a good address; the committed pin is well formed; the bundle this tree
    would serve has that pin; AND the deployed-pin record (a FILE outside the repo, see deployed_pins) lists it. The tree's bundle and its ext_pin.txt are
    re-pinned together, so they alone prove nothing about what altoext serves. It reads no network, no Firestore and no account: live_go is the release
    seat's own decision, passed by the flag (tools/keep_hook.py prints the line to export)."""
    env = os.environ if environ is None else environ
    if env.get(KEEP_ENV, "").strip() != "1":
        return ""
    u = env.get(ENV, "").strip()
    if not (_URL_RE.fullmatch(u) and not _NAMED.search(u)) or not pin()[0]:
        return ""
    tree = PIN_FILE.read_text("utf-8").strip()
    if tree not in deployed_pins(env):
        return ""
    from ..build import bass_hosted_ext
    return u if bass_hosted_ext.pin() == tree else ""


def edit_link_on() -> bool:
    """Edit with Bass's link in the editing bar: only in the publish that has the hook (ALTO_EXT_URL set and a pinned bundle). The private-timeline shell is the
    one place it is added (alto/build/private_shell.py): a share, a public page, the connector's site and every default build carry none of it."""
    return bool(url() and pin()[0])


def origin() -> str:
    u = url()
    return re.match(r"https://[^/]+", u).group(0) if u and pin()[0] else ""


PIN_FILE = Path(__file__).with_name("ext_pin.txt")
_PIN_RE = re.compile(r"(sha384-[A-Za-z0-9+/]{64}) ([1-9][0-9]{0,8})")


def pin() -> tuple:
    """(integrity, bytes) of the ONE script this site will ever run from the URL, from the committed ext_pin.txt; ("", 0) when it is
    missing or malformed (fail closed: no hook)."""
    try:
        m = _PIN_RE.fullmatch(PIN_FILE.read_text("utf-8").strip())
    except OSError:
        m = None
    return (m.group(1), int(m.group(2))) if m else ("", 0)


# The answer is run ONLY when its UTF-8 bytes are exactly the pinned size and hash to the pinned SHA-384 (WebCrypto). Anything else (a changed
# byte, another script, an oversized or malformed body, no WebCrypto) runs nothing and shows nothing. The verified text is run as an inline
# script whose content is exactly the pinned bytes, so a CSP hash source 'sha384-...' for it would match it too.
_HOOK = r"""
/* optional extension (alto/cloud/ext_hook.py): one question after sign-in; it runs only the one pinned script */
(function(){
  var U=__URL__, PIN=__PIN__, N=__N__, src=null, asked='';
  function here(){ var p=location.pathname; return p==='/'||p==='/index.html'; }
  function apply(){ if(!src||!document.head||!document.body||document.getElementById('alto-ext')) return;
    var s=document.createElement('script'); s.id='alto-ext'; s.textContent=src; document.head.appendChild(s); }
  function check(x){ if(typeof x!=='string'||x.length>N||!window.crypto||!crypto.subtle||!window.TextEncoder) return null;
    var b=new TextEncoder().encode(x); if(b.length!==N) return null;
    return crypto.subtle.digest('SHA-384',b).then(function(d){ var a=new Uint8Array(d), t=''; for(var i=0;i<a.length;i++) t+=String.fromCharCode(a[i]);
      return ('sha384-'+btoa(t))===PIN?x:null; }); }
  function ask(){ var c=window.AltoCloud, u=c&&c.user; if(src||!u||!u.getIdToken||!here()||asked===u.uid) return; asked=u.uid;
    u.getIdToken().then(function(t){ return fetch(U,{method:'POST',mode:'cors',credentials:'omit',cache:'no-store',referrerPolicy:'no-referrer',
        headers:{'content-type':'application/json','authorization':'Bearer '+t},body:'{"action":"ext","args":{}}'}); })
      .then(function(r){ var l=+(r.headers.get('content-length')||0); return (r.ok&&!(l>2*N+64))?r.text():null; })
      .then(function(t){ if(typeof t!=='string'||!t||t.length>2*N+64) return null; var j=null; try{ j=JSON.parse(t); }catch(e){} return j&&check(j.x); })
      .then(function(x){ var n=window.AltoCloud&&window.AltoCloud.user;
        if(typeof x!=='string'||!x||!n||n.uid!==u.uid||src) return;
        window.__altoExtUrl=U; src=x; apply(); })
      .catch(function(){}); }
  addEventListener('alto-auth',ask); ask();
})();
"""


def hook_js(u: str, integrity: str | None = None, size: int | None = None) -> str:
    if integrity is None:
        integrity, size = pin()
    return _HOOK.replace("__URL__", json.dumps(u)).replace("__PIN__", json.dumps(integrity)).replace("__N__", str(int(size)))


def append(src: str) -> str:
    """alto-cloud.js with the hook appended when ALTO_EXT_URL is set; unchanged otherwise."""
    u, (integrity, size) = url(), pin()
    return src + hook_js(u, integrity, size) if u and integrity else src
