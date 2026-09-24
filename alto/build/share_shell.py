"""The public shell for a shared timeline or project (served at /s/{key}/).

Sibling of private_shell.py, and the same shape: world-readable, byte-identical
for every share, carrying NO timeline content at all. It works out which share
it is showing from its own URL. Fetching it with curl tells an attacker nothing.

The difference is who may open it. A private page is fetched from
users/{uid}/pages/{key}, where the rules let exactly one account read it. A
share is fetched from shares/{key}, where the rules allow `get` to anyone and
`list` to no one — so the 22-character key IS the access control. That is a
bearer capability: whoever holds the URL can read it, until it is revoked.
Everything else here follows from saying that plainly rather than pretending
otherwise.

Two properties this shell must not lose:

* **It never touches the master.** The page it renders was re-identified before
  it was written (see reidentify.py), so a reader's highlights land in the
  share's own storage. The shell does not rely on that — it is already true of
  the document it fetches — but it must not undo it.
* **It is a snapshot.** The owner decides when a share moves, from their own
  homepage. Nothing here reads the master, so nothing here can leak an edit the
  owner has not published.
"""
from __future__ import annotations

from .fingerprint import meta_tag

# Same ceiling as a private page: Firestore rejects a document over 1 MiB.
MAX_PAGE_BYTES = 900_000

_CSS = """
:root{--bg:#f0efea;--surface:#fff;--text:#1a1a24;--muted:#6b6b80;
  --border:#c8c8d8;--btn:rgba(255,255,255,.5);--hover:rgba(0,0,0,.06)}
@media (prefers-color-scheme:dark){:root{--bg:#0a0a0f;--surface:#12121a;
  --text:#ececf4;--muted:#9a9ab0;--border:#1e1e2e;--btn:rgba(34,36,52,.48);
  --hover:rgba(255,255,255,.08)}}
html,body{margin:0;height:100%;background:var(--bg);color:var(--text);
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}
#stage{position:fixed;inset:0;width:100%;height:100%;border:0;display:none}
#stage.on{display:block}
#gate{position:fixed;inset:0;display:flex;align-items:center;
  justify-content:center;padding:24px;box-sizing:border-box;overflow:auto}
#gate.off{display:none}
.card{width:100%;max-width:440px;background:var(--surface);
  border:1px solid var(--border);border-radius:16px;padding:30px}
h1{font-size:15px;letter-spacing:.22em;text-transform:uppercase;margin:0 0 8px}
p{font-size:13px;color:var(--muted);line-height:1.65;margin:0 0 20px}
button{display:flex;align-items:center;justify-content:center;gap:10px;
  width:100%;height:44px;border-radius:12px;border:1px solid var(--border);
  background:var(--btn);color:var(--text);font-family:inherit;font-size:13.5px;
  cursor:pointer;box-sizing:border-box;margin:0 0 10px}
button:hover{background:var(--hover)}
button[disabled]{opacity:.55;cursor:default}
.item{text-align:left;padding:14px 16px;height:auto;display:block}
.item b{display:block;font-size:14px;font-weight:600;margin:0 0 2px}
.item span{font-size:11.5px;color:var(--muted)}
.muted{font-size:11px;color:var(--muted);margin:12px 0 0;line-height:1.6}
/* Offered over a rendered timeline, where the card is gone. Bottom-LEFT: the
   engine keeps its own controls bottom-right. */
#pill{position:fixed;left:16px;bottom:16px;z-index:5;width:auto;height:36px;
  padding:0 14px;margin:0;border-radius:18px;font-size:12.5px;
  background:var(--surface);border:1px solid var(--border);
  box-shadow:0 8px 24px rgba(0,0,0,.28);display:none}
#pill.on{display:flex}
@media (max-width:640px){#pill{left:10px;bottom:10px}}
"""

