"""/connect/ — where the connector on the user's computer signs in as them.

The connector (alto/cloud/session.py) opens this page with ?port=N&state=S. The
page signs in with Google through alto-cloud.js — the same sign-in as the rest
of the site — and, on the user's click, hands the account's refresh token to
the connector by navigating the whole window to http://127.0.0.1:N/cb#…

Only a loopback address on a numeric port is ever navigated to, the state is
passed through untouched for the connector to check, and nothing happens
without the click: a link to this page cannot sign anyone's computer in on its
own. Like every page on the site it carries no timeline data.
"""
from __future__ import annotations

from .fingerprint import meta_tag

_CSS = """
:root{--bg:#f0efea;--surface:#fff;--text:#1a1a24;--muted:#6b6b80;--border:#c8c8d8;
  --btn:rgba(255,255,255,.5);--hover:rgba(0,0,0,.06)}
@media (prefers-color-scheme:dark){:root{--bg:#0a0a0f;--surface:#12121a;--text:#ececf4;
  --muted:#9a9ab0;--border:#1e1e2e;--btn:rgba(34,36,52,.48);--hover:rgba(255,255,255,.08)}}
html,body{margin:0;height:100%;background:var(--bg);color:var(--text);
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}
#gate{position:fixed;inset:0;display:flex;align-items:center;justify-content:center;
  padding:24px;box-sizing:border-box}
.card{width:100%;max-width:400px;background:var(--surface);border:1px solid var(--border);
  border-radius:16px;padding:30px}
h1{font-size:15px;letter-spacing:.22em;text-transform:uppercase;margin:0 0 8px}
p{font-size:13px;color:var(--muted);line-height:1.65;margin:0 0 20px}
button{display:flex;align-items:center;justify-content:center;width:100%;height:44px;
  border-radius:12px;border:1px solid var(--border);background:var(--btn);color:var(--text);
  font-family:inherit;font-size:13.5px;cursor:pointer}
button:hover{background:var(--hover)}
button[disabled]{opacity:.55;cursor:default}
.muted{font-size:11px;color:var(--muted);margin:12px 0 0;line-height:1.6}
"""

_JS = r"""
(function(){
  var q = new URLSearchParams(location.search);
  var port = q.get('port') || '', state = q.get('state') || '';
  var body = document.getElementById('body');
  function show(h){ body.innerHTML = h; }
  // Loopback only, numeric port only, and a state shaped like the connector's.
  var ok = /^\d{2,5}$/.test(port) && +port > 1023 && +port < 65536 &&
           /^[A-Za-z0-9_-]{16,64}$/.test(state);
  if(!ok){
    show('<h1>Connect Alto</h1><p>This page is opened by Alto on your computer. ' +
         'Go back to Claude and ask it to sign Alto in.</p>');
    return;
  }
  function handOver(user){
    var rt = user && user.refreshToken;
    if(!rt){ show('<h1>Connect Alto</h1><p>Sign-in did not return an account. Try again.</p>'); return; }
    location.href = 'http://127.0.0.1:' + port + '/cb#state=' + encodeURIComponent(state) +
                    '&rt=' + encodeURIComponent(rt);
  }
  function offer(){
    var c = window.AltoCloud;
    if(!c || !c.enabled){
      show('<h1>Connect Alto</h1><p>Sign-in is not set up for this site.</p>');
      return;
    }
    var who = c.user && (c.user.email || c.user.displayName);
    show('<h1>Connect Alto</h1>' +
         '<p>Alto on your computer is asking to use your account, so Claude can ' +
         'open and edit your projects there. Your timelines stay in your account.</p>' +
         '<button id="go"></button><p class="muted" id="st"></p>');
    var btn = document.getElementById('go'), st = document.getElementById('st');
    btn.textContent = who ? 'Connect as ' + who : 'Continue with Google';
    btn.onclick = function(){
      btn.disabled = true;
      if(c.user){ handOver(c.user); return; }
      var p = c.signIn();
      (p && p.then ? p : Promise.resolve()).then(function(cred){
        var u = (cred && cred.user) || c.user;
        if(u) handOver(u);
        else { btn.disabled = false; }
      }).catch(function(e){
        btn.disabled = false;
        if(e && e.code === 'auth/popup-closed-by-user') return;
        st.textContent = 'Sign-in did not complete' + ((e && e.code) ? ' (' + e.code + ')' : '') + '. Try again.';
      });
    };
  }
  // alto-cloud.js calls renderAccount on every auth change; the first call is
  // the moment we know whether someone is already signed in here.
  window.renderAccount = offer;
  show('<h1>Connect Alto</h1><p>Loading…</p>');
  window.addEventListener('load', function(){
    setTimeout(function(){ var c = window.AltoCloud; if(!c || !c.enabled || c.known) offer(); }, 600);
  });
})();
"""


def connect_page(cloud_version: str = "") -> str:
    src = "/alto-cloud.js" + (f"?v={cloud_version}" if cloud_version else "")
    return (
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<meta name="robots" content="noindex, nofollow">\n'
        '<meta name="referrer" content="no-referrer">\n'
        f'{meta_tag()}\n'
        '<title>Connect Alto</title>\n'
        f'<style>{_CSS}</style>\n'
        '</head><body>\n'
        '<div id="gate"><div class="card" id="body"></div></div>\n'
        f'<script>{_JS}</script>\n'
        f'<script type="module" src="{src}"></script>\n'
        '</body></html>\n'
    )
