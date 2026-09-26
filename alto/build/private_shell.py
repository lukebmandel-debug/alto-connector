"""The public shell for a private timeline (served at /pv/{key}/).

This page is world-readable and carries NO timeline information whatsoever — no
title, no timeline id, no node text. It is byte-identical for every private
timeline, and it works out which one it is showing from its own URL. Fetching it
with curl tells an attacker nothing at all.

The key in that URL is opaque on purpose. A published `link` timeline lives at
/t/{tid}-{8 random}/, which is unguessable but still says what it is about; for
a private timeline even that is too much, so the key is random throughout and
the Firestore document is filed under the key rather than the timeline id.

What actually enforces privacy is the Firestore rule, applied by Google:

    match /users/{uid}/{document=**} {
      allow read, write: if request.auth != null && request.auth.uid == uid;
    }

so a viewer who is not the owner is refused by the server, never by this script.

Why the owner uploads the page by hand: the connector ships with `mcp` as its
only dependency and holds no Firebase credentials, so it cannot write to
Firestore itself. The browser can — alto-cloud.js has already authenticated it
as the author. One upload per publish is the cost of that.
"""
from __future__ import annotations

import json

from .fingerprint import META_NAME, meta_tag, page_fingerprint

# Firestore rejects a document over 1 MiB (1,048,576 bytes), counting the field
# names, the document's path and a little overhead on top of the value. A page
# is one string plus two short ones, so ~1,000,000 bytes of page leaves the
# best part of 48 KB for all of that. It was 900,000 until the page outgrew it.
# Stop short of it with a message the author can act on, rather than a raw
# backend error.
MAX_PAGE_BYTES = 1_000_000

_CSS = """
:root{--bg:#f0efea;--surface:#fff;--text:#1a1a24;--muted:#6b6b80;
  --border:#c8c8d8;--btn:rgba(255,255,255,.5);--hover:rgba(0,0,0,.06)}
@media (prefers-color-scheme:dark){:root{--bg:#0a0a0f;--surface:#12121a;
  --text:#ececf4;--muted:#9a9ab0;--border:#1e1e2e;--btn:rgba(34,36,52,.48);
  --hover:rgba(255,255,255,.08)}}
html,body{margin:0;height:100%;background:var(--bg);color:var(--text);
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}
#gate{position:fixed;inset:0;display:flex;align-items:center;
  justify-content:center;padding:24px;box-sizing:border-box}
#gate.off{display:none}
.card{width:100%;max-width:380px;background:var(--surface);
  border:1px solid var(--border);border-radius:16px;padding:30px}
h1{font-size:15px;letter-spacing:.22em;text-transform:uppercase;margin:0 0 8px}
p{font-size:13px;color:var(--muted);line-height:1.65;margin:0 0 20px}
button,label.file{display:flex;align-items:center;justify-content:center;
  gap:10px;width:100%;height:44px;border-radius:12px;border:1px solid
  var(--border);background:var(--btn);color:var(--text);font-family:inherit;
  font-size:13.5px;cursor:pointer;box-sizing:border-box}
button:hover,label.file:hover{background:var(--hover)}
button[disabled]{opacity:.55;cursor:default}
.muted{font-size:11px;color:var(--muted);margin:12px 0 0;line-height:1.6}
input[type=file]{display:none}
"""

# Shown over a page that is older than the site serving it. It is put up after
# the page has replaced the shell, so it brings its own rules into the page.
# Bottom-RIGHT is taken by the engine's own controls, so this sits bottom-left.
_STALE_CSS = (
    "#stale{position:fixed;left:16px;bottom:60px;z-index:600;display:none;"
    "align-items:center;gap:10px;max-width:min(92vw,420px);padding:10px 14px;"
    "border-radius:14px;background:var(--surface,#fff);color:var(--text,#1a1a24);"
    "border:1px solid var(--border,#c8c8d8);box-shadow:0 10px 30px rgba(0,0,0,.3);"
    "font:12px/1.45 -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}"
    "#stale.on{display:flex}"
    "#stale label{display:flex;align-items:center;height:30px;padding:0 12px;"
    "border-radius:10px;border:1px solid var(--border,#c8c8d8);cursor:pointer;white-space:nowrap}"
    "#stale input{display:none}"
    "#stale .x{cursor:pointer;opacity:.7;padding:0 2px}"
)