_JS = """
(function(){
  // Which share is this? Only the URL knows, and the URL is the capability.
  var KEY = (location.pathname.replace(/\\/+$/, '').split('/').pop() || '');
  var gate = document.getElementById('gate'),
      body = document.getElementById('gate-body'),
      stage = document.getElementById('stage');
  var MANIFEST = null;

  function show(h){ body.innerHTML = h; }
  function waiting(msg, head){
    show('<h1>' + (head || 'Shared timeline') + '</h1><p>' + msg + '</p>');
  }

  function render(pageHtml){
    gate.classList.add('off');
    stage.classList.add('on');
    stage.srcdoc = pageHtml;
  }

  function unrender(){
    stage.classList.remove('on');
    stage.srcdoc = '';
    gate.classList.remove('off');
  }

  // The framed page routes its brand links through __altoGo, which calls this.
  // A project share goes back to its own list; a single timeline has nowhere
  // else to be, so it stays exactly where it is rather than navigating to a
  // homepage that is not the recipient's and would tell them nothing.
  window.__altoSwap = function(url){
    if(!/^\\.?\\/?index\\.html/.test(String(url||''))) return;
    if(MANIFEST){ unrender(); chooser(MANIFEST); }
  };

  function chooser(man){
    MANIFEST = man;
    hidePill();
    var items = man.items || [];
    var h = '<h1>' + esc(man.title || 'Shared project') + '</h1>' +
            '<p>' + items.length + ' timeline' + (items.length === 1 ? '' : 's') +
            ' shared with you. No account needed.</p>';
    items.forEach(function(it, i){
      h += '<button class="item" data-i="' + i + '"><b>' + esc(it.title || 'Timeline') +
           '</b><span>Open</span></button>';
    });
    h += saveBlock();
    show(h);
    Array.prototype.forEach.call(body.querySelectorAll('.item'), function(b){
      b.onclick = function(){ openItem(items[+b.dataset.i]); };
    });
    wireSave(man.title || '');
  }

  function openItem(it){
    if(!it || !it.shareKey) return;
    waiting('Opening\\u2026');
    window.AltoCloud.getShare(it.shareKey).then(function(d){
      if(d && d.html){ render(d.html); savePill((MANIFEST && MANIFEST.title) || ''); }
      else waiting('That timeline is no longer shared.');
    }).catch(function(){ waiting('That timeline is no longer shared.'); });
  }

  function esc(s){
    return String(s == null ? '' : s).replace(/[&<>"']/g, function(c){
      return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#x27;'})[c];
    });
  }

  /* ── keeping a share ───────────────────────────────────────────────────────
     Signing in is never required to READ a share. It is offered only so a
     recipient can keep it: we store a reference in their own account, never a
     copy, so that revoking the share actually revokes it. */
  function saveBlock(){
    var c = window.AltoCloud;
    if(!c || !c.enabled) return '';
    return '<button id="save">Save to my Alto</button>' +
           '<p class="muted" id="save-note"></p>';
  }

  // A single-timeline share replaces the card with the timeline, so the card's
  // save button is gone the moment there is anything to save. Without this the
  // whole "keep what someone sent you" path is unreachable for the only kind
  // of share that exists.
  var pill = null;
  function savePill(title){
    var c = window.AltoCloud;
    if(!c || !c.enabled) return;
    if(!pill){
      pill = document.createElement('button');
      pill.id = 'pill';
      document.body.appendChild(pill);
    }
    pill.className = 'on';
    pill.disabled = false;
    // renderAccount re-reads this to rewrite the label once sign-in resolves.
    pill.dataset.t = title || '';
    pill.textContent = c.user ? 'Save to my Alto' : 'Sign in to save this';
    pill.onclick = function(){
      pill.disabled = true;
      if(!c.user){
        c.signIn().catch(function(){ pill.disabled = false; });
        return;
      }
      pill.textContent = 'Saving\u2026';
      c.saveShare(KEY, title).then(function(){
        pill.textContent = 'Saved to your Alto \u2713';
        setTimeout(function(){ pill.classList.remove('on'); }, 2600);
      }).catch(function(){
        pill.disabled = false;
        pill.textContent = 'Could not save \u2014 try again';
      });
    };
  }
  function hidePill(){ if(pill) pill.classList.remove('on'); }

  function wireSave(title){
    var btn = document.getElementById('save');
    if(!btn) return;
    var c = window.AltoCloud, note = document.getElementById('save-note');
    if(!c.user){
      btn.textContent = 'Sign in to save this to your Alto';
      btn.onclick = function(){
        btn.disabled = true;
        c.signIn().catch(function(e){
          btn.disabled = false;
          if(e && e.code === 'auth/popup-closed-by-user') return;
          note.textContent = 'Sign-in did not complete' +
            ((e && e.code) ? ' (' + e.code + ')' : '') + '. Please try again.';
        });
      };
      return;
    }
    btn.onclick = function(){
      btn.disabled = true;
      note.textContent = 'Saving\\u2026';
      c.saveShare(KEY, title).then(function(){
        note.textContent = 'Saved. It is on your Alto homepage now.';
      }).catch(function(e){
        btn.disabled = false;
        note.textContent = 'Could not save: ' + ((e && e.message) || e);
      });
    };
  }

  function open(){
    if(!KEY){ waiting('Not found.'); return; }
    waiting('Opening\\u2026');
    window.AltoCloud.getShare(KEY).then(function(d){
      if(!d){ waiting('This link is not shared any more.'); return; }
      if(d.kind === 'project'){ chooser(d); return; }
      if(d.html){
        render(d.html);
        savePill(d.title || '');
        return;
      }
      waiting('This link is not shared any more.');
    }).catch(function(){
      // A rules refusal and a missing document look the same on purpose.
      waiting('This link is not shared any more.');
    });
  }

  // Unlike the private shell this does NOT wait to know who you are: a share
  // is readable signed out, and gating the first paint on an auth round-trip
  // would make every recipient stare at "checking your account" for no reason.
  window.renderAccount = function(){
    // Re-offer the save control once sign-in resolves, without disturbing a
    // timeline already on screen.
    if(stage.classList.contains('on')){
      if(pill && pill.classList.contains('on')) savePill(pill.dataset.t || '');
      return;
    }
    if(MANIFEST) chooser(MANIFEST);
  };

  function start(){
    var c = window.AltoCloud;
    if(!c || !c.enabled){
      waiting('This link cannot be opened here: the site it came from has no ' +
              'sign-in configured, so there is nowhere to read it from.');
      return;
    }
    open();
  }

  waiting('Opening\\u2026');
  window.addEventListener('load', function(){ setTimeout(start, 250); });
})();
"""


def shell(cloud_version: str = "") -> str:
    """Return the public share shell. Identical for every share.

    `cloud_version` busts a stale browser cache entry for alto-cloud.js; see
    private_shell.shell(), which takes it for the same reason.
    """
    src = "/alto-cloud.js" + (f"?v={cloud_version}" if cloud_version else "")
    return (
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, '
        'viewport-fit=cover">\n'
        '<meta name="robots" content="noindex, nofollow">\n'
        f'{meta_tag()}\n'
        '<title>Alto</title>\n'
        f'<style>{_CSS}</style>\n'
        '</head><body>\n'
        '<iframe id="stage" title="Alto" '
        'allow="clipboard-write; clipboard-read"></iframe>\n'
        '<div id="gate"><div class="card" id="gate-body"></div></div>\n'
        f'<script>{_JS}</script>\n'
        f'<script type="module" src="{src}"></script>\n'
        '</body></html>\n'
    )