_JS = """
(function(){
  var MAX = __MAX__;
  // Which private timeline is this? Only the URL knows, and the URL is the
  // capability. Nothing about the timeline is written into this page.
  var KEY = (location.pathname.replace(/\\/+$/, '').split('/').pop() || '');
  var gate = document.getElementById('gate'),
      body = document.getElementById('gate-body');
  var STALE_CSS = __STALE_CSS__;

  function show(h){ body.innerHTML = h; }
  function waiting(msg){ show('<h1>Private timeline</h1><p>' + msg + '</p>'); }

  // The counterpart to render(). Signing out (here, in another tab, or by a
  // token expiring) fires renderAccount with no user. Once the page has
  // replaced this document, every word of it is in the window, and the only
  // way to take it away is to load the shell again, which opens on the gate.
  var shown = '';
  function lock(){
    if(shownTop){ location.reload(); return; }
    shown = '';
    gate.classList.remove('off');
  }

  // The page's own <title> is the only name this shell ever sees, and it only
  // sees it once the rules have already let the page through. Nothing here
  // reads a name from the URL, which is the whole reason the URL is opaque.
  function titleOf(pageHtml){
    // The publisher's own name for this timeline, stamped into the page at
    // build time. Preferred over <title>, which is built from the brief and so
    // is identical across every outline of one course.
    var lm = /<meta name="alto-label" content="([^"]*)"/i.exec(String(pageHtml || ''));
    if(lm && lm[1]) return lm[1].replace(/&amp;/g, '&').replace(/&quot;/g, '"')
                                .replace(/&#x27;/g, "'").replace(/&lt;/g, '<')
                                .replace(/&gt;/g, '>').trim();
    var m = /<title>([^<]*)<\\/title>/i.exec(String(pageHtml || ''));
    return m ? m[1].replace(/\\s*\\u2014\\s*Alto(\\s+Timeline)?\\s*$/, '').trim() : '';
  }

  // Which course this page is, for the homepage's reports link and its notes
  // lookup. Same reason as titleOf: the listing never downloads the page, so
  // the one moment this is in hand is here.
  function idOf(pageHtml){
    var m = /var COURSE_ID = '([^']*)';/.exec(String(pageHtml || ''));
    return m ? m[1] : '';
  }

  // A private page is uploaded by hand and then frozen in Firestore. Every
  // other page on this site is rewritten by each publish, and verify_live only
  // ever sees the shell — so this is the one page that can quietly fall months
  // behind the engine while every check says the site is current. Compare the
  // stamp the page carries with the one this shell was built with, and say so.
  // NOT this shell's own alto-build, which covers the whole site: the page
  // inside is a timeline document and only timeline sources can change it.
  // See _TIMELINE_SOURCES in fingerprint.py.
  function shellBuild(){
    var m = document.querySelector('meta[name="alto-page-build"]');
    return (m && m.content) || '';
  }
  function pageBuild(html){
    var m = /<meta name="alto-build" content="([0-9a-f]+)"/.exec(String(html || ''));
    return m ? m[1] : '';
  }
  var SHELL_BUILD = shellBuild();   // read now: the page replaces this document
  function checkFresh(html){
    var want = SHELL_BUILD, have = pageBuild(html);
    if(!want || want === have) return;
    var bar = document.getElementById('stale');
    if(!bar){
      var st = document.createElement('style'); st.textContent = STALE_CSS;
      document.head.appendChild(st);
      bar = document.createElement('div'); bar.id = 'stale';
      document.body.appendChild(bar);
    }
    bar.className = 'on';
    bar.innerHTML =
      '<span>This copy was built by an older Alto' +
      (have ? '' : ' and carries no version at all') +
      ', so recent fixes are missing from it.</span>' +
      '<label class="file">Update<input type="file" id="rf" ' +
      'accept=".html,text/html"></label><span class="x" id="rx">\u00d7</span>';
    document.getElementById('rx').onclick = function(){ bar.className = ''; };
    document.getElementById('rf').onchange = function(){
      var f = this.files && this.files[0];
      if(!f) return;
      bar.firstChild.textContent = 'Updating\u2026';
      f.text().then(function(h){
        return window.AltoCloud.putPage(KEY, h, titleOf(h))
          .then(function(){ location.reload(); });
      }).catch(function(e){
        bar.firstChild.textContent = 'Could not update: ' + ((e && e.message) || e);
      });
    };
  }

  // A #find=<node> from the homepage search is on THIS url. The page reads its
  // hash through __altoHash(), which prefers __altoQuery — so hand it over in
  // the document, then drop it from the url so a reload does not jump again.
  var HANDOFF = location.hash || '';
  function withHandoff(pageHtml){
    if(!HANDOFF) return pageHtml;
    var i = pageHtml.indexOf('<head>');
    if(i < 0) return pageHtml;
    var tag = '<script>window.__altoQuery={hash:' +
      JSON.stringify(HANDOFF).replace(/</g, '\\\\u003c') + '};<\\/script>';
    HANDOFF = '';
    try{ history.replaceState(null, '', location.pathname + location.search); }catch(e){}
    return pageHtml.slice(0, i + 6) + tag + pageHtml.slice(i + 6);
  }

  // The page becomes THIS document (document.open/write), not the content of
  // a frame. Safari (iOS 26 on) reads only the top-level document when it
  // paints the strips behind the clock and the toolbar, so a framed page could
  // never run its wallpaper behind them, whatever it did (see
  // engine_patches.py, mobile-runway-behind-bars). The window — and with it
  // AltoCloud, this closure and the hooks below — survives the rewrite; the
  // shell's own elements do not, so everything after it works through the
  // window alone.
  var shownTop = false, shownUid = '', writing = null;
  function whenCloud(){
    // document.open() drops a module script that has not run yet, and
    // alto-cloud.js is one. Write only once it has.
    return new Promise(function(res){
      var n = 0;
      (function wait(){
        if(window.AltoCloud || ++n > 200) res(); else setTimeout(wait, 25);
      })();
    });
  }
  function render(pageHtml){
    if(shownTop){ if(pageHtml !== shown) replaceWith(pageHtml); return writing; }
    if(writing) return writing;
    shown = pageHtml;
    writing = whenCloud().then(function(){
      var u = window.AltoCloud && window.AltoCloud.user, s = remembered();
      shownUid = (u && u.uid) || (s && s.uid) || '';
      shownTop = true;
      document.open();
      document.write(withHandoff(pageHtml));
      document.close();
    });
    return writing;
  }
  // A newer copy arrived while an older one is on screen. A document written
  // into this window cannot be written over again (its scripts' declarations
  // are still in the window), so store it and start again from the top.
  function replaceWith(pageHtml){
    var u = window.AltoCloud && window.AltoCloud.user;
    try{ if(sessionStorage.getItem('alto-pv-swap') === KEY) return; }catch(e){}
    try{ sessionStorage.setItem('alto-pv-swap', KEY); }catch(e){}
    var put = (u && window.AltoCloud.getPageMeta)
      ? window.AltoCloud.getPageMeta(KEY).then(function(m){
          return cachePut({ uid: u.uid, html: pageHtml, updatedAt: m && m.updatedAt });
        })
      : Promise.resolve();
    put.catch(function(){}).then(function(){ location.reload(); });
  }
  try{ setTimeout(function(){ sessionStorage.removeItem('alto-pv-swap'); }, 5000); }catch(e){}

  /* ── device cache ─────────────────────────────────────────────────────────
     Every visit used to wait for Firebase to load, then for sign-in to be
     confirmed, then for the whole page to download — "Checking your account",
     then "Opening", on every hop back from the homepage. The page is cached
     here, in this browser, for the account that opened it: shown at once when
     the same account is remembered, then checked against Firestore in the
     background and replaced only if it changed. Signing out deletes the cache
     (alto-cloud.js), and a different account never sees another's entry. */
  var DB = 'alto-pv-cache';
  function idb(){
    return new Promise(function(res, rej){
      try{
        var r = indexedDB.open(DB, 1);
        r.onupgradeneeded = function(){ r.result.createObjectStore('pages'); };
        r.onsuccess = function(){ res(r.result); };
        r.onerror = function(){ rej(r.error); };
      }catch(e){ rej(e); }
    });
  }
  function cacheGet(){
    return idb().then(function(d){ return new Promise(function(res){
      var q = d.transaction('pages').objectStore('pages').get(KEY);
      q.onsuccess = function(){ res(q.result || null); };
      q.onerror = function(){ res(null); };
    }); }).catch(function(){ return null; });
  }
  function cachePut(v){
    return idb().then(function(d){
      d.transaction('pages', 'readwrite').objectStore('pages').put(v, KEY);
    }).catch(function(){});
  }
  function remembered(){
    try{ return JSON.parse(localStorage.getItem('alto-account-v1') || 'null'); }
    catch(e){ return null; }
  }
  var cached = null;
  var early = (function(){
    var s = remembered();
    if(!KEY || !s || !s.uid) return Promise.resolve(null);
    return cacheGet().then(function(v){
      // Firebase may already have answered, and said someone else (or no one).
      var u = window.AltoCloud && window.AltoCloud.user;
      if(confirmed && (!u || u.uid !== s.uid)) return null;
      if(v && v.uid === s.uid && v.html){
        cached = v;
        render(v.html);
      }
      return v;
    });
  })();
  var confirmed = false;

  // The page routes its links through __altoGo, which calls this (it is on
  // the page's own window once the page has been written into it).
  // "index.html" means the homepage; anything else is a real path on this site
  // (the reports repository).
  window.__altoSwap = function(url){
    var u = String(url || '');
    if(/^\\.?\\/?index\\.html/.test(u)){ window.top.location = '/'; return; }
    if(/^\\//.test(u)){ window.top.location = u; return; }
  };

  // A page in a frame asks for this (see _ACCOUNT_BRIDGE in single_file.py).
  // A page written into this window does not need it: window.AltoCloud there
  // is the real session already.
  window.__altoAccount = function(){
    var c = window.AltoCloud;
    if(!c) return null;
    return {
      enabled: !!c.enabled,
      get user(){ return c.user; },
      signIn: function(){ return c.signIn(); },
      // Goes through the real Firebase sign-out, which fires renderAccount
      // here and puts the page back behind the gate. The panel used to be
      // hidden precisely because a framed "Sign out" could not do this.
      signOut: function(){ return c.signOut(); }
    };
  };

  function signedOut(){
    show('<h1>Private timeline</h1>' +
         '<p>This is visible only to the account that published it.</p>' +
         '<button id="si">Continue with Google</button>');
    var btn = document.getElementById('si');
    btn.onclick = function(){
      var c = window.AltoCloud;
      if(!c || !c.enabled) return;
      btn.disabled = true;
      // signIn() REJECTS on a refused popup, and the first version of this
      // swallowed that and left the button disabled: the window blinked shut
      // and there was no way to try again and nothing saying why. Always
      // re-enable, and name the one cause the owner can actually fix.
      c.signIn().catch(function(e){
        btn.disabled = false;
        if(e && e.code === 'auth/popup-closed-by-user') return;
        var msg = (e && e.code === 'auth/unauthorized-domain')
          ? 'Sign-in is not enabled for this address yet. The site owner needs ' +
            'to add ' + location.hostname + ' in Firebase under Authentication, ' +
            'Settings, Authorized domains.'
          : 'Sign-in did not complete' + ((e && e.code) ? ' (' + e.code + ')' : '') +
            '. Please try again.';
        var note = document.createElement('p');
        note.className = 'muted';
        note.textContent = msg;
        btn.parentNode.appendChild(note);
      });
    };
  }

  function needsUpload(){
    show('<h1>One more step</h1>' +
         '<p>Nothing has been uploaded here yet. Choose the private.html file ' +
         'Alto built for this timeline.</p>' +
         '<label class="file">Choose private.html' +
         '<input type="file" id="f" accept=".html,text/html"></label>' +
         '<p class="muted" id="st"></p>');
    document.getElementById('f').onchange = function(){
      var file = this.files && this.files[0];
      if(!file) return;
      var st = document.getElementById('st');
      if(file.size > MAX){
        st.textContent = 'That file is ' + Math.round(file.size/1024) +
          ' KB; the limit is ' + Math.round(MAX/1024) + ' KB.';
        return;
      }
      st.textContent = 'Uploading\\u2026';
      file.text().then(function(html){
        return window.AltoCloud.putPage(KEY, html, titleOf(html))
          .then(function(){ st.textContent = 'Saved.'; checked = true; render(html); });
      }).catch(function(e){
        st.textContent = 'Upload failed: ' + ((e && e.message) || e);
      });
    };
  }

  // Once the page is the document: signing out (here, in another tab, or by a
  // token expiring) or a different account takes it off the screen by
  // reloading into the gate. The same account only checks, once, that the
  // copy on screen is the current one.
  var checked = false;
  function topCheck(){
    var cloud = window.AltoCloud;
    // The page calls renderAccount itself as it starts, before Firebase has
    // said who is signed in; until it has (cloud.known), a null user means
    // "not known yet", not "signed out".
    if(!cloud || !cloud.enabled || !cloud.known) return;
    if(!cloud.user || (shownUid && cloud.user.uid !== shownUid)){ location.reload(); return; }
    shownUid = cloud.user.uid;
    if(checked) return;
    checked = true;
    var have = cached && cached.html === shown ? cached : null;
    var fresh = have && cloud.getPageMeta
      ? cloud.getPageMeta(KEY).then(function(m){
          return !!(m && m.updatedAt && m.updatedAt === have.updatedAt);
        }).catch(function(){ return false; })
      : Promise.resolve(false);
    fresh.then(function(ok){
      if(ok){ checkFresh(shown); return; }
      return cloud.getPage(KEY).then(function(page){
        if(!page){ location.reload(); return; }
        if(page !== shown){ replaceWith(page); return; }
        checkFresh(page);
      });
    }).catch(function(){ location.reload(); });
  }

  // alto-cloud.js calls renderAccount() on every auth state change, and the
  // page, once written, installs its own renderAccount for its account panel.
  // Both run: the page's assignment is kept, not allowed to replace this one.
  var pageRA = null;
  function shellRA(){
    if(shownTop){ topCheck(); return; }
    var cloud = window.AltoCloud;
    if(!cloud || !cloud.enabled){
      lock();
      waiting('Sign-in is not set up for this site, so this cannot be opened here.');
      return;
    }
    confirmed = true;
    if(!cloud.user){ cached = null; lock(); signedOut(); return; }
    if(!KEY){ lock(); waiting('Not found.'); return; }
    var uid = cloud.user.uid;
    early.then(function(){
      var mine = cached && cached.uid === uid ? cached : null;
      if(!mine){ cached = null; lock(); waiting('Opening\\u2026'); }
      // With a copy on screen, ask only for the small listing record: if the
      // page has not been re-uploaded since, there is nothing to download.
      var fresh = mine && cloud.getPageMeta
        ? cloud.getPageMeta(KEY).then(function(m){
            return !!(m && m.updatedAt && m.updatedAt === mine.updatedAt);
          }).catch(function(){ return false; })
        : Promise.resolve(false);
      return fresh.then(function(ok){
        if(ok){ checked = true; if(writing) writing.then(function(){ checkFresh(mine.html); }); return; }
        return cloud.getPage(KEY).then(function(page){
          if(!page){ needsUpload(); return; }
          checked = true;
          if(shownTop){ if(page !== shown) replaceWith(page); else checkFresh(page); }
          else render(page).then(function(){ checkFresh(page); });
          // Listing record (colours, project, search terms) for pages uploaded
          // before records existed, then the cache — keyed to the record's
          // updatedAt, which is what the next visit compares against.
          var meta = cloud.ensureMeta ? cloud.ensureMeta(KEY, page).catch(function(){})
                                      : Promise.resolve();
          if(cloud.ensureTitle)
            cloud.ensureTitle(KEY, titleOf(page), idOf(page)).catch(function(){});
          meta.then(function(){ return cloud.getPageMeta ? cloud.getPageMeta(KEY) : null; })
            .then(function(m){
              if(m && m.updatedAt) cachePut({ uid: uid, html: page, updatedAt: m.updatedAt });
            }).catch(function(){});
        });
      });
    }).catch(function(){
      // A rules refusal lands here. Say nothing about what does or does not exist.
      lock();
      waiting('Not found, or not available to this account.');
    });
  }
  Object.defineProperty(window, 'renderAccount', {
    configurable: true,
    get: function(){
      return function(){
        shellRA();
        if(shownTop && pageRA){ try{ pageRA.apply(window, arguments); }catch(e){} }
      };
    },
    set: function(f){ pageRA = f; }
  });

  // A remembered session means the cached page (above) is about to appear,
  // so there is nothing to check out loud; otherwise say what is happening.
  waiting(remembered() ? 'Opening\\u2026' : 'Checking your account\\u2026');

  // alto-cloud.js drives renderAccount from onAuthStateChanged, but it returns
  // early — before ever calling it — when the publisher has no Firebase project
  // configured. Without this the page sits on "Checking your account" forever
  // on exactly the sites least able to explain why.
  window.addEventListener('load', function(){
    setTimeout(function(){
      var c = window.AltoCloud;
      if(!c || !c.enabled) window.renderAccount();
    }, 400);
  });
})();
"""


def shell(cloud_version: str = "") -> str:
    """Return the public shell page. Identical for every private timeline.

    `cloud_version` is a short digest of the alto-cloud.js this site ships, used
    only to bust a browser cache entry. A browser that already holds the file
    under an old max-age serves it from disk WITHOUT revalidating, so fixing the
    header on the server cannot reach it — the request never arrives. Changing
    the URL is the only thing that does. Empty version = plain URL, for callers
    that have no digest to hand.
    """
    js = (_JS.replace("__MAX__", str(MAX_PAGE_BYTES))
            .replace("__STALE_CSS__", json.dumps(_STALE_CSS)))
    src = "/alto-cloud.js" + (f"?v={cloud_version}" if cloud_version else "")
    return (
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, '
        'viewport-fit=cover">\n'
        '<meta name="robots" content="noindex, nofollow">\n'
        f'{meta_tag()}\n'
        # What the page inside this shell should have been built by.
        f'<meta name="alto-page-build" content="{page_fingerprint()}">\n'
        '<title>Alto</title>\n'
        f'<style>{_CSS}</style>\n'
        '</head><body>\n'
        '<div id="gate"><div class="card" id="gate-body"></div></div>\n'
        '<div id="stale"></div>\n'
        f'<script>{js}</script>\n'
        f'<script type="module" src="{src}"></script>\n'
        '</body></html>\n'
    )
